# Finelo Quiz API

A production-ready, read-optimized quiz service built with FastAPI, supporting multi-language content, various question types (single/multi choice, fill-in-the-gap, image↔text matching), and designed for horizontal scalability.

## 🏗️ Architecture Overview

This implementation follows the production-minded design you provided:

- **Read-optimized**: Separate read/write paths with read replicas and Redis caching
- **Multi-language**: Full i18n support with fallbacks
- **Scalable**: Designed for 2M+ active users with caching and CDN integration
- **Question Types**: Single choice, multi-choice, fill-in-the-gap, and image↔text matching
- **Media Support**: S3 integration with CDN and presigned URLs

### Core Components

- **Quiz API**: Read-heavy service for quiz content delivery
- **PostgreSQL**: Primary database with read replicas
- **Redis**: Caching layer for quiz content and stats
- **S3 + CDN**: Media asset storage and delivery
- **FastAPI**: High-performance async web framework

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (recommended)

### Option 1: Docker Compose (Recommended)

```bash
# Clone and navigate to project
cd Zimran_assignment

# Copy environment configuration
cp .env.example .env

# Start all services
docker-compose up -d

# Run database migrations
docker-compose exec app alembic upgrade head

# The API will be available at http://localhost:8000
```

### Option 2: Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your database and Redis URLs

# Run database migrations
alembic upgrade head

# Start the application
uvicorn main:app --reload

# API available at http://localhost:8000
```

## 📊 Database Schema

The database implements your comprehensive PostgreSQL schema with:

- **Quiz Management**: `quiz`, `quiz_i18n` tables
- **Questions**: `question`, `question_i18n` with support for 4 question types
- **Choice Options**: `choice_option`, `choice_option_i18n`
- **Fill-in-the-Gap**: `fill_gap`, `fill_gap_answer`
- **Matching**: `matching_pair` with text/image support
- **Media Assets**: `media_asset`, `media_asset_i18n`
- **Statistics**: `question_stats`, `quiz_stats`

### Supported Question Types

1. **Single Choice**: One correct answer from multiple options
2. **Multi Choice**: Multiple correct answers from options
3. **Fill-in-the-Gap**: Text input with multiple accepted answers
4. **Matching**: Pair text/images (supports all combinations)

## 🔌 API Endpoints

### Quiz Content

```http
GET /api/quizzes/{quiz_id}?locale=en
```
Get complete quiz content optimized for a specific locale.

**Features:**
- Cached responses (1-hour TTL)
- Read replica queries
- CDN URLs for images
- Localized content with fallbacks

### Quiz Statistics

```http
GET /api/quizzes/{quiz_id}/stats
```
Get quiz performance statistics for "compare to others" features.

**Returns:**
- Overall submission stats
- Per-question correctness rates
- Data for percentile calculations

### Quiz Listing

```http
GET /api/quizzes?page=1&size=20&locale=en
```
Paginated list of published quizzes with localized metadata.

## 🎯 Read Optimization Strategy

### Caching Layer

- **Quiz Content**: Assembled blobs cached by `(quiz_id, locale)`
- **Statistics**: Question/quiz stats cached with 5-minute TTL
- **Cache Keys**: `quiz:{id}:{locale}`, `quiz:stats:{id}`

### Database Optimization

- **Read Replicas**: All GET requests use read replicas
- **Eager Loading**: Single queries with `selectinload` for related data
- **Indexes**: Optimized for quiz→questions→options traversal

### Media Assets

- **CDN Integration**: Public assets served via CDN
- **Presigned URLs**: Private assets get short-lived S3 URLs
- **Image Metadata**: Width, height, MIME type included

## 🌍 Multi-Language Support

### Supported Locales

- English (en) - Default/fallback
- Spanish (es)
- Portuguese (pt)
- German (de)
- Turkish (tr)
- French (fr)
- Italian (it)
- Filipino (fil)
- Japanese (ja)

### Fallback Strategy

1. Try exact locale match
2. Fallback to English (`en`)
3. Use first available if no English

## 📝 Example Quiz Response

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "slug": "general-knowledge-quiz",
  "title": "General Knowledge Quiz",
  "description": "Test your general knowledge",
  "locale": "en",
  "questions": [
    {
      "id": "789e4567-e89b-12d3-a456-426614174001",
      "qtype": "single_choice",
      "display_order": 1,
      "points": 100,
      "prompt": "What is the capital of France?",
      "explanation": "Paris is the capital and most populous city of France.",
      "choice_options": [
        {
          "id": "option1",
          "label": "London",
          "display_order": 1
        },
        {
          "id": "option2", 
          "label": "Paris",
          "display_order": 2
        }
      ]
    }
  ]
}
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Primary database connection | `postgresql+asyncpg://...` |
| `DATABASE_READ_REPLICA_URL` | Read replica connection | Same as primary |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` |
| `AWS_ACCESS_KEY_ID` | S3 access key | - |
| `AWS_SECRET_ACCESS_KEY` | S3 secret key | - |
| `S3_BUCKET` | S3 bucket for assets | `finelo-quiz-assets` |
| `CDN_DOMAIN` | CDN domain for assets | - |
| `QUIZ_CACHE_TTL` | Quiz cache TTL (seconds) | `3600` |
| `STATS_CACHE_TTL` | Stats cache TTL (seconds) | `300` |

## 🚀 Deployment

### Production Checklist

- [ ] Configure read replicas
- [ ] Set up Redis cluster
- [ ] Configure S3 bucket and CDN
- [ ] Set up monitoring and logging
- [ ] Configure CORS for your frontend domain
- [ ] Set appropriate cache TTLs
- [ ] Enable connection pooling

### Health Checks

```http
GET /health
```

Returns service status including cache and database connectivity.

## 🧪 Testing

The API includes comprehensive HTTP tests in `test_main.http`:

```http
### Get quiz content
GET http://127.0.0.1:8000/api/quizzes/{quiz_id}?locale=en

### Get quiz statistics  
GET http://127.0.0.1:8000/api/quizzes/{quiz_id}/stats

### List quizzes
GET http://127.0.0.1:8000/api/quizzes?page=1&size=10&locale=en
```

## 📈 Performance Targets

Based on your 2M+ active users requirement:

- **Read Latency**: P95 < 120ms (with cache)
- **Cache Hit Rate**: >90% for quiz content
- **Database Connections**: Pooled with 20-30 connections
- **Memory Usage**: ~500MB per service instance

## 🔮 Future Extensions

This foundation supports your complete architecture:

1. **Attempts API**: For answer submission and validation
2. **Balance API**: For currency awards and ledger
3. **Stats Aggregator**: For real-time statistics updates
4. **Event Bus**: For async processing (Kafka/SNS)
5. **Analytics**: ClickHouse for advanced reporting

## 📚 API Documentation

Once running, visit:
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🤝 Contributing

This implementation follows your production architecture design. The codebase is structured for:

- Clean separation of concerns
- Easy testing and deployment
- Horizontal scalability
- Multi-service architecture evolution

---

Built with ❤️ following your comprehensive production design for scalable quiz services. 