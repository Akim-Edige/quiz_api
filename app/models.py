import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Text, Integer, Boolean, DateTime, Numeric, LargeBinary,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class QuizStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class QuestionType(str, enum.Enum):
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    FILL_GAP = "fill_gap"
    MATCHING = "matching"


class SideKind(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"


# === Content & i18n ===

class Quiz(Base):
    __tablename__ = "quiz"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    status: Mapped[QuizStatus] = mapped_column(
        SQLEnum(QuizStatus, name="quizstatus", values_callable=lambda x: [e.value for e in x], create_type=False), 
        nullable=False, 
        default=QuizStatus.PUBLISHED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    i18n: Mapped[list["QuizI18n"]] = relationship("QuizI18n", back_populates="quiz", cascade="all, delete-orphan")
    questions: Mapped[list["Question"]] = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")


class QuizI18n(Base):
    __tablename__ = "quiz_i18n"
    
    quiz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quiz.id", ondelete="CASCADE"), primary_key=True)
    locale: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships
    quiz: Mapped["Quiz"] = relationship("Quiz", back_populates="i18n")


class Question(Base):
    __tablename__ = "question"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quiz.id", ondelete="CASCADE"), nullable=False)
    qtype: Mapped[QuestionType] = mapped_column(SQLEnum(QuestionType, name="questiontype", values_callable=lambda x: [e.value for e in x], create_type=False), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    
    __table_args__ = (
        UniqueConstraint("quiz_id", "display_order"),
        Index("idx_question_quiz_order", "quiz_id", "display_order"),
    )
    
    # Relationships
    quiz: Mapped["Quiz"] = relationship("Quiz", back_populates="questions")
    i18n: Mapped[list["QuestionI18n"]] = relationship("QuestionI18n", back_populates="question", cascade="all, delete-orphan")
    choice_options: Mapped[list["ChoiceOption"]] = relationship("ChoiceOption", back_populates="question", cascade="all, delete-orphan")
    fill_gaps: Mapped[list["FillGap"]] = relationship("FillGap", back_populates="question", cascade="all, delete-orphan")
    matching_pairs: Mapped[list["MatchingPair"]] = relationship("MatchingPair", back_populates="question", cascade="all, delete-orphan")


class QuestionI18n(Base):
    __tablename__ = "question_i18n"
    
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("question.id", ondelete="CASCADE"), primary_key=True)
    locale: Mapped[str] = mapped_column(String, primary_key=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships
    question: Mapped["Question"] = relationship("Question", back_populates="i18n")


# === Choice Options ===

class ChoiceOption(Base):
    __tablename__ = "choice_option"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("question.id", ondelete="CASCADE"), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    __table_args__ = (
        UniqueConstraint("question_id", "display_order"),
        Index("idx_choice_question", "question_id"),
    )
    
    # Relationships
    question: Mapped["Question"] = relationship("Question", back_populates="choice_options")
    i18n: Mapped[list["ChoiceOptionI18n"]] = relationship("ChoiceOptionI18n", back_populates="option", cascade="all, delete-orphan")


class ChoiceOptionI18n(Base):
    __tablename__ = "choice_option_i18n"
    
    option_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("choice_option.id", ondelete="CASCADE"), primary_key=True)
    locale: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Relationships
    option: Mapped["ChoiceOption"] = relationship("ChoiceOption", back_populates="i18n")


# === Fill the Gap ===

class FillGap(Base):
    __tablename__ = "fill_gap"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("question.id", ondelete="CASCADE"), nullable=False)
    gap_index: Mapped[int] = mapped_column(Integer, nullable=False)
    case_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    __table_args__ = (
        UniqueConstraint("question_id", "gap_index"),
    )
    
    # Relationships
    question: Mapped["Question"] = relationship("Question", back_populates="fill_gaps")
    answers: Mapped[list["FillGapAnswer"]] = relationship("FillGapAnswer", back_populates="gap", cascade="all, delete-orphan")


class FillGapAnswer(Base):
    __tablename__ = "fill_gap_answer"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gap_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fill_gap.id", ondelete="CASCADE"), nullable=False)
    accepted_value: Mapped[str] = mapped_column(Text, nullable=False)
    
    __table_args__ = (
        Index("idx_fga_gap", "gap_id"),
    )
    
    # Relationships
    gap: Mapped["FillGap"] = relationship("FillGap", back_populates="answers")


# === Media Assets ===

class MediaAsset(Base):
    __tablename__ = "media_asset"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    s3_bucket: Mapped[str] = mapped_column(String, nullable=False)
    s3_key: Mapped[str] = mapped_column(String, nullable=False)
    mime: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("s3_bucket", "s3_key"),
    )
    
    # Relationships
    i18n: Mapped[list["MediaAssetI18n"]] = relationship("MediaAssetI18n", back_populates="asset", cascade="all, delete-orphan")


class MediaAssetI18n(Base):
    __tablename__ = "media_asset_i18n"
    
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("media_asset.id", ondelete="CASCADE"), primary_key=True)
    locale: Mapped[str] = mapped_column(String, primary_key=True)
    alt_text: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships
    asset: Mapped["MediaAsset"] = relationship("MediaAsset", back_populates="i18n")


# === Matching ===

class MatchingPair(Base):
    __tablename__ = "matching_pair"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("question.id", ondelete="CASCADE"), nullable=False)
    left_kind: Mapped[SideKind] = mapped_column(SQLEnum(SideKind, name="sidekind", values_callable=lambda x: [e.value for e in x], create_type=False), nullable=False)
    left_text: Mapped[Optional[str]] = mapped_column(Text)
    left_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("media_asset.id"))
    right_kind: Mapped[SideKind] = mapped_column(SQLEnum(SideKind, name="sidekind", values_callable=lambda x: [e.value for e in x], create_type=False), nullable=False)
    right_text: Mapped[Optional[str]] = mapped_column(Text)
    right_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("media_asset.id"))
    
    __table_args__ = (
        CheckConstraint("(left_kind='text' AND left_text IS NOT NULL) OR (left_kind='image' AND left_asset_id IS NOT NULL)"),
        CheckConstraint("(right_kind='text' AND right_text IS NOT NULL) OR (right_kind='image' AND right_asset_id IS NOT NULL)"),
        Index("idx_match_question", "question_id"),
    )
    
    # Relationships
    question: Mapped["Question"] = relationship("Question", back_populates="matching_pairs")
    left_asset: Mapped[Optional["MediaAsset"]] = relationship("MediaAsset", foreign_keys=[left_asset_id])
    right_asset: Mapped[Optional["MediaAsset"]] = relationship("MediaAsset", foreign_keys=[right_asset_id])


# === Stats ===

class QuestionStats(Base):
    __tablename__ = "question_stats"
    
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("question.id"), primary_key=True)
    total_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class QuizStats(Base):
    __tablename__ = "quiz_stats"
    
    quiz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quiz.id"), primary_key=True)
    total_submissions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# === Attempts & Answers ===

class Attempt(Base):
    __tablename__ = "attempt"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quiz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quiz.id"), nullable=False)
    locale: Mapped[Optional[str]] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    __table_args__ = (
        Index("idx_attempt_user_quiz", "user_id", "quiz_id", "started_at"),
        Index("idx_attempt_quiz_time", "quiz_id", "started_at"),
    )
    
    # Relationships
    quiz: Mapped["Quiz"] = relationship("Quiz")
    answers: Mapped[list["AttemptAnswer"]] = relationship("AttemptAnswer", back_populates="attempt", cascade="all, delete-orphan")


class AttemptAnswer(Base):
    __tablename__ = "attempt_answer"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attempt.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("question.id"), nullable=False)
    answer: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id"),
        Index("idx_ans_attempt", "attempt_id"),
        Index("idx_ans_user_q", "question_id", "is_correct"),
    )
    
    # Relationships
    attempt: Mapped["Attempt"] = relationship("Attempt", back_populates="answers")
    question: Mapped["Question"] = relationship("Question")


class UserQuestionState(Base):
    __tablename__ = "user_question_state"
    
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    first_correct_attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attempt.id"), nullable=False)
    first_correct_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# === Awards & Balance ===

class BalanceAccount(Base):
    __tablename__ = "balance_account"
    
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    current_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BalanceLedger(Base):
    __tablename__ = "balance_ledger"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        Index("idx_ledger_user_time", "user_id", "created_at"),
    )


class QuizAward(Base):
    __tablename__ = "quiz_award"
    
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    quiz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now()) 