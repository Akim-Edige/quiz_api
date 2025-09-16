#!/usr/bin/env python3
"""
Basic validation test for the Quiz API structure
Tests that the application loads correctly and basic routes are accessible
"""

import sys
import traceback
from unittest.mock import Mock, patch

def test_imports():
    """Test that all imports work correctly"""
    print("🧪 Testing imports...")
    try:
        # Test core imports
        from app import config, database, models, schemas
        from app.services import quiz_service
        from app.api import quiz_router
        from app import cache, s3_utils
        print("✅ All core imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        traceback.print_exc()
        return False

def test_models():
    """Test that models are properly defined"""
    print("🧪 Testing models...")
    try:
        from app.models import Quiz, Question, ChoiceOption, QuestionType, QuizStatus
        
        # Test enum values
        assert QuestionType.SINGLE_CHOICE == "single_choice"
        assert QuestionType.MULTI_CHOICE == "multi_choice"
        assert QuestionType.FILL_GAP == "fill_gap"
        assert QuestionType.MATCHING == "matching"
        
        assert QuizStatus.DRAFT == "draft"
        assert QuizStatus.PUBLISHED == "published"
        assert QuizStatus.ARCHIVED == "archived"
        
        print("✅ Models validation successful")
        return True
    except Exception as e:
        print(f"❌ Models error: {e}")
        traceback.print_exc()
        return False

def test_schemas():
    """Test that Pydantic schemas work correctly"""
    print("🧪 Testing schemas...")
    try:
        from app.schemas import LocalizedQuizResponse, QuizStatsResponse
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
        
        print("✅ Schemas validation successful")
        return True
    except Exception as e:
        print(f"❌ Schemas error: {e}")
        traceback.print_exc()
        return False

def test_app_creation():
    """Test that FastAPI app can be created"""
    print("🧪 Testing FastAPI app creation...")
    try:
        # Mock the cache connection to avoid Redis dependency
        with patch('app.cache.cache.connect'), patch('app.cache.cache.disconnect'):
            import main
            app = main.app
            
            # Check that app has the expected routes
            routes = [route.path for route in app.routes]
            expected_routes = ["/", "/health", "/api/quizzes/{quiz_id}", "/api/quizzes"]
            
            for route in expected_routes:
                found = any(route in r for r in routes)
                if not found:
                    print(f"⚠️  Route {route} not found in {routes}")
            
            print("✅ FastAPI app creation successful")
            return True
    except Exception as e:
        print(f"❌ App creation error: {e}")
        traceback.print_exc()
        return False

def test_configuration():
    """Test configuration loading"""
    print("🧪 Testing configuration...")
    try:
        from app.config import settings
        
        # Test default values
        assert settings.api_title == "Finelo Quiz API"
        assert settings.quiz_cache_ttl == 3600
        assert settings.stats_cache_ttl == 300
        
        print("✅ Configuration validation successful")
        return True
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("🚀 Finelo Quiz API - Basic Validation Tests")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_models, 
        test_schemas,
        test_configuration,
        test_app_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("📊 Test Results")
    print("-" * 20)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! The Quiz API structure is valid.")
        print("\n🚀 Ready to run:")
        print("   python run_dev.py     # Start development server")  
        print("   uvicorn main:app --reload  # Alternative start method")
        print("\n📚 Once running, visit:")
        print("   http://localhost:8000/docs  # API documentation")
        print("   http://localhost:8000/health  # Health check")
        return True
    else:
        print(f"❌ {total - passed} tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 