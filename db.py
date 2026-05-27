from datetime import datetime
import sqlite3

from config import DB_PATH, DEFAULT_PATIENT_ID_PREFIX, DEFAULT_PATIENT_NAME


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def generate_patient_id(user_id: int) -> str:
    return f"{DEFAULT_PATIENT_ID_PREFIX}{user_id:05d}"


def default_settings(user_id: int):
    return {
        "sms_alerts": False,
        "sound_alerts": True,
        "vibration": True,
        "patient_name": f"{DEFAULT_PATIENT_NAME} {user_id}",
        "patient_id": generate_patient_id(user_id),
    }


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """CREATE TABLE IF NOT EXISTS users
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        password_salt TEXT NOT NULL,
        created_at TEXT NOT NULL)"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS sessions
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id))"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS health_history
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        timestamp TEXT,
        heart_rate INTEGER, spo2 INTEGER, bp_sys INTEGER, bp_dia INTEGER,
        risk TEXT, confidence FLOAT, activity TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id))"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS emergency_contacts
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT, phone TEXT, relationship TEXT, created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id))"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS user_settings
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        sms_alerts BOOLEAN DEFAULT 0,
        sound_alerts BOOLEAN DEFAULT 1,
        vibration BOOLEAN DEFAULT 1,
        patient_name TEXT DEFAULT 'Patient',
        patient_id TEXT DEFAULT 'SES00000',
        updated_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id))"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS reports
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT, filepath TEXT, uploaded_at TEXT, description TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id))"""
    )

    for statement in [
        "ALTER TABLE health_history ADD COLUMN user_id INTEGER",
        "ALTER TABLE emergency_contacts ADD COLUMN user_id INTEGER",
        "ALTER TABLE user_settings ADD COLUMN user_id INTEGER",
        "ALTER TABLE user_settings ADD COLUMN patient_name TEXT DEFAULT 'Patient'",
        "ALTER TABLE user_settings ADD COLUMN patient_id TEXT DEFAULT 'SES00000'",
        "ALTER TABLE reports ADD COLUMN user_id INTEGER",
    ]:
        try:
            cursor.execute(statement)
        except sqlite3.OperationalError:
            pass

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_health_history_user_id ON health_history(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_user_id ON emergency_contacts(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id)")

    repair_legacy_user_scoped_rows(cursor)

    conn.commit()
    conn.close()


def repair_legacy_user_scoped_rows(cursor):
    cursor.execute(
        """
        UPDATE health_history
        SET
            user_id = CAST(timestamp AS INTEGER),
            timestamp = CAST(heart_rate AS TEXT),
            heart_rate = spo2,
            spo2 = bp_sys,
            bp_sys = bp_dia,
            bp_dia = CAST(risk AS INTEGER),
            risk = CAST(confidence AS TEXT),
            confidence = CAST(activity AS FLOAT),
            activity = CAST(user_id AS TEXT)
        WHERE timestamp GLOB '[0-9]*'
          AND user_id IN ('Resting', 'Walking', 'Running')
        """
    )

    cursor.execute(
        """
        UPDATE emergency_contacts
        SET
            user_id = CAST(name AS INTEGER),
            name = phone,
            phone = relationship,
            relationship = created_at,
            created_at = CAST(user_id AS TEXT)
        WHERE name GLOB '[0-9]*'
          AND user_id LIKE '____-__-__ __:__:__'
        """
    )

    cursor.execute(
        """
        UPDATE reports
        SET
            user_id = CAST(filename AS INTEGER),
            filename = filepath,
            filepath = uploaded_at,
            uploaded_at = description,
            description = CASE
                WHEN user_id IS NULL OR user_id = '' THEN ''
                ELSE CAST(user_id AS TEXT)
            END
        WHERE filename GLOB '[0-9]*'
        """
    )


def ensure_user_settings(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM user_settings WHERE user_id = ?", (user_id,))
    existing = cursor.fetchone()
    if not existing:
        defaults = default_settings(user_id)
        cursor.execute(
            """
            INSERT INTO user_settings
            (user_id, sms_alerts, sound_alerts, vibration, patient_name, patient_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                int(defaults["sms_alerts"]),
                int(defaults["sound_alerts"]),
                int(defaults["vibration"]),
                defaults["patient_name"],
                defaults["patient_id"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
    conn.close()


def get_current_settings(user_id: int):
    ensure_user_settings(user_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_settings WHERE user_id = ? LIMIT 1", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return default_settings(user_id)

    settings = default_settings(user_id)
    settings["sms_alerts"] = bool(row["sms_alerts"])
    settings["sound_alerts"] = bool(row["sound_alerts"])
    settings["vibration"] = bool(row["vibration"])
    settings["patient_name"] = row["patient_name"] or settings["patient_name"]
    settings["patient_id"] = row["patient_id"] or settings["patient_id"]
    return settings
