"""Task use cases and the business rules that go with them.

Two kinds of authorisation live in this app:

* Role-based ("are you an admin?") is checked at the route with `require_role`,
  because it only needs the current user.
* Ownership-based ("is this *your* task?") is checked here, because it needs
  the task loaded from storage first. Only the service has that.
"""

from dataclasses import replace
from datetime import UTC, datetime

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.domain.models import Task, TaskStatus, User
from app.repositories.interfaces import TaskRepository
from app.schemas.tasks import TaskCreate, TaskUpdate


class TaskService:
    def __init__(self, tasks: TaskRepository) -> None:
        self._tasks = tasks

    # ---- queries -------------------------------------------------------

    def get_task(self, actor: User, task_id: int) -> Task:
        task = self._tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")
        self._ensure_can_access(actor, task)
        return task

    def list_my_tasks(
        self, actor: User, *, status: TaskStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[Task]:
        return self._tasks.list(owner_id=actor.id, status=status, limit=limit, offset=offset)

    def list_all_tasks(
        self, actor: User, *, status: TaskStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[Task]:
        # The route already requires the admin role. Checking again here is
        # defence in depth: the rule holds even if another caller forgets.
        if not actor.is_admin:
            raise ForbiddenError("Only admins can list all tasks")
        return self._tasks.list(status=status, limit=limit, offset=offset)

    # ---- commands ------------------------------------------------------

    def create_task(self, actor: User, data: TaskCreate) -> Task:
        task = Task(title=data.title, description=data.description, owner_id=actor.id)  # type: ignore[arg-type]
        return self._tasks.add(task)

    def update_task(self, actor: User, task_id: int, data: TaskUpdate) -> Task:
        task = self.get_task(actor, task_id)  # reuses the not-found and ownership checks
        changes = data.model_dump(exclude_unset=True)

        # Business rule: a finished task is locked. The only allowed change is
        # to reopen it by moving its status away from DONE.
        if task.status == TaskStatus.DONE and set(changes) - {"status"}:
            raise ConflictError("Completed tasks can't be edited. Reopen the task first.")

        updated = replace(task, **changes, updated_at=datetime.now(UTC))
        return self._tasks.update(updated)

    def delete_task(self, actor: User, task_id: int) -> None:
        task = self.get_task(actor, task_id)
        self._tasks.delete(task.id)  # type: ignore[arg-type]

    # ---- rules ---------------------------------------------------------

    @staticmethod
    def _ensure_can_access(actor: User, task: Task) -> None:
        if actor.is_admin or task.owner_id == actor.id:
            return
        # Some APIs return 404 here instead, to hide that the task exists at all.
        # 403 is clearer for learning; either is a defensible interview answer.
        raise ForbiddenError("You don't have access to this task")
