import json
import redis.asyncio as redis
from typing import Optional, Any, Dict
from app.config import settings


class CacheService:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Initialize Redis connection"""
        self.redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.redis_client:
            return None
        
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception:
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL"""
        if not self.redis_client:
            return False
        
        try:
            serialized_value = json.dumps(value, default=str)
            await self.redis_client.setex(key, ttl, serialized_value)
            return True
        except Exception:
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.delete(key)
            return True
        except Exception:
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.redis_client:
            return 0
        
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
        except Exception:
            return 0
    
    # Quiz-specific cache methods
    
    def get_quiz_cache_key(self, quiz_id: str, locale: str) -> str:
        """Generate cache key for quiz content (versioned)"""
        from app.config import settings
        return f"quiz:{settings.quiz_payload_version}:{quiz_id}:{locale}"
    
    def get_quiz_stats_cache_key(self, quiz_id: str) -> str:
        """Generate cache key for quiz stats (versioned)"""
        from app.config import settings
        return f"quiz:stats:{settings.quiz_stats_version}:{quiz_id}"
    
    async def get_cached_quiz(self, quiz_id: str, locale: str) -> Optional[Dict[str, Any]]:
        """Get cached quiz content for specific locale"""
        key = self.get_quiz_cache_key(quiz_id, locale)
        return await self.get(key)
    
    async def cache_quiz(self, quiz_id: str, locale: str, quiz_data: Dict[str, Any]) -> bool:
        """Cache quiz content for specific locale"""
        key = self.get_quiz_cache_key(quiz_id, locale)
        return await self.set(key, quiz_data, settings.quiz_cache_ttl)
    
    async def invalidate_quiz_cache(self, quiz_id: str) -> int:
        """Invalidate all cached versions of a quiz (all locales and payload versions)"""
        # Match both old and new versions
        deleted = 0
        deleted += await self.delete_pattern(f"quiz:{quiz_id}:*")
        deleted += await self.delete_pattern(f"quiz:*:{quiz_id}:*")
        return deleted
    
    async def get_cached_quiz_stats(self, quiz_id: str) -> Optional[Dict[str, Any]]:
        """Get cached quiz statistics"""
        key = self.get_quiz_stats_cache_key(quiz_id)
        return await self.get(key)
    
    async def cache_quiz_stats(self, quiz_id: str, stats_data: Dict[str, Any]) -> bool:
        """Cache quiz statistics"""
        key = self.get_quiz_stats_cache_key(quiz_id)
        return await self.set(key, stats_data, settings.stats_cache_ttl)

    async def invalidate_quiz_stats_cache(self, quiz_id: str) -> int:
        """Invalidate all cached versions of quiz stats"""
        deleted = 0
        deleted += await self.delete_pattern(f"quiz:stats:{quiz_id}")
        deleted += await self.delete_pattern(f"quiz:stats:*:{quiz_id}")
        return deleted


# Global cache instance
cache = CacheService() 