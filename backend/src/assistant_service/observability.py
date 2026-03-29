"""Langfuse observability helpers."""

from __future__ import annotations

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from assistant_service.config import settings

_langfuse_client: Langfuse | None = None


def init_langfuse() -> None:
    """Initialize the global Langfuse client from settings.

    Call once at application startup (e.g. in the FastAPI lifespan handler).
    If keys are not configured, this is a no-op and tracing stays disabled.
    """
    global _langfuse_client
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return
    _langfuse_client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def get_langfuse_handler(
    session_id: str | None = None,
    user_id: str | None = None,
    device_id: str | None = None,
    model_metadata: dict | None = None,
) -> tuple[CallbackHandler, dict] | tuple[None, dict]:
    """Return a (CallbackHandler, metadata) pair for use in graph.astream() config.

    Returns (None, {}) when Langfuse is not configured so callers can always
    unpack the tuple without branching.

    The metadata dict carries ``langfuse_session_id`` / ``langfuse_user_id``
    which Langfuse v3+ reads from the LangChain run metadata to attach those
    attributes to the trace. ``device_id`` is stored as plain metadata so
    developers can correlate a trace back to a specific browser/device.
    Additional model metadata (e.g. model names and parameters) can be passed
    via ``model_metadata`` and will be merged in.

    Usage::

        handler, lf_metadata = get_langfuse_handler(
            session_id=body.thread_id,
            user_id=user_id,
            device_id=device_id,
            model_metadata={"agent_model": settings.agent_model},
        )
        callbacks = [handler] if handler else []
        await graph.astream(
            ...,
            config={"callbacks": callbacks, "metadata": lf_metadata},
        )
    """
    if _langfuse_client is None:
        return None, {}

    metadata: dict = {}
    if session_id:
        metadata["langfuse_session_id"] = session_id
    if user_id:
        metadata["langfuse_user_id"] = user_id
    if device_id:
        metadata["device_id"] = device_id
    if model_metadata:
        metadata.update(model_metadata)

    return CallbackHandler(), metadata
