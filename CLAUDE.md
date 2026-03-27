# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

FastAPI backend for an AI-powered creative writing assistant (Scrivener-like). Users organize their work into **series** (sagas), **books**, and **manuscript nodes** (a hierarchical tree of parts, chapters, scenes, etc.) written in Markdown. Content is persisted in PostgreSQL and vectorized in ChromaDB to power a RAG system that can answer questions about the story.

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
- **PostgreSQL** (via SQLAlchemy async + asyncpg): persists series, books, manuscript nodes, conversations and messages
- **ChromaDB** (remote client): vector store for semantic search over manuscript content

### Project structure

```
app/
├── main.py                   # FastAPI app entry point — lifespan hook calls init_db()
├── core/
│   ├── auth.py               # OIDC/JWT authentication (JWKS caching)
│   ├── config.py             # Pydantic Settings — reads from .env via lru_cache
│   ├── database.py           # Async SQLAlchemy engine, Base, get_db() dependency
│   └── dependancies.py       # Shared dependencies: ChatConfig, EmbeddingConfig, get_book_for_user()
├── models/
│   ├── book.py               # Book ORM model (table: books)
│   ├── manuscript_node.py    # ManuscriptNode ORM model (table: manuscript_nodes) — self-referential tree
│   ├── series.py             # Series ORM model (table: series)
│   ├── conversation.py       # Conversation + ChatMessage ORM models
│   └── user.py               # User ORM model (table: users)
├── schemas/
│   ├── book.py               # BookCreate, BookUpdate, BookRead (includes manuscript_nodes list)
│   ├── manuscript_node.py    # ManuscriptNodeCreate, ManuscriptNodeUpdate, ManuscriptNodeRead
│   ├── series.py             # SeriesCreate, SeriesUpdate, SeriesRead
│   ├── conversation.py       # Conversation & ChatMessage schemas
│   └── user.py               # UserRead
├── routers/
│   ├── auth.py               # POST /auth/login
│   ├── books.py              # CRUD /books/ + POST /{id}/vectorize + GET /{id}/query
│   ├── manuscript_nodes.py   # CRUD /books/{book_id}/manuscript-nodes/
│   ├── series.py             # CRUD /series/
│   └── chat.py               # Conversations + streaming chat /books/chat/
└── services/
    ├── rag.py                # vectorize_book(), query_book() — chunking + ChromaDB ingestion
    ├── chat.py               # chat_with_book_history(), stream_chat_with_book_history()
    ├── chat_factory.py       # LLM instantiation (OpenAI-compatible)
    └── embeddings_factory.py # Embeddings instantiation
```

### Data model

```
series          (user_id FK → users, optional)
  └── books     (user_id FK → users, series_id FK → series, parent_book_id FK → books)
        └── manuscript_nodes  (book_id FK → books, parent_id FK → manuscript_nodes — self-referential)
              conversation     (book_id FK → books)
                └── chat_messages
```

#### Key tables

**books** — No `content` field; content lives in manuscript nodes.
- `series_id` (nullable FK → series): the saga this book belongs to
- `parent_book_id` (nullable FK → books): link a spin-off to a specific volume
- `position_in_series` (float, nullable): fractional indexing within the saga
- `is_spinoff` (bool, default false)
- `embedding_model_used`: set after vectorization

**manuscript_nodes** — Hierarchical tree structure replacing the old monolithic `content` field.
- `parent_id` (nullable FK → manuscript_nodes): self-referential for nesting
- `node_type`: `'part'`, `'chapter'`, `'scene'`, `'interlude'`, etc.
- `content` (TEXT, nullable): null for container nodes like `'part'`
- `position` (float): fractional indexing among siblings
- `is_numbered` (bool)

**series** — Groups of books (sagas). Always owned by a user (`user_id` required).

### Request flow

1. **Series**: create a saga, then attach books to it via `series_id`
2. **Books**: created with no content field; on creation, a first `ManuscriptNode` (`node_type='chapter'`, `position=1000.0`) is automatically created
3. **Manuscript nodes**: CRUD via `/books/{book_id}/manuscript-nodes/`; `parent_id` enables tree nesting; `position` uses fractional indexing among siblings
4. `POST /books/{id}/vectorize` triggers RAG ingestion:
   - Loads all nodes with non-null `content`, ordered by `position`
   - Concatenates them as `# {title}\n\n{content}` per node
   - Splits into chunks via `MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter` (size=1500, overlap=200)
   - Upserts into a ChromaDB collection named `book_{id}_{embedding_model}` (special chars → underscores)
   - Updates `book.embedding_model_used`
5. Each ChromaDB collection is scoped per book + embedding model combination

### Key modules

- [app/main.py](app/main.py) — FastAPI app entry point (lifespan + routers)
- [app/core/auth.py](app/core/auth.py) — OIDC JWT validation with JWKS caching
- [app/core/dependancies.py](app/core/dependancies.py) — `get_book_for_user()` (loads book + checks access), `ChatConfig`, `EmbeddingConfig`
- [app/models/book.py](app/models/book.py) — `Book` ORM model; relationship `manuscript_nodes` loaded via `selectin`
- [app/models/manuscript_node.py](app/models/manuscript_node.py) — `ManuscriptNode` ORM model with self-referential `parent_id`
- [app/models/series.py](app/models/series.py) — `Series` ORM model
- [app/services/rag.py](app/services/rag.py) — `vectorize_book(book, config, nodes)` — chunking + ChromaDB ingestion
- [migrations/](migrations/) — Alembic migration scripts

### Access control

| Resource | Rule |
|---|---|
| Series | `series.user_id == user_id` (always private) |
| Book | `book.user_id is None` (public) OR `book.user_id == user_id` |
| ManuscriptNode | inherits from book — via `get_book_for_user()` dependency; also checks `node.book_id == book_id` |

The `get_book_for_user(book_id, sub, db)` dependency in `app/core/dependancies.py` centralizes book loading and access checks. All book/node routers use it via `Depends(get_book_for_user)`.

### Database

Managed by **Alembic**. Tables are never auto-created at startup.

```bash
# Apply all migrations
alembic upgrade head

# Generate a new migration after modifying a model
alembic revision --autogenerate -m "description"
```

L'utilisateur s'occupera toujours de créer les nouvelles migrations manuellement.

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
| `CHROMA_HOST` | `localhost` | ChromaDB host |
| `CHROMA_PORT` | `8001` | ChromaDB port |
| `APP_ENV` | `development` | Application environment |
| `OIDC_ISSUER_URL` | `http://localhost:8080/realms/writting_assistant` | OIDC provider (Keycloak by default) |
| `OIDC_AUDIENCE` | *(optional)* | JWT audience claim |

Copy `.env.example` to `.env` to configure locally.

### ChromaDB collection naming

Collection names follow the pattern `book_{id}_{model_name}` with all non-alphanumeric characters (including `/` and `-`) replaced by `_`. This normalization is handled by `_normalize_collection_name()` in [app/services/rag.py](app/services/rag.py).

### Fractional indexing

`manuscript_nodes.position` and `books.position_in_series` use floating-point fractional indexing for ordering. The first node in a book is created at `position=1000.0`. To insert between two siblings, use the midpoint of their positions. This allows O(1) reordering without renumbering.
