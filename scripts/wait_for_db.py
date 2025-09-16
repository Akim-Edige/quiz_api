import asyncio
import os
import sys

import asyncpg

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@db:5432/finelo_quiz")


async def wait_for_db(max_attempts: int = 30, delay_seconds: float = 1.0) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            conn = await asyncpg.connect(DB_URL.replace("+asyncpg", ""))
            await conn.close()
            print(f"✅ Database is ready (attempt {attempt})")
            return
        except Exception as e:
            print(f"⏳ Waiting for DB... attempt {attempt}/{max_attempts}: {e}")
            await asyncio.sleep(delay_seconds)
    print("❌ Database not ready in time", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(wait_for_db()) 