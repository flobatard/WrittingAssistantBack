from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class ConversationRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: Optional[str]
    book_id: int
    start_date: datetime


class ChatEventRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    conversation_id: int
    role: str
    content: Optional[str] = None
    tool_calls: Optional[list] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    status: str
    created_at: datetime


class ResumeAgentRequest(BaseModel):
    chat_event_id: int  # ChatEvent.id of the pending assistant event
    user_decision: Literal["accept", "reject"]
    modified_content: Optional[str] = None
    feedback: Optional[str] = None
    answer: Optional[str] = None  # user's answer for ask_question tool calls


class ResumeAgentResponse(BaseModel):
    status: str
    chat_event_id: int


class ConversationChatRequest(BaseModel):
    question: str
    k: int = 5
    stream: bool = False


class ConversationChatResponse(BaseModel):
    conversation: ConversationRead
    message: ChatEventRead
    answer: str
    sources: list[dict]


class MessageChatResponse(BaseModel):
    message: ChatEventRead
    answer: str
    sources: list[dict]
