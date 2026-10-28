"""Error type shared by the engine and the REST layer: maps to `{"code", "message"}`."""

from __future__ import annotations

from app.schemas import ERROR_CODES


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str = "") -> None:
        if code not in ERROR_CODES:
            raise ValueError(f"unknown error code: {code!r}")
        super().__init__(message or code)
        self.status = status
        self.code = code
        self.message = message or code
