from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
import time

from app.config import settings
from app.cache import cache
from app.api.quiz_router import router as quiz_router


# Configure logging once at startup
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s - %(message)s"
logging.basicConfig(
    level=getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO),
    format=LOG_FORMAT,
    stream=sys.stdout,
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    logger.info("Starting up application")
    await cache.connect()
    yield
    # Shutdown
    await cache.disconnect()
    logger.info("Shutting down application")


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


# Simple request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request %s %s status=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            getattr(response, "status_code", "-"),
            duration_ms,
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
        logger.exception("Health check failed: %s", e)
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


# Legacy endpoints for compatibility
@app.get("/hello/{name}")
async def say_hello(name: str):
    """Legacy endpoint"""
    return {"message": f"Hello {name}"}
