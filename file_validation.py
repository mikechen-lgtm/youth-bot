"""File upload validation utilities.

Provides secure validation and sanitization for uploaded files.
"""
from __future__ import annotations

import io
import logging
from typing import Set

from PIL import Image
from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)

# Configuration constants
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS: Set[str] = {"jpg", "jpeg", "png", "webp"}
MAX_IMAGE_DIMENSION = 4096  # pixels

# PIL format names for re-encoding
SUPPORTED_FORMATS = {"jpeg": "JPEG", "png": "PNG", "webp": "WebP"}


class FileValidationError(Exception):
    """Raised when file validation fails."""


def _get_file_extension(filename: str) -> str:
    """Extract lowercase extension from filename."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _validate_and_open_image(file_data: bytes) -> tuple[Image.Image, str]:
    """
    Validate image data and return opened image with detected format.

    Raises:
        FileValidationError: If image is invalid or unsupported
    """
    try:
        img = Image.open(io.BytesIO(file_data))
        detected_format = (img.format or "").lower()

        if detected_format not in SUPPORTED_FORMATS:
            raise FileValidationError("檔案內容不是有效的圖片格式")

        width, height = img.size
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            raise FileValidationError(f"圖片尺寸過大（最大 {MAX_IMAGE_DIMENSION}px）")

        img.verify()
        return img, detected_format

    except FileValidationError:
        raise
    except Exception as e:
        raise FileValidationError(f"無效或損壞的圖片: {e}") from e


def validate_image_upload(file: FileStorage) -> bytes:
    """Validate and sanitize image upload.

    Performs the following validations:
    1. Filename presence and extension
    2. File size limits
    3. Image type verification (magic bytes)
    4. Image dimensions
    5. Re-encodes to strip metadata

    Args:
        file: FileStorage object from request.files

    Returns:
        Sanitized image data as bytes

    Raises:
        FileValidationError: If any validation check fails
    """
    # Validate filename
    if not file.filename:
        raise FileValidationError("檔案名稱為空")

    filename = file.filename.lower()
    ext = _get_file_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise FileValidationError(f"不支援的檔案格式（只支援 {allowed}）")

    # Validate file size
    file_data = file.read()
    file_size = len(file_data)

    if file_size == 0:
        raise FileValidationError("檔案是空的")

    max_mb = MAX_FILE_SIZE // (1024 * 1024)
    if file_size > MAX_FILE_SIZE:
        raise FileValidationError(f"檔案過大（最大 {max_mb}MB）")

    # Validate and get image info
    _, detected_format = _validate_and_open_image(file_data)

    # Re-encode to strip metadata
    with Image.open(io.BytesIO(file_data)) as img:
        output = io.BytesIO()
        save_format = SUPPORTED_FORMATS[detected_format]
        img.save(output, format=save_format, quality=95)
        sanitized_data = output.getvalue()

    width, height = img.size
    logger.info(
        "Image validated: %s, size: %d bytes, dimensions: %dx%d",
        filename, file_size, width, height,
    )

    return sanitized_data
