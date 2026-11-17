"""SQLAlchemy implementations of the repository interfaces.

Each repository receives the request's Session from outside (dependency
injection). It translates between ORM rows and domain entities and never
commits: the session scope owns the transaction.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.orm import TaskRow, UserRow
from app.domain.models import Role, Task, TaskStatus, User


def _to_user(row: UserRow) -> User:
    return User(
        id=row.id,
        username=row.username,
        password_hash=row.password_hash,
        role=Role(row.role),
        created_at=row.created_at,
    )


def _to_task(row: TaskRow) -> Task:
    return Task(
        id=row.id,
        title=row.title,
        description=row.description,
        status=TaskStatus(row.status),
        owner_id=row.owner_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: int) -> User | None:
        row = self._session.get(UserRow, user_id)
        return _to_user(row) if row else None

    def get_by_username(self, username: str) -> User | None:
        stmt = select(UserRow).where(UserRow.username == username)
        row = self._session.scalars(stmt).one_or_none()
        return _to_user(row) if row else None

    def add(self, user: User) -> User:
        row = UserRow(
            username=user.username,
            password_hash=user.password_hash,
            role=user.role.value,
            created_at=user.created_at,
        )
        self._session.add(row)
        self._session.flush()  # sends the INSERT so the DB assigns an id
        return _to_user(row)


class SqlAlchemyTaskRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, task_id: int) -> Task | None:
        row = self._session.get(TaskRow, task_id)
        return _to_task(row) if row else None

    def list(
        self,
        *,
        owner_id: int | None = None,
        status: TaskStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
        # Build the query up step by step. Parameters are always bound,
        # never string-formatted, so this is safe from SQL injection.
        stmt = select(TaskRow).order_by(TaskRow.id)
        if owner_id is not None:
            stmt = stmt.where(TaskRow.owner_id == owner_id)
        if status is not None:
            stmt = stmt.where(TaskRow.status == status.value)
        stmt = stmt.limit(limit).offset(offset)
        return [_to_task(row) for row in self._session.scalars(stmt)]

    def add(self, task: Task) -> Task:
        row = TaskRow(
            title=task.title,
            description=task.description,
            status=task.status.value,
            owner_id=task.owner_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        self._session.add(row)
        self._session.flush()
        return _to_task(row)

    def update(self, task: Task) -> Task:
        row = self._session.get(TaskRow, task.id)
        if row is None:  # the service checks existence first, so this is a programming error
            raise LookupError(f"Task {task.id} does not exist")
        row.title = task.title
        row.description = task.description
        row.status = task.status.value
        self._session.flush()
        return _to_task(row)

    def delete(self, task_id: int) -> None:
        row = self._session.get(TaskRow, task_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()
