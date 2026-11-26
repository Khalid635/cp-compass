"""CP Compass API — FastAPI. JWT auth on everything except /api/health
and the read-only demo routes. No Celery: sync runs in BackgroundTasks.
"""
import time
from datetime import datetime

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from . import seed, services, sync as sync_engine
from .auth import create_token, get_current_user, hash_password, verify_password
from .cf import CFError, cf
from .db import Base, SessionLocal, engine, get_db
from .models import ProblemFeedback, Revision, Submission, User

Base.metadata.create_all(bind=engine)

app = FastAPI(title="CP Compass API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


# ---------- schemas ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class HandleIn(BaseModel):
    handle: str


class FeedbackIn(BaseModel):
    contest_id: int
    index: str
    action: str  # later | not_interested


class ReviewIn(BaseModel):
    revision_id: int
    result: str  # again | hard | good | easy


class AuthOut(BaseModel):
    token: str
    email: str
    cf_handle: str | None


# ---------- helpers ----------
_rating_cache: dict[str, tuple[float, list]] = {}


async def _rating_history(handle: str) -> list[dict]:
    now = time.monotonic()
    if handle in _rating_cache and now - _rating_cache[handle][0] < 300:
        return _rating_cache[handle][1]
    try:
        rows = await cf.user_rating(handle)
        hist = [{"contest": r["contestName"], "rating": r["newRating"],
                 "date": datetime.utcfromtimestamp(r["ratingUpdateTimeSeconds"]).isoformat()}
                for r in rows]
    except CFError:
        hist = []
    _rating_cache[handle] = (now, hist)
    return hist


def _problem_json(p) -> dict:
    return {"contest_id": p.contest_id, "index": p.index, "name": p.name,
            "rating": p.rating, "tags": p.tags or []}


# ---------- health / auth ----------
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "cp-compass", "demo": True}


@app.post("/api/auth/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(400, "Email already registered")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return AuthOut(token=create_token(user.id), email=user.email, cf_handle=None)


@app.post("/api/auth/login", response_model=AuthOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return AuthOut(token=create_token(user.id), email=user.email, cf_handle=user.cf_handle)


@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"email": user.email, "cf_handle": user.cf_handle,
            "current_rating": user.current_rating}


@app.post("/api/auth/handle")
async def set_handle(body: HandleIn, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    handle = body.handle.strip()
    if not handle:
        raise HTTPException(400, "Handle is empty")
    try:
        info = await cf.verify_handle(handle)
    except CFError as exc:
        raise HTTPException(400, f"Codeforces could not verify this handle: {exc}")
    user.cf_handle = handle
    user.current_rating = info.get("rating")
    db.commit()
    return {"cf_handle": handle, "current_rating": user.current_rating,
            "rank": info.get("rank")}


# ---------- sync ----------
@app.post("/api/sync")
def start_sync(background: BackgroundTasks, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if not user.cf_handle:
        raise HTTPException(400, "Connect your Codeforces handle first")
    job = sync_engine.get_or_create_job(db, user.id)
    if job is None:
        raise HTTPException(409, "A sync is already running")
    job_id = job.id
    user_id = user.id  # pass only primitives: the request session closes
    db.close()  # background task opens its own session

    def _run():
        session = SessionLocal()
        try:
            u = session.query(User).get(user_id)
            j = session.query(sync_engine.SyncJob).get(job_id)
            import asyncio
            asyncio.run(sync_engine.run_sync(session, u, j))
        finally:
            session.close()

    background.add_task(_run)
    return {"job_id": job_id, "status": "running"}


@app.get("/api/sync/status")
def sync_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = sync_engine.latest_job(db, user.id)
    if not job:
        return {"status": "never", "total_synced": 0}
    return {"status": job.status, "total_synced": job.total_synced,
            "last_synced_at": job.last_synced_at.isoformat() if job.last_synced_at else None,
            "error": job.error}


# ---------- dashboard ----------
@app.get("/api/dashboard")
async def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.cf_handle:
        return {"has_handle": False, "synced": False, "user": {"handle": None},
                "stats": None, "rating_history": [], "today_plan": {"problems": [], "revisions": []},
                "tag_strengths": [], "heatmap": [], "recent": []}
    solved = len(services.solved_problem_ids(db, user.id))
    due = services.revision_list(db, user.id, "due")
    recs = []
    try:
        problems = await cf.problemset()
        recs = services.recommend(db, user, problems, limit=3)
    except CFError:
        recs = []
    return {
        "has_handle": True,
        "synced": db.query(Submission).filter_by(user_id=user.id).first() is not None,
        "user": {"handle": user.cf_handle, "rating": user.current_rating},
        "stats": {"rating": user.current_rating, "solved": solved,
                  "streak": services.current_streak(db, user.id),
                  "revisions_due": len(due)},
        "rating_history": await _rating_history(user.cf_handle),
        "today_plan": {"problems": recs, "revisions": due[:2]},
        "tag_strengths": services.tag_stats(db, user.id),
        "heatmap": services.heatmap(db, user.id),
        "recent": services.recent_submissions(db, user.id),
    }


# ---------- recommendations ----------
@app.get("/api/recommendations")
async def recommendations(
        user: User = Depends(get_current_user), db: Session = Depends(get_db),
        tag: str | None = None, min_rating: int | None = None,
        max_rating: int | None = None, hide_solved: bool = True):
    if not user.cf_handle:
        raise HTTPException(400, "Connect your Codeforces handle first")
    try:
        problems = await cf.problemset()
    except CFError as exc:
        raise HTTPException(502, f"Codeforces didn't respond: {exc}")
    return services.recommend(db, user, problems, limit=24, tag=tag,
                              min_rating=min_rating, max_rating=max_rating,
                              hide_solved=hide_solved)


@app.post("/api/recommendations/action")
def recommendation_action(body: FeedbackIn, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    if body.action not in ("later", "not_interested"):
        raise HTTPException(400, "Unknown action")
    fb = db.query(ProblemFeedback).filter_by(
        user_id=user.id, contest_id=body.contest_id, problem_index=body.index).first()
    if fb is None:
        fb = ProblemFeedback(user_id=user.id, contest_id=body.contest_id,
                             problem_index=body.index, action=body.action)
        db.add(fb)
    else:
        fb.action = body.action
    db.commit()
    return {"ok": True}


# ---------- revisions ----------
@app.get("/api/revisions")
def revisions(tab: str = Query("due", pattern="^(due|upcoming|done)$"),
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return services.revision_list(db, user.id, tab)


@app.post("/api/revisions/review")
def review(body: ReviewIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    rev = services.review_revision(db, user.id, body.revision_id, body.result)
    if rev is None:
        raise HTTPException(404, "Revision not found")
    return {"ok": True, "next_due": rev.due_date.isoformat(),
            "interval_days": rev.interval_days}


@app.get("/api/revisions/counts")
def revision_counts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {tab: len(services.revision_list(db, user.id, tab))
            for tab in ("due", "upcoming", "done")}


# ---------- export ----------
@app.get("/api/export")
def export_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subs = db.query(Submission).filter_by(user_id=user.id).all()
    return {
        "handle": user.cf_handle, "email": user.email,
        "submissions": [
            {"cf_id": s.cf_submission_id, "verdict": s.verdict,
             "submitted_at": s.submitted_at.isoformat()} for s in subs],
        "tag_stats": services.tag_stats(db, user.id),
        "revisions": services.revision_list(db, user.id, "due")
        + services.revision_list(db, user.id, "upcoming"),
    }


# ---------- demo (no auth, read-only, honestly labelled) ----------
@app.get("/api/demo/dashboard")
def demo_dashboard():
    return seed.dashboard_payload()


@app.get("/api/demo/recommendations")
def demo_recommendations():
    return seed.RECOMMENDATIONS


@app.get("/api/demo/revisions")
def demo_revisions():
    return seed.REVISIONS
