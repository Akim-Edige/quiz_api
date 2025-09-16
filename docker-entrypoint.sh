#!/bin/bash
set -euo pipefail

echo "🚀 Entry: Starting Finelo Quiz API"

# Wait for DB
echo "⏳ Waiting for database to be ready..."
python scripts/wait_for_db.py

# Run migrations
echo "🗄️ Running database migrations..."
python -m alembic upgrade head

# Bootstrap LocalStack S3 if requested
if [[ "${INIT_S3_ON_START:-1}" == "1" ]]; then
  echo "🪣 Initializing S3 (LocalStack) assets..."
  python scripts/bootstrap_s3_local.py || echo "⚠️ S3 bootstrap skipped/failed"
fi

# Seed data if requested
if [[ "${SEED_ON_START:-1}" == "1" ]]; then
  echo "🌱 Seeding sample data..."
  python seed_runner.py || echo "⚠️ Seed step skipped/failed"
fi

# Start server
echo "🎯 Starting FastAPI server on :8000"
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload 