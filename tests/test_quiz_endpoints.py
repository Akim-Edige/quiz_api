import asyncio
import os
import uuid
import pytest
import httpx

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


@pytest.mark.asyncio
async def test_get_quiz_list():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        r = await client.get("/api/quizzes", params={"page": 1, "size": 20, "locale": "en"})
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and isinstance(data["items"], list)
        assert "meta" in data


@pytest.mark.asyncio
async def test_get_quiz_by_id_and_slug():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
        # get list, pick first quiz id and slug via stats endpoint if empty
        r = await client.get("/api/quizzes", params={"page": 1, "size": 1, "locale": "en"})
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert items, "No quizzes found; ensure seeding ran"
        quiz_id = items[0]["id"]
        # by id
        q = await client.get(f"/api/quizzes/{quiz_id}", params={"locale": "en"})
        assert q.status_code == 200
        body = q.json()
        assert body["id"] == quiz_id
        assert "questions" in body
        # by slug (uses seed slug)
        slug = body["slug"]
        qs = await client.get(f"/api/quizzes/slug/{slug}", params={"locale": "en"})
        assert qs.status_code == 200
        body2 = qs.json()
        assert body2["id"] == quiz_id


@pytest.mark.asyncio
async def test_quiz_stats():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        r = await client.get("/api/quizzes", params={"page": 1, "size": 1, "locale": "en"})
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert items, "No quizzes found; ensure seeding ran"
        quiz_id = items[0]["id"]
        s = await client.get(f"/api/quizzes/{quiz_id}/stats")
        assert s.status_code == 200
        data = s.json()
        assert data["quiz_id"] == quiz_id
        assert "question_stats" in data 