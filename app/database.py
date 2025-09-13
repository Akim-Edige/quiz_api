from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

# Create async engines
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
)

# Read replica engine (fallback to primary if not configured)
read_engine = create_async_engine(
    settings.database_read_replica_url or settings.database_url,
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