from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class EHDMError(Exception):
    """Base exception for the library."""


class EHDMTransportError(EHDMError):
    """Raised when the HTTP transport fails before a valid API response is received."""


@dataclass(slots=True)
class EHDMAPIError(EHDMError):
    code: int
    message: str
    error_message: str | None = None
    payload: dict[str, Any] | None = None

    def __str__(self) -> str:
        if self.error_message:
            return f"[{self.code}] {self.message}: {self.error_message}"
        return f"[{self.code}] {self.message}"

