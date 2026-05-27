from datetime import datetime
import os
import random
import shutil
import time

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from twilio.rest import Client

from config import ALERT_COOLDOWN, FEATURE_COLUMNS, GUARDIAN_PHONE, TWILIO_AUTH_TOKEN, TWILIO_PHONE, TWILIO_SID, UPLOAD_DIR
from db import default_settings, generate_patient_id, get_current_settings, get_db_connection
from ml_utils import predict_risk
from schemas import ContactPayload, ReportDeletePayload, SettingsPayload
from security import get_current_user

router = APIRouter(prefix="/api", tags=["monitoring"])
LAST_ALERT_TIMES: dict[int, float] = {}


def get_ml_features(user_id: int, current_hr: int, current_spo2: int, current_bp: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT heart_rate, spo2, bp_sys FROM health_history WHERE user_id = ? ORDER BY id DESC LIMIT 5",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    if len(rows) < 5:
        return [current_hr, current_spo2, current_bp, 0, 0, 0, current_hr, current_spo2]

    hr_diff = current_hr - rows[0]["heart_rate"]
    spo2_diff = current_spo2 - rows[0]["spo2"]
    bp_diff = current_bp - rows[0]["bp_sys"]
    hr_avg_5 = sum(row["heart_rate"] for row in rows) / len(rows)
    spo2_avg_5 = sum(row["spo2"] for row in rows) / len(rows)
    return [current_hr, current_spo2, current_bp, hr_diff, spo2_diff, bp_diff, hr_avg_5, spo2_avg_5]


def send_emergency_alert(user_id: int, hr: int, spo2: int, sys_bp: int, current_act: str, forecast_msg: str, status: str):
    current_time = time.time()
    last_alert_time = LAST_ALERT_TIMES.get(user_id, 0)
    if current_time - last_alert_time < ALERT_COOLDOWN:
        return

    settings = get_current_settings(user_id)
    reasons = []
    if current_act == "Resting" and hr > 100:
        reasons.append("High HR while Resting")
    if spo2 < 90:
        reasons.append("Critical Oxygen (Hypoxia)")
    if sys_bp > 155:
        reasons.append("Hypertensive Crisis (High BP)")

    reason_str = ", ".join(reasons) if reasons else "Abnormal Vital Combination"
    bp = f"{sys_bp}/{int(sys_bp * 0.7)}"
    msg = (
        f"EMERGENCY ALERT! Status: {status}\n"
        f"Patient: {settings['patient_name']} ({settings['patient_id']})\n"
        f"Reason: {reason_str}\n"
        f"HR: {hr}bpm, SpO2: {spo2}%, BP: {bp}\n"
        f"Act: {current_act}\n"
        f"Forecast: {forecast_msg[:25]}..."
    )

    twilio_ready = all([TWILIO_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE])
    if settings["sms_alerts"] and twilio_ready:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT phone FROM emergency_contacts WHERE user_id = ?", (user_id,))
        contacts = cursor.fetchall()
        conn.close()

        recipients = [GUARDIAN_PHONE] if GUARDIAN_PHONE else []
        recipients.extend(contact["phone"] for contact in contacts if contact["phone"])
        recipients = list(dict.fromkeys(recipients))

        client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
        for phone in recipients:
            try:
                client.messages.create(body=msg, from_=TWILIO_PHONE, to=phone)
            except Exception as exc:
                print(f"SMS send error to {phone}: {exc}")

    LAST_ALERT_TIMES[user_id] = current_time


def create_monitoring_router(model):
    @router.get("/vitals/latest")
    async def get_latest(background_tasks: BackgroundTasks, current_user=Depends(get_current_user)):
        user_id = current_user["id"]
        activity = random.choice(["Resting", "Walking", "Running"])
        if activity == "Running":
            hr, spo2 = random.randint(130, 165), random.randint(94, 99)
        else:
            hr, spo2 = random.randint(65, 105), random.randint(88, 100)

        bp_sys = random.randint(110, 160)
        bp_dia = int(bp_sys * 0.7)
        features = get_ml_features(user_id, hr, spo2, bp_sys)
        prediction = predict_risk(model, features)
        status_map = {0: "STABLE", 1: "CRITICAL_SOON", 2: "CRITICAL_NOW"}
        risk = status_map[prediction]
        confidence = round(random.uniform(94, 99), 1)

        if prediction == 2:
            background_tasks.add_task(send_emergency_alert, user_id, hr, spo2, bp_sys, activity, "Immediate Danger Detected", risk)

        timestamp = datetime.now().strftime("%H:%M:%S")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO health_history
            (user_id, timestamp, heart_rate, spo2, bp_sys, bp_dia, risk, confidence, activity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, timestamp, hr, spo2, bp_sys, bp_dia, risk, confidence, activity),
        )
        conn.commit()
        conn.close()

        return {
            "timestamp": timestamp,
            "hr": hr,
            "spo2": spo2,
            "bp_sys": bp_sys,
            "bp_dia": bp_dia,
            "risk": risk,
            "conf": confidence,
            "activity": activity,
            "prediction": prediction,
        }

    return router


@router.get("/vitals/history")
async def get_history(limit: int = 5, current_user=Depends(get_current_user)):
    safe_limit = max(1, min(limit, 100))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM health_history WHERE user_id = ? ORDER BY id DESC LIMIT ?", (current_user["id"], safe_limit))
    rows = cursor.fetchall()
    conn.close()
    return [{"timestamp": row["timestamp"], "hr": row["heart_rate"], "spo2": row["spo2"], "bp_sys": row["bp_sys"], "bp_dia": row["bp_dia"], "risk": row["risk"]} for row in rows]


@router.get("/contacts")
async def get_contacts(current_user=Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, phone, relationship FROM emergency_contacts WHERE user_id = ? ORDER BY id DESC", (current_user["id"],))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": row["id"], "name": row["name"], "phone": row["phone"], "relationship": row["relationship"]} for row in rows]


@router.post("/contacts")
async def add_contact(contact: ContactPayload, current_user=Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO emergency_contacts
        (user_id, name, phone, relationship, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            current_user["id"],
            contact.name.strip(),
            contact.phone.strip(),
            contact.relationship.strip(),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.commit()
    conn.close()
    return {"message": "Contact added successfully"}


@router.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: int, current_user=Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM emergency_contacts WHERE id = ? AND user_id = ?", (contact_id, current_user["id"]))
    conn.commit()
    conn.close()
    return {"message": "Contact deleted successfully"}


@router.get("/settings")
async def get_settings(current_user=Depends(get_current_user)):
    return get_current_settings(current_user["id"])


@router.post("/settings/update")
async def update_settings(settings: SettingsPayload, current_user=Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    payload = settings.model_dump(exclude_none=True)
    update_fields = []
    values = []

    if "sms_alerts" in payload:
        update_fields.append("sms_alerts = ?")
        values.append(int(payload["sms_alerts"]))
    if "sound_alerts" in payload:
        update_fields.append("sound_alerts = ?")
        values.append(int(payload["sound_alerts"]))
    if "vibration" in payload:
        update_fields.append("vibration = ?")
        values.append(int(payload["vibration"]))
    if "patient_name" in payload:
        update_fields.append("patient_name = ?")
        values.append((payload["patient_name"] or "").strip() or default_settings(current_user["id"])["patient_name"])
    if "patient_id" in payload:
        update_fields.append("patient_id = ?")
        values.append((payload["patient_id"] or "").strip() or generate_patient_id(current_user["id"]))

    update_fields.append("updated_at = ?")
    values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    values.append(current_user["id"])
    cursor.execute(f"UPDATE user_settings SET {', '.join(update_fields)} WHERE user_id = ?", values)
    conn.commit()
    conn.close()
    return {"message": "Settings updated successfully"}


@router.post("/reports/upload")
async def upload_report(file: UploadFile = File(...), description: str = "", current_user=Depends(get_current_user)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = os.path.basename(file.filename)
    filename = f"user_{current_user['id']}_{timestamp}_{safe_name}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reports (user_id, filename, filepath, uploaded_at, description) VALUES (?, ?, ?, ?, ?)",
        (current_user["id"], safe_name, filepath, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), description),
    )
    conn.commit()
    conn.close()
    return {"message": "Report uploaded successfully", "filename": filename}


@router.get("/reports")
def get_reports(current_user=Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, uploaded_at, description FROM reports WHERE user_id = ? ORDER BY uploaded_at DESC", (current_user["id"],))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": row["id"], "filename": row["filename"], "uploaded_at": row["uploaded_at"], "description": row["description"]} for row in rows]


@router.post("/reports/delete")
async def delete_report(data: ReportDeletePayload, current_user=Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filepath FROM reports WHERE id = ? AND user_id = ?", (data.report_id, current_user["id"]))
    result = cursor.fetchone()
    if not result:
        conn.close()
        raise HTTPException(status_code=404, detail="Report not found")

    filepath = result["filepath"]
    cursor.execute("DELETE FROM reports WHERE id = ? AND user_id = ?", (data.report_id, current_user["id"]))
    conn.commit()
    conn.close()
    if os.path.exists(filepath):
        os.remove(filepath)
    return {"message": "Report deleted successfully"}


@router.get("/reports/{report_id}")
def get_report_file(report_id: int, current_user=Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filepath, filename FROM reports WHERE id = ? AND user_id = ?", (report_id, current_user["id"]))
    result = cursor.fetchone()
    conn.close()
    if not result:
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(result["filepath"], media_type="application/pdf", filename=result["filename"])
