"""Domain exceptions.

Services raise these instead of HTTP errors. That keeps the service layer
independent of FastAPI: the same service could be called from a CLI, a
background worker or a test without any HTTP concepts leaking in.

A single set of exception handlers (see app/main.py) maps them to status codes.
"""


class DomainError(Exception):
    """Base class for all expected, business-level errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AuthenticationError(DomainError):
    """Who are you? Credentials missing or invalid. Maps to 401."""


class ForbiddenError(DomainError):
    """We know who you are, but you can't do this. Maps to 403."""


class NotFoundError(DomainError):
    """The thing you asked for doesn't exist. Maps to 404."""


class ConflictError(DomainError):
    """The request clashes with existing state, e.g. a duplicate username. Maps to 409."""
