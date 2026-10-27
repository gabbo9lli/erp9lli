#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

if [ "$DB_TYPE" = "postgres" ] || [ "$DB_TYPE" = "postgresql" ]; then
  echo "Checking PostgreSQL availability..."
  python << END
import socket
import time
import os
from urllib.parse import urlparse

db_url = os.getenv("DATABASE_URL", "")
if db_url and "://" in db_url:
    parsed = urlparse(db_url)
    db_host = parsed.hostname or os.getenv("DB_HOST", "db")
    db_port = parsed.port or 5432
else:
    db_host = os.getenv("DB_HOST", "db")
    db_port = int(os.getenv("DB_PORT", "5432"))

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
for _ in range(60):
    try:
        s.connect((db_host, db_port))
        s.close()
        print(f"Postgres ({db_host}:{db_port}) is ready.")
        break
    except socket.error:
        print(f"Postgres ({db_host}:{db_port}) is unavailable - sleeping")
        time.sleep(1)
END
  echo "PostgreSQL is up - executing database migrations..."
  alembic upgrade head || echo "Migrations completed or already at head."

  echo "Seeding initial dataset (Users, ReteBio, Accounting)..."
  python seed.py || true
  python seed_accounting.py || true
  python seed_retebio.py || true
fi

# Start Server based on Environment
if [ "$APP_ENV" = "production" ] || [ "$APP_ENV" = "staging" ]; then
    echo "Starting Uvicorn in production/staging mode (port 8000)..."
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
else
    echo "Starting Uvicorn in development mode (port 5000 with reload)..."
    exec uvicorn main:app --host 0.0.0.0 --port 5000 --reload
fi
