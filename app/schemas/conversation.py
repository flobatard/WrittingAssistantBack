from datetime import datetime
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field


class ConversationRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: Optional[str]
    book_id: int
    start_date: datetime


class ChatMessageRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    conversation_id: int
    emit_date: datetime
    author: str
    content: str


class ConversationChatRequest(BaseModel):
    question: str
    k: int = 5
    stream: bool = False


class ToolStep(BaseModel):
    tool: str
    args: dict
    result: str


class ConversationChatResponse(BaseModel):
    conversation: ConversationRead
    message: ChatMessageRead
    answer: str
    sources: list[dict]
    tool_steps: list[ToolStep] = []


class MessageChatResponse(BaseModel):
    message: ChatMessageRead
    answer: str
    sources: list[dict]
    tool_steps: list[ToolStep] = []


class TimelineMessage(BaseModel):
    type: Literal["message"] = "message"
    id: int
    author: str
    content: str
    at: datetime


class TimelineToolCall(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    id: int
    tool: str
    args: dict
    result: str
    at: datetime


TimelineEvent = Annotated[Union[TimelineMessage, TimelineToolCall], Field(discriminator="type")]
