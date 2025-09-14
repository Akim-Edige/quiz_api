import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field

from app.models import QuizStatus, QuestionType, SideKind


# === Base Schemas ===

class BaseSchema(BaseModel):
    class Config:
        from_attributes = True


# === Quiz Schemas ===

class QuizI18nResponse(BaseSchema):
    locale: str
    title: str
    description: Optional[str] = None


class QuizResponse(BaseSchema):
    id: uuid.UUID
    slug: str
    status: QuizStatus
    created_at: datetime
    i18n: List[QuizI18nResponse] = []


# === Question Schemas ===

class QuestionI18nResponse(BaseSchema):
    locale: str
    prompt: str
    explanation: Optional[str] = None


class ChoiceOptionI18nResponse(BaseSchema):
    locale: str
    label: str


class ChoiceOptionResponse(BaseSchema):
    id: uuid.UUID
    display_order: int
    is_correct: bool
    i18n: List[ChoiceOptionI18nResponse] = []


class FillGapAnswerResponse(BaseSchema):
    id: uuid.UUID
    accepted_value: str


class FillGapResponse(BaseSchema):
    id: uuid.UUID
    gap_index: int
    case_sensitive: bool
    answers: List[FillGapAnswerResponse] = []


class MediaAssetI18nResponse(BaseSchema):
    locale: str
    alt_text: Optional[str] = None


class MediaAssetResponse(BaseSchema):
    id: uuid.UUID
    s3_bucket: str
    s3_key: str
    mime: str
    width: Optional[int] = None
    height: Optional[int] = None
    url: Optional[str] = None  # Computed field for CDN/presigned URL
    i18n: List[MediaAssetI18nResponse] = []


class MatchingPairResponse(BaseSchema):
    id: uuid.UUID
    left_kind: SideKind
    left_text: Optional[str] = None
    left_asset: Optional[MediaAssetResponse] = None
    right_kind: SideKind
    right_text: Optional[str] = None
    right_asset: Optional[MediaAssetResponse] = None


class QuestionResponse(BaseSchema):
    id: uuid.UUID
    qtype: QuestionType
    display_order: int
    points: int
    meta: Dict[str, Any] = {}
    i18n: List[QuestionI18nResponse] = []
    choice_options: List[ChoiceOptionResponse] = []
    fill_gaps: List[FillGapResponse] = []
    matching_pairs: List[MatchingPairResponse] = []


# === Quiz Detail Response (optimized for frontend) ===

class QuizDetailResponse(BaseSchema):
    id: uuid.UUID
    slug: str
    status: QuizStatus
    created_at: datetime
    title: str
    description: Optional[str] = None
    questions: List[QuestionResponse] = []


# === Stats Schemas ===

class QuestionStatsResponse(BaseSchema):
    question_id: uuid.UUID
    total_attempts: int
    total_correct: int
    correctness_rate: float = Field(..., description="Percentage of correct answers")
    updated_at: Optional[datetime] = None

    @classmethod
    def from_orm_with_rate(cls, stats):
        """Create response with calculated correctness rate"""
        rate = (stats.total_correct / stats.total_attempts * 100) if stats.total_attempts > 0 else 0
        return cls(
            question_id=stats.question_id,
            total_attempts=stats.total_attempts,
            total_correct=stats.total_correct,
            correctness_rate=round(rate, 2),
            updated_at=stats.updated_at
        )


class QuizStatsResponse(BaseSchema):
    quiz_id: uuid.UUID
    total_submissions: int
    avg_score: float
    question_stats: List[QuestionStatsResponse] = []
    updated_at: Optional[datetime] = None


# === Error Schemas ===

class ErrorResponse(BaseSchema):
    detail: str
    error_code: Optional[str] = None


class ValidationErrorResponse(BaseSchema):
    detail: List[Dict[str, Any]]
    error_code: str = "validation_error"


# === Localized Content Schemas ===

class LocalizedQuestionResponse(BaseSchema):
    """Optimized question response for a specific locale"""
    id: uuid.UUID
    qtype: QuestionType
    display_order: int
    points: int
    prompt: str
    explanation: Optional[str] = None
    meta: Dict[str, Any] = {}
    
    # Type-specific content
    choice_options: Optional[List[Dict[str, Any]]] = None  # For single/multi choice
    fill_gaps: Optional[List[Dict[str, Any]]] = None       # For fill-in-the-gap
    matching_pairs: Optional[List[Dict[str, Any]]] = None  # For matching


class LocalizedQuizResponse(BaseSchema):
    """Optimized quiz response for a specific locale (main API response)"""
    id: uuid.UUID
    slug: str
    status: QuizStatus
    title: str
    description: Optional[str] = None
    locale: str
    questions: List[LocalizedQuestionResponse] = []
    created_at: datetime


# === Pagination ===

class PaginationMeta(BaseSchema):
    total: int
    page: int
    size: int
    pages: int


class PaginatedQuizResponse(BaseSchema):
    items: List[QuizResponse]
    meta: PaginationMeta


# === Attempts & Answers Schemas ===

class CreateAttemptRequest(BaseSchema):
    quiz_id: uuid.UUID
    locale: Optional[str] = "en"


class CreateAttemptResponse(BaseSchema):
    attempt_id: uuid.UUID
    started_at: datetime


class SubmitAnswerRequest(BaseSchema):
    question_id: uuid.UUID
    answer: Dict[str, Any]


class SubmitAnswerResponse(BaseSchema):
    attempt_id: uuid.UUID
    question_id: uuid.UUID
    is_correct: bool
    answered_at: datetime
    

class QuestionAnswerStats(BaseSchema):
    total_attempts: int
    total_correct: int
    correctness_rate: float
    better_than_percent: float


class SubmitAnswerWithStatsResponse(SubmitAnswerResponse):
    question_stats: QuestionAnswerStats


class SubmitAttemptResponse(BaseSchema):
    attempt_id: uuid.UUID
    submitted_at: datetime
    total_answered: int
    total_correct: int
    score: int
    award_amount: int
    average_score: float
    better_than_average_percent: Optional[float] = None


# === Balance Schemas ===

class LedgerEntryResponse(BaseSchema):
    id: uuid.UUID
    delta: int
    reason: str
    created_at: datetime


class BalanceResponse(BaseSchema):
    user_id: uuid.UUID
    current_balance: int
    recent_ledger: List[LedgerEntryResponse] = []


# === Attempts Listing ===

class AttemptListItemResponse(BaseSchema):
    attempt_id: uuid.UUID
    quiz_id: uuid.UUID
    started_at: datetime
    submitted_at: Optional[datetime] = None
    status: str
    correct_answers: int
    total_questions: int
    award_amount: int
    score: int
    average_score: float
    better_than_average_percent: Optional[float] = None


class PaginatedAttemptsResponse(BaseSchema):
    items: List[AttemptListItemResponse]
    meta: PaginationMeta 