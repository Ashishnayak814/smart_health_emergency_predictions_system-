import os

import joblib
import pandas as pd

from config import FEATURE_COLUMNS, MODEL_PATH


def load_model():
    try:
        model = joblib.load(MODEL_PATH) if MODEL_PATH and os.path.exists(MODEL_PATH) else None
        if model:
            print("ML Trend Model Loaded")
        else:
            print(f"trend_model.pkl not found at {MODEL_PATH}")
        return model
    except Exception as exc:
        print(f"Error loading model: {exc}")
        return None


def predict_risk(model, features: list[float]) -> int:
    if model is None:
        return 0
    input_df = pd.DataFrame([features], columns=FEATURE_COLUMNS)
    return int(model.predict(input_df)[0])
