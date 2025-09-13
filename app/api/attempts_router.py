import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.attempts_service import attempts_service
from app.models import BalanceAccount, BalanceLedger
from app.schemas import (
    CreateAttemptRequest, CreateAttemptResponse,
    SubmitAnswerRequest, SubmitAnswerResponse,
    SubmitAttemptResponse, BalanceResponse, LedgerEntryResponse
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


@router.post("/{attempt_id}/answers", response_model=SubmitAnswerResponse, summary="Submit answer")
async def submit_answer(
    attempt_id: uuid.UUID,
    body: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    parse_user_id(x_user_id)
    try:
        ans = await attempts_service.submit_answer(db, attempt_id, body.question_id, body.answer)
        await db.commit()
        return SubmitAnswerResponse(
            attempt_id=ans.attempt_id,
            question_id=ans.question_id,
            is_correct=ans.is_correct,
            answered_at=ans.answered_at,
        )
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{attempt_id}/submit", response_model=SubmitAttemptResponse, summary="Submit attempt")
async def submit_attempt(
    attempt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    parse_user_id(x_user_id)
    try:
        total_answered, total_correct, score, award, submitted_at = await attempts_service.submit_attempt(db, attempt_id)
        await db.commit()
        return SubmitAttemptResponse(
            attempt_id=attempt_id,
            submitted_at=submitted_at,
            total_answered=total_answered,
            total_correct=total_correct,
            score=score,
            award_amount=award,
        )
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