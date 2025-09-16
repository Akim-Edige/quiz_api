from typing import Optional, Tuple
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import logging

from app.models import (
    Attempt, AttemptAnswer, Quiz, Question, FillGap,
    UserQuestionState, QuizAward, BalanceAccount, BalanceLedger,
    QuestionStats, QuizStats
)
from app.services.quiz_service import evaluate_answer
from app.cache import cache
from sqlalchemy import func, desc

logger = logging.getLogger("app.attempts_service")


class AttemptsService:
    async def create_attempt(self, session: AsyncSession, user_id: uuid.UUID, quiz_id: uuid.UUID, locale: Optional[str]) -> Attempt:
        # Ensure quiz exists
        quiz = await session.get(Quiz, quiz_id)
        if not quiz:
            raise ValueError("Quiz not found")
        attempt = Attempt(user_id=user_id, quiz_id=quiz_id, locale=locale)
        session.add(attempt)
        await session.flush()
        logger.info("Created attempt id=%s user=%s quiz=%s", str(attempt.id), str(user_id), str(quiz_id))
        return attempt

    async def list_attempts(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        size: int = 20
    ) -> tuple[list[Attempt], int, dict[uuid.UUID, int], dict[uuid.UUID, int], dict[uuid.UUID, int]]:
        offset = (page - 1) * size
        # Order: most recent submitted_at; if NULL use started_at
        order_expr = desc(func.coalesce(Attempt.submitted_at, Attempt.started_at))
        # Count
        count_stmt = select(func.count()).select_from(Attempt).where(Attempt.user_id == user_id)
        total = (await session.execute(count_stmt)).scalar_one()
        # Page
        stmt = (
            select(Attempt)
            .where(Attempt.user_id == user_id)
            .order_by(order_expr)
            .offset(offset)
            .limit(size)
        )
        items = (await session.execute(stmt)).scalars().all()
        if not items:
            return items, total, {}, {}, {}

        attempt_ids = [a.id for a in items]
        quiz_ids = list({a.quiz_id for a in items})

        # Correct counts per attempt
        ans_stmt = (
            select(AttemptAnswer.attempt_id, func.count().filter(AttemptAnswer.is_correct.is_(True)).label("correct"))
            .where(AttemptAnswer.attempt_id.in_(attempt_ids))
            .group_by(AttemptAnswer.attempt_id)
        )
        ans_rows = (await session.execute(ans_stmt)).all()
        correct_by_attempt = {row[0]: int(row[1] or 0) for row in ans_rows}

        # Total questions per quiz
        q_stmt = (
            select(Question.quiz_id, func.count().label("total"))
            .where(Question.quiz_id.in_(quiz_ids))
            .group_by(Question.quiz_id)
        )
        q_rows = (await session.execute(q_stmt)).all()
        total_by_quiz = {row[0]: int(row[1]) for row in q_rows}

        # Award amount per attempt
        award_stmt = (
            select(QuizAward.attempt_id, QuizAward.amount)
            .where(QuizAward.user_id == user_id, QuizAward.attempt_id.in_(attempt_ids))
        )
        award_rows = (await session.execute(award_stmt)).all()
        award_by_attempt = {row[0]: int(row[1] or 0) for row in award_rows}

        # Average score per quiz (derived like in submit/stats)
        from sqlalchemy import case
        avg_by_quiz: dict[uuid.UUID, float] = {}
        if quiz_ids:
            # total_submissions per quiz
            subs_rows = (await session.execute(
                select(Attempt.quiz_id, func.count().label("subs"))
                .where(Attempt.quiz_id.in_(quiz_ids))
                .where(Attempt.submitted_at.is_not(None))
                .group_by(Attempt.quiz_id)
            )).all()
            subs_by_quiz = {row[0]: int(row[1]) for row in subs_rows}

            # total questions per quiz already computed: total_by_quiz

            # correct totals per quiz
            corr_rows = (await session.execute(
                select(Attempt.quiz_id, func.coalesce(func.sum(case((AttemptAnswer.is_correct.is_(True), 1), else_=0)), 0))
                .select_from(Attempt)
                .join(AttemptAnswer, AttemptAnswer.attempt_id == Attempt.id, isouter=True)
                .where(Attempt.quiz_id.in_(quiz_ids))
                .where(Attempt.submitted_at.is_not(None))
                .group_by(Attempt.quiz_id)
            )).all()
            corr_by_quiz = {row[0]: int(row[1] or 0) for row in corr_rows}

            for qid in quiz_ids:
                subs = subs_by_quiz.get(qid, 0)
                tq = total_by_quiz.get(qid, 0)
                corr = corr_by_quiz.get(qid, 0)
                avg = (corr / (subs * tq) * 100.0) if subs > 0 and tq > 0 else 0.0
                avg_by_quiz[qid] = float(round(avg, 2))

        return items, total, correct_by_attempt, total_by_quiz, award_by_attempt

    async def submit_answer(
        self,
        session: AsyncSession,
        attempt_id: uuid.UUID,
        question_id: uuid.UUID,
        answer_payload: dict
    ) -> tuple[AttemptAnswer, int, int, float, float]:
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
        logger.debug(
            "Evaluated answer attempt=%s question=%s qtype=%s correct=%s",
            str(attempt_id), str(question_id), question.qtype, is_correct,
        )

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
            ans_obj = existing
            logger.info("Updated answer id=%s attempt=%s correct=%s", str(ans_obj.id), str(attempt_id), is_correct)
        else:
            ans_obj = AttemptAnswer(
                attempt_id=attempt_id,
                question_id=question_id,
                answer=answer_payload,
                is_correct=is_correct,
            )
            session.add(ans_obj)
            await session.flush()
            logger.info("Created answer id=%s attempt=%s correct=%s", str(ans_obj.id), str(attempt_id), is_correct)

        # Compute per-question stats for user feedback
        qs = await session.get(QuestionStats, question_id)
        if qs:
            total_attempts = int(qs.total_attempts or 0)
            total_correct = int(qs.total_correct or 0)
            correctness_rate = round((total_correct / total_attempts * 100) if total_attempts > 0 else 0.0, 2)
            # Better than percent: if correct, user is better than (100 - correctness_rate) percent; if wrong, 0
            better_than = round(100.0 - correctness_rate, 2) if is_correct else 0.0
        else:
            total_attempts = 0
            total_correct = 0
            correctness_rate = 0.0
            better_than = 0.0

        return ans_obj, total_attempts, total_correct, correctness_rate, better_than

    async def submit_attempt(self, session: AsyncSession, attempt_id: uuid.UUID) -> Tuple[int, int, int, int, datetime]:
        # Mark submitted and compute score; perform awarding
        attempt = await session.get(Attempt, attempt_id)
        if not attempt:
            raise ValueError("Attempt not found")
        already_submitted = attempt.submitted_at is not None
        if already_submitted:
            # Per requirements, do not allow resubmission
            raise ValueError("Attempt already submitted")
        else:
            attempt.submitted_at = datetime.utcnow()
            await session.flush()
            submitted_at = attempt.submitted_at

        # Load answers
        answers_stmt = select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt_id)
        ans_list = (await session.execute(answers_stmt)).scalars().all()

        # Recompute correctness at submission time to ensure no partial credit for matching
        if ans_list:
            qids = [a.question_id for a in ans_list]
            from app.models import Question, FillGap, ChoiceOption, MatchingPair
            q_stmt = (
                select(Question)
                .options(
                    selectinload(Question.choice_options),
                    selectinload(Question.fill_gaps).selectinload(FillGap.answers),
                    selectinload(Question.matching_pairs),
                )
                .where(Question.id.in_(qids))
            )
            q_rows = (await session.execute(q_stmt)).scalars().all()
            by_qid = {q.id: q for q in q_rows}
            for a in ans_list:
                q = by_qid.get(a.question_id)
                if q is None:
                    a.is_correct = False
                else:
                    # Use strict evaluation for matching when scoring at submission
                    from app.models import QuestionType
                    from app.services.quiz_service import evaluate_matching_strict, evaluate_fill_gap, evaluate_single_or_multi_choice
                    if q.qtype in [QuestionType.SINGLE_CHOICE, QuestionType.MULTI_CHOICE]:
                        a.is_correct = await evaluate_single_or_multi_choice(q, a.answer.get("option_ids", []))
                    elif q.qtype == QuestionType.FILL_GAP:
                        a.is_correct = await evaluate_fill_gap(q, a.answer.get("gaps", {}))
                    elif q.qtype == QuestionType.MATCHING:
                        a.is_correct = await evaluate_matching_strict(q, a.answer.get("pairs", []))
                    else:
                        a.is_correct = False
            await session.flush()

        total_answered = len(ans_list)
        total_correct = sum(1 for a in ans_list if a.is_correct)
        # Compute total number of questions in this quiz to derive percentage score
        total_questions_stmt = select(func.count()).select_from(Question).where(Question.quiz_id == attempt.quiz_id)
        total_questions = (await session.execute(total_questions_stmt)).scalar_one() or 0
        # Avoid division by zero; if quiz has zero questions, score is 0
        score = int(round((total_correct / total_questions) * 100)) if total_questions > 0 else 0
        logger.info(
            "Submitted attempt id=%s total_answered=%s total_correct=%s score=%s",
            str(attempt_id), total_answered, total_correct, score,
        )

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
            # naive rolling average of percentage scores
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

        # Average and relative performance
        # Derive average score from submitted attempts and correct answers
        # total_submissions
        total_submissions = (await session.execute(
            select(func.count()).select_from(Attempt)
            .where(Attempt.quiz_id == attempt.quiz_id)
            .where(Attempt.submitted_at.is_not(None))
        )).scalar_one() or 0
        # total questions
        total_questions_stmt = select(func.count()).select_from(Question).where(Question.quiz_id == attempt.quiz_id)
        total_questions_final = (await session.execute(total_questions_stmt)).scalar_one() or 0
        # sum of correct answers across submitted attempts
        from sqlalchemy import case
        correct_total = (await session.execute(
            select(func.coalesce(func.sum(case((AttemptAnswer.is_correct.is_(True), 1), else_=0)), 0))
            .select_from(AttemptAnswer)
            .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
            .where(Attempt.quiz_id == attempt.quiz_id)
            .where(Attempt.submitted_at.is_not(None))
        )).scalar_one() or 0
        average_score = 0.0
        if total_submissions > 0 and total_questions_final > 0:
            average_score = (correct_total / (total_submissions * total_questions_final)) * 100.0

        # Sync quiz_stats to derived values
        qstats_row = await session.get(QuizStats, attempt.quiz_id)
        if not qstats_row:
            qstats_row = QuizStats(quiz_id=attempt.quiz_id, total_submissions=0, avg_score=0)
            session.add(qstats_row)
            await session.flush()
        qstats_row.total_submissions = total_submissions
        qstats_row.avg_score = average_score

        better_than_avg = None
        if score > average_score:
            # absolute difference in percentage points
            better_than_avg = round(score - float(average_score), 2)

        logger.info(
            "Attempt finalized id=%s award=%s average_score=%.2f better_than_delta=%s",
            str(attempt_id), award_amount, float(round(average_score, 2)), better_than_avg,
        )
        return total_answered, total_correct, score, award_amount, submitted_at, float(round(average_score, 2)), better_than_avg

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
            AttemptAnswer.is_correct == True
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
        logger.info("Award computed user=%s quiz=%s attempt=%s amount=%s", str(user_id), str(quiz_id), str(attempt_id), amount)
        return amount


attempts_service = AttemptsService() 