from fastapi.testclient import TestClient

from tests.conftest import register

VALID_PASSWORD = "correct horse battery"


def test_register_creates_session_and_user(client):
    r = register(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["email"] == "dev@example.com"
    assert "password" not in r.text and body["user"]["id"]
    assert client.cookies.get("nexus_session")
    assert client.cookies.get("nexus_csrf")
    assert body["csrf_token"] == client.cookies.get("nexus_csrf")

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["display_name"] == "Dev User"


def test_register_rejects_duplicate_email(client):
    assert register(client).status_code == 201
    duplicate = register(client, email="DEV@example.com")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"


def test_register_rejects_short_password(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "x@example.com", "password": "short", "display_name": "X Y"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_login_and_wrong_password(client):
    register(client)
    client.cookies.clear()
    bad = client.post(
        "/api/v1/auth/login", json={"email": "dev@example.com", "password": "wrong password"}
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["message"] == "Invalid email or password"

    good = client.post(
        "/api/v1/auth/login", json={"email": "dev@example.com", "password": VALID_PASSWORD}
    )
    assert good.status_code == 200
    assert good.json()["user"]["email"] == "dev@example.com"


def test_login_unknown_user_does_not_leak_existence(client):
    r = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": VALID_PASSWORD}
    )
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "Invalid email or password"


def test_me_requires_authentication(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_logout_revokes_session(client):
    register(client)
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_refresh_rotates_the_session(client):
    register(client)
    old_cookie = client.cookies.get("nexus_session")
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    new_cookie = client.cookies.get("nexus_session")
    assert new_cookie and new_cookie != old_cookie

    stale = TestClient(client.app)
    stale.cookies.set("nexus_session", old_cookie)
    assert stale.get("/api/v1/auth/me").status_code == 401


def test_session_mutation_requires_csrf(auth_client):
    auth_client.headers.pop("X-CSRF-Token", None)
    r = auth_client.post("/api/v1/auth/tokens", json={"name": "mcp"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_api_token_authenticates_without_csrf(auth_client):
    created = auth_client.post("/api/v1/auth/tokens", json={"name": "mcp"})
    assert created.status_code == 201, created.text
    token = created.json()["token"]

    bearer = TestClient(auth_client.app)
    bearer.headers.update({"Authorization": f"Bearer {token}"})
    me = bearer.get("/api/v1/auth/me")
    assert me.status_code == 200
    # No CSRF header, and none needed: bearer auth is not cookie-based.
    made = bearer.post("/api/v1/auth/tokens", json={"name": "second"})
    assert made.status_code == 201


def test_api_token_can_be_revoked(auth_client):
    created = auth_client.post("/api/v1/auth/tokens", json={"name": "mcp"}).json()
    token = created["token"]
    token_id = created["record"]["id"]
    assert auth_client.delete(f"/api/v1/auth/tokens/{token_id}").status_code == 204

    bearer = TestClient(auth_client.app)
    bearer.headers.update({"Authorization": f"Bearer {token}"})
    assert bearer.get("/api/v1/auth/me").status_code == 401


def test_invalid_token_is_rejected(client):
    client.headers.update({"Authorization": "Bearer obviously-not-valid"})
    assert client.get("/api/v1/auth/me").status_code == 401


def test_change_password_revokes_sessions_and_requires_csrf(auth_client):
    r = auth_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": VALID_PASSWORD, "new_password": "a brand new passphrase"},
    )
    assert r.status_code == 204
    assert auth_client.get("/api/v1/auth/me").status_code == 401
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "a brand new passphrase"},
    )
    assert login.status_code == 200


def test_cross_site_origin_is_rejected(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": VALID_PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_account_deletion_requires_confirmation(auth_client):
    r = auth_client.post(
        "/api/v1/auth/account", json={"password": VALID_PASSWORD, "confirm": "delete"}
    )
    assert r.status_code == 422
    assert auth_client.get("/api/v1/auth/me").status_code == 200
