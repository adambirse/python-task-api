"""API tests for tasks: status codes, JSON shapes and authorisation end to end."""


def create_task(client, headers, title="A task", **extra):
    response = client.post("/tasks", json={"title": title, **extra}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_tasks_require_authentication(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401


def test_create_and_fetch_task(client, alice):
    created = create_task(client, alice, "Buy milk", description="Semi-skimmed")

    response = client.get(f"/tasks/{created['id']}", headers=alice)

    assert response.status_code == 200
    assert response.json()["title"] == "Buy milk"
    assert response.json()["status"] == "todo"


def test_list_only_shows_my_tasks(client, alice, bob):
    create_task(client, alice, "Alice's")
    create_task(client, bob, "Bob's")

    response = client.get("/tasks", headers=alice)

    assert [t["title"] for t in response.json()] == ["Alice's"]


def test_list_validates_query_params(client, alice):
    assert client.get("/tasks?limit=0", headers=alice).status_code == 422
    assert client.get("/tasks?status=bogus", headers=alice).status_code == 422


def test_patch_updates_only_sent_fields(client, alice):
    task = create_task(client, alice, "Title", description="Keep")

    response = client.patch(f"/tasks/{task['id']}", json={"status": "done"}, headers=alice)

    assert response.status_code == 200
    assert response.json()["status"] == "done"
    assert response.json()["description"] == "Keep"


def test_editing_completed_task_is_409(client, alice):
    task = create_task(client, alice)
    client.patch(f"/tasks/{task['id']}", json={"status": "done"}, headers=alice)

    response = client.patch(f"/tasks/{task['id']}", json={"title": "Edit"}, headers=alice)

    assert response.status_code == 409


def test_other_user_gets_403_on_my_task(client, alice, bob):
    task = create_task(client, alice)

    assert client.get(f"/tasks/{task['id']}", headers=bob).status_code == 403
    assert client.patch(f"/tasks/{task['id']}", json={"title": "x"}, headers=bob).status_code == 403
    assert client.delete(f"/tasks/{task['id']}", headers=bob).status_code == 403


def test_admin_can_see_any_task(client, alice, admin):
    task = create_task(client, alice)

    assert client.get(f"/tasks/{task['id']}", headers=admin).status_code == 200


def test_delete_then_404(client, alice):
    task = create_task(client, alice)

    assert client.delete(f"/tasks/{task['id']}", headers=alice).status_code == 204
    assert client.get(f"/tasks/{task['id']}", headers=alice).status_code == 404


def test_writes_are_committed_across_requests(client, alice):
    """Each request has its own session, so this proves the commit really happened."""
    create_task(client, alice, "Persisted")

    assert len(client.get("/tasks", headers=alice).json()) == 1
