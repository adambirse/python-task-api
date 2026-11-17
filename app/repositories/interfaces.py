"""Repository interfaces.

A `Protocol` is Python's structural typing: any class with these methods
satisfies it, no inheritance needed. Services depend on these interfaces,
never on a concrete implementation (the Dependency Inversion Principle).
"""

from typing import Protocol

from app.domain.models import Task, TaskStatus, User


class UserRepository(Protocol):
    def get_by_id(self, user_id: int) -> User | None: ...

    def get_by_username(self, username: str) -> User | None: ...

    def add(self, user: User) -> User: ...


class TaskRepository(Protocol):
    def get_by_id(self, task_id: int) -> Task | None: ...

    def list(
        self,
        *,
        owner_id: int | None = None,
        status: TaskStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]: ...

    def add(self, task: Task) -> Task: ...

    def update(self, task: Task) -> Task: ...

    def delete(self, task_id: int) -> None: ...
