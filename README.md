# Smart Emergency Alert System

This project contains a FastAPI backend and a static frontend dashboard for monitoring simulated health vitals, tracking risk predictions, managing emergency contacts, storing PDF reports, and authenticating multiple users with isolated data.

 Developed a real-time health monitoring system that continuously tracks vital parameters — Heart Rate, Blood Oxygen Saturation (SpO₂), and Blood Pressure and predicts potential medical emergencies using a Random Forest machine learning model. The system classifies health conditions into three categories: Stable, Critical Soon, and Critical Now, using trend-based feature engineering instead of fixed thresholds. When a critical condition is detected with confidence above 0.85, the system automatically sends SMS alerts to emergency contacts via Twilio API without any manual intervention. A web-based dashboard built with HTML, JavaScript, and Chart.js provides real-time data visualization. Backend developed using FastAPI with SQLite database for storing health records, emergency contacts, and user settings

## Project Structure

- `backend/main.py`: FastAPI server and API routes
- `backend/ml_train_real.py`: training script for the real CSV dataset
- `frontend/index.html`: dashboard UI
- `frontend/script.js`: dashboard logic
- `frontend/style.css`: custom styles

## Setup

1. Create and activate a virtual environment.
2. Install the required Python packages:

```powershell
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in the Twilio values if you want real SMS alerts.

Environment variables:

- `TWILIO_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE`
- `GUARDIAN_PHONE`
- `CORS_ORIGINS`

If these values are not set, the app still runs, but SMS sending stays disabled.

## Authentication

- Users can register with `full_name`, `email`, and `password`
- Login returns a bearer token session
- All vitals history, contacts, settings, and reports are stored per user
- Frontend stores the session token in local storage and sends it on every API call

## Run

Start the backend:

```powershell
python backend/main.py
```

Then open:

`http://127.0.0.1:8001/frontend/index.html`

<img width="1919" height="1067" alt="Screenshot 2026-04-09 090604" src="https://github.com/user-attachments/assets/ae6481a8-d751-49b4-b6e2-d392e92c3fd2" />

alert:
<img width="1919" height="1079" alt="Screenshot 2026-04-09 094937" src="https://github.com/user-attachments/assets/9f675832-c997-4818-8713-f5beb8afef6a" />


## Notes

- Uploaded reports are stored in `backend/uploads/`.
- SQLite data is stored in `backend/health_system.db`.
- The current ML model may warn if your local `scikit-learn` version differs from the version used to train the `.pkl` file.
- For production, set `CORS_ORIGINS` to your deployed frontend URL instead of `*`.
