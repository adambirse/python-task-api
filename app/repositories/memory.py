"""In-memory implementations of the repository interfaces.

These are *fakes*: real, working implementations that keep data in a dict.
Unit tests use them so service tests run in milliseconds with no database,
and they double as a living example that the services really don't care
how data is stored.
"""

from dataclasses import replace
from itertools import count

from app.domain.models import Task, TaskStatus, User


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._users: dict[int, User] = {}
        self._ids = count(1)

    def get_by_id(self, user_id: int) -> User | None:
        return self._users.get(user_id)

    def get_by_username(self, username: str) -> User | None:
        return next((u for u in self._users.values() if u.username == username), None)

    def add(self, user: User) -> User:
        saved = replace(user, id=next(self._ids))
        self._users[saved.id] = saved  # type: ignore[index]
        return saved


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[int, Task] = {}
        self._ids = count(1)

    def get_by_id(self, task_id: int) -> Task | None:
        return self._tasks.get(task_id)

    def list(
        self,
        *,
        owner_id: int | None = None,
        status: TaskStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
        tasks = sorted(self._tasks.values(), key=lambda t: t.id or 0)
        if owner_id is not None:
            tasks = [t for t in tasks if t.owner_id == owner_id]
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        return tasks[offset : offset + limit]

    def add(self, task: Task) -> Task:
        saved = replace(task, id=next(self._ids))
        self._tasks[saved.id] = saved  # type: ignore[index]
        return saved

    def update(self, task: Task) -> Task:
        if task.id not in self._tasks:
            raise LookupError(f"Task {task.id} does not exist")
        self._tasks[task.id] = task
        return task

    def delete(self, task_id: int) -> None:
        self._tasks.pop(task_id, None)
