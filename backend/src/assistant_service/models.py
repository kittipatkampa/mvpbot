from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    thread_id: str = Field(..., description="Thread UUID")
    message: str = Field(..., description="User message text")
    regenerate: bool = Field(
        default=False,
        description="If true, drop the last assistant reply and re-run from the latest user turn without inserting a new user message.",
    )


class ThreadCreateResponse(BaseModel):
    thread_id: str


class ThreadCreateBody(BaseModel):
    id: str | None = Field(
        default=None,
        description="Optional client-generated id (assistant-ui remote id)",
    )


class ThreadOut(BaseModel):
    id: str
    title: str
    updated_at: str
    archived: bool = False


class ThreadPatchRequest(BaseModel):
    title: str | None = None
    archived: bool | None = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    reasoning: str | None = None
    created_at: str
