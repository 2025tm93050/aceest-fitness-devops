# syntax=docker/dockerfile:1

# ---------- Base: slim Python + runtime dependencies only ----------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Unprivileged user to run the app (never run as root)
RUN groupadd --system app && useradd --system --gid app --create-home --home-dir /home/app app

# Copy requirements first so this layer is cached until dependencies change
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------- Test: adds pytest/flake8 and the test suite ----------
FROM base AS test

COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt

COPY . .
# /app is read-only for the non-root user, so keep coverage data in /tmp
ENV COVERAGE_FILE=/tmp/.coverage
USER app

CMD ["python", "-m", "pytest", "-v", "-p", "no:cacheprovider"]

# ---------- Production: only the application code ----------
FROM base AS production

COPY app.py fitness.py ./
RUN mkdir /app/data && chown app:app /app/data

ENV ACEEST_DB=/app/data/aceest_fitness.db
USER app
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--access-logfile", "-", "app:create_app()"]
