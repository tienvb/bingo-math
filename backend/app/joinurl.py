"""*QR và địa chỉ join*: validate `join_base_url` and build `join_url`."""

from __future__ import annotations

from urllib.parse import urlsplit

from app.errors import ApiError
from app.schemas import ERR_INVALID_JOIN_URL


def _invalid(msg: str) -> ApiError:
    return ApiError(422, ERR_INVALID_JOIN_URL, msg)


def normalize_join_base_url(value: str) -> str:
    """`http(s)://host[:port]`, optional trailing `/`; no other path, query or hash.

    Returns the base without the trailing slash.
    """
    if not isinstance(value, str):
        raise _invalid("join_base_url must be a string")
    raw = value.strip()
    if not raw or any(ch.isspace() for ch in raw):
        raise _invalid("join_base_url must not be empty or contain spaces")
    if "?" in raw or "#" in raw:
        raise _invalid("join_base_url must not have a query or hash")
    try:
        parts = urlsplit(raw)
        _ = parts.port  # raises ValueError on a bad port
    except ValueError as exc:
        raise _invalid(f"join_base_url is not a valid URL: {exc}") from exc
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise _invalid("join_base_url must start with http:// or https://")
    if not parts.hostname:
        raise _invalid("join_base_url must have a host")
    if parts.path not in ("", "/"):
        raise _invalid("join_base_url must not have a path")
    return f"{scheme}://{parts.netloc}"


def build_join_url(base: str, pin: str) -> str:
    return f"{base}/play/{pin}"
