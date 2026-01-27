"""Structured logging configuration for Flask applications.

Provides JSON-formatted logs with request context for better observability.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from flask import Flask, g, has_request_context, request, session


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter with request context."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        if has_request_context():
            log_data['request_id'] = getattr(g, 'request_id', None)
            log_data['user_id'] = getattr(g, 'user_id', None)
            log_data['path'] = request.path
            log_data['method'] = request.method

        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)

        return json.dumps(log_data, ensure_ascii=False)

def configure_logging(app: Flask) -> Flask:
    """Configure structured logging for the Flask application.

    Args:
        app: Flask application instance

    Returns:
        The configured Flask application
    """
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())

    logging.root.handlers = [handler]
    logging.root.setLevel(logging.INFO)

    @app.before_request
    def inject_request_context() -> None:
        g.request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        user = session.get('user')
        if user:
            g.user_id = user.get('member_id')

    return app
