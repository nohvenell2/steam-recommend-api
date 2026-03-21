# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastAPI-based Steam game recommendation engine using PostgreSQL with the `pgvector` extension for vector similarity search. Implements two recommendation strategies: Item-to-Item (game similarity) and User-to-Item (user taste profile matching).

## Commands

```bash
# Development (hot-reload)
uvicorn src.main:app --reload --port 8000

# Run with Docker Compose
docker-compose up --build

# Manual endpoint testing
python test_endpoints.py
```

Environment setup: copy `.env.example` to `.env` and fill in DB credentials.

## Architecture

**3-tier structure:** `main.py` → `services.py` → `database.py` → PostgreSQL + pgvector

- `src/main.py` — FastAPI app with two POST endpoints: `/recommend/game` and `/recommend/user`. Calls `init_db()` on startup via lifespan context manager.
- `src/services.py` — All business logic. Uses raw SQL with pgvector's `<=>` cosine distance operator for fast ANN search.
- `src/database.py` — SQLAlchemy engine setup, connection pooling (pool_size=10, max_overflow=20), and `get_db()` dependency injection generator.
- `src/models.py` — Pydantic v2 request/response models. `BaseFilterParams` holds soft filter fields shared by both request types.

## Recommendation Logic

**Item-to-Item** (`/recommend/game`): Fetches the target game's 446-dim TF-IDF embedding from `game_embeddings`, then runs a pgvector similarity search using a CTE. `sim_score = 1 - cosine_distance`.

**User-to-Item** (`/recommend/user`): Fetches embeddings for all user-owned games, computes a weighted sum `Σ(vector * log(1 + playtime))`, L2-normalizes the result to create a user profile vector, then searches with pgvector excluding owned games.

**Soft filters** applied in SQL WHERE clause: `release_date`, `total_review_count`, `total_review_positive_percent`, `recent_review_count`, `recent_review_positive_percent`.

## Database Schema (key tables)

- `basic_info` — Game metadata (game_id PK, title, release_date, etc.)
- `reviews` — Review metrics (1:1 with basic_info; review counts, positive percentages)
- `game_embeddings` — pgvector column storing 446-dim TF-IDF embeddings, HNSW indexed for ~0.1s query time

## Docker / Deployment

The API container (`steam-recommend-api`) connects to the external Docker network `steam-spider_steam-network` to reach the PostgreSQL container managed by a separate `steam-spider` project. The network name is configured via `DB_NETWORK_NAME` in `.env`.

## Reference Docs

- `etc/logic_recommend.md` — Algorithm details (TF-IDF weighting, user profile vector math)
- `etc/README-tfidf.md` — System architecture, hard/soft filter strategy, HNSW indexing rationale
- `etc/example_dbschema.py` — Full SQLAlchemy ORM schema reference
