# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastAPI-based Steam game recommendation engine using PostgreSQL with the `pgvector` extension for vector similarity search. Implements two recommendation strategies: Item-to-Item (game similarity) and User-to-Item (user taste profile matching).

Code comments and UI strings are written in Korean.

## Commands

```bash
# Development (hot-reload, requires running PostgreSQL with pgvector)
uvicorn src.main:app --reload --port 8000

# Run with Docker Compose
docker-compose up --build

# Manual endpoint testing (server must be running on :8000)
python test_endpoints.py
```

Environment setup: copy `.env.example` to `.env` and fill in DB credentials.

## Architecture

**3-tier structure:** `main.py` → `services.py` → `database.py` → PostgreSQL + pgvector

- `src/main.py` — FastAPI app with two POST endpoints: `/recommend/game` and `/recommend/user`. Calls `init_db()` on startup via lifespan context manager. CORS is wide open (`allow_origins=["*"]`).
- `src/services.py` — All business logic. Uses raw SQL (not ORM) with pgvector's `<=>` cosine distance operator. Embeddings are retrieved as text and parsed with `json.loads`. numpy is used for vector math (weighted sum, L2 normalization).
- `src/database.py` — SQLAlchemy engine setup with connection pooling (pool_size=10, max_overflow=20). `get_db()` is a FastAPI dependency generator. `init_db()` is lazily called if `SessionLocal` is None. `close_db()` is currently a no-op.
- `src/models.py` — Pydantic v2 request/response models. `BaseFilterParams` holds soft filter fields (with defaults) shared by both `GameRecommendRequest` and `UserRecommendRequest`.

## Recommendation Logic

**Item-to-Item** (`/recommend/game`): Fetches the target game's 446-dim TF-IDF embedding from `game_embeddings`, then runs a pgvector similarity search using a CTE. `sim_score = 1 - cosine_distance`.

**User-to-Item** (`/recommend/user`): Fetches embeddings for all user-owned games, computes a weighted sum `Σ(vector * log(1 + playtime))`, L2-normalizes the result to create a user profile vector, then searches with pgvector excluding owned games. Returns `skipped_game_ids` for games without embeddings.

**Soft filters** applied in SQL WHERE clause: `release_date`, `total_review_count`, `total_review_positive_percent`, `recent_review_count`, `recent_review_positive_percent`. All have defaults in `BaseFilterParams`.

## Database Schema (key tables)

- `basic_info` — Game metadata (game_id PK, title, release_date, etc.)
- `reviews` — Review metrics (1:1 with basic_info; review counts, positive percentages)
- `game_embeddings` — pgvector column storing 446-dim TF-IDF embeddings, HNSW indexed for ~0.1s query time

## Key Dependencies

Python 3.12. Core packages: `fastapi`, `sqlalchemy` (2.x, raw SQL only — no ORM models defined), `psycopg2-binary`, `pgvector`, `numpy`, `python-dotenv`. `requests` is used only by `test_endpoints.py`.

## Docker / Deployment

The API container (`steam-recommend-api`) connects to the external Docker network `steam-spider_steam-network` to reach the PostgreSQL container managed by a separate `steam-spider` project. The network name is configured via `DB_NETWORK_NAME` in `.env`. When running via docker-compose, `DB_HOST` defaults to `host.docker.internal` (for host DB access), and `/src` is volume-mounted for hot reload.

## Reference Docs

- `etc/logic_recommend.md` — Algorithm details (TF-IDF weighting, user profile vector math)
- `etc/README-tfidf.md` — System architecture, hard/soft filter strategy, HNSW indexing rationale
- `etc/pipeline.md` — Data pipeline documentation
- `etc/example_dbschema.py` — Full SQLAlchemy ORM schema reference
- `etc/test_search.py` — Search testing utilities
