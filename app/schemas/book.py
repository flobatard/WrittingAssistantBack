from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.manuscript_node import ManuscriptNodeRead


class BookAISettings(BaseModel):
    preprompt: str = Field(
        default="",
        description="Instructions globales sur le rôle de l'IA.",
    )
    style_guidelines: str = Field(
        default="",
        description="Directives narratives et style d'écriture.",
    )
    temperature: float = Field(
        default=0.7,
        description="Niveau de créativité du modèle.",
    )
    top_k_rag: int = Field(
        default=7,
        description="Nombre de chunks à remonter lors d'une recherche vectorielle.",
    )
    enabled_tools: List[str] = Field(
        default=[
            "search_book", "read_chapter", "list_chapters",
            "propose_node_edit", "propose_new_node", "ask_question",
            "list_assets", "read_asset",
        ],
        description="Liste blanche des outils LangChain autorisés.",
    )
    hitl_strictness: str = Field(
        default="strict",
        description="Niveau d'autonomie ('strict' = validation systématique requise, 'copilot' = bypass autorisé).",
    )


class BookCreate(BaseModel):
    title: str
    genre: Optional[str] = None
    series_id: Optional[int] = None
    parent_book_id: Optional[int] = None
    position_in_series: Optional[float] = None
    is_spinoff: bool = False


class BookUpdate(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    series_id: Optional[int] = None
    parent_book_id: Optional[int] = None
    position_in_series: Optional[float] = None
    is_spinoff: Optional[bool] = None


class IaSettingsUpdate(BaseModel):
    ia_settings: BookAISettings


class BookRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    user_id: Optional[int]
    series_id: Optional[int]
    parent_book_id: Optional[int]
    position_in_series: Optional[float]
    is_spinoff: bool
    title: str
    genre: Optional[str]
    ia_settings: Optional[BookAISettings]
    embedding_model_used: Optional[str]
    last_vectorized_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    manuscript_nodes: list[ManuscriptNodeRead]


class ChatRequest(BaseModel):
    question: str
    k: int = 5
    stream: bool = False


class ChatSource(BaseModel):
    content: str
    score: float
    chunk_index: int


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[ChatSource]
