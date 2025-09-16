import os
import uuid
import pytest
import httpx

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
USER_ID = os.getenv("TEST_USER_ID", "00000000-0000-0000-0000-000000000001")


@pytest.mark.asyncio
async def test_attempts_flow():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        # pick a quiz
        r = await client.get("/api/quizzes", params={"page": 1, "size": 1, "locale": "en"})
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert items
        quiz_id = items[0]["id"]

        # create attempt
        c = await client.post(
            "/api/attempts",
            headers={"x-user-id": USER_ID},
            json={"quiz_id": quiz_id, "locale": "en"},
        )
        assert c.status_code == 200
        attempt_id = c.json()["attempt_id"]

        # fetch quiz to get matching opaque ids
        q = await client.get(f"/api/quizzes/{quiz_id}", params={"locale": "en"})
        assert q.status_code == 200
        quiz = q.json()
        matching = next((x for x in quiz["questions"] if x["qtype"] == "matching"), None)
        assert matching is not None
        left = matching["matching_pairs"]["left_items"][0]["id"]
        right = matching["matching_pairs"]["right_items"][1]["id"]

        # submit one (likely incorrect) pair to exercise endpoint
        s = await client.post(
            f"/api/attempts/{attempt_id}/answers",
            headers={"x-user-id": USER_ID},
            json={"question_id": matching["id"], "answer": {"pairs": [{"left_id": left, "right_id": right}]}}
        )
        assert s.status_code == 200
        ans = s.json()
        assert ans["attempt_id"] == attempt_id
        assert "question_stats" in ans

        # submit attempt
        sub = await client.post(
            f"/api/attempts/{attempt_id}/submit",
            headers={"x-user-id": USER_ID},
        )
        assert sub.status_code == 200
        summary = sub.json()
        assert summary["attempt_id"] == attempt_id
        assert "score" in summary

        # get balance
        b = await client.get("/api/attempts/me/balance", headers={"x-user-id": USER_ID})
        assert b.status_code == 200
        bal = b.json()
        assert bal["user_id"] == USER_ID

        # list attempts
        la = await client.get("/api/attempts/me", headers={"x-user-id": USER_ID}, params={"page": 1, "size": 10})
        assert la.status_code == 200
        data = la.json()
        assert "items" in data and isinstance(data["items"], list) 