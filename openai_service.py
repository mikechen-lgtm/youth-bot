"""OpenAI API service with File Search RAG support.

Provides vector store management and RAG-based content generation.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger(__name__)

# 導入時間工具（保留用於非活動查詢的時間問題）
try:
    from time_tools import TIME_TOOLS_DEFINITIONS, execute_time_tool
    TIME_TOOLS_AVAILABLE = True
    logger.info("時間工具模組載入成功")
except ImportError as e:
    TIME_TOOLS_AVAILABLE = False
    logger.warning("時間工具模組載入失敗: %s", e)

# 導入資料庫工具
try:
    from database_tools import DATABASE_TOOLS_DEFINITIONS, execute_database_tool
    DATABASE_TOOLS_AVAILABLE = True
    logger.info("資料庫工具模組載入成功")
except ImportError as e:
    DATABASE_TOOLS_AVAILABLE = False
    logger.warning("資料庫工具模組載入失敗: %s", e)

# 合併所有工具定義（優先使用資料庫工具）
ALL_TOOLS_DEFINITIONS = []
if DATABASE_TOOLS_AVAILABLE:
    ALL_TOOLS_DEFINITIONS.extend(DATABASE_TOOLS_DEFINITIONS)
# 時間工具作為備用（僅用於非活動查詢的時間問題）
# if TIME_TOOLS_AVAILABLE:
#     ALL_TOOLS_DEFINITIONS.extend(TIME_TOOLS_DEFINITIONS)

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
    return os.getenv("OPENAI_MODEL", "").strip() or default_model


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
    """Create a new vector store for File Search."""
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
    """Poll vector store files until the given file is processed."""
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
    """Upload a file to the vector store with polling for completion."""
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
        except (APITimeoutError, APIError, FileNotFoundError) as e:
            logger.error("Error uploading %s: %s", rag_file.name, e)
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
    """Delete the vector store."""
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
        parts = [_get_attr_or_key(part, "text") for part in content]
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


def _process_function_calls(
    messages: List[Dict[str, Any]],
    resolved_model: str,
) -> Generator[Dict[str, Any], None, List[Dict[str, Any]]]:
    """
    執行 function calling 階段，處理時間工具調用

    Yields:
        function_call 事件（用於前端通知）

    Returns:
        更新後的 messages 列表
    """
    response = OPENAI_CLIENT.chat.completions.create(
        model=resolved_model,
        messages=messages,
        tools=ALL_TOOLS_DEFINITIONS if ALL_TOOLS_DEFINITIONS else TIME_TOOLS_DEFINITIONS,
        tool_choice="auto",
        max_tokens=50,
        temperature=0.3,
    )

    assistant_message = response.choices[0].message
    if not assistant_message.tool_calls:
        return messages

    logger.info("檢測到 %d 個工具調用", len(assistant_message.tool_calls))

    # 添加助手消息（包含 tool calls）
    messages.append({
        "role": "assistant",
        "content": assistant_message.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in assistant_message.tool_calls
        ],
    })

    # 執行每個 tool call
    for tool_call in assistant_message.tool_calls:
        function_name = tool_call.function.name
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            arguments = {}

        logger.info("執行工具: %s，參數: %s", function_name, arguments)

        # 根據函數名稱分派到對應的執行函數
        if function_name in ["get_past_activities", "get_recent_activities"]:
            result = execute_database_tool(function_name, arguments)
        elif function_name in ["get_current_time_info", "calculate_date_range"]:
            # 時間工具已整合進資料庫工具，保留此處以防萬一
            result = execute_time_tool(function_name, arguments) if TIME_TOOLS_AVAILABLE else {
                "error": "時間工具已停用，請使用 get_recent_activities 或 get_past_activities"
            }
        else:
            result = {"error": f"未知的工具函數: {function_name}"}

        yield {
            "type": "function_call",
            "content": {"function": function_name, "arguments": arguments, "result": result},
        }

        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result, ensure_ascii=False),
        })

    return messages


def _clean_messages_for_responses_api(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    清理 messages 以兼容 Responses API

    Responses API 不支持：
    - tool_calls 字段
    - role="tool" 的消息

    此函數將 function calling 的結果合併到 assistant 消息中
    """
    cleaned = []

    for msg in messages:
        role = msg.get("role")

        # 過濾掉 tool 角色的消息
        if role == "tool":
            continue

        # 處理包含 tool_calls 的 assistant 消息
        if role == "assistant" and "tool_calls" in msg:
            # 移除 tool_calls，只保留 content
            cleaned_msg = {
                "role": "assistant",
                "content": msg.get("content") or "",
            }
            cleaned.append(cleaned_msg)
        else:
            # 保留其他消息
            cleaned.append(msg)

    return cleaned


def _stream_rag_response(
    messages: List[Dict[str, Any]],
    resolved_model: str,
    vector_store_id: str,
) -> Generator[Dict[str, Any], None, None]:
    """執行 RAG streaming 生成"""
    # 清理 messages 以兼容 Responses API
    cleaned_messages = _clean_messages_for_responses_api(messages)

    with OPENAI_CLIENT.responses.stream(
        model=resolved_model,
        input=cleaned_messages,
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


def generate_with_rag_stream(
    query: str,
    system_prompt: str,
    chat_history: List[Dict[str, str]],
    model: str = "gpt-4o-mini",
) -> Generator[Dict[str, Any], None, None]:
    """Stream content generation using OpenAI File Search with optional function calling.

    使用兩階段策略：
    1. 階段1：使用 Chat Completions API 檢查並執行 function calling
    2. 階段2：使用 Responses API 進行 streaming 生成

    Yields:
        Dict with 'type' ('text', 'function_call', 'sources', 'end') and 'content'
    """
    if not OPENAI_CLIENT:
        raise RuntimeError("OpenAI client not initialized")

    vector_store_id = get_rag_store_name()
    if not vector_store_id:
        raise RuntimeError("Vector store not initialized")

    messages = _build_input(system_prompt, chat_history, query)
    resolved_model = _resolve_model(model)

    # 階段1：Function Calling（如果啟用且時間工具可用）
    enable_function_calling = os.getenv("ENABLE_FUNCTION_CALLING", "true").lower() == "true"

    if enable_function_calling and TIME_TOOLS_AVAILABLE:
        try:
            logger.info("階段1：檢查 function calling 需求")
            fc_generator = _process_function_calls(messages, resolved_model)

            # 消費 generator 並 yield function_call 事件
            try:
                while True:
                    event = next(fc_generator)
                    yield event
            except StopIteration as e:
                messages = e.value if e.value else messages

        except Exception as e:
            logger.warning("Function calling 失敗，回退到標準模式: %s", e)

    # 階段2：RAG Streaming
    logger.info("階段2：開始 streaming 生成")
    yield from _stream_rag_response(messages, resolved_model, vector_store_id)


def generate_with_rag(
    query: str,
    system_prompt: str,
    chat_history: List[Dict[str, str]],
    model: str = "gpt-4o-mini",
) -> Dict[str, Any]:
    """Non-streaming content generation using OpenAI File Search."""
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
