import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import select, and_, func
import logging

from app.models import (
    Quiz, QuizI18n, Question, QuestionI18n, 
    ChoiceOption, ChoiceOptionI18n, FillGap, FillGapAnswer,
    MatchingPair, MediaAsset, MediaAssetI18n, QuestionStats, QuizStats,
    QuestionType, SideKind, QuizStatus
)
from app.schemas import LocalizedQuizResponse, LocalizedQuestionResponse, QuizStatsResponse
from app.cache import cache
from app.s3_utils import s3_service
from app.config import settings

logger = logging.getLogger("app.quiz_service")


class QuizService:
    
    async def get_quiz_by_id(
        self, 
        session: AsyncSession, 
        quiz_id: uuid.UUID, 
        locale: str = "en"
    ) -> Optional[LocalizedQuizResponse]:
        """
        Get quiz with all content optimized for a specific locale.
        Uses cache for read optimization.
        """
        quiz_id_str = str(quiz_id)
        
        # Try cache first
        cached_quiz = await cache.get_cached_quiz(quiz_id_str, locale)
        if cached_quiz:
            logger.debug("Quiz cache hit quiz_id=%s locale=%s", quiz_id_str, locale)
            return LocalizedQuizResponse(**cached_quiz)
        logger.debug("Quiz cache miss quiz_id=%s locale=%s", quiz_id_str, locale)
        
        # Fetch from database with optimized queries
        quiz_data = await self._fetch_quiz_from_db(session, quiz_id, locale)
        if not quiz_data:
            logger.warning("Quiz not found quiz_id=%s", quiz_id_str)
            return None
        
        # Cache the result
        await cache.cache_quiz(quiz_id_str, locale, quiz_data.model_dump())
        
        return quiz_data
    
    async def get_quiz_by_slug(
        self,
        session: AsyncSession,
        slug: str,
        locale: str = "en"
    ) -> Optional[LocalizedQuizResponse]:
        """Resolve quiz by slug, then reuse the ID-based flow (with caching)."""
        row = await session.execute(select(Quiz.id).where(Quiz.slug == slug))
        quiz_id = row.scalar_one_or_none()
        if not quiz_id:
            logger.warning("Quiz not found slug=%s", slug)
            return None
        return await self.get_quiz_by_id(session, quiz_id, locale)
    
    async def _fetch_quiz_from_db(
        self, 
        session: AsyncSession, 
        quiz_id: uuid.UUID, 
        locale: str
    ) -> Optional[LocalizedQuizResponse]:
        """Fetch quiz from database with all related data"""
        
        # Query quiz with i18n
        quiz_query = (
            select(Quiz)
            .options(selectinload(Quiz.i18n))
            .where(Quiz.id == quiz_id)
        )
        quiz_result = await session.execute(quiz_query)
        quiz = quiz_result.scalar_one_or_none()
        
        if not quiz:
            return None
        
        # Get localized quiz info (fallback to 'en' if locale not found)
        quiz_i18n = self._get_localized_content(quiz.i18n, locale)
        if not quiz_i18n:
            return None
        
        # Fetch questions with all related data
        questions_query = (
            select(Question)
            .options(
                selectinload(Question.i18n),
                selectinload(Question.choice_options).selectinload(ChoiceOption.i18n),
                selectinload(Question.fill_gaps).selectinload(FillGap.answers),
                selectinload(Question.matching_pairs)
                    .selectinload(MatchingPair.left_asset)
                    .selectinload(MediaAsset.i18n),
                selectinload(Question.matching_pairs)
                    .selectinload(MatchingPair.right_asset)
                    .selectinload(MediaAsset.i18n),
            )
            .where(Question.quiz_id == quiz_id)
            .order_by(Question.display_order)
        )
        questions_result = await session.execute(questions_query)
        questions = questions_result.scalars().all()
        logger.debug("Fetched %s questions for quiz_id=%s", len(questions), str(quiz_id))
        
        # Build localized questions
        localized_questions = []
        for question in questions:
            localized_question = await self._build_localized_question(question, locale)
            if localized_question:
                localized_questions.append(localized_question)
        
        return LocalizedQuizResponse(
            id=quiz.id,
            slug=quiz.slug,
            status=quiz.status,
            title=quiz_i18n.title,
            description=quiz_i18n.description,
            locale=locale,
            questions=localized_questions,
            created_at=quiz.created_at
        )
    
    async def _build_localized_question(
        self, 
        question: Question, 
        locale: str
    ) -> Optional[LocalizedQuestionResponse]:
        """Build localized question response with type-specific content"""
        
        # Get localized question content
        question_i18n = self._get_localized_content(question.i18n, locale)
        if not question_i18n:
            return None
        
        # Build type-specific content
        choice_options = None
        fill_gaps = None
        matching_pairs = None
        
        if question.qtype in [QuestionType.SINGLE_CHOICE, QuestionType.MULTI_CHOICE]:
            choice_options = self._build_choice_options(question.choice_options, locale)
        
        elif question.qtype == QuestionType.FILL_GAP:
            fill_gaps = self._build_fill_gaps(question.fill_gaps)
        
        elif question.qtype == QuestionType.MATCHING:
            matching_pairs = await self._build_matching_pairs(question.matching_pairs, locale)
        
        return LocalizedQuestionResponse(
            id=question.id,
            qtype=question.qtype,
            display_order=question.display_order,
            points=question.points,
            prompt=question_i18n.prompt,
            explanation=question_i18n.explanation,
            meta=question.meta,
            choice_options=choice_options,
            fill_gaps=fill_gaps,
            matching_pairs=matching_pairs
        )
    
    def _build_choice_options(self, choice_options: List[ChoiceOption], locale: str) -> List[Dict[str, Any]]:
        """Build choice options for single/multi choice questions"""
        options = []
        for option in sorted(choice_options, key=lambda x: x.display_order):
            option_i18n = self._get_localized_content(option.i18n, locale)
            if option_i18n:
                options.append({
                    "id": str(option.id),
                    "label": option_i18n.label,
                    "display_order": option.display_order
                    # Note: is_correct is intentionally excluded from response
                })
        return options
    
    def _build_fill_gaps(self, fill_gaps: List[FillGap]) -> List[Dict[str, Any]]:
        """Build fill gaps for fill-in-the-gap questions"""
        gaps = []
        for gap in sorted(fill_gaps, key=lambda x: x.gap_index):
            gaps.append({
                "id": str(gap.id),
                "gap_index": gap.gap_index,
                "case_sensitive": gap.case_sensitive
                # Note: accepted answers are intentionally excluded from response
            })
        return gaps
    
    async def _build_matching_pairs(self, matching_pairs: List[MatchingPair], locale: str) -> Dict[str, List[Dict[str, Any]]]:
        """Build matching items for matching questions without revealing correct pairs.
        Returns a dict with separate left and right item lists, each item having an opaque side-specific id.
        """
        left_items: List[Dict[str, Any]] = []
        right_items: List[Dict[str, Any]] = []
        for pair in matching_pairs:
            left_content = await self._build_side_content(
                pair.left_kind, pair.left_text, pair.left_asset, locale
            )
            right_content = await self._build_side_content(
                pair.right_kind, pair.right_text, pair.right_asset, locale
            )

            left_items.append({
                "id": make_matching_side_id(pair.id, "L"),
                **left_content
            })
            right_items.append({
                "id": make_matching_side_id(pair.id, "R"),
                **right_content
            })
        logger.debug("Built matching pairs left=%s right=%s", len(left_items), len(right_items))
        return {"left_items": left_items, "right_items": right_items}
    
    async def _build_side_content(
        self, 
        side_kind: SideKind, 
        text: Optional[str], 
        asset: Optional[MediaAsset], 
        locale: str
    ) -> Dict[str, Any]:
        """Build content for one side of a matching pair"""
        if side_kind == SideKind.TEXT:
            return {
                "type": "text",
                "content": text
            }
        else:  # IMAGE
            if asset:
                asset_i18n = self._get_localized_content(asset.i18n, locale)
                url = s3_service.get_asset_url(asset.s3_bucket, asset.s3_key)
                logger.debug("Resolved asset URL key=%s url=%s", asset.s3_key, url)
                return {
                    "type": "image",
                    "url": url,
                    "alt_text": asset_i18n.alt_text if asset_i18n else None,
                    "width": asset.width,
                    "height": asset.height,
                    "mime": asset.mime
                }
            return {
                "type": "image",
                "url": None,
                "alt_text": None
            }
    
    def _get_localized_content(self, i18n_list: List, locale: str):
        """Get localized content with fallback to 'en'"""
        # Try exact locale match
        for item in i18n_list:
            if item.locale == locale:
                return item
        
        # Fallback to English
        for item in i18n_list:
            if item.locale == "en":
                return item
        
        # Return first available if no English
        return i18n_list[0] if i18n_list else None
    
    async def get_quiz_stats(
        self, 
        session: AsyncSession, 
        quiz_id: uuid.UUID
    ) -> Optional[QuizStatsResponse]:
        """Get quiz statistics with caching
        Computes average score as percentage of total quiz questions over submitted attempts,
        and per-question correctness from attempt answers to ensure consistency.
        """
        quiz_id_str = str(quiz_id)
        
        # Try cache first
        cached_stats = await cache.get_cached_quiz_stats(quiz_id_str)
        if cached_stats:
            logger.debug("Quiz stats cache hit quiz_id=%s", quiz_id_str)
            return QuizStatsResponse(**cached_stats)
        logger.debug("Quiz stats cache miss quiz_id=%s", quiz_id_str)
        
        # Verify quiz exists
        quiz_exists = await session.execute(select(Quiz.id).where(Quiz.id == quiz_id))
        if not quiz_exists.scalar_one_or_none():
            return None
        
        # Total questions for this quiz
        total_questions = (await session.execute(
            select(func.count()).select_from(Question).where(Question.quiz_id == quiz_id)
        )).scalar_one() or 0
        
        # Submitted attempts count
        total_submissions = (await session.execute(
            select(func.count()).select_from(__import__('app.models').models.Attempt)
            .where(__import__('app.models').models.Attempt.quiz_id == quiz_id)
            .where(__import__('app.models').models.Attempt.submitted_at.is_not(None))
        )).scalar_one() or 0
        
        # Total attempts started (including unsubmitted)
        total_started = (await session.execute(
            select(func.count()).select_from(__import__('app.models').models.Attempt)
            .where(__import__('app.models').models.Attempt.quiz_id == quiz_id)
        )).scalar_one() or 0
        completion_rate = float(round(((total_submissions / total_started) * 100.0) if total_started > 0 else 0.0, 2))
        total_unsubmitted_attempts = max(total_started - total_submissions, 0)
        
        # Average score across attempts as percent of total questions
        # Get per-attempt correct counts (including 0 for attempts with no correct answers)
        Attempt = __import__('app.models').models.Attempt
        AttemptAnswer = __import__('app.models').models.AttemptAnswer
        from sqlalchemy import case
        per_attempt_correct = (await session.execute(
            select(
                Attempt.id,
                func.coalesce(
                    func.sum(case((AttemptAnswer.is_correct.is_(True), 1), else_=0)),
                    0
                ).label("correct_count")
            )
            .select_from(Attempt)
            .join(AttemptAnswer, AttemptAnswer.attempt_id == Attempt.id, isouter=True)
            .where(Attempt.quiz_id == quiz_id)
            .where(Attempt.submitted_at.is_not(None))
            .group_by(Attempt.id)
        )).all()
        
        if total_submissions > 0 and total_questions > 0:
            scores = [(row[1] or 0) / total_questions * 100.0 for row in per_attempt_correct]
            avg_score = sum(scores) / len(scores) if scores else 0.0
        else:
            avg_score = 0.0
        
        # Compute updated_at for quiz: prefer stored aggregate timestamp if present, else latest submitted_at
        quiz_stats_row = (await session.execute(select(QuizStats).where(QuizStats.quiz_id == quiz_id))).scalar_one_or_none()
        max_submit_ts = (await session.execute(
            select(func.max(Attempt.submitted_at))
            .where(Attempt.quiz_id == quiz_id)
            .where(Attempt.submitted_at.is_not(None))
        )).scalar_one_or_none()
        quiz_updated_at = quiz_stats_row.updated_at if quiz_stats_row and quiz_stats_row.updated_at else max_submit_ts
        
        # Per-question stats from answers on submitted attempts
        question_rows = (await session.execute(
            select(Question.id, Question.display_order).where(Question.quiz_id == quiz_id)
        )).all()
        question_ids = [row[0] for row in question_rows]
        id_to_order = {row[0]: int(row[1] or 0) for row in question_rows}
        first_question_id = min(question_ids, key=lambda q: id_to_order.get(q, 0)) if question_ids else None
        question_stats_list = []
        if question_ids:
            qa_counts = (await session.execute(
                select(AttemptAnswer.question_id,
                       func.count().label('total'),
                       func.count().filter(AttemptAnswer.is_correct.is_(True)).label('correct'))
                .select_from(AttemptAnswer)
                .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
                .where(Attempt.quiz_id == quiz_id)
                .where(Attempt.submitted_at.is_not(None))
                .where(AttemptAnswer.question_id.in_(question_ids))
                .group_by(AttemptAnswer.question_id)
            )).all()
            by_q = {row[0]: (int(row[1] or 0), int(row[2] or 0)) for row in qa_counts}
            # latest answered_at per question among submitted attempts
            latest_answered = (await session.execute(
                select(AttemptAnswer.question_id, func.max(AttemptAnswer.answered_at))
                .select_from(AttemptAnswer)
                .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
                .where(Attempt.quiz_id == quiz_id)
                .where(Attempt.submitted_at.is_not(None))
                .where(AttemptAnswer.question_id.in_(question_ids))
                .group_by(AttemptAnswer.question_id)
            )).all()
            latest_by_q = {row[0]: row[1] for row in latest_answered}
            # stored question stats updated_at (if any)
            stored_qstats = (await session.execute(
                select(QuestionStats.question_id, QuestionStats.updated_at)
                .where(QuestionStats.question_id.in_(question_ids))
            )).all()
            stored_updated_by_q = {row[0]: row[1] for row in stored_qstats}

            # Dropoff analysis for unsubmitted attempts: find their last answered question (or none)
            unsubmitted_attempt_ids = (await session.execute(
                select(Attempt.id)
                .where(Attempt.quiz_id == quiz_id)
                .where(Attempt.submitted_at.is_(None))
            )).scalars().all()
            dropoff_by_qid: dict[uuid.UUID, int] = {}
            total_unsubmitted = 0
            if unsubmitted_attempt_ids:
                total_unsubmitted = len(unsubmitted_attempt_ids)
                # Fetch all answers for these attempts
                ua_rows = (await session.execute(
                    select(AttemptAnswer.attempt_id, AttemptAnswer.question_id, AttemptAnswer.answered_at)
                    .where(AttemptAnswer.attempt_id.in_(unsubmitted_attempt_ids))
                )).all()
                # Group by attempt and pick the latest answer; break ties by highest display_order
                from collections import defaultdict
                by_attempt: dict[uuid.UUID, list[tuple[uuid.UUID, Any]]] = defaultdict(list)
                for aid, qid, ts in ua_rows:
                    by_attempt[aid].append((qid, ts))
                attempts_with_answers: set[uuid.UUID] = set()
                for aid, items in by_attempt.items():
                    if not items:
                        continue
                    attempts_with_answers.add(aid)
                    # Find max timestamp
                    max_ts = max(ts for (_, ts) in items if ts is not None)
                    # Candidates with max_ts
                    candidates = [qid for (qid, ts) in items if ts == max_ts and qid in id_to_order]
                    if not candidates:
                        continue
                    # Choose the candidate with highest display_order (latest in flow)
                    last_qid = max(candidates, key=lambda q: id_to_order.get(q, 0))
                    dropoff_by_qid[last_qid] = dropoff_by_qid.get(last_qid, 0) + 1
                # Attempts with zero answers count as dropping at the first question
                zero_answer_count = total_unsubmitted - len(attempts_with_answers)
                if zero_answer_count > 0 and first_question_id is not None:
                    dropoff_by_qid[first_question_id] = dropoff_by_qid.get(first_question_id, 0) + zero_answer_count

            for qid in question_ids:
                total = by_q.get(qid, (0, 0))[0]
                correct = by_q.get(qid, (0, 0))[1]
                rate = round((correct / total * 100.0) if total > 0 else 0.0, 2)
                q_updated = stored_updated_by_q.get(qid) or latest_by_q.get(qid)
                dropoff = None
                if total_unsubmitted and total_unsubmitted > 0:
                    dropoff = round((dropoff_by_qid.get(qid, 0) / total_unsubmitted) * 100.0, 2)
                question_stats_list.append({
                    "question_id": str(qid),
                    "total_attempts": total,
                    "total_correct": correct,
                    "correctness_rate": rate,
                    "updated_at": q_updated,
                    "dropoff_rate_unsubmitted_percent": dropoff
                })
        
        quiz_stats_data = QuizStatsResponse(
            quiz_id=quiz_id,
            total_submissions=total_submissions,
            avg_score=round(float(avg_score), 2),
            completion_rate=completion_rate,
            question_stats=question_stats_list,
            updated_at=quiz_updated_at,
            total_unsubmitted_attempts=total_unsubmitted_attempts
        )
        
        # Cache the result
        await cache.cache_quiz_stats(quiz_id_str, quiz_stats_data.model_dump())
        
        return quiz_stats_data
    
    async def list_quizzes(
        self, 
        session: AsyncSession, 
        page: int = 1, 
        size: int = 20,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """List quizzes with pagination"""
        offset = (page - 1) * size
        
        # Query for total count
        count_query = select(Quiz).where(Quiz.status == QuizStatus.PUBLISHED)
        count_result = await session.execute(count_query)
        total = len(count_result.scalars().all())
        
        # Query for quizzes with i18n
        quizzes_query = (
            select(Quiz)
            .options(selectinload(Quiz.i18n))
            .where(Quiz.status == QuizStatus.PUBLISHED)
            .order_by(Quiz.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        quizzes_result = await session.execute(quizzes_query)
        quizzes = quizzes_result.scalars().all()
        
        # Build response with localized titles
        quiz_items = []
        for quiz in quizzes:
            quiz_i18n = self._get_localized_content(quiz.i18n, locale)
            if quiz_i18n:
                quiz_items.append({
                    "id": str(quiz.id),
                    "slug": quiz.slug,
                    "status": quiz.status,
                    "title": quiz_i18n.title,
                    "description": quiz_i18n.description,
                    "created_at": quiz.created_at
                })
        
        pages = (total + size - 1) // size
        
        return {
            "items": quiz_items,
            "meta": {
                "total": total,
                "page": page,
                "size": size,
                "pages": pages
            }
        }


# Service instance
quiz_service = QuizService()


# === Evaluation helpers (pure functions) ===

async def evaluate_single_or_multi_choice(question: Question, submitted_option_ids: list[str]) -> bool:
    correct_ids = {str(opt.id) for opt in question.choice_options if opt.is_correct}
    submitted_ids = set(submitted_option_ids or [])
    if question.qtype == QuestionType.SINGLE_CHOICE:
        return len(submitted_ids) == 1 and submitted_ids.issubset(correct_ids)
    # MULTI_CHOICE: must match exactly
    return submitted_ids == correct_ids


def normalize_text(value: str) -> str:
    return (value or "").strip()


async def evaluate_fill_gap(question: Question, submitted_values_by_gap: dict) -> bool:
    # submitted_values_by_gap: {gap_id: value}
    by_id = {str(g.id): g for g in question.fill_gaps}
    for gap_id, gap in by_id.items():
        answers = [a.accepted_value for a in gap.answers]
        submitted = submitted_values_by_gap.get(gap_id)
        if submitted is None:
            return False
        if gap.case_sensitive:
            ok = any(submitted == acc for acc in answers)
        else:
            s = normalize_text(submitted).lower()
            ok = any(normalize_text(acc).lower() == s for acc in answers)
        if not ok:
            return False
    return True


async def evaluate_matching(question: Question, submitted_pairs: list[dict]) -> bool:
    # submitted_pairs: list of {left_id: str, right_id: str}
    # Build mapping of valid left->right ids from DB
    valid_map: dict[str, str] = {}
    left_ids: set[str] = set()
    right_ids: set[str] = set()
    for p in question.matching_pairs:
        left_id = make_matching_side_id(p.id, "L")
        right_id = make_matching_side_id(p.id, "R")
        valid_map[left_id] = right_id
        left_ids.add(left_id)
        right_ids.add(right_id)

    # Normalize submitted
    seen_left: set[str] = set()
    seen_right: set[str] = set()
    if not submitted_pairs:
        return False

    for pair in submitted_pairs:
        l = pair.get("left_id")
        r = pair.get("right_id")
        if not l or not r:
            return False
        if l in seen_left or r in seen_right:
            return False
        # Left/right must be known opaque ids
        expected_r = valid_map.get(l)
        if expected_r is None:
            return False
        if r != expected_r:
            return False
        seen_left.add(l)
        seen_right.add(r)

    # All submitted pairs are correct so far
    return True


async def evaluate_matching_strict(question: Question, submitted_pairs: list[dict]) -> bool:
    """Strict evaluation for scoring: requires all pairs submitted and all correct."""
    # Build mapping of valid left->right ids
    valid_map: dict[str, str] = {}
    for p in question.matching_pairs:
        valid_map[make_matching_side_id(p.id, "L")] = make_matching_side_id(p.id, "R")

    if not submitted_pairs:
        return False
    if len(submitted_pairs) != len(question.matching_pairs):
        return False

    seen_left: set[str] = set()
    seen_right: set[str] = set()
    for pair in submitted_pairs:
        l = pair.get("left_id")
        r = pair.get("right_id")
        if not l or not r:
            return False
        if l in seen_left or r in seen_right:
            return False
        expected_r = valid_map.get(l)
        if expected_r is None or r != expected_r:
            return False
        seen_left.add(l)
        seen_right.add(r)
    return True


async def evaluate_answer(question: Question, normalized_answer: dict) -> bool:
    if question.qtype in [QuestionType.SINGLE_CHOICE, QuestionType.MULTI_CHOICE]:
        return await evaluate_single_or_multi_choice(question, normalized_answer.get("option_ids", []))
    if question.qtype == QuestionType.FILL_GAP:
        return await evaluate_fill_gap(question, normalized_answer.get("gaps", {}))
    if question.qtype == QuestionType.MATCHING:
        return await evaluate_matching(question, normalized_answer.get("pairs", []))
    return False 


def make_matching_side_id(pair_id: uuid.UUID, side_label: str) -> str:
    """Create an opaque, stable ID for a matching side that does not reveal the pair relation.
    Uses a salted UUID5 derived from (salt, pair_id, side_label).
    side_label should be either "L" or "R".
    """
    import uuid as _uuid
    seed = f"{settings.matching_side_id_salt}:{pair_id}:{side_label}"
    return _uuid.uuid5(_uuid.NAMESPACE_URL, seed).hex 