"""Task controller.

Every handler follows the same shape: validated input in, one service call,
response model out. No business rules, no try/except, no database code.
Errors raised by the service are turned into HTTP responses in app/main.py.
"""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, TaskServiceDep
from app.domain.models import TaskStatus
from app.schemas.tasks import TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("", response_model=list[TaskRead])
def list_my_tasks(
    user: CurrentUser,
    tasks: TaskServiceDep,
    status: TaskStatus | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[TaskRead]:
    result = tasks.list_my_tasks(user, status=status, limit=limit, offset=offset)
    return [TaskRead.model_validate(t) for t in result]


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(data: TaskCreate, user: CurrentUser, tasks: TaskServiceDep) -> TaskRead:
    return TaskRead.model_validate(tasks.create_task(user, data))


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, user: CurrentUser, tasks: TaskServiceDep) -> TaskRead:
    return TaskRead.model_validate(tasks.get_task(user, task_id))


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int, data: TaskUpdate, user: CurrentUser, tasks: TaskServiceDep
) -> TaskRead:
    return TaskRead.model_validate(tasks.update_task(user, task_id, data))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, user: CurrentUser, tasks: TaskServiceDep) -> None:
    tasks.delete_task(user, task_id)
