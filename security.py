from datetime import datetime, timedelta
from typing import Optional
import hashlib
import hmac
import secrets

from fastapi import Depends, Header, HTTPException

from config import SESSION_TTL_DAYS
from db import ensure_user_settings, get_db_connection


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return hashed, salt


def verify_password(password: str, password_hash: str, password_salt: str) -> bool:
    computed_hash, _ = hash_password(password, password_salt)
    return hmac.compare_digest(computed_hash, password_hash)


def create_session(user_id: int) -> dict:
    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    expires_at = now + timedelta(days=SESSION_TTL_DAYS)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (user_id, token, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (user_id, token, expires_at.isoformat(), now.isoformat()),
    )
    conn.commit()
    conn.close()
    return {"token": token, "expires_at": expires_at.isoformat()}


def get_current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = authorization.removeprefix("Bearer ").strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT users.id, users.full_name, users.email, sessions.expires_at
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ?
        """,
        (token,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid session")

    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Session expired")

    ensure_user_settings(row["id"])
    return {"id": row["id"], "full_name": row["full_name"], "email": row["email"], "token": token}


CurrentUser = Depends(get_current_user)
