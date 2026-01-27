"""Audit logging for admin operations.

Provides structured audit trail for administrative actions.
"""

import logging
from typing import Any, Dict, Optional, Union

from flask import request, session

logger = logging.getLogger(__name__)


def log_admin_action(
    action: str,
    resource_type: str,
    resource_id: Optional[Union[int, str]],
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Log admin actions for audit trail.

    Args:
        action: Action type (e.g., 'create', 'update', 'delete', 'login')
        resource_type: Type of resource (e.g., 'hero_image', 'survey', 'admin')
        resource_id: ID of the resource (or None for list operations)
        details: Additional details dictionary
    """
    logger.info(
        "Admin action: %s %s",
        action,
        resource_type,
        extra={
            'extra_fields': {
                'audit': True,
                'action': action,
                'resource_type': resource_type,
                'resource_id': resource_id,
                'admin_session': session.get('is_admin', False),
                'ip_address': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', 'Unknown'),
                'details': details or {},
            }
        },
    )
