from fastapi.testclient import TestClient
from main import app
import uuid

client = TestClient(app)


def unique_username():
    return "testuser_" + uuid.uuid4().hex[:8]


def register_and_login(username, password="testpass123"):
    client.post("/register", json={"username": username, "password": password})
    response = client.post("/login", data={"username": username, "password": password})
    token = response.json()["access_token"]
    return token


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_user():
    username = unique_username()
    response = client.post("/register", json={
        "username": username,
        "password": "testpass123"
    })
    assert response.status_code == 200
    assert response.json()["message"] == "User created successfully"


def test_register_duplicate_username_fails():
    username = unique_username()
    client.post("/register", json={"username": username, "password": "pass123"})
    response = client.post("/register", json={"username": username, "password": "pass123"})
    assert response.status_code == 400


def test_login_with_wrong_password_fails():
    username = unique_username()
    client.post("/register", json={"username": username, "password": "correctpass"})
    response = client.post("/login", data={"username": username, "password": "wrongpass"})
    assert response.status_code == 401


def test_create_client_requires_login():
    response = client.post("/clients", json={"name": "Test Co", "email": None})
    assert response.status_code == 401


def test_create_and_get_client():
    token = register_and_login(unique_username())
    response = client.post("/clients", json={"name": "Test Co", "email": None}, headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["name"] == "Test Co"

    response = client.get("/clients", headers=auth_headers(token))
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert "Test Co" in names


def test_users_cannot_see_each_others_clients():
    token_a = register_and_login(unique_username())
    token_b = register_and_login(unique_username())

    client.post("/clients", json={"name": "User A's Client", "email": None}, headers=auth_headers(token_a))

    response = client.get("/clients", headers=auth_headers(token_b))
    names = [c["name"] for c in response.json()]
    assert "User A's Client" not in names


def test_invite_gives_access_to_second_user():
    username_a = unique_username()
    username_b = unique_username()
    token_a = register_and_login(username_a)
    token_b = register_and_login(username_b)

    create_response = client.post("/clients", json={"name": "Shared Client", "email": None}, headers=auth_headers(token_a))
    client_id = create_response.json()["id"]

    invite_response = client.post(f"/clients/{client_id}/invite", json={"username": username_b}, headers=auth_headers(token_a))
    assert invite_response.status_code == 200

    response = client.get("/clients", headers=auth_headers(token_b))
    names = [c["name"] for c in response.json()]
    assert "Shared Client" in names


def test_task_not_found_returns_404():
    token = register_and_login(unique_username())
    response = client.get("/tasks/999999", headers=auth_headers(token))
    assert response.status_code == 404
    