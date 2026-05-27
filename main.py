import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from auth_routes import router as auth_router
from config import CORS_ORIGINS, FRONTEND_DIR, UPLOAD_DIR
from db import init_db
from ml_utils import load_model
from monitoring_routes import create_monitoring_router, router as monitoring_router

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ---------------------------------------------------------------------------
# Static directories
# ---------------------------------------------------------------------------

os.makedirs(UPLOAD_DIR, exist_ok=True)

if not os.path.isdir(FRONTEND_DIR):
    raise RuntimeError(f"Frontend directory does not exist: {FRONTEND_DIR}")

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

# ---------------------------------------------------------------------------
# Database — single init_db() creates all tables (users, sessions,
# health_history, emergency_contacts, user_settings, reports)
# ---------------------------------------------------------------------------

init_db()

# ---------------------------------------------------------------------------
# ML model
# ---------------------------------------------------------------------------

model = load_model()

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router)                      # /api/auth/*
app.include_router(create_monitoring_router(model))  # /api/vitals/latest (needs model)
app.include_router(monitoring_router)                # all other /api/* routes

# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/frontend/index.html")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
