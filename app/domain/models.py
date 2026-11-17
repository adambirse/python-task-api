"""Domain entities: plain Python objects that the services work with.

They know nothing about SQLAlchemy, Pydantic or HTTP. The SQLAlchemy repository
maps database rows to these, and the in-memory repository stores them directly.
That is what lets us swap storage without touching any business logic.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class User:
    username: str
    password_hash: str
    role: Role = Role.USER
    id: int | None = None  # None until the repository saves it
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN


@dataclass
class Task:
    title: str
    owner_id: int
    description: str | None = None
    status: TaskStatus = TaskStatus.TODO
    id: int | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
