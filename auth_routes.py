from datetime import datetime
import sys

from fastapi import APIRouter, Depends, HTTPException

from db import ensure_user_settings, get_db_connection
from schemas import LoginPayload, RegisterPayload, ResetPasswordPayload
from security import create_session, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
async def register(payload: RegisterPayload):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE lower(email) = lower(?)", (payload.email,))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=409, detail="Email already registered")

        password_hash, password_salt = hash_password(payload.password)
        created_at = datetime.utcnow().isoformat()
        cursor.execute(
            "INSERT INTO users (full_name, email, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?, ?)",
            (payload.full_name.strip(), payload.email.lower(), password_hash, password_salt, created_at),
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        ensure_user_settings(user_id)
        session = create_session(user_id)
        return {
            "token": session["token"],
            "expires_at": session["expires_at"],
            "user": {"id": user_id, "full_name": payload.full_name.strip(), "email": payload.email.lower()},
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Register error: {str(e)}", file=sys.stderr)
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")


@router.post("/login")
async def login(payload: LoginPayload):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE lower(email) = lower(?)", (payload.email,))
        user = cursor.fetchone()
        conn.close()

        if not user or not verify_password(payload.password, user["password_hash"], user["password_salt"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        ensure_user_settings(user["id"])
        session = create_session(user["id"])
        
        # Verify session was created
        verify_conn = get_db_connection()
        verify_cursor = verify_conn.cursor()
        verify_cursor.execute("SELECT token FROM sessions WHERE token = ?", (session["token"],))
        token_exists = verify_cursor.fetchone()
        verify_conn.close()
        
        if not token_exists:
            print(f"Session creation failed for user {user['id']}", file=sys.stderr)
            raise HTTPException(status_code=500, detail="Session creation failed. Please try again.")
        
        return {
            "token": session["token"],
            "expires_at": session["expires_at"],
            "user": {"id": user["id"], "full_name": user["full_name"], "email": user["email"]},
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {str(e)}", file=sys.stderr)
        raise HTTPException(status_code=500, detail="Login failed. Please try again.")


@router.get("/me")
async def auth_me(current_user=Depends(get_current_user)):
    from db import get_current_settings

    settings = get_current_settings(current_user["id"])
    return {
        "user": {
            "id": current_user["id"],
            "full_name": current_user["full_name"],
            "email": current_user["email"],
        },
        "settings": settings,
    }


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordPayload):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE lower(email) = lower(?)", (payload.email,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="No account found for this email")

    password_hash, password_salt = hash_password(payload.new_password)
    cursor.execute(
        "UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
        (password_hash, password_salt, user["id"]),
    )
    cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
    conn.commit()
    conn.close()
    return {"message": "Password reset successful. Please login with your new password."}


@router.post("/logout")
async def logout(current_user=Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (current_user["token"],))
    conn.commit()
    conn.close()
    return {"message": "Logged out successfully"}
