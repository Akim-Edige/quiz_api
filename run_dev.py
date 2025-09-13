#!/usr/bin/env python3
"""
Development runner for Finelo Quiz API
Usage: python run_dev.py [--seed]
"""

import os
import sys
import subprocess
import time
import asyncio
from pathlib import Path

def run_command(command, description=""):
    """Run a shell command and handle errors"""
    if description:
        print(f"📋 {description}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        if result.stdout.strip():
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stderr:
            print(f"Error details: {e.stderr}")
        return False

async def check_services():
    """Check if required services are available"""
    print("🔍 Checking services...")
    
    # Check if PostgreSQL is available
    try:
        import asyncpg
        # Try to connect with default settings
        conn = await asyncpg.connect("postgresql://postgres:password@localhost:5432/finelo_quiz")
        await conn.close()
        print("✅ PostgreSQL connection successful")
    except Exception as e:
        print(f"⚠️  PostgreSQL not available: {e}")
        print("💡 You can start PostgreSQL with Docker: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:15")
    
    # Check if Redis is available  
    try:
        import redis.asyncio as redis
        r = redis.from_url("redis://localhost:6379/0")
        await r.ping()
        await r.close()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"⚠️  Redis not available: {e}")
        print("💡 You can start Redis with Docker: docker run -d -p 6379:6379 redis:7-alpine")

def main():
    """Main development setup and run function"""
    print("🚀 Finelo Quiz API - Development Setup")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("main.py").exists():
        print("❌ Please run this script from the project root directory")
        sys.exit(1)
    
    # Create .env if it doesn't exist
    if not Path(".env").exists():
        print("📝 Creating .env file from template...")
        if Path(".env.example").exists():
            import shutil
            shutil.copy(".env.example", ".env")
            print("✅ .env file created")
        else:
            print("⚠️  .env.example not found, please create .env manually")
    
    # Install dependencies
    print("📦 Installing dependencies...")
    if not run_command("pip install -r requirements.txt", "Installing Python dependencies"):
        print("❌ Failed to install dependencies")
        sys.exit(1)
    
    # Check services availability
    asyncio.run(check_services())
    
    # Run migrations
    print("🗄️ Running database migrations...")
    if not run_command("python -m alembic upgrade head", "Applying database migrations"):
        print("⚠️  Database migrations failed - make sure PostgreSQL is running")
        print("💡 You can start PostgreSQL with Docker Compose: docker-compose up -d db")
    
    # Seed data if requested
    if "--seed" in sys.argv:
        print("🌱 Seeding sample data...")
        if not run_command("python scripts/seed_data.py", "Creating sample quiz data"):
            print("⚠️  Failed to seed data")
    
    print("\n🎯 Starting FastAPI development server...")
    print("📍 API: http://localhost:8000")
    print("📚 Docs: http://localhost:8000/docs")
    print("🔄 Auto-reload enabled")
    print("\n⌨️  Press Ctrl+C to stop")
    print("-" * 50)
    
    # Start the server
    try:
        os.system("uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
    except KeyboardInterrupt:
        print("\n👋 Server stopped")

if __name__ == "__main__":
    main() 