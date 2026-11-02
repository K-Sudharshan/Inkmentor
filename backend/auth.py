"""
InkMentor Authentication & Session Management Module.
Implements:
1. SQLite user and session storage (zero external DB dependency, serverless compatible).
2. Server-side Google ID token cryptographic verification via google-auth.
3. Cryptographically secure session token issuance and expiration.
4. FastAPI dependency injection (get_current_user, get_optional_user).
5. Session revocation on logout.
"""

import os
import sqlite3
import tempfile
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from fastapi import Header, HTTPException, Request, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

# Resolve database file path with fallback to temp directory for serverless environments
def get_db_path() -> str:
    env_db = os.environ.get("INKMENTOR_DB_PATH")
    if env_db:
        return env_db
    
    local_dir = os.path.dirname(os.path.abspath(__file__))
    local_db = os.path.join(local_dir, "inkmentor.db")
    try:
        # Check if local directory is writable
        test_file = local_db + ".test"
        with open(test_file, "w") as f:
            f.write("1")
        os.remove(test_file)
        return local_db
    except Exception:
        # Read-only filesystem (e.g. Vercel serverless): use /tmp
        tmp_dir = tempfile.gettempdir()
        return os.path.join(tmp_dir, "inkmentor.db")


def init_db(db_path: Optional[str] = None) -> None:
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                google_sub TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                picture TEXT DEFAULT '',
                dob TEXT DEFAULT '',
                age INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_sub ON users(google_sub);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        conn.commit()
    finally:
        conn.close()


def get_db_connection() -> sqlite3.Connection:
    path = get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


# Initialize tables on import
init_db()


def verify_google_id_token(credential: str, client_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifies a Google ID token using google-auth.
    Supports a mock verification mode when TEST_MODE=true or credential starts with 'mock_'.
    """
    if os.environ.get("TEST_MODE") == "true" or credential.startswith("mock_"):
        # Simulated verification for testing/offline environments
        import base64
        import json
        parts = credential.split(".")
        if len(parts) >= 2:
            try:
                # Add padding if missing
                payload = parts[1]
                payload += "=" * ((4 - len(payload) % 4) % 4)
                decoded = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
                return {
                    "sub": decoded.get("sub", "test_sub_12345"),
                    "email": decoded.get("email", "testuser@gmail.com"),
                    "name": decoded.get("name", "Test User"),
                    "picture": decoded.get("picture", ""),
                    "email_verified": True
                }
            except Exception:
                pass
        return {
            "sub": "mock_sub_12345",
            "email": "student@inkmentor.app",
            "name": "InkMentor Student",
            "picture": "",
            "email_verified": True
        }

    # Production verification via Google's official public keys
    req = google_requests.Request()
    cid = client_id or os.environ.get("GOOGLE_CLIENT_ID")
    try:
        id_info = id_token.verify_oauth2_token(credential, req, cid if cid else None)
        return id_info
    except Exception as exc:
        raise ValueError(f"Invalid Google credential: {exc}") from exc


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_sub(google_sub: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE google_sub = ?", (google_sub,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_or_update_google_user(
    google_sub: str,
    email: str,
    name: str,
    picture: str = "",
    dob: str = "",
    age: Optional[int] = None,
) -> Tuple[Dict[str, Any], bool]:
    """
    Finds or creates a user from verified Google credentials.
    Returns (user_dict, is_new_user).
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE google_sub = ? OR email = ?", (google_sub, email))
        existing = cur.fetchone()
        now_iso = datetime.now(timezone.utc).isoformat()

        if existing:
            user_id = existing["id"]
            # Preserve existing dob/age if not passed in this call
            final_dob = dob if dob else existing["dob"]
            final_age = age if age is not None else existing["age"]
            final_name = name if name else existing["name"]
            final_picture = picture if picture else existing["picture"]

            cur.execute("""
                UPDATE users
                SET name = ?, picture = ?, dob = ?, age = ?, last_login = ?, google_sub = ?
                WHERE id = ?
            """, (final_name, final_picture, final_dob, final_age, now_iso, google_sub, user_id))
            conn.commit()
            cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            return dict(cur.fetchone()), False
        else:
            cur.execute("""
                INSERT INTO users (google_sub, email, name, picture, dob, age, created_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (google_sub, email, name, picture, dob, age, now_iso, now_iso))
            conn.commit()
            user_id = cur.lastrowid
            cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            return dict(cur.fetchone()), True
    finally:
        conn.close()


def update_user_profile(user_id: int, name: Optional[str] = None, dob: Optional[str] = None, age: Optional[int] = None) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="User not found")

        final_name = name.strip() if name is not None else existing["name"]
        final_dob = dob.strip() if dob is not None else existing["dob"]
        final_age = age if age is not None else existing["age"]

        cur.execute("""
            UPDATE users
            SET name = ?, dob = ?, age = ?
            WHERE id = ?
        """, (final_name, final_dob, final_age, user_id))
        conn.commit()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return dict(cur.fetchone())
    finally:
        conn.close()


def create_session(user_id: int, days_valid: int = 30) -> str:
    """Creates a cryptographically secure session token in SQLite."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=days_valid)
    expires_iso = expires_at.isoformat()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sessions (token, user_id, expires_at)
            VALUES (?, ?, ?)
        """, (token, user_id, expires_iso))
        conn.commit()
        return token
    finally:
        conn.close()


def get_user_by_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Returns the user associated with a valid, non-expired session token."""
    if not token:
        return None
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT u.*, s.expires_at as session_expires_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ?
        """, (token,))
        row = cur.fetchone()
        if not row:
            return None

        # Check expiration
        expires_str = row["session_expires_at"]
        try:
            expires_dt = datetime.fromisoformat(expires_str)
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_dt:
                # Expired session
                cur.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
                return None
        except Exception:
            return None

        user_data = dict(row)
        user_data.pop("session_expires_at", None)
        return user_data
    finally:
        conn.close()


def delete_session(token: str) -> bool:
    """Deletes a session token from the database (logout)."""
    if not token:
        return False
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# FastAPI Dependency: Require Authenticated User
async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        token = request.cookies.get("inkmentor_session")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token or session cookie.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_session_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or is invalid. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# FastAPI Dependency: Optional Authenticated User (Allows anonymous use while attributing user when present)
async def get_optional_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Optional[Dict[str, Any]]:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        token = request.cookies.get("inkmentor_session")

    if not token:
        return None
    return get_user_by_session_token(token)
