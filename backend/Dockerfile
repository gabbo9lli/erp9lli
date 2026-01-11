# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN chmod +x entrypoint.sh

# Development Stage
FROM base AS development
ENV FLASK_ENV=development

ENTRYPOINT ["./entrypoint.sh"]

# Production Stage
FROM base AS production
RUN pip install gunicorn
ENV FLASK_ENV=production
ENTRYPOINT ["./entrypoint.sh"]