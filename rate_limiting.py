"""Rate limiting with in-memory storage.

Provides request rate limiting to prevent abuse and ensure fair usage.
Note: In-memory storage resets on app restart and does not work across
multiple instances. For production at scale, consider using Redis.
"""

import logging

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

logger = logging.getLogger(__name__)

# Default rate limits
DEFAULT_LIMITS = ["200 per day", "50 per hour"]


def create_limiter(app: Flask) -> Limiter:
    """Create rate limiter with in-memory storage.

    Args:
        app: Flask application instance

    Returns:
        Configured Limiter instance
    """
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        storage_uri="memory://",
        default_limits=DEFAULT_LIMITS,
        headers_enabled=True,
    )

    logger.info("Rate limiter initialized with in-memory storage")

    return limiter
