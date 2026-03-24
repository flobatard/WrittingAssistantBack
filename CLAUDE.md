# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

FastAPI backend for a RAG-powered writing assistant. Two storage layers:
- **PostgreSQL** (via SQLAlchemy async + asyncpg): stores books with their Markdown content
- **ChromaDB** (`./chroma_data/`): vector store for semantic search over book chunks

### Request flow

1. Books are created/updated via CRUD endpoints (`/books/`)
2. `POST /books/{id}/vectorize` triggers RAG ingestion: Markdown content is split into chunks (size=500, overlap=50) via `MarkdownTextSplitter`, then stored in a ChromaDB collection named `book_{id}_{embedding_model}`
3. Each ChromaDB collection is scoped per book + embedding model combination

### Key modules

- [app/main.py](app/main.py) — FastAPI app with lifespan hook that auto-creates DB tables on startup (`init_db()`)
- [app/core/config.py](app/core/config.py) — Pydantic Settings config (reads from `.env`)
- [app/core/database.py](app/core/database.py) — Async SQLAlchemy engine and session dependency
- [app/models/book.py](app/models/book.py) — `Book` ORM model (PostgreSQL)
- [app/schemas/book.py](app/schemas/book.py) — Pydantic request/response schemas
- [app/routers/books.py](app/routers/books.py) — All API endpoints
- [app/services/rag.py](app/services/rag.py) — `vectorize_book()` — chunking + ChromaDB ingestion

### Database

No Alembic — tables are auto-created at startup via `Base.metadata.create_all()`. Schema changes require dropping and recreating tables in development.

PostgreSQL connection: `postgresql+asyncpg://writing_user:writing_password@localhost:5430/writing_assistant`

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...@localhost:5430/writing_assistant` | PostgreSQL connection string |
| `CHROMA_PERSIST_DIR` | `./chroma_data` | ChromaDB persistence path |
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace embedding model |
| `APP_ENV` | `development` | Application environment |

Copy `.env.example` to `.env` to configure locally.
