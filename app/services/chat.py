import json
from datetime import datetime, timezone
from typing import AsyncGenerator

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.tools import make_book_tools

from app.core.dependancies import ChatConfig, EmbeddingConfig
from app.models.book import Book
from app.services.chat_factory import get_chat

_AGENTIC_SYSTEM = (
    "You are an expert literary assistant helping the author analyze and develop their manuscript.\n"
    "You have access to specific tools to explore the book. You are allowed and ENCOURAGED to use multiple tools in sequence to gather complete context before answering.\n\n"
    
    "=== YOUR WORKFLOW ===\n"
    "1. PLAN: Always think step-by-step about what information you need.\n"
    "2. DISCOVER: If the user asks about the overall structure or you need to find a specific chapter, use `list_chapters` first.\n"
    "3. SEARCH: If the user asks about a character, event, or theme, use `search_book` to find relevant passages.\n"
    "4. DEEP DIVE: If `search_book` returns interesting excerpts but you need the full context of the scene, look at the chapter ID in the search results and use `read_chapter` on that ID.\n"
    "5. SYNTHESIZE: Once you have gathered enough information through your tools, provide a detailed and accurate answer.\n\n"
    
    "CRITICAL RULES:\n"
    "- NEVER guess, hallucinate, or invent story details. If the tools don't provide the answer, say you don't know.\n"
    "- Do not answer immediately if you only have partial information. Take another turn to use another tool.\n"
    "- Always cite the chapter titles or IDs when providing facts from the manuscript.\n"

    "IMPORTANT: Use the standard tool-calling format. Do not use XML tags like <tool_call> or </tool_call>. Generate your tool calls purely through the provided API structure."
)


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


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


async def stream_chat_with_book_history_agentic(
    book: Book,
    question: str,
    history: list,
    chat_config: ChatConfig,
    embedding_config: EmbeddingConfig,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:

    tools = make_book_tools(book, db, embedding_config)
    llm = get_chat(chat_config).bind_tools(tools)
    tools_by_name = {t.name: t for t in tools}

    messages = [SystemMessage(content=_AGENTIC_SYSTEM)]
    for msg in history:
        cls = HumanMessage if msg.author == "user" else AIMessage
        messages.append(cls(content=msg.content))
    messages.append(HumanMessage(content=question))

    full_response = ""
    tool_steps = []
    MAX_ITER = 6

    for _ in range(MAX_ITER):
        accumulated: AIMessageChunk | None = None

        async for chunk in llm.astream(messages):
            accumulated = chunk if accumulated is None else accumulated + chunk
            if chunk.content:
                full_response += chunk.content
                yield _sse_event("token", {"content": chunk.content})

        if accumulated is None:
            break

        messages.append(accumulated)

        if not accumulated.tool_calls:
            break

        for tc in accumulated.tool_calls:
            print("Tool call: ", tc)
            yield _sse_event("tool_call", {"tool": tc["name"], "args": tc["args"]})
            tool_fn = tools_by_name[tc["name"]]
            called_at = datetime.now(timezone.utc).replace(tzinfo=None)
            try:
                result = await tool_fn.ainvoke(tc["args"])
            except Exception as e:
                result = f"Tool error: {e}"
            result_str = str(result)
            tool_steps.append({"tool": tc["name"], "args": tc["args"], "result": result_str, "called_at": called_at.isoformat()})
            messages.append(ToolMessage(content=result_str, tool_call_id=tc["id"]))
            yield _sse_event("tool_result", {"tool": tc["name"], "result": result_str})

    yield _sse_event("done", {"full_response": full_response, "sources": [], "tool_steps": tool_steps})


async def chat_with_book_history_agentic(
    book: Book,
    question: str,
    history: list,
    chat_config: ChatConfig,
    embedding_config: EmbeddingConfig,
    db: AsyncSession,
) -> dict:

    tools = make_book_tools(book, db, embedding_config)
    llm = get_chat(chat_config).bind_tools(tools)
    tools_by_name = {t.name: t for t in tools}

    messages = [SystemMessage(content=_AGENTIC_SYSTEM)]
    for msg in history:
        cls = HumanMessage if msg.author == "user" else AIMessage
        messages.append(cls(content=msg.content))
    messages.append(HumanMessage(content=question))

    full_response = ""
    tool_steps = []
    MAX_ITER = 6

    for _ in range(MAX_ITER):
        response = await llm.ainvoke(messages)
        messages.append(response)

        if not response.tool_calls:
            full_response = response.content
            break

        for tc in response.tool_calls:
            tool_fn = tools_by_name[tc["name"]]
            called_at = datetime.now(timezone.utc).replace(tzinfo=None)
            try:
                result = await tool_fn.ainvoke(tc["args"])
            except Exception as e:
                result = f"Tool error: {e}"
            result_str = str(result)
            tool_steps.append({"tool": tc["name"], "args": tc["args"], "result": result_str, "called_at": called_at.isoformat()})
            messages.append(ToolMessage(content=result_str, tool_call_id=tc["id"]))

    return {"question": question, "answer": full_response, "sources": [], "tool_steps": tool_steps}
