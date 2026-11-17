"""Role-based authorisation over HTTP."""


def test_admin_can_list_all_tasks(client, alice, bob, admin):
    client.post("/tasks", json={"title": "A"}, headers=alice)
    client.post("/tasks", json={"title": "B"}, headers=bob)

    response = client.get("/admin/tasks", headers=admin)

    assert response.status_code == 200
    assert {t["title"] for t in response.json()} == {"A", "B"}


def test_normal_user_gets_403_on_admin_routes(client, alice):
    assert client.get("/admin/tasks", headers=alice).status_code == 403


def test_anonymous_gets_401_on_admin_routes(client):
    assert client.get("/admin/tasks").status_code == 401
