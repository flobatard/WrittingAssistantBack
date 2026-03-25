# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

FastAPI backend for an AI-powered creative writing assistant (Scrivener-like). Users write their book in Markdown; content is persisted in PostgreSQL and vectorized in ChromaDB to power a RAG system that can answer questions about the story.

## Commands

### Running the API

```bash
# Docker Compose (recommended — starts PostgreSQL + API)
docker-compose up --build

# Local development
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API available at `http://localhost:8000`, Swagger UI at `http://localhost:8000/docs`.

### Dependencies

```bash
pip install -r requirements.txt
```

## Architecture

Two storage layers:
- **PostgreSQL** (via SQLAlchemy async + asyncpg): persists books with their raw Markdown content
- **ChromaDB** (`./chroma_data/`): local vector store for semantic search over book chunks

### Project structure

```
app/
├── main.py              # FastAPI app entry point — lifespan hook calls init_db()
├── core/
│   ├── config.py        # Pydantic Settings — reads from .env via lru_cache
│   └── database.py      # Async SQLAlchemy engine, Base, get_db() dependency
├── models/
│   └── book.py          # Book ORM model (table: books)
├── schemas/
│   └── book.py          # Pydantic schemas: BookCreate, BookUpdate, BookRead
├── routers/
│   └── books.py         # All endpoints: CRUD + POST /{id}/vectorize
└── services/
    └── rag.py           # vectorize_book() — Markdown chunking + ChromaDB ingestion
```

### Request flow

1. Books are created/updated via CRUD endpoints (`/books/`)
2. `POST /books/{id}/vectorize` triggers RAG ingestion:
   - Markdown content is split into chunks (size=500, overlap=50) via `MarkdownTextSplitter`
   - Chunks are upserted into a ChromaDB collection named `book_{id}_{embedding_model}` (special chars normalized to underscores)
   - `book.embedding_model_used` is updated on the ORM object
3. Each ChromaDB collection is scoped per book + embedding model combination

### Key modules

- [app/main.py](app/main.py) — FastAPI app entry point (lifespan + routers)
- [app/core/config.py](app/core/config.py) — Pydantic Settings config (reads from `.env`)
- [app/core/database.py](app/core/database.py) — Async SQLAlchemy engine and session dependency
- [app/models/book.py](app/models/book.py) — `Book` ORM model (PostgreSQL)
- [app/schemas/book.py](app/schemas/book.py) — Pydantic request/response schemas
- [app/routers/books.py](app/routers/books.py) — All API endpoints
- [app/services/rag.py](app/services/rag.py) — `vectorize_book()` — chunking + ChromaDB ingestion
- [migrations/](migrations/) — Alembic migration scripts

### Database

Managed by **Alembic**. Tables are never auto-created at startup.

```bash
# Apply all migrations
alembic upgrade head

# Generate a new migration after modifying a model
alembic revision --autogenerate -m "description"
```

PostgreSQL connection (default): `postgresql+asyncpg://writing_user:writing_password@localhost:5430/writing_assistant`

### Scripts

| Script | Description |
|---|---|
| `bash scripts/init.sh` | Create the database (if not exists) then run `alembic upgrade head` |
| `bash scripts/drop.sh` | Drop the database (asks for confirmation) |
| `python scripts/init_db.py` | Create the database only |
| `python scripts/drop_db.py` | Drop the database only |

All scripts read connection info from `DATABASE_URL` (via `app.core.config`).

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://writing_user:writing_password@localhost:5430/writing_assistant` | PostgreSQL connection string |
| `CHROMA_PERSIST_DIR` | `./chroma_data` | ChromaDB persistence path |
| `APP_ENV` | `development` | Application environment |

Copy `.env.example` to `.env` to configure locally.

### ChromaDB collection naming

Collection names follow the pattern `book_{id}_{model_name}` with all non-alphanumeric characters (including `/` and `-`) replaced by `_`. This normalization is handled by `_normalize_collection_name()` in [app/services/rag.py](app/services/rag.py).
