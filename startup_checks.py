"""Startup health checks with fail-fast option.

Provides configurable health checks for application startup validation.
"""

import logging
from typing import Any, Callable, Dict, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class StartupHealthCheck:
    """Run health checks on application startup."""

    def __init__(self) -> None:
        self.checks: Dict[str, Callable[[], None]] = {}

    def add_check(self, name: str, check_fn: Callable[[], None]) -> None:
        """Add a health check function."""
        self.checks[name] = check_fn

    def run_all(self, fail_fast: bool = False) -> Dict[str, str]:
        """Run all health checks.

        Args:
            fail_fast: If True, raise RuntimeError on first failure

        Returns:
            Dictionary mapping check names to result strings
        """
        results: Dict[str, str] = {}

        for name, check_fn in self.checks.items():
            try:
                check_fn()
                results[name] = 'OK'
                logger.info("Startup check '%s': OK", name)
            except Exception as e:
                error_msg = f"FAIL: {e}"
                results[name] = error_msg
                logger.error("Startup check '%s': %s", name, error_msg)

                if fail_fast:
                    raise RuntimeError(f"Startup check failed: {name} - {e}") from e

        return results


def create_health_checks(
    mysql_engine: Engine,
    openai_client: Optional[Any],
    vector_store_id: Optional[str],
) -> StartupHealthCheck:
    """Create standard health checks for the application.

    Args:
        mysql_engine: SQLAlchemy database engine
        openai_client: OpenAI client instance
        vector_store_id: Vector store ID for RAG

    Returns:
        Configured StartupHealthCheck instance
    """
    health = StartupHealthCheck()

    def check_database() -> None:
        with mysql_engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            if result != 1:
                raise RuntimeError("Database query returned unexpected result")

    health.add_check('database', check_database)

    def check_openai() -> None:
        if openai_client is None:
            raise RuntimeError("OpenAI client not initialized")
        openai_client.models.list()

    health.add_check('openai_api', check_openai)

    def check_rag_store() -> None:
        if vector_store_id is None:
            raise RuntimeError("RAG vector store ID not set")
        # 使用正確的 API 路徑（不通過 beta）
        store = openai_client.vector_stores.retrieve(vector_store_id)
        file_counts = getattr(store, 'file_counts', None)
        if file_counts and getattr(file_counts, 'total', 0) == 0:
            logger.warning("RAG vector store has no files")

    health.add_check('rag_store', check_rag_store)

    return health
