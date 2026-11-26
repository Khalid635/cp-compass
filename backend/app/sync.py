"""Incremental Codeforces sync — the engine of the project.

- Pages user.status (newest first) until the newest already-saved submission
  is reached → incremental, never re-fetches history.
- Idempotent upsert keyed on cf_submission_id: a sync run twice never
  doubles data.
- Resumable: sync_jobs records the last saved submission id; a job killed
  mid-way (e.g. Render restart) resumes from there. A "running" job older
  than SYNC_STALE_AFTER_S is treated as dead.
- One sync per user at a time.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from . import services
from .cf import CFError, cf
from .config import SYNC_STALE_AFTER_S
from .models import Problem, Submission, SyncJob, User


def _upsert_problem(db: Session, cf_prob: dict) -> Problem:
    prob = db.query(Problem).filter_by(
        contest_id=cf_prob["contestId"], index=cf_prob["index"],
        platform="codeforces").first()
    if prob is None:
        prob = Problem(
            contest_id=cf_prob["contestId"], index=cf_prob["index"],
            name=cf_prob["name"], rating=cf_prob.get("rating"),
            tags=cf_prob.get("tags", []), platform="codeforces",
        )
        db.add(prob)
        db.flush()
    return prob


def get_or_create_job(db: Session, user_id: int) -> SyncJob | None:
    """Returns a fresh/running job, or None if one is already running."""
    now = datetime.utcnow()
    running = db.query(SyncJob).filter(
        SyncJob.user_id == user_id, SyncJob.status == "running").first()
    if running:
        age = (now - (running.updated_at or running.created_at)).total_seconds()
        if age < SYNC_STALE_AFTER_S:
            return None  # a live sync is already going
        running.status = "failed"
        running.error = "Sync interrupted (stale running job)"
        db.commit()
    job = SyncJob(user_id=user_id, status="running", total_synced=0)
    db.add(job)
    db.commit()
    return job


def latest_job(db: Session, user_id: int) -> SyncJob | None:
    return (db.query(SyncJob).filter(SyncJob.user_id == user_id)
            .order_by(SyncJob.created_at.desc()).first())


async def run_sync(db: Session, user: User, job: SyncJob) -> None:
    """Runs in a FastAPI BackgroundTask. Uses its own session lifetime."""
    handle = user.cf_handle
    if not handle:
        job.status = "failed"
        job.error = "No Codeforces handle connected"
        db.commit()
        return
    try:
        # Resume point: newest submission we already have.
        last_seen = job.last_synced_submission_id
        if last_seen is None:
            newest = (db.query(Submission.cf_submission_id)
                      .filter(Submission.user_id == user.id)
                      .order_by(Submission.cf_submission_id.desc()).first())
            last_seen = newest[0] if newest else None
        new_count = 0
        page = 1
        while True:
            subs = await cf.user_status(handle, start_from=page, count=1000)
            if not subs:
                break
            reached_old = False
            for s in subs:
                cf_id = s["id"]
                if last_seen is not None and cf_id <= last_seen:
                    reached_old = True
                    break
                if db.query(Submission).filter_by(cf_submission_id=cf_id).first():
                    continue
                prob = _upsert_problem(db, s["problem"])
                db.add(Submission(
                    cf_submission_id=cf_id, user_id=user.id, problem_id=prob.id,
                    verdict=s["verdict"], language=s.get("programmingLanguage"),
                    submitted_at=datetime.utcfromtimestamp(s["creationTimeSeconds"]),
                    time_consumed=s.get("timeConsumedMillis"),
                    memory_consumed=s.get("memoryConsumedBytes"),
                ))
                new_count += 1
                job.last_synced_submission_id = max(
                    job.last_synced_submission_id or 0, cf_id)
                job.total_synced = new_count
                job.last_synced_at = datetime.utcnow()
            db.commit()
            if reached_old or len(subs) < 1000:
                break
            page += 1000
        # Refresh current rating from CF.
        try:
            rating_history = await cf.user_rating(handle)
            if rating_history:
                user.current_rating = rating_history[-1]["newRating"]
                db.commit()
        except CFError:
            pass
        services.build_revision_queue(db, user.id)
        job.status = "done"
        job.error = None
        db.commit()
    except CFError as exc:
        job.status = "failed"
        job.error = str(exc)
        db.commit()
    except Exception as exc:  # never crash the worker silently
        db.rollback()
        job.status = "failed"
        job.error = f"Unexpected error: {exc}"
        db.commit()
