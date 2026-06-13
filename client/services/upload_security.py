"""Shared safeguards for uploaded images and upload-local file paths."""

import base64
import os
import re
import uuid
from pathlib import Path
from typing import Optional

from config import settings

UPLOAD_DIR = "uploads"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def sanitize_filename_part(value: object, fallback: str = "file") -> str:
    text = str(value or "").strip()
    text = SAFE_NAME_RE.sub("_", text)
    text = text.strip("._")
    return (text or fallback)[:80]


def safe_image_extension(filename: Optional[str], content_type: Optional[str] = None) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return ext
    by_type = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    return by_type.get(content_type or "", ".jpg")


def upload_root() -> Path:
    root = Path(UPLOAD_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_upload_path(path_or_name: Optional[str]) -> Optional[Path]:
    """Resolve a user-provided upload path and reject paths outside uploads/."""
    if not path_or_name:
        return None

    normalized = str(path_or_name).replace("\\", "/").strip()
    if not normalized:
        return None
    if normalized.startswith(("http://", "https://")):
        return None

    # Persisted values are either "uploads/name.jpg" or just "name.jpg".
    name = Path(normalized).name
    if not name or name in {".", ".."}:
        return None
    candidate = (upload_root() / name).resolve()
    root = upload_root()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def make_upload_filename(prefix: str, ext: str = ".jpg") -> str:
    safe_prefix = sanitize_filename_part(prefix, "image")
    if ext.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        ext = ".jpg"
    return f"{safe_prefix}_{uuid.uuid4().hex[:12]}{ext.lower()}"


def decode_base64_image(image_base64: str) -> Optional[bytes]:
    if not image_base64:
        return None
    if len(image_base64) > settings.MAX_BASE64_IMAGE_CHARS:
        raise ValueError("image is too large")
    return base64.b64decode(image_base64, validate=True)


def save_image_bytes(filename: str, data: bytes) -> str:
    if len(data) > settings.MAX_IMAGE_BYTES:
        raise ValueError("image is too large")
    path = (upload_root() / Path(filename).name).resolve()
    path.write_bytes(data)
    return os.path.join(UPLOAD_DIR, path.name)
