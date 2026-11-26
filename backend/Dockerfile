# CP Compass backend — production image (Render free web service).
# Python 3.14 slim; scikit-learn ships cp314 wheels, no compiler needed.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

# Render sets $PORT; uvicorn serves the FastAPI app.
# Single worker: the free instance has 512 MB RAM and the ML model trains
# in a background thread on first boot (small dataset, a few seconds).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
