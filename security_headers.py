"""Security headers configuration for Flask application.

Implements defense-in-depth security headers including:
- HSTS (HTTP Strict Transport Security)
- CSP (Content Security Policy)
- X-Frame-Options
- X-Content-Type-Options
- Referrer-Policy
- Permissions-Policy
"""

import logging
from flask import Flask, Response
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# HSTS duration constants (in seconds)
HSTS_MAX_AGE_PRODUCTION = 31536000  # 1 year
HSTS_MAX_AGE_DEVELOPMENT = 86400  # 1 day


def get_security_headers(is_production: bool = False) -> Dict[str, str]:
    """Build security headers dictionary for HTTP responses.

    Args:
        is_production: Enable stricter settings for production environment

    Returns:
        Dictionary mapping header names to values
    """
    headers: Dict[str, str] = {}

    # HSTS: Force HTTPS for future requests
    if is_production:
        headers['Strict-Transport-Security'] = (
            f'max-age={HSTS_MAX_AGE_PRODUCTION}; includeSubDomains; preload'
        )
    else:
        headers['Strict-Transport-Security'] = f'max-age={HSTS_MAX_AGE_DEVELOPMENT}'

    # CSP: Restrict resource loading to prevent XSS
    csp_directives = [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob: https:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "object-src 'none'",
        "form-action 'self'",
        "plugin-types",
        "base-uri 'self'",
    ]

    if is_production:
        csp_directives.append("upgrade-insecure-requests")

    headers['Content-Security-Policy'] = '; '.join(csp_directives)

    # Clickjacking protection
    headers['X-Frame-Options'] = 'DENY'

    # Prevent MIME type sniffing
    headers['X-Content-Type-Options'] = 'nosniff'

    # Control referrer information
    headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

    # Disable unnecessary browser features
    headers['Permissions-Policy'] = ', '.join([
        'geolocation=()',
        'microphone=()',
        'camera=()',
        'payment=()',
        'usb=()',
        'magnetometer=()',
        'gyroscope=()',
        'accelerometer=()',
    ])

    # Legacy XSS protection for older browsers
    headers['X-XSS-Protection'] = '1; mode=block'

    return headers


def configure_security_headers(app: Flask, is_production: Optional[bool] = None) -> None:
    """Register an after_request handler that adds security headers to all responses.

    Args:
        app: Flask application instance
        is_production: Enable stricter settings (defaults to FLASK_ENV check)
    """
    if is_production is None:
        is_production = app.config.get('ENV') == 'production'

    security_headers = get_security_headers(is_production)

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        for header, value in security_headers.items():
            response.headers[header] = value

        # Development: Allow WebSocket connections for Vite HMR
        if not is_production:
            is_html = response.content_type and 'text/html' in response.content_type
            if is_html:
                csp = response.headers.get('Content-Security-Policy', '')
                if 'connect-src' in csp:
                    response.headers['Content-Security-Policy'] = csp.replace(
                        "connect-src 'self'",
                        "connect-src 'self' ws: wss:"
                    )

        return response

    logger.info("Security headers configured (production=%s)", is_production)


REQUIRED_SECURITY_HEADERS = [
    'Strict-Transport-Security',
    'Content-Security-Policy',
    'X-Frame-Options',
    'X-Content-Type-Options',
    'Referrer-Policy',
    'Permissions-Policy',
]


def validate_security_headers(response: Response) -> Dict[str, str]:
    """Check that required security headers are present and non-empty.

    Args:
        response: Flask response object

    Returns:
        Dictionary of header names to issue descriptions (empty if all valid)
    """
    issues: Dict[str, str] = {}

    for header in REQUIRED_SECURITY_HEADERS:
        if header not in response.headers:
            issues[header] = 'Missing'
        elif not response.headers[header]:
            issues[header] = 'Empty'

    return issues
