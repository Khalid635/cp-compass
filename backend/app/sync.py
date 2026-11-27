"""Incremental Codeforces sync — DB-backed job queue (blueprint §4).

Replaces reliance on FastAPI BackgroundTasks with a controlled worker loop
that lives inside the FastAPI process:

- POST /api/v1/sync only ENQUEUES a job row (status=pending). The worker
  loop claims pending jobs one at a time (global serial execution, so no
  two syncs ever run concurrently) and runs them in a worker thread.
- Each run holds a lease (lease_owner + lease_expires_at, heartbeat after
  every page). A "running" job whose lease expired is stale: at startup
  (and before every enqueue) it is reset to pending so the worker resumes
  it from the last committed checkpoint — up to SYNC_MAX_ATTEMPTS times,
  then it is marked failed.
- Checkpoint = one DB commit per page: last_synced_submission_id and
  checkpoint_from (the `from` value of the next page). Resume always
  re-scans from page 1 and stops at last_seen — new submissions shift the
  pagination, so an index checkpoint alone would skip them; the submission
  id is the true resume key (ids are monotonic with creation time).
- Idempotent upsert keyed on cf_submission_id: a sync run twice never
  doubles data. One sync per user at a time (enqueue refuses when a
  pending/running job exists for the user).
- After a successful sync: rating_history rows are upserted, daily_stats
  and weekly_reports are rebuilt from the submission table.
"""
import asyncio
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from . import services
from .cf import CFError, cf
from .config import SYNC_LEASE_S, SYNC_MAX_ATTEMPTS, WORKER_POLL_S
from .models import (
    CfAccount,
    DailyStat,
    Problem,
    RatingHistory,
    Submission,
    SyncJob,
    User,
    WeeklyReport,
)

WORKER_ID = uuid.uuid4().hex[:12]


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
    elif not prob.name or prob.rating is None:
        # Bare row created by set_preference before the problem ever
        # synced — backfill the real data now.
        prob.name = cf_prob["name"]
        prob.rating = cf_prob.get("rating")
        prob.tags = cf_prob.get("tags", [])
        db.flush()
    return prob


def enqueue_sync(db: Session, user_id: int) -> SyncJob | None:
    """Creates a pending job, or None if one is already pending/running."""
    now = datetime.utcnow()
    recover_stale_jobs(db)
    existing = db.query(SyncJob).filter(
        SyncJob.user_id == user_id,
        SyncJob.status.in_(("pending", "running"))).first()
    if existing:
        return None
    job = SyncJob(user_id=user_id, status="pending", total_synced=0)
    db.add(job)
    db.commit()
    return job


def recover_stale_jobs(db: Session) -> int:
    """Resets stale running jobs to pending so the worker resumes them.
    Returns how many were recovered. Jobs that died too often fail."""
    now = datetime.utcnow()
    stale = db.query(SyncJob).filter(
        SyncJob.status == "running",
        SyncJob.lease_expires_at.isnot(None),
        SyncJob.lease_expires_at < now).all()
    recovered = 0
    for job in stale:
        job.attempts += 1
        if job.attempts >= SYNC_MAX_ATTEMPTS:
            job.status = "failed"
            job.error = "Sync interrupted repeatedly (stale running job)"
        else:
            job.status = "pending"
            job.error = "Sync interrupted — will resume from checkpoint"
            job.lease_owner = None
            job.lease_expires_at = None
            recovered += 1
    if stale:
        db.commit()
    return recovered


def latest_job(db: Session, user_id: int) -> SyncJob | None:
    return (db.query(SyncJob).filter(SyncJob.user_id == user_id)
            .order_by(SyncJob.created_at.desc()).first())


def _claim_next_job(db: Session) -> SyncJob | None:
    """Worker claim: oldest pending job becomes running under our lease."""
    job = (db.query(SyncJob).filter(SyncJob.status == "pending")
           .order_by(SyncJob.created_at.asc()).first())
    if job is None:
        return None
    now = datetime.utcnow()
    job.status = "running"
    job.lease_owner = WORKER_ID
    job.lease_expires_at = now + timedelta(seconds=SYNC_LEASE_S)
    job.heartbeat_at = now
    db.commit()
    return job


def _heartbeat(db: Session, job: SyncJob) -> None:
    now = datetime.utcnow()
    job.heartbeat_at = now
    job.lease_expires_at = now + timedelta(seconds=SYNC_LEASE_S)
    db.commit()


def _store_rating_history(db: Session, user: User, history: list[dict]) -> None:
    for row in history:
        contest_id = row.get("contestId")
        if contest_id is None:
            continue
        rated_at = datetime.utcfromtimestamp(row["ratingUpdateTimeSeconds"])
        existing = db.query(RatingHistory).filter_by(
            user_id=user.id, contest_id=contest_id).first()
        if existing is None:
            db.add(RatingHistory(
                user_id=user.id, contest_id=contest_id,
                contest_name=row.get("contestName", ""),
                rating=row["newRating"],
                old_rating=row.get("oldRating"),
                rated_at=rated_at))
        else:
            existing.rating = row["newRating"]
            existing.old_rating = row.get("oldRating")
            existing.rated_at = rated_at
    db.commit()


def _rebuild_daily_weekly(db: Session, user_id: int) -> None:
    """Rebuilds daily_stats + weekly_reports from the submissions table."""
    subs = (db.query(Submission, Problem)
            .join(Problem, Submission.problem_id == Problem.id)
            .filter(Submission.user_id == user_id).all())
    per_day: dict[object, dict] = defaultdict(lambda: {"solved": 0, "attempted": 0})
    per_week: dict[object, dict] = defaultdict(
        lambda: {"solved": 0, "attempted": 0, "tags": defaultdict(lambda: [0, 0])})
    for sub, prob in subs:
        day = sub.submitted_at.date()
        per_day[day]["attempted"] += 1
        monday = day - timedelta(days=day.weekday())
        per_week[monday]["attempted"] += 1
        if sub.verdict == "OK":
            per_day[day]["solved"] += 1
            per_week[monday]["solved"] += 1
        for tag in prob.tags or []:
            cell = per_week[monday]["tags"][tag]
            cell[1] += 1
            if sub.verdict == "OK":
                cell[0] += 1
    db.query(DailyStat).filter(DailyStat.user_id == user_id).delete()
    for day, counts in per_day.items():
        db.add(DailyStat(user_id=user_id, day=day,
                         solved=counts["solved"], attempted=counts["attempted"]))
    db.query(WeeklyReport).filter(WeeklyReport.user_id == user_id).delete()
    for monday, counts in per_week.items():
        tag_acc = {tag: round(s / a, 2) if a else 0.0
                   for tag, (s, a) in counts["tags"].items()}
        db.add(WeeklyReport(user_id=user_id, week_start=monday,
                            solved=counts["solved"], attempted=counts["attempted"],
                            tag_acceptance=tag_acc))
    db.commit()


async def backfill_passed_test_counts(db: Session, user: User,
                                      max_pages: int = 5) -> int:
    """Fills passed_test_count on rows synced before Batch 2 added the
    column. Fetches user.status pages (newest first) and updates rows
    whose count is still NULL. Bounded: at most max_pages per call, so
    a huge history backfills over several syncs; once every row is
    filled this is never called again (the caller checks first)."""
    account = db.query(CfAccount).filter_by(user_id=user.id).first()
    if not account:
        return 0
    by_id = {r[0]: r[1] for r in db.query(
        Submission.cf_submission_id, Submission.id).filter(
        Submission.user_id == user.id,
        Submission.passed_test_count.is_(None)).all()}
    if not by_id:
        return 0
    filled = 0
    page_from = 1
    for _ in range(max_pages):
        subs = await cf.user_status(account.handle, start_from=page_from,
                                    count=1000)
        if not subs:
            break
        for s in subs:
            row_id = by_id.pop(s["id"], None)
            if row_id is not None:
                row = db.query(Submission).get(row_id)
                if row is not None:
                    row.passed_test_count = s.get("passedTestCount")
                    filled += 1
        db.commit()
        if not by_id or len(subs) < 1000:
            break
        page_from += 1000
    return filled


async def run_sync(db: Session, user: User, job: SyncJob) -> None:
    """Runs one sync job (called from the worker thread)."""
    account = db.query(CfAccount).filter_by(user_id=user.id).first()
    handle = account.handle if account else None
    if not handle:
        job.status = "failed"
        job.error = "No Codeforces handle connected"
        db.commit()
        return
    try:
        # Resume point: newest submission id we already have.
        last_seen = job.last_synced_submission_id
        if last_seen is None:
            newest = (db.query(Submission.cf_submission_id)
                      .filter(Submission.user_id == user.id)
                      .order_by(Submission.cf_submission_id.desc()).first())
            last_seen = newest[0] if newest else None
        new_count = 0
        page_from = 1
        while True:
            subs = await cf.user_status(handle, start_from=page_from, count=1000)
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
                    # Batch 2: tests passed before the verdict.
                    passed_test_count=s.get("passedTestCount"),
                ))
                new_count += 1
                job.last_synced_submission_id = max(
                    job.last_synced_submission_id or 0, cf_id)
                job.total_synced = new_count
                job.last_synced_at = datetime.utcnow()
            # Checkpoint: one commit per page, lease heartbeat with it.
            job.checkpoint_from = page_from + 1000
            db.commit()
            _heartbeat(db, job)
            if reached_old or len(subs) < 1000:
                break
            page_from += 1000
        # Refresh current rating + store rating history.
        try:
            rating_history = await cf.user_rating(handle)
            if rating_history:
                user.current_rating = rating_history[-1]["newRating"]
                _store_rating_history(db, user, rating_history)
                db.commit()
        except CFError:
            pass
        services.build_revision_queue(db, user.id)
        _rebuild_daily_weekly(db, user.id)
        # Batch 2: fill passed_test_count on rows synced before the
        # column existed. Only runs while NULL rows remain.
        missing = db.query(Submission).filter(
            Submission.user_id == user.id,
            Submission.passed_test_count.is_(None)).count()
        if missing:
            try:
                await backfill_passed_test_counts(db, user)
            except CFError:
                pass  # backfill is best-effort; the sync itself succeeded
        job.status = "done"
        job.error = None
        job.lease_owner = None
        job.lease_expires_at = None
        db.commit()
    except CFError as exc:
        # Checkpoint is already committed — the next run resumes from it.
        job.status = "failed"
        job.error = str(exc)
        job.lease_owner = None
        job.lease_expires_at = None
        db.commit()
    except Exception as exc:  # never crash the worker silently
        db.rollback()
        job.status = "failed"
        job.error = f"Unexpected error: {exc}"
        job.lease_owner = None
        job.lease_expires_at = None
        db.commit()


def _run_job_sync(job_id: int, user_id: int) -> None:
    """Worker-thread entry: own session, own event loop (same shape as the
    old BackgroundTasks path, so the sync code itself is unchanged)."""
    from .db import SessionLocal

    session = SessionLocal()
    try:
        user = session.query(User).get(user_id)
        job = session.query(SyncJob).get(job_id)
        if user is None or job is None:
            return
        asyncio.run(run_sync(session, user, job))
    finally:
        session.close()


async def worker_loop() -> None:
    """Polls for pending jobs and runs them one at a time, forever."""
    from .db import SessionLocal

    while True:
        session = SessionLocal()
        try:
            job = _claim_next_job(session)
            job_id = job.id if job else None
            user_id = job.user_id if job else None
        finally:
            session.close()
        if job_id is None:
            await asyncio.sleep(WORKER_POLL_S)
            continue
        await asyncio.to_thread(_run_job_sync, job_id, user_id)
