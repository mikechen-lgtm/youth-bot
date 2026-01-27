"""Input validation decorators for Flask routes.

Provides reusable validation decorators for request data.
"""

import logging
from functools import wraps
from typing import Any, Callable, TypeVar

from flask import Response, current_app, jsonify, request
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Configuration constants
MAX_MESSAGE_LENGTH = 4000  # Maximum characters per message
MAX_CHAT_HISTORY = 50      # Maximum messages per session

F = TypeVar('F', bound=Callable[..., Any])


def validate_message_input(f: F) -> F:
    """Validate chat message input.

    Checks for:
    - JSON content type
    - Non-empty message
    - Message length limit
    - Session history limit (optional)
    """
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Response:
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400

        data = request.get_json() or {}
        message = (data.get('message') or '').strip()

        if not message:
            logger.warning("Empty message received")
            return jsonify({'error': '訊息不能為空'}), 400

        if len(message) > MAX_MESSAGE_LENGTH:
            logger.warning("Message too long: %d characters", len(message))
            return jsonify({
                'error': f'訊息過長（最多 {MAX_MESSAGE_LENGTH} 字元）'
            }), 400

        session_id = data.get('session_id')
        if session_id:
            mysql_engine = getattr(current_app, 'deps', None)
            mysql_engine = getattr(mysql_engine, 'mysql_engine', None) if mysql_engine else None

            if mysql_engine:
                try:
                    with mysql_engine.connect() as conn:
                        history_count = conn.execute(
                            text("SELECT COUNT(*) FROM chat_messages WHERE session_id = :session_id"),
                            {"session_id": session_id}
                        ).scalar()

                        if history_count and history_count > MAX_CHAT_HISTORY:
                            logger.warning("Session %s exceeded message limit", session_id)
                            return jsonify({
                                'error': '聊天記錄已達上限，請開始新對話'
                            }), 400
                except Exception as e:
                    logger.error("Failed to check chat history: %s", e)

        return f(*args, **kwargs)

    return decorated  # type: ignore[return-value]
