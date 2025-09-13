from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/finelo_quiz"
    database_read_replica_url: Optional[str] = None
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # AWS S3
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    s3_bucket: str = "finelo-quiz-assets"
    
    # CDN
    cdn_domain: Optional[str] = None
    
    # Cache settings
    quiz_cache_ttl: int = 3600  # 1 hour
    stats_cache_ttl: int = 300   # 5 minutes
    
    # API settings
    api_title: str = "Finelo Quiz API"
    api_version: str = "1.0.0"
    debug: bool = False

    class Config:
        env_file = ".env"


settings = Settings() 