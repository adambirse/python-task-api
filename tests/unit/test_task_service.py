"""Unit tests for TaskService business rules and ownership authorisation.

No HTTP and no database: the service gets an in-memory repository, so each
test runs in well under a millisecond and reads as a plain specification.
Tests follow Arrange / Act / Assert.
"""

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.domain.models import Role, TaskStatus, User
from app.repositories.memory import InMemoryTaskRepository
from app.schemas.tasks import TaskCreate, TaskUpdate
from app.services.task_service import TaskService

ALICE = User(id=1, username="alice", password_hash="x")
BOB = User(id=2, username="bob", password_hash="x")
ADMIN = User(id=99, username="admin", password_hash="x", role=Role.ADMIN)


@pytest.fixture
def service() -> TaskService:
    return TaskService(InMemoryTaskRepository())


def test_created_task_belongs_to_the_creator(service):
    task = service.create_task(ALICE, TaskCreate(title="Write tests"))

    assert task.id is not None
    assert task.owner_id == ALICE.id
    assert task.status == TaskStatus.TODO


def test_list_my_tasks_only_returns_my_tasks(service):
    service.create_task(ALICE, TaskCreate(title="Alice's task"))
    service.create_task(BOB, TaskCreate(title="Bob's task"))

    titles = [t.title for t in service.list_my_tasks(ALICE)]

    assert titles == ["Alice's task"]


def test_list_my_tasks_can_filter_by_status(service):
    done = service.create_task(ALICE, TaskCreate(title="Done"))
    service.create_task(ALICE, TaskCreate(title="Not done"))
    service.update_task(ALICE, done.id, TaskUpdate(status=TaskStatus.DONE))

    result = service.list_my_tasks(ALICE, status=TaskStatus.DONE)

    assert [t.title for t in result] == ["Done"]


# ---- ownership-based authorisation -----------------------------------------


def test_owner_can_read_their_task(service):
    task = service.create_task(ALICE, TaskCreate(title="Mine"))

    assert service.get_task(ALICE, task.id).title == "Mine"


@pytest.mark.parametrize("action", ["get", "update", "delete"])
def test_other_users_cannot_touch_my_task(service, action):
    task = service.create_task(ALICE, TaskCreate(title="Private"))

    with pytest.raises(ForbiddenError):
        if action == "get":
            service.get_task(BOB, task.id)
        elif action == "update":
            service.update_task(BOB, task.id, TaskUpdate(title="Hacked"))
        else:
            service.delete_task(BOB, task.id)

    assert service.get_task(ALICE, task.id).title == "Private"  # unchanged


def test_admin_can_access_any_task(service):
    task = service.create_task(ALICE, TaskCreate(title="Alice's"))

    updated = service.update_task(ADMIN, task.id, TaskUpdate(title="Moderated"))

    assert updated.title == "Moderated"


def test_missing_task_raises_not_found(service):
    with pytest.raises(NotFoundError):
        service.get_task(ALICE, 12345)


# ---- role-based authorisation (defence in depth) ----------------------------


def test_only_admins_can_list_all_tasks(service):
    service.create_task(ALICE, TaskCreate(title="A"))
    service.create_task(BOB, TaskCreate(title="B"))

    assert len(service.list_all_tasks(ADMIN)) == 2
    with pytest.raises(ForbiddenError):
        service.list_all_tasks(ALICE)


# ---- business rules ---------------------------------------------------------


def test_partial_update_only_changes_fields_that_were_sent(service):
    task = service.create_task(ALICE, TaskCreate(title="Title", description="Keep me"))

    updated = service.update_task(ALICE, task.id, TaskUpdate(status=TaskStatus.IN_PROGRESS))

    assert updated.status == TaskStatus.IN_PROGRESS
    assert updated.title == "Title"
    assert updated.description == "Keep me"


def test_completed_task_cannot_be_edited(service):
    task = service.create_task(ALICE, TaskCreate(title="Finished"))
    service.update_task(ALICE, task.id, TaskUpdate(status=TaskStatus.DONE))

    with pytest.raises(ConflictError):
        service.update_task(ALICE, task.id, TaskUpdate(title="Sneaky edit"))


def test_completed_task_can_be_reopened(service):
    task = service.create_task(ALICE, TaskCreate(title="Finished"))
    service.update_task(ALICE, task.id, TaskUpdate(status=TaskStatus.DONE))

    reopened = service.update_task(ALICE, task.id, TaskUpdate(status=TaskStatus.IN_PROGRESS))

    assert reopened.status == TaskStatus.IN_PROGRESS


def test_delete_removes_the_task(service):
    task = service.create_task(ALICE, TaskCreate(title="Temp"))

    service.delete_task(ALICE, task.id)

    with pytest.raises(NotFoundError):
        service.get_task(ALICE, task.id)
