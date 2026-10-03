FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==26.2.1 && pip install --no-cache-dir -r requirements.txt

RUN groupadd --gid 1000 tester && useradd --uid 1000 --gid tester --no-create-home tester
COPY app.py storage.py security.py VERSION ./
COPY static/ ./static/
COPY templates/ ./templates/

USER 1000:1000

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "180", "--access-logfile", "-", "--error-logfile", "-", "app:app"]

FROM runtime AS test
USER root
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests/ ./tests/
USER 1000:1000
CMD ["pytest", "-q", "-p", "no:cacheprovider", "tests"]
