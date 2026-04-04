import json
from typing import AsyncGenerator

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.tools import make_book_tools

from app.core.dependancies import ChatConfig, EmbeddingConfig
from app.models.book import Book
from app.models.conversation import ChatEvent
from app.services.chat_factory import get_chat

HITL_TOOLS = {"propose_new_node", "propose_node_edit", "ask_question"}

_AGENTIC_SYSTEM = (
    "You are an expert literary assistant helping the author analyze and develop their manuscript.\n"
    "You have access to specific tools to explore the book. You are allowed and ENCOURAGED to use multiple tools in sequence to gather complete context before answering.\n\n"

    "=== YOUR WORKFLOW ===\n"
    "1. PLAN: Always think step-by-step about what information you need.\n"
    "2. DISCOVER: If the user asks about the overall structure or you need to find a specific chapter, use `list_chapters` first.\n"
    "3. SEARCH: If the user asks about a character, event, or theme, use `search_book` to find relevant passages.\n"
    "4. DEEP DIVE: If `search_book` returns interesting excerpts but you need the full context of the scene, look at the chapter ID in the search results and use `read_chapter` on that ID.\n"
    "5. SYNTHESIZE: Once you have gathered enough information through your tools, provide a detailed and accurate answer.\n\n"

    "=== MANUSCRIPT EDITING ===\n"
    "To propose changes to the manuscript, use ONLY these tools:\n"
    "- `propose_node_edit(front_id, new_content)`: propose replacing an existing node's full content\n"
    "- `propose_new_node(title, content, ...)`: propose adding a new chapter or scene\n"
    "Only use them when the user explicitly requests a manuscript edit.\n\n"

    "=== ASKING CLARIFYING QUESTIONS ===\n"
    "If you need information from the user before you can proceed (e.g., a character name, a plot detail, a stylistic preference), use:\n"
    "- `ask_question(question)`: pauses the agent and presents the question to the user.\n"
    "IMPORTANT: Call at most ONE HITL tool per response (ask_question, propose_node_edit, or propose_new_node). Never combine them with each other or with other tool calls in the same response.\n\n"

    "CRITICAL RULES:\n"
    "- NEVER guess, hallucinate, or invent story details. If the tools don't provide the answer, say you don't know.\n"
    "- Do not answer immediately if you only have partial information. Take another turn to use another tool.\n"
    "- Always cite the chapter titles or IDs when providing facts from the manuscript.\n"

    "IMPORTANT: Use the standard tool-calling format. Do not use XML tags like <tool_call> or </tool_call>. Generate your tool calls purely through the provided API structure."
)


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _content_to_str(content) -> str:
    """Normalize LangChain chunk content to a plain string.

    OpenAI/Anthropic return str; Gemini returns a list of content blocks
    like [{"type": "text", "text": "..."}].
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


def generate_conversation_title(
    question: str,
    chat_config: ChatConfig,
    answer: str = "",
) -> str:
    try:
        llm = get_chat(chat_config)
        if answer:
            prompt = (
                "Based on the following question and answer from a conversation about a book, "
                "generate a very short and concise title (maximum 8 words) that summarizes the topic.\n"
                "Return ONLY the title, no punctuation at the end, no quotes.\n\n"
                f"Question: {question}\nAnswer: {answer}"
            )
        else:
            prompt = (
                "Based on the following question about a book, "
                "generate a very short and concise title (maximum 8 words) that summarizes the topic.\n"
                "Return ONLY the title, no punctuation at the end, no quotes.\n\n"
                f"Question: {question}"
            )
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception:
        return question[:60]


async def stream_chat_with_book_history_agentic(
    book: Book,
    lc_history: list,
    chat_config: ChatConfig,
    embedding_config: EmbeddingConfig,
    db: AsyncSession,
    conversation_id: int | None = None,
) -> AsyncGenerator[str, None]:

    tools = make_book_tools(book, db, embedding_config)
    llm = get_chat(chat_config).bind_tools(tools)
    tools_by_name = {t.name: t for t in tools}

    messages = lc_history
    full_response = ""
    MAX_ITER = 6

    for _ in range(MAX_ITER):
        accumulated: AIMessageChunk | None = None

        try:
            async for chunk in llm.astream(messages):
                accumulated = chunk if accumulated is None else accumulated + chunk
                if chunk.content:
                    text = _content_to_str(chunk.content)
                    full_response += text
                    yield _sse_event("token", {"content": text})
        except Exception as e:
            yield _sse_event("error", {"message": str(e)})
            return

        if accumulated is None:
            break

        ai_msg = AIMessage(
            content=_content_to_str(accumulated.content) if accumulated.content else "",
            tool_calls=list(accumulated.tool_calls) if accumulated.tool_calls else [],
        )
        messages.append(ai_msg)

        if not ai_msg.tool_calls:
            if conversation_id is not None:
                db.add(ChatEvent(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=ai_msg.content,
                    status="done",
                ))
                await db.flush()
            break

        for tc in ai_msg.tool_calls:
            yield _sse_event("tool_call", {"tool": tc["name"], "args": tc["args"]})

        hitl_tc = next((tc for tc in ai_msg.tool_calls if tc["name"] in HITL_TOOLS), None)

        if hitl_tc is not None:
            if conversation_id is not None:
                ai_event = ChatEvent(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=ai_msg.content or None,
                    tool_calls=ai_msg.tool_calls,
                    status="pending",
                )
                db.add(ai_event)
                await db.flush()
                await db.refresh(ai_event)

                yield _sse_event("human_in_the_loop", {
                    "chat_event_id": ai_event.id,
                    "tool_call_id": hitl_tc["id"],
                    "name": hitl_tc["name"],
                    "args": hitl_tc["args"],
                })
            return  # no "done" event — stream closed for HITL

        # Regular tool calls
        if conversation_id is not None:
            db.add(ChatEvent(
                conversation_id=conversation_id,
                role="assistant",
                content=ai_msg.content or None,
                tool_calls=ai_msg.tool_calls,
                status="done",
            ))
            await db.flush()

        for tc in ai_msg.tool_calls:
            tool_fn = tools_by_name[tc["name"]]
            try:
                result = await tool_fn.ainvoke(tc["args"])
            except Exception as e:
                result = f"Tool error: {e}"
            result_str = str(result)

            messages.append(ToolMessage(content=result_str, tool_call_id=tc["id"]))
            yield _sse_event("tool_result", {"tool": tc["name"], "result": result_str})

            if conversation_id is not None:
                db.add(ChatEvent(
                    conversation_id=conversation_id,
                    role="tool",
                    content=result_str,
                    tool_call_id=tc["id"],
                    tool_name=tc["name"],
                    tool_args=tc["args"],
                    status="done",
                ))

        if conversation_id is not None:
            await db.flush()

    yield _sse_event("done", {"full_response": full_response, "sources": []})


async def chat_with_book_history_agentic(
    book: Book,
    lc_history: list,
    chat_config: ChatConfig,
    embedding_config: EmbeddingConfig,
    db: AsyncSession,
    conversation_id: int | None = None,
) -> dict:

    tools = make_book_tools(book, db, embedding_config)
    llm = get_chat(chat_config).bind_tools(tools)
    tools_by_name = {t.name: t for t in tools}

    messages = lc_history
    full_response = ""
    MAX_ITER = 6

    for _ in range(MAX_ITER):
        response = await llm.ainvoke(messages)
        messages.append(response)

        if not response.tool_calls:
            full_response = response.content
            if conversation_id is not None:
                db.add(ChatEvent(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=response.content,
                    status="done",
                ))
                await db.flush()
            break

        if conversation_id is not None:
            db.add(ChatEvent(
                conversation_id=conversation_id,
                role="assistant",
                content=response.content or None,
                tool_calls=list(response.tool_calls),
                status="done",
            ))
            await db.flush()

        for tc in response.tool_calls:
            tool_fn = tools_by_name[tc["name"]]
            try:
                result = await tool_fn.ainvoke(tc["args"])
            except Exception as e:
                result = f"Tool error: {e}"
            result_str = str(result)
            messages.append(ToolMessage(content=result_str, tool_call_id=tc["id"]))

            if conversation_id is not None:
                db.add(ChatEvent(
                    conversation_id=conversation_id,
                    role="tool",
                    content=result_str,
                    tool_call_id=tc["id"],
                    tool_name=tc["name"],
                    tool_args=tc["args"],
                    status="done",
                ))

        if conversation_id is not None:
            await db.flush()

    return {"answer": full_response, "sources": []}
