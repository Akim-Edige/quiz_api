from typing import Optional, Tuple
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import (
    Attempt, AttemptAnswer, Quiz, Question, FillGap,
    UserQuestionState, QuizAward, BalanceAccount, BalanceLedger,
    QuestionStats, QuizStats
)
from app.services.quiz_service import evaluate_answer
from app.cache import cache


class AttemptsService:
    async def create_attempt(self, session: AsyncSession, user_id: uuid.UUID, quiz_id: uuid.UUID, locale: Optional[str]) -> Attempt:
        # Ensure quiz exists
        quiz = await session.get(Quiz, quiz_id)
        if not quiz:
            raise ValueError("Quiz not found")
        attempt = Attempt(user_id=user_id, quiz_id=quiz_id, locale=locale)
        session.add(attempt)
        await session.flush()
        return attempt

    async def submit_answer(
        self,
        session: AsyncSession,
        attempt_id: uuid.UUID,
        question_id: uuid.UUID,
        answer_payload: dict
    ) -> AttemptAnswer:
        # Load question with required relations
        question_stmt = (
            select(Question)
            .options(
                selectinload(Question.choice_options),
                selectinload(Question.fill_gaps).selectinload(FillGap.answers),
                selectinload(Question.matching_pairs),
            )
            .where(Question.id == question_id)
        )
        q_res = await session.execute(question_stmt)
        question = q_res.scalar_one_or_none()
        if not question:
            raise ValueError("Question not found")

        # Ensure attempt exists and matches quiz
        attempt = await session.get(Attempt, attempt_id)
        if not attempt or attempt.quiz_id != question.quiz_id:
            raise ValueError("Invalid attempt or mismatched quiz/question")
        if attempt.submitted_at:
            raise ValueError("Attempt already submitted")

        # Evaluate correctness
        is_correct = await evaluate_answer(question, answer_payload)

        # Upsert attempt answer (unique on attempt_id, question_id)
        existing_stmt = (
            select(AttemptAnswer)
            .where(AttemptAnswer.attempt_id == attempt_id, AttemptAnswer.question_id == question_id)
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            existing.answer = answer_payload
            existing.is_correct = is_correct
            await session.flush()
            return existing

        ans = AttemptAnswer(
            attempt_id=attempt_id,
            question_id=question_id,
            answer=answer_payload,
            is_correct=is_correct,
        )
        session.add(ans)
        await session.flush()
        return ans

    async def submit_attempt(self, session: AsyncSession, attempt_id: uuid.UUID) -> Tuple[int, int, int, int, datetime]:
        # Mark submitted and compute score; perform awarding
        attempt = await session.get(Attempt, attempt_id)
        if not attempt:
            raise ValueError("Attempt not found")
        already_submitted = attempt.submitted_at is not None
        if already_submitted:
            submitted_at = attempt.submitted_at
        else:
            attempt.submitted_at = datetime.utcnow()
            await session.flush()
            submitted_at = attempt.submitted_at

        # Load answers
        answers_stmt = select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt_id)
        ans_list = (await session.execute(answers_stmt)).scalars().all()
        total_answered = len(ans_list)
        total_correct = sum(1 for a in ans_list if a.is_correct)
        score = total_correct * 100

        if not already_submitted:
            # Update stats (upsert-like)
            for a in ans_list:
                qs = await session.get(QuestionStats, a.question_id)
                if not qs:
                    qs = QuestionStats(question_id=a.question_id, total_attempts=0, total_correct=0)
                    session.add(qs)
                qs.total_attempts = (qs.total_attempts or 0) + 1
                if a.is_correct:
                    qs.total_correct = (qs.total_correct or 0) + 1
            # Quiz stats
            qstats = await session.get(QuizStats, attempt.quiz_id)
            if not qstats:
                qstats = QuizStats(quiz_id=attempt.quiz_id, total_submissions=0, avg_score=0)
                session.add(qstats)
            # naive rolling average
            n = (qstats.total_submissions or 0)
            qstats.avg_score = ((float(qstats.avg_score) * n) + score) / (n + 1)
            qstats.total_submissions = n + 1

        # Awarding: ensure single award per attempt and only for first-time correct per question
        award_amount = await self._award_for_attempt(session, attempt.user_id, attempt.quiz_id, attempt.id)

        if not already_submitted:
            # Invalidate caches
            try:
                await cache.invalidate_quiz_cache(str(attempt.quiz_id))
                await cache.delete(cache.get_quiz_stats_cache_key(str(attempt.quiz_id)))
            except Exception:
                pass

        return total_answered, total_correct, score, award_amount, submitted_at

    async def _award_for_attempt(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        quiz_id: uuid.UUID,
        attempt_id: uuid.UUID
    ) -> int:
        # Idempotency: if quiz_award exists for (user,quiz,attempt), return amount
        existing_award = await session.get(QuizAward, (user_id, quiz_id, attempt_id))
        if existing_award:
            return existing_award.amount

        # Gather correct answers for this attempt
        answers_stmt = select(AttemptAnswer).where(
            AttemptAnswer.attempt_id == attempt_id,
            AttemptAnswer.is_correct == True  # noqa: E712
        )
        correct_answers = (await session.execute(answers_stmt)).scalars().all()

        newly_correct = 0
        for ans in correct_answers:
            # Try to insert into user_question_state; if exists, skip
            existing_state = await session.get(UserQuestionState, (user_id, ans.question_id))
            if not existing_state:
                state = UserQuestionState(
                    user_id=user_id,
                    question_id=ans.question_id,
                    first_correct_attempt_id=attempt_id,
                )
                session.add(state)
                newly_correct += 1
        await session.flush()

        amount = newly_correct * 100

        # Record award even if zero to maintain idempotency
        award = QuizAward(user_id=user_id, quiz_id=quiz_id, attempt_id=attempt_id, amount=amount)
        session.add(award)

        if amount > 0:
            # Upsert balance account and insert ledger entry
            account = await session.get(BalanceAccount, user_id)
            if not account:
                account = BalanceAccount(user_id=user_id, current_balance=0)
                session.add(account)
                await session.flush()
            account.current_balance = (account.current_balance or 0) + amount
            ledger = BalanceLedger(user_id=user_id, delta=amount, reason=f"quiz_award:{quiz_id}:{attempt_id}")
            session.add(ledger)

        await session.flush()
        return amount


attempts_service = AttemptsService() 