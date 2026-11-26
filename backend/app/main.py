"""CP Compass API — FastAPI. JWT auth on everything except /api/v1/health
and the read-only demo routes.

API version: /api/v1 (the old unversioned /api was removed in the
blueprint pass — the frontend is the only client and it was updated).
Sync runs in the DB-backed worker loop (app.sync), not BackgroundTasks.
Schema is managed by Alembic; migrations run automatically at startup.
"""
import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import seed, services, sync as sync_engine
from .auth import (
    get_current_user,
    hash_password,
    issue_tokens,
    refresh_tokens,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    verify_password,
)
from .cf import CFError, cf
from .db import SessionLocal, get_db
from .models import CfAccount, Submission, User

V1 = "/api/v1"


def _run_migrations() -> None:
    """Applies Alembic migrations at startup so `uvicorn` just works.
    Failures are logged, not fatal — the endpoints will fail loudly
    instead of the process dying silently at import time."""
    try:
        import os

        from alembic import command
        from alembic.config import Config

        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg = Config(os.path.join(backend_dir, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        command.upgrade(cfg, "head")
    except Exception as exc:  # noqa: BLE001 — startup must not crash here
        print(f"[startup] alembic upgrade failed: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_migrations()
    db = SessionLocal()
    try:
        recovered = sync_engine.recover_stale_jobs(db)
        if recovered:
            print(f"[startup] recovered {recovered} stale sync job(s)")
    finally:
        db.close()
    worker_task = asyncio.create_task(sync_engine.worker_loop())
    yield
    worker_task.cancel()


app = FastAPI(title="CP Compass API", version="1.0.0", lifespan=lifespan)
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


class RefreshIn(BaseModel):
    refresh_token: str


class FeedbackIn(BaseModel):
    contest_id: int
    index: str
    action: str  # later | dismissed | interested (not_interested accepted)


class ReviewIn(BaseModel):
    revision_id: int
    result: str  # again | hard | good | easy


class AuthOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
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


def _cf_handle(db: Session, user: User) -> str | None:
    account = services.get_cf_account(db, user.id)
    return account.handle if account else None


# ---------- health / auth ----------
@app.get(f"{V1}/health")
def health():
    return {"status": "ok", "service": "cp-compass", "demo": True}


@app.post(f"{V1}/auth/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(400, "Email already registered")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    tokens = issue_tokens(db, user.id)
    return AuthOut(**tokens, email=user.email, cf_handle=None)


@app.post(f"{V1}/auth/login", response_model=AuthOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    tokens = issue_tokens(db, user.id)
    return AuthOut(**tokens, email=user.email, cf_handle=_cf_handle(db, user))


@app.post(f"{V1}/auth/refresh", response_model=AuthOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    result = refresh_tokens(db, body.refresh_token)
    if result is None:
        raise HTTPException(401, "Invalid or expired refresh token")
    tokens, user_id = result
    user = db.query(User).get(user_id)
    return AuthOut(**tokens, email=user.email if user else "",
                    cf_handle=_cf_handle(db, user) if user else None)


@app.post(f"{V1}/auth/logout")
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    if not revoke_refresh_token(db, body.refresh_token):
        raise HTTPException(401, "Invalid refresh token")
    return {"ok": True}


@app.post(f"{V1}/auth/logout-all")
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"ok": True, "revoked": revoke_all_refresh_tokens(db, user.id)}


@app.get(f"{V1}/auth/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"email": user.email, "cf_handle": _cf_handle(db, user),
            "current_rating": user.current_rating}


@app.post(f"{V1}/auth/handle")
async def set_handle(body: HandleIn, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    handle = body.handle.strip()
    if not handle:
        raise HTTPException(400, "Handle is empty")
    try:
        info = await cf.verify_handle(handle)
    except CFError as exc:
        raise HTTPException(400, f"Codeforces could not verify this handle: {exc}")
    account = services.get_cf_account(db, user.id)
    if account is None:
        account = CfAccount(user_id=user.id, handle=handle,
                            handle_norm=handle.lower(), rank=info.get("rank"))
        db.add(account)
    else:
        account.handle = handle
        account.handle_norm = handle.lower()
        account.rank = info.get("rank")
    user.current_rating = info.get("rating")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "This handle is already connected to another account")
    return {"cf_handle": handle, "current_rating": user.current_rating,
            "rank": info.get("rank")}


# ---------- sync ----------
@app.post(f"{V1}/sync", status_code=status.HTTP_202_ACCEPTED)
def start_sync(user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if _cf_handle(db, user) is None:
        raise HTTPException(400, "Connect your Codeforces handle first")
    job = sync_engine.enqueue_sync(db, user.id)
    if job is None:
        raise HTTPException(409, "A sync is already running")
    return {"job_id": job.id, "status": "pending"}


@app.get(f"{V1}/sync/status")
def sync_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = sync_engine.latest_job(db, user.id)
    if not job:
        return {"status": "never", "total_synced": 0}
    return {"status": job.status, "total_synced": job.total_synced,
            "last_synced_at": job.last_synced_at.isoformat() if job.last_synced_at else None,
            "error": job.error}


# ---------- dashboard ----------
@app.get(f"{V1}/dashboard")
async def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    handle = _cf_handle(db, user)
    if not handle:
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
        "user": {"handle": handle, "rating": user.current_rating},
        "stats": {"rating": user.current_rating, "solved": solved,
                  "streak": services.current_streak(db, user.id),
                  "revisions_due": len(due)},
        "rating_history": await _rating_history(handle),
        "today_plan": {"problems": recs, "revisions": due[:2]},
        "tag_strengths": services.tag_stats(db, user.id),
        "heatmap": services.heatmap(db, user.id),
        "recent": services.recent_submissions(db, user.id),
    }


# ---------- recommendations ----------
@app.get(f"{V1}/recommendations")
async def recommendations(
        user: User = Depends(get_current_user), db: Session = Depends(get_db),
        tag: str | None = None, min_rating: int | None = None,
        max_rating: int | None = None, hide_solved: bool = True):
    if _cf_handle(db, user) is None:
        raise HTTPException(400, "Connect your Codeforces handle first")
    try:
        problems = await cf.problemset()
    except CFError as exc:
        raise HTTPException(502, f"Codeforces didn't respond: {exc}")
    return services.recommend(db, user, problems, limit=24, tag=tag,
                              min_rating=min_rating, max_rating=max_rating,
                              hide_solved=hide_solved)


@app.post(f"{V1}/recommendations/action")
def recommendation_action(body: FeedbackIn, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    action = body.action
    if action == "not_interested":  # legacy frontend name
        action = "dismissed"
    if action not in ("later", "dismissed", "interested"):
        raise HTTPException(400, "Unknown action")
    services.set_preference(db, user.id, body.contest_id, body.index, action)
    return {"ok": True}


@app.get(f"{V1}/practice/preferences")
def practice_preferences(user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    return services.list_preferences(db, user.id)


# ---------- revisions ----------
@app.get(f"{V1}/revisions")
def revisions(tab: str = Query("due", pattern="^(due|upcoming|done)$"),
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return services.revision_list(db, user.id, tab)


@app.post(f"{V1}/revisions/review")
def review(body: ReviewIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    rev = services.review_revision(db, user.id, body.revision_id, body.result)
    if rev is None:
        raise HTTPException(404, "Revision not found")
    return {"ok": True, "next_due": rev.due_date.isoformat(),
            "interval_days": rev.interval_days}


@app.get(f"{V1}/revisions/counts")
def revision_counts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {tab: len(services.revision_list(db, user.id, tab))
            for tab in ("due", "upcoming", "done")}


# ---------- export ----------
@app.get(f"{V1}/export")
def export_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subs = db.query(Submission).filter_by(user_id=user.id).all()
    return {
        "handle": _cf_handle(db, user), "email": user.email,
        "submissions": [
            {"cf_id": s.cf_submission_id, "verdict": s.verdict,
             "submitted_at": s.submitted_at.isoformat()} for s in subs],
        "tag_stats": services.tag_stats(db, user.id),
        "revisions": services.revision_list(db, user.id, "due")
        + services.revision_list(db, user.id, "upcoming"),
    }


# ---------- demo (no auth, read-only, honestly labelled) ----------
@app.get(f"{V1}/demo/dashboard")
def demo_dashboard():
    return seed.dashboard_payload()


@app.get(f"{V1}/demo/recommendations")
def demo_recommendations():
    return seed.RECOMMENDATIONS


@app.get(f"{V1}/demo/revisions")
def demo_revisions():
    return seed.REVISIONS
