#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

if [ "$DB_TYPE" = "postgres" ]; then
  echo "Checking PostgreSQL availability..."
  # We use a simple python command to check the connection
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
  echo "PostgreSQL is up - executing migrations"
fi

# Apply migrations
# If the migrations folder doesn't exist yet, we initialize it
if [ ! -d "migrations" ]; then
    flask db init
fi

flask db migrate -m "Auto-migration" || echo "No changes to migrate"
flask db upgrade

# 3. Start Server based on Environment
if [ "$FLASK_ENV" = "production" ]; then
    echo "Starting Gunicorn in production mode..."
    # --bind 0.0.0.0:5000: liston on all interfaces
    # --workers 4: standard formula is (2 x CPUs) + 1
    # app:app refers to file_name:flask_instance_name
    exec gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app
else
    echo "Starting Flask Development Server..."
    exec python app.py
fi