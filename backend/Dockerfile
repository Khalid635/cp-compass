# Rung backend — production image (Render free web service).
# Python 3.14 slim; scikit-learn ships cp314 wheels, no compiler needed.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Hardening H4: never run as root. The app writes ml_model.joblib and
# dev_outbox.log into /app, so /app and everything copied in belong to
# the app user.
RUN useradd -m appuser && chown appuser:appuser /app

COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser alembic.ini .
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser app ./app

USER appuser

# Render sets $PORT; uvicorn serves the FastAPI app.
# Single worker: the free instance has 512 MB RAM and the ML model trains
# in a background thread on first boot (small dataset, a few seconds).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
