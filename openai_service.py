"""OpenAI API service with File Search RAG support."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator

from openai import OpenAI
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Global state
OPENAI_CLIENT: Optional[OpenAI] = None
_vector_store_id: Optional[str] = None

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    OPENAI_CLIENT = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("OpenAI client initialized")
else:
    logger.warning("OPENAI_API_KEY not configured")


def _resolve_vector_store_id() -> Optional[str]:
    return os.getenv("RAG_VECTOR_STORE_ID") or os.getenv("RAG_STORE_NAME")


def _resolve_model(passed_model: str) -> str:
    env_model = os.getenv("OPENAI_MODEL")
    if env_model:
        stripped = env_model.strip()
        if stripped:
            return stripped
    return passed_model


def _is_cloud_run() -> bool:
    return bool(os.getenv("K_SERVICE") or os.getenv("K_REVISION") or os.getenv("CLOUD_RUN_JOB"))


def create_rag_store(display_name: str) -> str:
    """Create a new vector store for File Search."""
    client = OPENAI_CLIENT
    if not client:
        raise RuntimeError("OpenAI client not initialized")

    store = client.vector_stores.create(name=display_name)
    store_id = getattr(store, "id", None) or (store.get("id") if isinstance(store, dict) else None)
    if not store_id:
        raise RuntimeError("Failed to create vector store: id is missing")

    logger.info("Created vector store: %s", store_id)
    return store_id


def _wait_for_vector_store_file(vector_store_id: str, file_id: str, timeout_s: int = 300) -> None:
    """Poll vector store files until the given file is processed."""
    client = OPENAI_CLIENT
    if not client:
        raise RuntimeError("OpenAI client not initialized")

    deadline = time.time() + timeout_s
    while True:
        listing = client.vector_stores.files.list(vector_store_id=vector_store_id)
        items = getattr(listing, "data", None) or (listing.get("data") if isinstance(listing, dict) else [])
        target = next((item for item in items if (getattr(item, "id", None) or item.get("id")) == file_id), None)
        if target:
            status = getattr(target, "status", None) or (target.get("status") if isinstance(target, dict) else None)
            if status == "completed":
                return
            if status == "failed":
                raise RuntimeError(f"Vector store file failed: {file_id}")
        if time.time() > deadline:
            raise TimeoutError(f"Timed out waiting for vector store file: {file_id}")
        time.sleep(2)


def upload_file_to_rag_store(vector_store_id: str, file_path: str) -> None:
    """Upload a file to the vector store with polling for completion."""
    client = OPENAI_CLIENT
    if not client:
        raise RuntimeError("OpenAI client not initialized")

    with open(file_path, "rb") as file_handle:
        uploaded = client.files.create(file=file_handle, purpose="assistants")

    file_id = getattr(uploaded, "id", None) or (uploaded.get("id") if isinstance(uploaded, dict) else None)
    if not file_id:
        raise RuntimeError("Failed to upload file: id is missing")

    client.vector_stores.files.create(vector_store_id=vector_store_id, file_id=file_id)
    _wait_for_vector_store_file(vector_store_id, file_id)

    logger.info("Uploaded %s to vector store %s", file_path, vector_store_id)


def initialize_rag_store(display_name: str = "TaoyuanYouthBureauKB") -> Optional[str]:
    """Initialize vector store and upload default documents."""
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

    rag_data_dir = os.getenv("RAG_DATA_DIR", "rag_data")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    rag_path = Path(base_dir) / rag_data_dir

    if rag_path.exists():
        md_files = list(rag_path.glob("*.md"))
        logger.info("Found %s markdown files in %s", len(md_files), rag_path)
        for md_file in md_files:
            try:
                upload_file_to_rag_store(_vector_store_id, str(md_file))
            except Exception as exc:
                logger.error("Failed to upload %s: %s", md_file, exc)
    else:
        logger.warning("RAG data directory not found: %s", rag_path)

    logger.info("Vector store initialized: %s", _vector_store_id)
    return _vector_store_id


def get_rag_store_name() -> Optional[str]:
    """Get the current vector store id."""
    return _vector_store_id


def delete_rag_store(vector_store_id: Optional[str] = None) -> None:
    """Delete the vector store."""
    client = OPENAI_CLIENT
    if not client:
        raise RuntimeError("OpenAI client not initialized")

    store_id = vector_store_id or _vector_store_id
    if not store_id:
        logger.warning("No vector store to delete")
        return

    client.vector_stores.delete(store_id)
    logger.info("Deleted vector store: %s", store_id)


def _build_input(system_prompt: str, chat_history: List[Dict[str, str]], query: str) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for msg in chat_history:
        role = msg.get("role")
        content = msg.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": query})
    return messages


def _extract_text_from_content(content: Any) -> Optional[str]:
    if not content:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for part in content:
            text = None
            if isinstance(part, dict):
                text = part.get("text")
            else:
                text = getattr(part, "text", None)
            if text:
                parts.append(text)
        if parts:
            return "\n".join(parts)
    return None


def _extract_sources(response: Any) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    output = getattr(response, "output", None) or (response.get("output") if isinstance(response, dict) else [])
    for item in output or []:
        item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
        if item_type != "file_search_call":
            continue
        results = getattr(item, "results", None) or (item.get("results") if isinstance(item, dict) else None) or []
        for result in results:
            text = None
            if isinstance(result, dict):
                text = result.get("text") or _extract_text_from_content(result.get("content"))
            else:
                text = getattr(result, "text", None) or _extract_text_from_content(getattr(result, "content", None))
            if text:
                sources.append({"text": text})
    return sources


def _extract_output_text(response: Any) -> str:
    text = getattr(response, "output_text", None) or (response.get("output_text") if isinstance(response, dict) else None)
    if text:
        return text
    output = getattr(response, "output", None) or (response.get("output") if isinstance(response, dict) else [])
    parts: List[str] = []
    for item in output or []:
        item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
        if item_type == "output_text":
            item_text = None
            if isinstance(item, dict):
                item_text = item.get("text") or _extract_text_from_content(item.get("content"))
            else:
                item_text = getattr(item, "text", None) or _extract_text_from_content(getattr(item, "content", None))
            if item_text:
                parts.append(item_text)
    return "".join(parts)


def generate_with_rag_stream(
    query: str,
    system_prompt: str,
    chat_history: List[Dict[str, str]],
    model: str = "gpt-4o-mini",
) -> Generator[Dict[str, Any], None, None]:
    """
    Stream content generation using OpenAI File Search.

    Yields:
        Dict with 'type' ('text', 'sources', 'end') and 'content'
    """
    client = OPENAI_CLIENT
    if not client:
        raise RuntimeError("OpenAI client not initialized")

    vector_store_id = get_rag_store_name()
    if not vector_store_id:
        raise RuntimeError("Vector store not initialized")

    messages = _build_input(system_prompt, chat_history, query)
    sources: List[Dict[str, Any]] = []
    resolved_model = _resolve_model(model)

    with client.responses.stream(
        model=resolved_model,
        input=messages,
        tools=[{"type": "file_search", "vector_store_ids": [vector_store_id]}],
        include=["file_search_call.results"],
    ) as stream:
        for event in stream:
            event_type = getattr(event, "type", None) or (event.get("type") if isinstance(event, dict) else None)
            if event_type == "response.output_text.delta":
                delta = getattr(event, "delta", None) or (event.get("delta") if isinstance(event, dict) else None)
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
    """
    Non-streaming content generation using OpenAI File Search.

    Returns:
        Dict with 'text' and 'sources' keys
    """
    client = OPENAI_CLIENT
    if not client:
        raise RuntimeError("OpenAI client not initialized")

    vector_store_id = get_rag_store_name()
    if not vector_store_id:
        raise RuntimeError("Vector store not initialized")

    messages = _build_input(system_prompt, chat_history, query)

    response = client.responses.create(
        model=_resolve_model(model),
        input=messages,
        tools=[{"type": "file_search", "vector_store_ids": [vector_store_id]}],
        include=["file_search_call.results"],
    )

    return {
        "text": _extract_output_text(response),
        "sources": _extract_sources(response),
    }
