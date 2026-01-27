"""OpenAI API service with File Search RAG support.

Provides vector store management and RAG-based content generation.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger(__name__)

# Global state
OPENAI_CLIENT: Optional[OpenAI] = None
_vector_store_id: Optional[str] = None

load_dotenv()

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if _OPENAI_API_KEY:
    OPENAI_CLIENT = OpenAI(api_key=_OPENAI_API_KEY)
    logger.info("OpenAI client initialized")
else:
    logger.warning("OPENAI_API_KEY not configured")


def _resolve_vector_store_id() -> Optional[str]:
    """Get vector store ID from environment variables."""
    return os.getenv("RAG_VECTOR_STORE_ID") or os.getenv("RAG_STORE_NAME")


def _resolve_model(default_model: str) -> str:
    """Get model name from environment or use default."""
    env_model = os.getenv("OPENAI_MODEL", "").strip()
    return env_model or default_model


def _is_cloud_run() -> bool:
    """Check if running in Google Cloud Run environment."""
    return bool(
        os.getenv("K_SERVICE") or
        os.getenv("K_REVISION") or
        os.getenv("CLOUD_RUN_JOB")
    )


def _get_attr_or_key(obj: Any, key: str, default: Any = None) -> Any:
    """Get attribute or dictionary key from an object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def create_rag_store(display_name: str) -> str:
    """Create a new vector store for File Search.

    Args:
        display_name: Name for the vector store

    Returns:
        Vector store ID

    Raises:
        RuntimeError: If client not initialized or creation fails
    """
    if not OPENAI_CLIENT:
        raise RuntimeError("OpenAI client not initialized")

    store = OPENAI_CLIENT.vector_stores.create(name=display_name)
    store_id = _get_attr_or_key(store, "id")
    if not store_id:
        raise RuntimeError("Failed to create vector store: id is missing")

    logger.info("Created vector store: %s", store_id)
    return store_id


def _wait_for_vector_store_file(
    vector_store_id: str,
    file_id: str,
    timeout_s: int = 300,
    poll_interval: int = 2,
) -> None:
    """Poll vector store files until the given file is processed.

    Args:
        vector_store_id: Vector store ID
        file_id: File ID to wait for
        timeout_s: Maximum wait time in seconds
        poll_interval: Time between polls in seconds

    Raises:
        RuntimeError: If file processing fails
        TimeoutError: If timeout exceeded
    """
    if not OPENAI_CLIENT:
        raise RuntimeError("OpenAI client not initialized")

    deadline = time.time() + timeout_s

    while time.time() < deadline:
        listing = OPENAI_CLIENT.vector_stores.files.list(vector_store_id=vector_store_id)
        items = _get_attr_or_key(listing, "data") or []

        for item in items:
            if _get_attr_or_key(item, "id") == file_id:
                status = _get_attr_or_key(item, "status")
                if status == "completed":
                    return
                if status == "failed":
                    raise RuntimeError(f"Vector store file failed: {file_id}")
                break

        time.sleep(poll_interval)

    raise TimeoutError(f"Timed out waiting for vector store file: {file_id}")


def upload_file_to_rag_store(vector_store_id: str, file_path: str) -> None:
    """Upload a file to the vector store with polling for completion.

    Args:
        vector_store_id: Target vector store ID
        file_path: Path to the file to upload

    Raises:
        RuntimeError: If client not initialized or upload fails
    """
    if not OPENAI_CLIENT:
        raise RuntimeError("OpenAI client not initialized")

    with open(file_path, "rb") as file_handle:
        uploaded = OPENAI_CLIENT.files.create(file=file_handle, purpose="assistants")

    file_id = _get_attr_or_key(uploaded, "id")
    if not file_id:
        raise RuntimeError("Failed to upload file: id is missing")

    OPENAI_CLIENT.vector_stores.files.create(vector_store_id=vector_store_id, file_id=file_id)
    _wait_for_vector_store_file(vector_store_id, file_id)

    logger.info("Uploaded %s to vector store %s", file_path, vector_store_id)


def initialize_rag_store(display_name: str = "TaoyuanYouthBureauKB") -> Optional[str]:
    """Initialize vector store and upload default documents.

    Args:
        display_name: Name for the vector store

    Returns:
        Vector store ID or None if initialization fails
    """
    global _vector_store_id

    persisted_id = _resolve_vector_store_id()
    if persisted_id:
        _vector_store_id = persisted_id
        logger.info("Using existing vector store: %s", _vector_store_id)
        return _vector_store_id

    auto_bootstrap = os.getenv("RAG_AUTO_BOOTSTRAP", "").lower() in {"1", "true", "yes"}
    if _is_cloud_run() and not auto_bootstrap:
        logger.warning(
            "No RAG_VECTOR_STORE_ID provided; skipping auto-bootstrap on Cloud Run. "
            "Set RAG_VECTOR_STORE_ID or enable RAG_AUTO_BOOTSTRAP=true."
        )
        return None

    _vector_store_id = create_rag_store(display_name)
    _upload_rag_files(_vector_store_id)

    logger.info("Vector store initialized: %s", _vector_store_id)
    return _vector_store_id


def _upload_rag_files(vector_store_id: str) -> None:
    """Upload RAG files from the data directory to the vector store."""
    from openai import APIError, APITimeoutError

    rag_data_dir = os.getenv("RAG_DATA_DIR", "rag_data")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    rag_path = Path(base_dir) / rag_data_dir

    if not rag_path.exists():
        logger.warning("RAG data directory not found: %s", rag_path)
        return

    supported_exts = {".md", ".txt", ".pdf", ".html", ".json"}
    rag_files = sorted(
        p for p in rag_path.iterdir()
        if p.is_file() and p.suffix.lower() in supported_exts
    )
    logger.info("Found %d RAG files in %s", len(rag_files), rag_path)

    upload_failures = 0
    for rag_file in rag_files:
        try:
            upload_file_to_rag_store(vector_store_id, str(rag_file))
            logger.info("Successfully uploaded %s", rag_file.name)
        except APITimeoutError:
            logger.error("Timeout uploading %s, skipping", rag_file.name)
            upload_failures += 1
        except APIError as e:
            logger.error("OpenAI API error uploading %s: %s", rag_file.name, e)
            upload_failures += 1
        except FileNotFoundError:
            logger.error("File not found: %s", rag_file)
            upload_failures += 1
        except Exception as exc:
            logger.error("Unexpected error uploading %s: %s", rag_file.name, exc, exc_info=True)
            upload_failures += 1

    if upload_failures > 0:
        logger.warning("%d/%d files failed to upload", upload_failures, len(rag_files))
        if upload_failures == len(rag_files):
            logger.error("All RAG files failed to upload - vector store may be empty")


def get_rag_store_name() -> Optional[str]:
    """Get the current vector store ID."""
    return _vector_store_id


def delete_rag_store(vector_store_id: Optional[str] = None) -> None:
    """Delete the vector store.

    Args:
        vector_store_id: ID of the store to delete, or None to use current

    Raises:
        RuntimeError: If OpenAI client not initialized
    """
    if not OPENAI_CLIENT:
        raise RuntimeError("OpenAI client not initialized")

    store_id = vector_store_id or _vector_store_id
    if not store_id:
        logger.warning("No vector store to delete")
        return

    OPENAI_CLIENT.vector_stores.delete(store_id)
    logger.info("Deleted vector store: %s", store_id)


def _build_input(
    system_prompt: str,
    chat_history: List[Dict[str, str]],
    query: str,
) -> List[Dict[str, str]]:
    """Build message input for OpenAI API."""
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    for msg in chat_history:
        role = msg.get("role")
        content = msg.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": query})
    return messages


def _extract_text_from_content(content: Any) -> Optional[str]:
    """Extract text from content which may be a string, list, or object."""
    if not content:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            _get_attr_or_key(part, "text")
            for part in content
        ]
        filtered = [p for p in parts if p]
        return "\n".join(filtered) if filtered else None
    return None


def _extract_sources(response: Any) -> List[Dict[str, Any]]:
    """Extract source references from file search results."""
    sources: List[Dict[str, Any]] = []
    output = _get_attr_or_key(response, "output") or []

    for item in output:
        if _get_attr_or_key(item, "type") != "file_search_call":
            continue

        results = _get_attr_or_key(item, "results") or []
        for result in results:
            text = (
                _get_attr_or_key(result, "text") or
                _extract_text_from_content(_get_attr_or_key(result, "content"))
            )
            if text:
                sources.append({"text": text})

    return sources


def _extract_output_text(response: Any) -> str:
    """Extract output text from response."""
    text = _get_attr_or_key(response, "output_text")
    if text:
        return text

    output = _get_attr_or_key(response, "output") or []
    parts: List[str] = []

    for item in output:
        if _get_attr_or_key(item, "type") == "output_text":
            item_text = (
                _get_attr_or_key(item, "text") or
                _extract_text_from_content(_get_attr_or_key(item, "content"))
            )
            if item_text:
                parts.append(item_text)

    return "".join(parts)


def generate_with_rag_stream(
    query: str,
    system_prompt: str,
    chat_history: List[Dict[str, str]],
    model: str = "gpt-4o-mini",
) -> Generator[Dict[str, Any], None, None]:
    """Stream content generation using OpenAI File Search.

    Args:
        query: User query
        system_prompt: System prompt for the model
        chat_history: Previous conversation messages
        model: Model name to use

    Yields:
        Dict with 'type' ('text', 'sources', 'end') and 'content'

    Raises:
        RuntimeError: If client or vector store not initialized
    """
    if not OPENAI_CLIENT:
        raise RuntimeError("OpenAI client not initialized")

    vector_store_id = get_rag_store_name()
    if not vector_store_id:
        raise RuntimeError("Vector store not initialized")

    messages = _build_input(system_prompt, chat_history, query)
    resolved_model = _resolve_model(model)

    with OPENAI_CLIENT.responses.stream(
        model=resolved_model,
        input=messages,
        tools=[{"type": "file_search", "vector_store_ids": [vector_store_id]}],
        include=["file_search_call.results"],
    ) as stream:
        for event in stream:
            if _get_attr_or_key(event, "type") == "response.output_text.delta":
                delta = _get_attr_or_key(event, "delta")
                if delta:
                    yield {"type": "text", "content": delta}

        response = stream.get_final_response()

    if response:
        sources = _extract_sources(response)
        if sources:
            yield {"type": "sources", "content": sources}

    yield {"type": "end", "content": ""}


def generate_with_rag(
    query: str,
    system_prompt: str,
    chat_history: List[Dict[str, str]],
    model: str = "gpt-4o-mini",
) -> Dict[str, Any]:
    """Non-streaming content generation using OpenAI File Search.

    Args:
        query: User query
        system_prompt: System prompt for the model
        chat_history: Previous conversation messages
        model: Model name to use

    Returns:
        Dict with 'text' and 'sources' keys

    Raises:
        RuntimeError: If client or vector store not initialized
    """
    if not OPENAI_CLIENT:
        raise RuntimeError("OpenAI client not initialized")

    vector_store_id = get_rag_store_name()
    if not vector_store_id:
        raise RuntimeError("Vector store not initialized")

    messages = _build_input(system_prompt, chat_history, query)

    response = OPENAI_CLIENT.responses.create(
        model=_resolve_model(model),
        input=messages,
        tools=[{"type": "file_search", "vector_store_ids": [vector_store_id]}],
        include=["file_search_call.results"],
    )

    return {
        "text": _extract_output_text(response),
        "sources": _extract_sources(response),
    }
