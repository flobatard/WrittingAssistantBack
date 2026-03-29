from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db
from app.routers import auth, book_commits, books, chat, manuscript_nodes, series


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Writing Assistant API",
    description="API pour l'écriture créative assistée par IA (RAG sur Markdown).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth")
app.include_router(series.router, prefix="/series")
app.include_router(books.router, prefix="/books")
app.include_router(manuscript_nodes.router, prefix="/books")
app.include_router(book_commits.router, prefix="/books_commits")
app.include_router(chat.router, prefix="/books/chat")

if get_settings().APP_ENV == "development":
    from app.routers import dev
    app.include_router(dev.router, prefix="/dev")
