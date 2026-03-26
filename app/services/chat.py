import asyncio
import json
from typing import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.dependancies import ChatConfig, EmbeddingConfig
from app.models.book import Book
from app.services.chat_factory import get_chat
from app.services.rag import query_book


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _build_messages(question: str, rag_results: list, history: list | None = None) -> list:
    context = "\n---\n".join(r["content"] for r in rag_results)
    system = (
        "You are an expert literary assistant helping the author understand their story.\n"
        "Use the following excerpts from the book to answer the question.\n"
        "Only use information present in the provided excerpts. If insufficient, say so.\n\n"
        f"Context:\n{context}"
    )
    messages = [SystemMessage(content=system)]
    if history:
        for msg in history:
            if msg.author == "user":
                messages.append(HumanMessage(content=msg.content))
            else:
                messages.append(AIMessage(content=msg.content))
    messages.append(HumanMessage(content=question))
    return messages


def _format_sources(rag_results: list) -> list:
    return [
        {
            "content": r["content"],
            "score": r["score"],
            "chunk_index": r["metadata"]["chunk_index"],
        }
        for r in rag_results
    ]


def chat_with_book(
    book: Book,
    question: str,
    k: int,
    chat_config: ChatConfig,
    embedding_config: EmbeddingConfig,
) -> dict:
    rag = query_book(book, question, embedding_config, k=k)
    messages = _build_messages(question, rag["results"])
    llm = get_chat(chat_config)
    response = llm.invoke(messages)
    return {
        "question": question,
        "answer": response.content,
        "sources": _format_sources(rag["results"]),
    }


async def stream_chat_with_book(
    book: Book,
    question: str,
    k: int,
    chat_config: ChatConfig,
    embedding_config: EmbeddingConfig,
) -> AsyncGenerator[str, None]:
    rag = await asyncio.to_thread(query_book, book, question, embedding_config, k=k)
    sources = _format_sources(rag["results"])

    yield _sse_event("progress", {
        "type": "context_retrieved",
        "chunks_count": len(rag["results"]),
        "sources": sources,
    })

    messages = _build_messages(question, rag["results"])
    llm = get_chat(chat_config)
    full_response = ""
    async for chunk in llm.astream(messages):
        if chunk.content:
            full_response += chunk.content
            yield _sse_event("token", {"content": chunk.content})

    yield _sse_event("done", {"full_response": full_response, "sources": sources})


def chat_with_book_history(
    book: Book,
    question: str,
    history: list,
    k: int,
    chat_config: ChatConfig,
    embedding_config: EmbeddingConfig,
) -> dict:
    rag = query_book(book, question, embedding_config, k=k)
    messages = _build_messages(question, rag["results"], history=history)
    llm = get_chat(chat_config)
    response = llm.invoke(messages)
    return {
        "question": question,
        "answer": response.content,
        "sources": _format_sources(rag["results"]),
    }


async def stream_chat_with_book_history(
    book: Book,
    question: str,
    history: list,
    k: int,
    chat_config: ChatConfig,
    embedding_config: EmbeddingConfig,
) -> AsyncGenerator[str, None]:
    rag = await asyncio.to_thread(query_book, book, question, embedding_config, k=k)
    sources = _format_sources(rag["results"])

    yield _sse_event("progress", {
        "type": "context_retrieved",
        "chunks_count": len(rag["results"]),
        "sources": sources,
    })

    messages = _build_messages(question, rag["results"], history=history)
    llm = get_chat(chat_config)
    full_response = ""
    async for chunk in llm.astream(messages):
        if chunk.content:
            full_response += chunk.content
            yield _sse_event("token", {"content": chunk.content})

    yield _sse_event("done", {"full_response": full_response, "sources": sources})


def generate_conversation_title(
    question: str,
    answer: str,
    chat_config: ChatConfig,
) -> str:
    llm = get_chat(chat_config)
    prompt = (
        "Based on the following question and answer from a conversation about a book, "
        "generate a very short and concise title (maximum 8 words) that summarizes the topic.\n"
        "Return ONLY the title, no punctuation at the end, no quotes.\n\n"
        f"Question: {question}\nAnswer: {answer}"
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content.strip()
