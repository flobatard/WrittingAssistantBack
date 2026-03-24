from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import init_db
from app.routers import books


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

app.include_router(books.router, prefix="/books")
