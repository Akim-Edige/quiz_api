import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_read_db
from app.services.quiz_service import quiz_service
from app.schemas import (
    LocalizedQuizResponse, QuizStatsResponse, PaginatedQuizResponse,
    ErrorResponse
)

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.get(
    "/{quiz_id}",
    response_model=LocalizedQuizResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Quiz not found"},
        400: {"model": ErrorResponse, "description": "Invalid quiz ID format"}
    },
    summary="Get quiz content",
    description="Get complete quiz content optimized for a specific locale. "
                "Includes all questions, options, and media URLs. Uses caching for optimal performance."
)
async def get_quiz(
    quiz_id: uuid.UUID,
    locale: str = Query("en", description="Language locale (e.g., en, es, pt, de, tr, fr, it, fil, ja)"),
    db: AsyncSession = Depends(get_read_db)
):
    """
    Get quiz content for a specific locale.
    
    This endpoint is read-optimized and uses:
    - Read replicas for database queries
    - Redis caching for assembled quiz content
    - CDN URLs for media assets
    """
    try:
        quiz = await quiz_service.get_quiz_by_id(db, quiz_id, locale)
        if not quiz:
            raise HTTPException(
                status_code=404,
                detail=f"Quiz with ID {quiz_id} not found"
            )
        return quiz
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid quiz ID format"
        )


@router.get(
    "/{quiz_id}/stats",
    response_model=QuizStatsResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Quiz not found"},
        400: {"model": ErrorResponse, "description": "Invalid quiz ID format"}
    },
    summary="Get quiz statistics",
    description="Get quiz performance statistics including question correctness rates and overall scores. "
                "Used for 'compare to others' functionality."
)
async def get_quiz_stats(
    quiz_id: uuid.UUID,
    db: AsyncSession = Depends(get_read_db)
):
    """
    Get quiz statistics for comparison features.
    
    Returns:
    - Overall quiz submission stats
    - Per-question correctness rates
    - Data for percentile calculations
    """
    try:
        stats = await quiz_service.get_quiz_stats(db, quiz_id)
        if not stats:
            raise HTTPException(
                status_code=404,
                detail=f"Quiz with ID {quiz_id} not found"
            )
        return stats
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid quiz ID format"
        )


@router.get(
    "",
    response_model=PaginatedQuizResponse,
    summary="List quizzes",
    description="Get paginated list of published quizzes with localized titles and descriptions."
)
async def list_quizzes(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    size: int = Query(20, ge=1, le=100, description="Number of items per page"),
    locale: str = Query("en", description="Language locale for titles and descriptions"),
    db: AsyncSession = Depends(get_read_db)
):
    """
    List published quizzes with pagination.
    
    Features:
    - Pagination with configurable page size
    - Localized content (titles, descriptions)
    - Only returns published quizzes
    - Ordered by creation date (newest first)
    """
    result = await quiz_service.list_quizzes(db, page, size, locale)
    return result


@router.get(
    "/slug/{slug}",
    response_model=LocalizedQuizResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Quiz not found"},
    },
    summary="Get quiz by slug",
    description="Get quiz content by slug identifier. Alternative to ID-based lookup."
)
async def get_quiz_by_slug(
    slug: str,
    locale: str = Query("en", description="Language locale"),
    db: AsyncSession = Depends(get_read_db)
):
    """
    Get quiz content by slug.
    
    This is a convenience endpoint for more user-friendly URLs.
    Internally converts slug to ID and uses the same optimization.
    """
    # This would need a method in quiz_service to fetch by slug
    # For now, return a placeholder response
    raise HTTPException(
        status_code=501,
        detail="Get by slug not yet implemented"
    ) 