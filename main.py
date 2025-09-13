from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.cache import cache
from app.api.quiz_router import router as quiz_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    await cache.connect()
    yield
    # Shutdown
    await cache.disconnect()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Production-ready Quiz API service with multi-language support, "
                "optimized for read-heavy workloads with caching and CDN integration.",
    lifespan=lifespan
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(quiz_router, prefix="/api")
from app.api.attempts_router import router as attempts_router
app.include_router(attempts_router, prefix="/api")


@app.get("/", tags=["health"])
async def root():
    """Health check endpoint"""
    return {
        "message": "Finelo Quiz API",
        "version": settings.api_version,
        "status": "healthy"
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Detailed health check with service status"""
    try:
        # Test cache connection
        cache_status = "healthy" if cache.redis_client else "disconnected"
        
        return {
            "status": "healthy",
            "services": {
                "cache": cache_status,
                "database": "healthy"  # Would add actual DB health check
            },
            "version": settings.api_version
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


# Legacy endpoints for compatibility
@app.get("/hello/{name}")
async def say_hello(name: str):
    """Legacy endpoint"""
    return {"message": f"Hello {name}"}
