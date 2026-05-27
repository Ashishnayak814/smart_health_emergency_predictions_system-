import os


def load_env_file(env_path: str) -> None:
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key:
                os.environ.setdefault(key, value)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

load_env_file(os.path.join(PROJECT_DIR, ".env"))

DB_PATH = os.path.join(BASE_DIR, "health_system.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
MODEL_PATH = os.path.join(BASE_DIR, "trend_model.pkl")

SESSION_TTL_DAYS = 14
DEFAULT_PATIENT_NAME = "Patient"
DEFAULT_PATIENT_ID_PREFIX = "SES"
FEATURE_COLUMNS = ["hr", "spo2", "bp", "hr_diff", "spo2_diff", "bp_diff", "hr_avg_5", "spo2_avg_5"]

TWILIO_SID = os.getenv("TWILIO_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE = os.getenv("TWILIO_PHONE", "")
GUARDIAN_PHONE = os.getenv("GUARDIAN_PHONE", "")
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]
ALERT_COOLDOWN = 300
