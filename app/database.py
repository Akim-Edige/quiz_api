from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings
import logging

logger = logging.getLogger("app.database")

# Create async engines
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
)

# Read replica engine (fallback to primary if not configured)
_replica_raw = (settings.database_read_replica_url or "").strip()
_invalid_placeholders = {"", "REPLICA_URL", "replica_url", "None", "none"}
read_url = settings.database_url if _replica_raw in _invalid_placeholders else _replica_raw
if read_url == settings.database_url:
    logger.info("Using primary DB URL for read engine (no valid replica URL configured)")
else:
    logger.info("Using read replica DB URL for read engine")

read_engine = create_async_engine(
    read_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
)

# Session makers
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
AsyncReadSessionLocal = async_sessionmaker(read_engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

# Dependency for write database sessions
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Dependency for read database sessions
async def get_read_db():
    async with AsyncReadSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close() 