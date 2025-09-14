import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.attempts_service import attempts_service
from app.models import BalanceAccount, BalanceLedger, Attempt
from app.schemas import (
    CreateAttemptRequest, CreateAttemptResponse,
    SubmitAnswerRequest, SubmitAnswerWithStatsResponse,
    SubmitAttemptResponse, BalanceResponse, LedgerEntryResponse,
    PaginatedAttemptsResponse
)

router = APIRouter(prefix="/attempts", tags=["attempts"])


def parse_user_id(x_user_id: Optional[str]) -> uuid.UUID:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing x-user-id header")
    try:
        return uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid x-user-id header")


@router.post("", response_model=CreateAttemptResponse, summary="Create attempt")
async def create_attempt(
    body: CreateAttemptRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    user_id = parse_user_id(x_user_id)
    try:
        attempt = await attempts_service.create_attempt(db, user_id, body.quiz_id, body.locale)
        await db.commit()
        return CreateAttemptResponse(attempt_id=attempt.id, started_at=attempt.started_at)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{attempt_id}/answers", response_model=SubmitAnswerWithStatsResponse, summary="Submit answer")
async def submit_answer(
    attempt_id: uuid.UUID,
    body: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    user_id = parse_user_id(x_user_id)
    try:
        # Authorization check: attempt must belong to this user
        attempt = await db.get(Attempt, attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="Attempt not found")
        if attempt.user_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden: attempt does not belong to this user")

        ans, total_attempts, total_correct, correctness_rate, better_than = await attempts_service.submit_answer(db, attempt_id, body.question_id, body.answer)
        await db.commit()
        return {
            "attempt_id": ans.attempt_id,
            "question_id": ans.question_id,
            "is_correct": ans.is_correct,
            "answered_at": ans.answered_at,
            "question_stats": {
                "total_attempts": total_attempts,
                "total_correct": total_correct,
                "correctness_rate": correctness_rate,
                "better_than_percent": better_than
            }
        }
    except HTTPException:
        await db.rollback()
        raise
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{attempt_id}/submit", response_model=SubmitAttemptResponse, summary="Submit attempt")
async def submit_attempt(
    attempt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    user_id = parse_user_id(x_user_id)
    try:
        # Authorization check: attempt must belong to this user
        attempt = await db.get(Attempt, attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="Attempt not found")
        if attempt.user_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden: attempt does not belong to this user")

        total_answered, total_correct, score, award, submitted_at, avg_score, better_than_avg = await attempts_service.submit_attempt(db, attempt_id)
        await db.commit()
        return {
            "attempt_id": attempt_id,
            "submitted_at": submitted_at,
            "total_answered": total_answered,
            "total_correct": total_correct,
            "score": score,
            "award_amount": award,
            "average_score": avg_score,
            "better_than_average_percent": better_than_avg
        }
    except HTTPException:
        await db.rollback()
        raise
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me/balance", response_model=BalanceResponse, summary="Get my balance")
async def get_my_balance(
    db: AsyncSession = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    user_id = parse_user_id(x_user_id)
    account = await db.get(BalanceAccount, user_id)
    if not account:
        account_balance = 0
    else:
        account_balance = account.current_balance or 0

    # recent 10 ledger entries
    from sqlalchemy import select, desc
    q = select(BalanceLedger).where(BalanceLedger.user_id == user_id).order_by(desc(BalanceLedger.created_at)).limit(10)
    res = await db.execute(q)
    items = res.scalars().all()
    return BalanceResponse(
        user_id=user_id,
        current_balance=account_balance,
        recent_ledger=[
            LedgerEntryResponse(id=i.id, delta=i.delta, reason=i.reason, created_at=i.created_at) for i in items
        ]
    )


@router.get("/me", summary="List my attempts", response_model=PaginatedAttemptsResponse)
async def list_my_attempts(
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    user_id = parse_user_id(x_user_id)
    if page < 1 or size < 1 or size > 100:
        raise HTTPException(status_code=400, detail="Invalid pagination parameters")
    # Fetch aggregates
    items, total, correct_by_attempt, total_by_quiz, award_by_attempt = await attempts_service.list_attempts(db, user_id, page, size)
    resp_items = []
    for a in items:
        status = "Submitted" if a.submitted_at else "In progress"
        correct = correct_by_attempt.get(a.id, 0)
        total_q = total_by_quiz.get(a.quiz_id, 0)
        award = award_by_attempt.get(a.id, 0)
        # score and average
        score = int(round((correct / total_q) * 100)) if total_q and a.submitted_at else 0
        # derive average per quiz similarly to service computation (reuse totals via a new call would be redundant).
        # For simplicity, call stats derivation inside service in future; here, compute via avg_by_quiz if returned.
        # But since we didn't return avg_by_quiz from service, recompute lightweight via QuizStats if available.
        from app.models import QuizStats
        qstats = await db.get(QuizStats, a.quiz_id)
        avg_score = float(qstats.avg_score) if qstats and qstats.avg_score is not None else 0.0
        better_than_avg = None
        if avg_score > 0 and score > avg_score:
            better_than_avg = round(((score - avg_score) / avg_score) * 100.0, 2)
        resp_items.append({
            "attempt_id": a.id,
            "quiz_id": a.quiz_id,
            "started_at": a.started_at,
            "submitted_at": a.submitted_at,
            "status": status,
            "correct_answers": correct,
            "total_questions": total_q,
            "award_amount": award,
            "score": score,
            "average_score": avg_score,
            "better_than_average_percent": better_than_avg,
        })
    pages = (total + size - 1) // size
    return {
        "items": resp_items,
        "meta": {
            "total": total,
            "page": page,
            "size": size,
            "pages": pages
        }
    } 