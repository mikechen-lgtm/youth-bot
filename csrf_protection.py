"""CSRF Protection Module for Flask Application.

Provides token-based CSRF protection with secure token generation and validation.
"""

import hmac
import secrets
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union

from flask import Request, Response, jsonify, request, session

F = TypeVar('F', bound=Callable[..., Any])


class CSRFProtection:
    """CSRF Token generator and validator."""

    def __init__(self, secret_key: Union[str, bytes]) -> None:
        """Initialize CSRF protection with a secret key.

        Args:
            secret_key: Secret key for token validation
        """
        self.secret_key = secret_key.encode() if isinstance(secret_key, str) else secret_key

    def generate_token(self) -> str:
        """Generate a new CSRF token and store it in session.

        Returns:
            CSRF token string
        """
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
        return token

    def get_token(self) -> str:
        """Get existing CSRF token from session or generate a new one.

        Returns:
            CSRF token string
        """
        token = session.get("csrf_token")
        if not token:
            token = self.generate_token()
        return token

    def validate_token(self, token: Optional[str]) -> bool:
        """Validate a CSRF token against the session token.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            token: Token to validate

        Returns:
            True if token is valid, False otherwise
        """
        if not token:
            return False

        session_token = session.get("csrf_token")
        if not session_token:
            return False

        return hmac.compare_digest(token, session_token)

    def extract_token_from_request(self, req: Request) -> Optional[str]:
        """Extract CSRF token from request headers, form data, or JSON body.

        Checks in order: X-CSRF-Token header, form data, JSON body.

        Args:
            req: Flask request object

        Returns:
            CSRF token string or None if not found
        """
        # Check X-CSRF-Token header first (recommended)
        token = req.headers.get("X-CSRF-Token")
        if token:
            return token

        # Fall back to form data
        if req.form:
            token = req.form.get("csrf_token")
            if token:
                return token

        # Check JSON body
        if req.is_json:
            data = req.get_json(silent=True)
            if isinstance(data, dict):
                return data.get("csrf_token")

        return None


def csrf_protect(f: F) -> F:
    """Decorator to protect routes with CSRF token validation.

    Skips validation for GET, HEAD, and OPTIONS requests.

    Usage:
        @app.post("/api/admin/login")
        @csrf_protect
        def admin_login():
            ...
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Response:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return f(*args, **kwargs)

        from flask import current_app
        csrf = getattr(current_app, "csrf_protection", None)
        if not csrf:
            return jsonify({
                "success": False,
                "error": "CSRF protection not configured"
            }), 500

        token = csrf.extract_token_from_request(request)
        if not csrf.validate_token(token):
            return jsonify({
                "success": False,
                "error": "Invalid or missing CSRF token"
            }), 403

        return f(*args, **kwargs)

    return decorated_function  # type: ignore[return-value]


def csrf_exempt(f: F) -> F:
    """Decorator to exempt a route from CSRF protection.

    Usage:
        @app.post("/api/webhook")
        @csrf_exempt
        def webhook():
            ...
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Response:
        return f(*args, **kwargs)

    decorated_function._csrf_exempt = True  # type: ignore[attr-defined]
    return decorated_function  # type: ignore[return-value]
