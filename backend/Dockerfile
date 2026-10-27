# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    mdbtools \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN chmod +x entrypoint.sh

# Development Stage
FROM base AS development
ENV APP_ENV=development

ENTRYPOINT ["./entrypoint.sh"]

# Production Stage
FROM base AS production
ENV APP_ENV=production
ENTRYPOINT ["./entrypoint.sh"]
