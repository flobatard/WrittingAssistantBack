# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

FastAPI backend for an AI-powered creative writing assistant (Scrivener-like). Users organize their work into **series** (sagas), **books**, and **manuscript nodes** (a hierarchical tree of parts, chapters, scenes, etc.) written in Markdown. Content is persisted in PostgreSQL and vectorized in ChromaDB to power a RAG system that can answer questions about the story.

## Commands

### Running the API

```bash
# Docker Compose (recommended — starts PostgreSQL + ChromaDB + LanguageTool)
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

Three storage layers:
- **PostgreSQL** (via SQLAlchemy async + asyncpg): persists series, books, manuscript nodes, conversations, chat events, book commits and snapshots
- **ChromaDB** (remote client): vector store for semantic search over manuscript content
- **MinIO / S3** (via boto3): object storage for file uploads (images, PDFs) attached to assets

### Project structure

```
app/
├── main.py                         # FastAPI app entry point — lifespan hook calls init_db()
├── core/
│   ├── auth.py                     # OIDC/JWT authentication (JWKS caching)
│   ├── config.py                   # Pydantic Settings — reads from .env via lru_cache
│   ├── database.py                 # Async SQLAlchemy engine, Base, get_db() dependency
│   ├── dependancies.py             # Shared dependencies: ChatConfig, EmbeddingConfig, get_book_for_user()
│   └── s3.py                       # S3 client (boto3) + presigned URL helpers
├── models/
│   ├── asset.py                    # Asset ORM model (table: assets) — World Bible elements
│   ├── book.py                     # Book ORM model (table: books)
│   ├── manuscript_node.py          # ManuscriptNode ORM model (table: manuscript_nodes) — self-referential tree
│   ├── manuscript_node_snapshot.py # ManuscriptNodeSnapshot ORM model (table: manuscript_node_snapshots)
│   ├── series.py                   # Series ORM model (table: series)
│   ├── conversation.py             # Conversation + ChatEvent ORM models
│   ├── book_commit.py              # BookCommit ORM model (table: book_commits)
│   └── user.py                     # User ORM model (table: users)
├── schemas/
│   ├── asset.py                    # AssetCreate, AssetUpdate, AssetRead
│   ├── book.py                     # BookCreate, BookUpdate, BookRead (includes manuscript_nodes list)
│   ├── manuscript_node.py          # ManuscriptNodeCreate, ManuscriptNodeUpdate, ManuscriptNodeRead
│   ├── series.py                   # SeriesCreate, SeriesUpdate, SeriesRead
│   ├── conversation.py             # Conversation, ChatEventRead, ResumeAgent* schemas
│   ├── book_commit.py              # CommitCreate, CommitRead, ManuscriptNodeSnapshotRead
│   ├── spellcheck.py               # SpellCheckRequest schema
│   └── user.py                     # UserRead
├── routers/
│   ├── auth.py                     # POST /auth/login
│   ├── assets.py                   # CRUD /books/{book_id}/assets/
│   ├── books.py                    # CRUD /books/ + POST /{id}/vectorize + GET /{id}/query
│   ├── manuscript_nodes.py         # CRUD /books/{book_id}/manuscript-nodes/
│   ├── series.py                   # CRUD /series/
│   ├── chat.py                     # Conversations + agentic streaming chat + HITL /books/chat/
│   ├── book_commits.py             # Snapshot-based versioning /books_commits/
│   ├── spellcheck.py               # LanguageTool proxy /spellcheck/
│   └── dev.py                      # Dev-only endpoints (active when APP_ENV=development)
└── services/
    ├── rag.py                      # vectorize_book(), query_book() — chunking + ChromaDB ingestion
    ├── chat.py                     # stream_chat_with_book_history_agentic(), chat_with_book_history_agentic()
    ├── tools.py                    # make_book_tools() — LangChain tools for the agentic loop
    ├── book_commits.py             # create_commit(), restore_commit() — snapshot versioning
    ├── chat_factory.py             # LLM instantiation (OpenAI-compatible)
    └── embeddings_factory.py       # Embeddings instantiation
```

### Data model

```
series          (user_id FK → users, optional)
  └── books     (user_id FK → users, series_id FK → series, parent_book_id FK → books)
        ├── assets            (book_id FK → books) — World Bible elements
        ├── manuscript_nodes  (book_id FK → books, parent_front_id FK → manuscript_nodes.front_id — self-referential)
        ├── book_commits      (book_id FK → books)
        │     └── manuscript_node_snapshots  (commit_id FK → book_commits)
        └── conversations     (book_id FK → books)
              └── chat_events (conversation_id FK → conversations)
```

#### Key tables

**assets** — World Bible elements scoped to a book.
- `id` (UUID PK, `gen_random_uuid()`): client-facing identifier
- `book_id` (int FK → books, CASCADE): owning book
- `type` (enum): `CHARACTER`, `LOCATION`, `ITEM`, `FACTION`, `LORE`, `IMAGE` — indexed
- `name` (string(255))
- `aliases` (PostgreSQL `text[]`, default `{}`): alternative names / pseudonyms
- `short_description` (TEXT, nullable)
- `attributes` (JSONB, nullable): open-ended type-specific fields (e.g. `{"age": 35, "role": "antagonist"}`). May contain S3 `object_key` references to uploaded files — managed by the frontend per asset type. Each asset has a dedicated S3 folder (`books/{book_id}/assets/{asset_id}/`) that is cleaned up on deletion.

**books** — No `content` field; content lives in manuscript nodes.
- `series_id` (nullable FK → series): the saga this book belongs to
- `parent_book_id` (nullable FK → books): link a spin-off to a specific volume
- `position_in_series` (float, nullable): fractional indexing within the saga
- `is_spinoff` (bool, default false)
- `embedding_model_used`: set after vectorization

**manuscript_nodes** — Hierarchical tree structure replacing the old monolithic `content` field.
- `front_id` (UUID, non-nullable, unique, indexed): stable client-facing identifier. Auto-generated by the DB (`gen_random_uuid()`) if not provided on creation. Used as the FK target for `parent_front_id`.
- `parent_front_id` (nullable FK → `manuscript_nodes.front_id`, `SET NULL` on delete): self-referential for nesting; uses `front_id` instead of `id` so the frontend can reference nodes before they are flushed.
- `node_type`: `'part'`, `'chapter'`, `'scene'`, `'interlude'`, etc.
- `content` (TEXT, nullable): null for container nodes like `'part'`
- `position` (float): fractional indexing among siblings
- `is_numbered` (bool)
- `depth_level` (int, default 2): visual/logical nesting level, maintained by the client

**chat_events** — Unified event table replacing the old `chat_messages` + `chat_tool_calls` split. Every LangChain message in the agentic loop is stored as one row, ordered by PK `id` (insertion order).

| Column | Type | Description |
|---|---|---|
| `id` | int PK | Insertion-order identifier — used for sorting |
| `conversation_id` | int FK | → conversations.id CASCADE |
| `role` | varchar(20) | `"user"` \| `"assistant"` \| `"tool"` |
| `content` | TEXT NULL | Text content; null for pure tool-call AIMessages |
| `tool_calls` | JSON NULL | `[{id, name, args, type}]` from `AIMessage.tool_calls` |
| `tool_call_id` | varchar(255) | LLM-internal ID (ToolMessage rows only) — links a tool result back to its call |
| `tool_name` | varchar(100) | Display name (tool rows only) |
| `tool_args` | JSON NULL | Display args (tool rows only) |
| `status` | varchar(30) | `"done"` \| `"pending"` \| `"accepted"` \| `"rejected"` |
| `created_at` | datetime | |

Mapping from LangChain message types:
- `HumanMessage` → `role="user", content=...`
- `AIMessage` (final response) → `role="assistant", content=..., tool_calls=null, status="done"`
- `AIMessage` (tool turn) → `role="assistant", tool_calls=[{id,name,args}], status="done"`
- `ToolMessage` → `role="tool", content=result, tool_call_id=llm_id, tool_name=..., status="done"`
- HITL pending → `role="assistant", tool_calls=[hitl_call], status="pending"`
- HITL resolved → `role="tool", content=observation, status="accepted"|"rejected"`

**book_commits** — Snapshot of the full manuscript at a point in time.
- `book_id` (FK → books)
- `message` (string, optional): human-readable description
- Related `manuscript_node_snapshots`: full copy of all nodes at commit time

**series** — Groups of books (sagas). Always owned by a user (`user_id` required).

### Agentic chat & Human-In-The-Loop (HITL)

The chat service runs a multi-turn LangChain agentic loop (max 6 iterations). Each turn:
1. LLM streams a response — may include tool calls
2. Regular tools (`search_book`, `read_chapter`, `list_chapters`) execute immediately; their result is fed back to the LLM
3. HITL tools (`propose_node_edit`, `propose_new_node`) pause the agent and require user approval before execution

**Available tools** (defined in [app/services/tools.py](app/services/tools.py)):

| Tool | Type | Description |
|---|---|---|
| `search_book` | Regular | Semantic search over vectorized manuscript content |
| `read_chapter` | Regular | Reads the full text of a node by UUID or title |
| `list_chapters` | Regular | Returns the full table of contents (IDs + titles) |
| `list_assets` | Regular | Returns a lightweight overview of World Bible assets (id, type, name, short_description); optional type filter |
| `read_asset` | Regular | Returns full details of a World Bible asset (including `attributes` JSONB) by UUID |
| `propose_node_edit` | **HITL** | Proposes replacing an existing node's content — pauses the agent |
| `propose_new_node` | **HITL** | Proposes creating a new node — pauses the agent |
| `ask_question` | **HITL** | Asks the user a clarifying question — pauses the agent |

**HITL flow:**
1. Agent calls `propose_node_edit` or `propose_new_node`
2. Service saves a `ChatEvent(role="assistant", status="pending")` and yields a `human_in_the_loop` SSE event with `db_id`
3. Stream closes — no `done` event
4. Client calls `POST .../resume-agent` with `tool_call_id=db_id` and `user_decision="accept"|"reject"`
5. Backend applies the change (accept) or records the rejection, saves a `ChatEvent(role="tool", status="accepted"|"rejected")`
6. Client calls `POST .../resume-stream` — backend loads all events, reconstructs LangChain history, and continues the agent loop

History reconstruction for `resume_stream` is trivial: query all `chat_events` ordered by `id`, then convert each row to the matching LangChain message type.

### Request flow

1. **Series**: create a saga, then attach books to it via `series_id`
2. **Books**: created with no content field; on creation, a first `ManuscriptNode` (`node_type='chapter'`, `position=1000.0`) is automatically created
3. **Manuscript nodes**: CRUD via `/books/{book_id}/manuscript-nodes/` (by integer `id`) or `/books/{book_id}/manuscript-nodes/by-front-id/{front_id}` (by UUID); `parent_front_id` enables tree nesting; `position` uses fractional indexing among siblings
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
- [app/core/s3.py](app/core/s3.py) — `get_s3_client()`, `generate_presigned_upload_url()`, `generate_presigned_download_url()`, `delete_object()`
- [app/models/asset.py](app/models/asset.py) — `Asset` ORM model + `AssetType` enum; UUID PK, PostgreSQL `ARRAY` + `JSONB`
- [app/models/book.py](app/models/book.py) — `Book` ORM model; relationship `manuscript_nodes` loaded via `selectin`
- [app/models/manuscript_node.py](app/models/manuscript_node.py) — `ManuscriptNode` ORM model with self-referential `parent_front_id → front_id`
- [app/models/conversation.py](app/models/conversation.py) — `Conversation` + `ChatEvent` ORM models
- [app/models/series.py](app/models/series.py) — `Series` ORM model
- [app/schemas/asset.py](app/schemas/asset.py) — `AssetCreate`, `AssetUpdate`, `AssetRead`
- [app/routers/assets.py](app/routers/assets.py) — CRUD `/books/{book_id}/assets/` + presigned upload/download URLs; `_get_asset_for_book()` enforces book-scoped access
- [app/services/rag.py](app/services/rag.py) — `vectorize_book(book, config, nodes)` — chunking + ChromaDB ingestion
- [app/services/chat.py](app/services/chat.py) — `stream_chat_with_book_history_agentic()`, `chat_with_book_history_agentic()` — agentic loop with real-time event persistence
- [app/services/tools.py](app/services/tools.py) — `make_book_tools(book, db, embedding_config)` — LangChain tools for the agent (includes `list_assets`, `read_asset`)
- [app/services/book_commits.py](app/services/book_commits.py) — `create_commit()`, `restore_commit()` — snapshot-based versioning
- [app/routers/chat.py](app/routers/chat.py) — conversation CRUD, agentic chat, HITL endpoints, timeline
- [app/routers/book_commits.py](app/routers/book_commits.py) — commit CRUD + restore
- [migrations/](migrations/) — Alembic migration scripts

### Access control

| Resource | Rule |
|---|---|
| Series | `series.user_id == user_id` (always private) |
| Book | `book.user_id is None` (public) OR `book.user_id == user_id` |
| ManuscriptNode | inherits from book — via `get_book_for_user()` dependency; also checks `node.book_id == book_id` |
| Asset | inherits from book — via `get_book_for_user()` dependency; `_get_asset_for_book()` checks both `asset_id` and `book_id` in a single query |

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
| `LANGUAGETOOL_HOST` | `localhost` | LanguageTool host |
| `LANGUAGETOOL_PORT` | `8010` | LanguageTool port |
| `APP_ENV` | `development` | Application environment (`development` enables dev router) |
| `OIDC_ISSUER_URL` | `http://localhost:8080/realms/writting_assistant` | OIDC provider (Keycloak by default) |
| `S3_ENDPOINT_URL` | `http://localhost:9000` | S3/MinIO API endpoint |
| `S3_PUBLIC_URL` | `http://localhost:9000` | Public S3 URL for presigned URLs (browser-reachable) |
| `S3_ACCESS_KEY` | `minioadmin` | S3 access key |
| `S3_SECRET_KEY` | `minioadmin` | S3 secret key |
| `S3_BUCKET_NAME` | `writing-assistant` | S3 bucket name |
| `S3_PRESIGNED_EXPIRY` | `3600` | Presigned URL expiry (seconds) |
| `OIDC_AUDIENCE` | *(optional)* | JWT audience claim |

Copy `.env.example` to `.env` to configure locally.

### ChromaDB collection naming

Collection names follow the pattern `book_{id}_{model_name}` with all non-alphanumeric characters (including `/` and `-`) replaced by `_`. This normalization is handled by `_normalize_collection_name()` in [app/services/rag.py](app/services/rag.py).

### Fractional indexing

`manuscript_nodes.position` and `books.position_in_series` use floating-point fractional indexing for ordering. The first node in a book is created at `position=1000.0`. To insert between two siblings, use the midpoint of their positions. This allows O(1) reordering without renumbering.
