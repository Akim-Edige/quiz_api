#!/usr/bin/env python3
"""
Basic validation test for the Quiz API structure
Tests that the application loads correctly and basic routes are accessible
"""

from unittest.mock import patch


def test_imports():
    """Test that all imports work correctly"""
    from app import config, database, models, schemas  # noqa: F401
    from app.services import quiz_service  # noqa: F401
    from app.api import quiz_router  # noqa: F401
    from app import cache, s3_utils  # noqa: F401


def test_models():
    """Test that models are properly defined"""
    from app.models import Quiz, Question, ChoiceOption, QuestionType, QuizStatus  # noqa: F401

    # Test enum values
    assert QuestionType.SINGLE_CHOICE == "single_choice"
    assert QuestionType.MULTI_CHOICE == "multi_choice"
    assert QuestionType.FILL_GAP == "fill_gap"
    assert QuestionType.MATCHING == "matching"

    assert QuizStatus.DRAFT == "draft"
    assert QuizStatus.PUBLISHED == "published"
    assert QuizStatus.ARCHIVED == "archived"


def test_schemas():
    """Test that Pydantic schemas work correctly"""
    from app.schemas import LocalizedQuizResponse, QuizStatsResponse  # noqa: F401
    from app.models import QuizStatus
    import uuid
    from datetime import datetime

    # Test creating a quiz response
    quiz_data = {
        "id": uuid.uuid4(),
        "slug": "test-quiz",
        "status": QuizStatus.PUBLISHED,
        "title": "Test Quiz",
        "description": "A test quiz",
        "locale": "en",
        "questions": [],
        "created_at": datetime.now()
    }

    quiz_response = LocalizedQuizResponse(**quiz_data)
    assert quiz_response.slug == "test-quiz"
    assert quiz_response.locale == "en"


def test_app_creation():
    """Test that FastAPI app can be created"""
    # Mock the cache connection to avoid Redis dependency
    with patch('app.cache.cache.connect'), patch('app.cache.cache.disconnect'):
        import main
        app = main.app

        # Check that app has the expected routes
        routes = [route.path for route in app.routes]
        expected_routes = ["/", "/health", "/api/quizzes/{quiz_id}", "/api/quizzes"]

        for route in expected_routes:
            assert any(route in r for r in routes), f"Route {route} not found in {routes}"


def test_configuration():
    """Test configuration loading"""
    from app.config import settings

    # Test default values
    assert settings.api_title == "Finelo Quiz API"
    assert settings.quiz_cache_ttl == 3600
    assert settings.stats_cache_ttl == 300 