"""One exception hierarchy, one wire shape.

Services raise these; `enola.api.main` is the only place that turns them into HTTP
responses. Route handlers never build error responses by hand.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class EnolaError(Exception):
    code: str = "internal_error"
    status: int = 500

    def __init__(self, message: str = "", *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code
        self.details = details


class NotFoundError(EnolaError):
    code = "not_found"
    status = 404


class ConflictError(EnolaError):
    code = "conflict"
    status = 409


class UnauthorizedError(EnolaError):
    code = "unauthorized"
    status = 401


class ForbiddenError(EnolaError):
    code = "forbidden"
    status = 403


class InvalidInputError(EnolaError):
    code = "invalid_input"
    status = 422


class RegistryError(EnolaError):
    """Raised when the tool registry is misused (duplicate name, unknown tool)."""

    code = "registry_error"
    status = 500


class AgentUnavailableError(EnolaError):
    """The agent cannot run: usually a missing API key."""

    code = "agent_unavailable"
    status = 503


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
