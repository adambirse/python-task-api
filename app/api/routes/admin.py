"""Admin-only endpoints.

The role check is declared once on the router, so every route below is
protected and nobody can forget it on a new endpoint.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, TaskServiceDep, require_role
from app.domain.models import Role, TaskStatus
from app.schemas.tasks import TaskRead

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


@router.get("/tasks", response_model=list[TaskRead])
def list_all_tasks(
    user: CurrentUser,
    tasks: TaskServiceDep,
    status: TaskStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TaskRead]:
    result = tasks.list_all_tasks(user, status=status, limit=limit, offset=offset)
    return [TaskRead.model_validate(t) for t in result]
