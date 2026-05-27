# Smart Emergency Alert System

This project contains a FastAPI backend and a static frontend dashboard for monitoring simulated health vitals, tracking risk predictions, managing emergency contacts, storing PDF reports, and authenticating multiple users with isolated data.

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

## Notes

- Uploaded reports are stored in `backend/uploads/`.
- SQLite data is stored in `backend/health_system.db`.
- The current ML model may warn if your local `scikit-learn` version differs from the version used to train the `.pkl` file.
- For production, set `CORS_ORIGINS` to your deployed frontend URL instead of `*`.
