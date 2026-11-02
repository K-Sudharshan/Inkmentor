"""
Unit and integration tests for InkMentor full-stack authentication layer.
Tests:
- Google OAuth token verification and user provisioning in SQLite
- Session token generation and expiration
- Protected endpoints (/api/auth/me, /api/auth/profile)
- Bearer token & cookie authorization
- 401 Unauthorized enforcement
- Session revocation on logout
"""

import json
import os
import sqlite3
import tempfile
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

# Use a temporary database for test isolation
tmp_db = os.path.join(tempfile.gettempdir(), f"inkmentor_test_{os.getpid()}.db")
os.environ["INKMENTOR_DB_PATH"] = tmp_db
os.environ["TEST_MODE"] = "true"

from backend.auth import init_db
from backend.main import app

@pytest.fixture(autouse=True)
def clean_db():
    client.cookies.clear()
    if os.path.exists(tmp_db):
        try:
            os.remove(tmp_db)
        except Exception:
            pass
    init_db(tmp_db)
    yield
    client.cookies.clear()
    if os.path.exists(tmp_db):
        try:
            os.remove(tmp_db)
        except Exception:
            pass

client = TestClient(app)

def test_1_google_login_new_user():
    payload = {
        "credential": "mock_google_jwt_token.eyJzdWIiOiIxMTIyMzMzNDQiLCJlbWFpbCI6Im5ld3VzZXJAZ21haWwuY29tIiwibmFtZSI6IkpvaG4gRG9lIiwicGljdHVyZSI6Imh0dHBzOi8vbGhzMy5nb29nbGUuY29tL3Bob3RvLmpwZyJ9.sig",
        "dob": "2000-05-15",
        "age": 26
    }
    res = client.post("/api/auth/google", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "token" in data
    assert data["token"] != ""
    assert data["is_new"] is True
    assert data["user"]["email"] == "newuser@gmail.com"
    assert data["user"]["name"] == "John Doe"
    assert data["user"]["dob"] == "2000-05-15"
    assert data["user"]["age"] == 26
    assert "inkmentor_session" in res.cookies


def test_2_google_login_existing_user():
    # Login 1 (creates user)
    payload = {
        "credential": "mock_google_token.eyJzdWIiOiJleGlzdF8xMjM0NSIsImVtYWlsIjoiZXhpc3RpbmdAZ21haWwuY29tIiwibmFtZSI6IkFsaWNlIFciLCJwaWN0dXJlIjoiIn0.sig",
        "dob": "1998-10-10",
        "age": 28
    }
    res1 = client.post("/api/auth/google", json=payload)
    assert res1.status_code == 200
    assert res1.json()["is_new"] is True

    # Login 2 (returning user)
    res2 = client.post("/api/auth/google", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_new"] is False
    assert data2["user"]["email"] == "existing@gmail.com"
    assert data2["user"]["dob"] == "1998-10-10"


def test_3_protected_get_me_with_bearer_token():
    payload = {
        "credential": "mock_token.eyJzdWIiOiJ1c2VyXzAwNyIsImVtYWlsIjoiYm9uZEBnbWFpbC5jb20iLCJuYW1lIjoiSmFtZXMgQm9uZCJ9.sig",
        "dob": "1990-01-01",
        "age": 36
    }
    auth_res = client.post("/api/auth/google", json=payload)
    token = auth_res.json()["token"]

    # Call /api/auth/me with Authorization: Bearer <token>
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    user = me_res.json()
    assert user["email"] == "bond@gmail.com"
    assert user["name"] == "James Bond"


def test_4_protected_get_me_with_cookie():
    payload = {
        "credential": "mock_token.eyJzdWIiOiJ1c2VyXzAwOCIsImVtYWlsIjoiY29va2llX3VzZXJAZ21haWwuY29tIiwibmFtZSI6IkNvb2tpZSBVc2VyIn0.sig",
    }
    auth_res = client.post("/api/auth/google", json=payload)
    token = auth_res.json()["token"]

    # Call /api/auth/me with session cookie
    me_res = client.get("/api/auth/me", cookies={"inkmentor_session": token})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "cookie_user@gmail.com"


def test_5_protected_get_me_unauthorized_without_token():
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert "Authentication required" in res.json()["detail"]


def test_6_protected_get_me_unauthorized_with_invalid_token():
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer fake_token_12345"})
    assert res.status_code == 401
    assert "Invalid" in res.json()["detail"] or "expired" in res.json()["detail"]


def test_7_update_learner_profile():
    # Login
    payload = {
        "credential": "mock_token.eyJzdWIiOiJ1c2VyXzAwOSIsImVtYWlsIjoicHJvZmlsZUBnbWFpbC5jb20iLCJuYW1lIjoiT3JpZ2luYWwgTmFtZSJ9.sig",
    }
    auth_res = client.post("/api/auth/google", json=payload)
    token = auth_res.json()["token"]

    # Update profile (Name, DOB, Age)
    update_res = client.post(
        "/api/auth/profile",
        json={"name": "Updated Name", "dob": "2004-12-25", "age": 22},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["name"] == "Updated Name"
    assert updated["dob"] == "2004-12-25"
    assert updated["age"] == 22

    # Verify updated profile persists on /api/auth/me
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.json()["name"] == "Updated Name"
    assert me_res.json()["dob"] == "2004-12-25"


def test_8_logout_revokes_session():
    # Login
    payload = {
        "credential": "mock_token.eyJzdWIiOiJsb2dvdXRfdXNlciIsImVtYWlsIjoibG9nb3V0QGdtYWlsLmNvbSIsIm5hbWUiOiJMb2dvdXQgVXNlciJ9.sig",
    }
    auth_res = client.post("/api/auth/google", json=payload)
    token = auth_res.json()["token"]

    # Verify session is valid
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    # Logout
    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "logged_out"

    # Subsequent request with revoked token must fail with 401
    me_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_after.status_code == 401


def test_9_expired_session_is_rejected():
    # Login
    payload = {
        "credential": "mock_token.eyJzdWIiOiJleHBpcmVkX3VzZXIiLCJlbWFpbCI6ImV4cGlyZWRAZ21haWwuY29tIiwibmFtZSI6IkV4cGlyZWQgVXNlciJ9.sig",
    }
    auth_res = client.post("/api/auth/google", json=payload)
    token = auth_res.json()["token"]

    # Manually expire the session in SQLite
    conn = sqlite3.connect(tmp_db)
    cur = conn.cursor()
    past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    cur.execute("UPDATE sessions SET expires_at = ? WHERE token = ?", (past_iso, token))
    conn.commit()
    conn.close()

    # Request with expired session must fail with 401
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
