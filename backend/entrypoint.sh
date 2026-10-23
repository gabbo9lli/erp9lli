#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

if [ "$DB_TYPE" = "postgres" ] || [ "$DB_TYPE" = "postgresql" ]; then
  echo "Checking PostgreSQL availability..."
  python << END
import socket
import time
import os

db_host = "db"
db_port = 5432
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
while True:
    try:
        s.connect((db_host, db_port))
        s.close()
        break
    except socket.error:
        print("Postgres is unavailable - sleeping")
        time.sleep(1)
END
  echo "PostgreSQL is up - executing database migrations..."
  alembic upgrade head || echo "Migrations completed or already at head."
fi

# Start Server based on Environment
if [ "$APP_ENV" = "production" ] || [ "$FLASK_ENV" = "production" ]; then
    echo "Starting Uvicorn in production mode (port 8000)..."
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
else
    echo "Starting Uvicorn in development mode (port 5000 with reload)..."
    exec uvicorn main:app --host 0.0.0.0 --port 5000 --reload
fi
