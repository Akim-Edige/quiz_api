#!/bin/bash

# Finelo Quiz API Startup Script
# This script sets up and starts the development environment

set -e

echo "🚀 Starting Finelo Quiz API Development Environment"
echo "================================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ .env file created. Please edit it with your configurations."
else
    echo "✅ .env file found"
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Wait for database (if using Docker)
if [ "$1" = "--docker" ]; then
    echo "⏳ Waiting for database to be ready..."
    sleep 5
fi

# Run migrations
echo "🗄️ Running database migrations..."
python -m alembic upgrade head

# Check if we should seed data
if [ "$1" = "--seed" ] || [ "$2" = "--seed" ]; then
    echo "🌱 Seeding sample data..."
    python scripts/seed_data.py
fi

echo "🎯 Starting FastAPI server..."
echo "📍 API will be available at: http://localhost:8000"
echo "📚 API Documentation: http://localhost:8000/docs"
echo ""

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload 