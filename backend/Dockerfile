# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Development Stage
FROM base AS development
ENV FLASK_ENV=development
CMD ["flask", "run", "--host=0.0.0.0"]

# Production Stage
FROM base AS production
RUN pip install gunicorn
ENV FLASK_ENV=production
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]