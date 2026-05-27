import sys

from db import get_db_connection
from security import hash_password


def reset_password(email: str, new_password: str) -> int:
    normalized_email = email.strip().lower()
    password_hash, password_salt = hash_password(new_password)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE lower(email) = lower(?)", (normalized_email,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise ValueError(f"User not found for email: {normalized_email}")

    cursor.execute(
        "UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
        (password_hash, password_salt, user["id"]),
    )
    cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
    conn.commit()
    conn.close()
    return int(user["id"])


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python backend/reset_password.py <email> <new_password>")
        return 1

    email, new_password = sys.argv[1], sys.argv[2]
    if len(new_password) < 8:
        print("Password must be at least 8 characters.")
        return 1

    try:
        user_id = reset_password(email, new_password)
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"Password reset successful for user_id={user_id}, email={email.strip().lower()}")
    print("Existing sessions cleared. Please login again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
