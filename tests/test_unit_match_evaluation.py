import asyncio
import uuid
import pytest

from app.models import Question, QuestionType, MatchingPair, SideKind
from app.services.quiz_service import evaluate_matching, evaluate_matching_strict, make_matching_side_id


@pytest.mark.asyncio
async def test_evaluate_matching_correct_partial_and_strict():
    q = Question(id=uuid.uuid4(), quiz_id=uuid.uuid4(), qtype=QuestionType.MATCHING, display_order=1, points=100, meta={})
    # two pairs
    p1 = MatchingPair(id=uuid.uuid4(), question_id=q.id, left_kind=SideKind.TEXT, left_text="A", right_kind=SideKind.TEXT, right_text="1")
    p2 = MatchingPair(id=uuid.uuid4(), question_id=q.id, left_kind=SideKind.TEXT, left_text="B", right_kind=SideKind.TEXT, right_text="2")
    q.matching_pairs = [p1, p2]

    # Build correct ids
    l1 = make_matching_side_id(p1.id, "L"); r1 = make_matching_side_id(p1.id, "R")
    l2 = make_matching_side_id(p2.id, "L"); r2 = make_matching_side_id(p2.id, "R")

    # Partial subset correct should pass non-strict
    ok = await evaluate_matching(q, [{"left_id": l1, "right_id": r1}])
    assert ok is True

    # Strict requires both pairs
    strict_ok = await evaluate_matching_strict(q, [{"left_id": l1, "right_id": r1}])
    assert strict_ok is False

    strict_ok2 = await evaluate_matching_strict(q, [{"left_id": l1, "right_id": r1}, {"left_id": l2, "right_id": r2}])
    assert strict_ok2 is True


@pytest.mark.asyncio
async def test_evaluate_matching_invalid_ids():
    q = Question(id=uuid.uuid4(), quiz_id=uuid.uuid4(), qtype=QuestionType.MATCHING, display_order=1, points=100, meta={})
    p1 = MatchingPair(id=uuid.uuid4(), question_id=q.id, left_kind=SideKind.TEXT, left_text="A", right_kind=SideKind.TEXT, right_text="1")
    q.matching_pairs = [p1]

    # Random ids should fail
    ok = await evaluate_matching(q, [{"left_id": "deadbeef", "right_id": "deadbeef"}])
    assert ok is False 