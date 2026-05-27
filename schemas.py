from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared email validator — single source of truth
# ---------------------------------------------------------------------------

def _validate_email(value: str) -> str:
    email = value.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("Enter a valid email address")
    local_part, _, domain = email.partition("@")
    if not local_part or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("Enter a valid email address")
    return email


# ---------------------------------------------------------------------------
# Auth payloads
# ---------------------------------------------------------------------------

class RegisterPayload(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


class LoginPayload(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


class ResetPasswordPayload(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


# ---------------------------------------------------------------------------
# Monitoring payloads
# ---------------------------------------------------------------------------

class ContactPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=5, max_length=20)
    relationship: str = Field(..., min_length=1, max_length=50)


class SettingsPayload(BaseModel):
    sms_alerts: bool | None = None
    sound_alerts: bool | None = None
    vibration: bool | None = None
    patient_name: str | None = Field(default=None, max_length=100)
    patient_id: str | None = Field(default=None, max_length=50)


class ReportDeletePayload(BaseModel):
    report_id: int
