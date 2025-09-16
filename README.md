# Finelo Quiz API

Production-ready Quiz API service with multi-language support, optimized for read-heavy workloads with caching and CDN integration.

## Quick Start (Docker)

Prerequisites:
- Docker + Docker Compose

One command to build and run locally (auto-migrations, S3 bootstrap, and seeding included):

```bash
docker compose up --build -d
```

Then visit:
- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

This will automatically:
- Wait for Postgres
- Run Alembic migrations
- Initialize LocalStack S3 bucket `finelo-quiz-assets` with CORS and upload flag images
- Seed the database with a sample quiz including matching question with flag images

## Services
- App (FastAPI): http://localhost:8000
- Postgres: localhost:5432
- Redis: localhost:6379
- LocalStack (S3): http://localhost:4566

## Database UML schema

![plantuml (1)](https://github.com/user-attachments/assets/e560cc52-1257-4869-b3b7-3d57f1e30c44)

## Environment variables
The app is configured via `app/config.py` (Pydantic settings) and Compose envs.

Key variables (with local defaults in `docker-compose.yml`):
- `DATABASE_URL`: asyncpg DSN to Postgres
- `DATABASE_READ_REPLICA_URL`: optional read-replica DSN; if missing/placeholder, primary is used
- `REDIS_URL`: Redis connection URL
- `LOG_LEVEL`: INFO/DEBUG/etc
- `AWS_REGION`: us-east-1
- `S3_BUCKET`: finelo-quiz-assets
- `AWS_ENDPOINT_URL`: http://localstack:4566 (for LocalStack)
- `CDN_DOMAIN`: when set, asset URLs will use this domain. In local it’s set to `http://localhost:4566/finelo-quiz-assets/`
- `INIT_S3_ON_START`: 1/0 to run S3 bootstrap script at container start
- `SEED_ON_START`: 1/0 to run seeding at container start

## Logging
- Centralized logging with level from `LOG_LEVEL`
- HTTP request logging middleware included
- Key logs in cache, services and S3 utils for visibility (cache hits/misses, evaluation, URL resolution)

## Endpoints
All endpoints are prefixed with `/api`.

### Quizzes

- GET `/api/quizzes/{quiz_id}`
  - Description: Get complete quiz content for a locale (cached).
  - Query params:
    - `locale` (string, default `en`): language code.
  - Response: `LocalizedQuizResponse` with questions.
```bash
curl "http://localhost:8000/api/quizzes/<quiz_id>?locale=en"
```

- GET `/api/quizzes/slug/{slug}`
  - Description: Get quiz content by slug. Same payload as the ID-based endpoint.
  - Query params: `locale` (string, default `en`)
```bash
curl "http://localhost:8000/api/quizzes/slug/general-knowledge-quiz?locale=en"
```

- GET `/api/quizzes/{quiz_id}/stats`
  - Description: Get quiz statistics for comparison features (cached briefly).
  - Response: `QuizStatsResponse` with per-question correctness and averages.
```bash
curl "http://localhost:8000/api/quizzes/<quiz_id>/stats"
```

- GET `/api/quizzes`
  - Description: List published quizzes with pagination and localized titles.
  - Query params:
    - `page` (int, default 1)
    - `size` (int, default 20, max 100)
    - `locale` (string, default `en`)
```bash
curl "http://localhost:8000/api/quizzes?page=1&size=20&locale=en"
```

### Attempts
All attempts endpoints require the header `x-user-id: <UUID>`.

- POST `/api/attempts`
  - Description: Create a new attempt for a quiz.
  - Headers: `x-user-id` (UUID)
  - Body: `CreateAttemptRequest`
    - `quiz_id` (UUID)
    - `locale` (optional, default `en`)
  - Response: `CreateAttemptResponse` with `attempt_id`, `started_at`.
```bash
curl -X POST http://localhost:8000/api/attempts \
  -H 'Content-Type: application/json' \
  -H 'x-user-id: 00000000-0000-0000-0000-000000000001' \
  -d '{"quiz_id":"<quiz_uuid>","locale":"en"}'
```

- POST `/api/attempts/{attempt_id}/answers`
  - Description: Submit an answer for a question within an attempt. Returns correctness and question stats.
  - Headers: `x-user-id` (UUID)
  - Body: `SubmitAnswerRequest`
    - For single/multi choice: `{ "question_id": "...", "answer": { "option_ids": ["..."] } }`
    - For fill gap: `{ "question_id": "...", "answer": { "gaps": { "<gap_id>": "value" } } }`
    - For matching: `{ "question_id": "...", "answer": { "pairs": [ {"left_id": "...", "right_id": "..."}, ... ] } }`
  - Response: `SubmitAnswerWithStatsResponse`
```bash
curl -X POST http://localhost:8000/api/attempts/<attempt_id>/answers \
  -H 'Content-Type: application/json' \
  -H 'x-user-id: 00000000-0000-0000-0000-000000000001' \
  -d '{"question_id":"<question_uuid>","answer":{"pairs":[{"left_id":"<L_id>","right_id":"<R_id>"}]}}'
```

- POST `/api/attempts/{attempt_id}/submit`
  - Description: Submit the attempt; computes final score, awards, and updates stats.
  - Headers: `x-user-id` (UUID)
  - Response: `SubmitAttemptResponse` with totals, score, award, average score.
```bash
curl -X POST http://localhost:8000/api/attempts/<attempt_id>/submit \
  -H 'x-user-id: 00000000-0000-0000-0000-000000000001'
```

- GET `/api/attempts/me`
  - Description: List my attempts with pagination and summary info.
  - Headers: `x-user-id` (UUID)
  - Query params: `page`, `size`
  - Response: `PaginatedAttemptsResponse`
```bash
curl "http://localhost:8000/api/attempts/me?page=1&size=20" -H 'x-user-id: 00000000-0000-0000-0000-000000000001'
```

- GET `/api/attempts/me/balance`
  - Description: Get my total award balance and recent ledger entries.
  - Headers: `x-user-id` (UUID)
  - Response: `BalanceResponse`
```bash
curl http://localhost:8000/api/attempts/me/balance -H 'x-user-id: 00000000-0000-0000-0000-000000000001'
```

## Development
Rebuild after code changes:
```bash
docker compose up --build -d app
```
Tail logs:
```bash
docker compose logs -f app
```

Re-run S3 bootstrap (if needed):
```bash
docker compose exec app python scripts/bootstrap_s3_local.py
```

Re-run seeding:
```bash
docker compose exec app python seed_runner.py
```

## Notes
- Local assets are uploaded to LocalStack S3 and served via the configured `CDN_DOMAIN`.
- In production, point `CDN_DOMAIN` to your CDN (e.g., CloudFront) with S3 as origin; the API will return CDN URLs.
- The matching question uses opaque IDs and returns left image items (flags) and right text items (capitals).

## Tests
Run the basic validation test locally (optional):
```bash
python test_basic.py
``` 
