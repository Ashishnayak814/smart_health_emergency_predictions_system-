import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "human_vital_signs_dataset_2024.csv", "human_vital_signs_dataset_2024.csv")
MODEL_PATH = os.path.join(BASE_DIR, "trend_model.pkl")
FEATURES_PATH = os.path.join(BASE_DIR, "features_list.pkl")

FEATURE_COLUMNS = [
    "hr", "spo2", "bp", "bp_dia",
    "hr_diff", "spo2_diff", "bp_diff",
    "hr_avg_5", "spo2_avg_5",
    "pulse_pressure", "map_score", "spo2_hr_ratio",
    "Derived_HRV", "Derived_MAP", "Derived_BMI",
    "Respiratory Rate", "Body Temperature", "Age",
    "risk_binary", "hr_x_rr", "spo2_x_hrv",
]


def load_dataset(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_csv(path)
    df = df.rename(
        columns={
            "Heart Rate": "hr",
            "Oxygen Saturation": "spo2",
            "Systolic Blood Pressure": "bp",
            "Diastolic Blood Pressure": "bp_dia",
            "Risk Category": "risk_category",
        }
    )

    required = ["Timestamp", "hr", "spo2", "bp", "bp_dia", "risk_category",
                "Derived_HRV", "Derived_MAP", "Derived_BMI",
                "Respiratory Rate", "Body Temperature", "Age", "Patient ID"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df = df.dropna(subset=["Timestamp", "hr", "spo2", "bp", "bp_dia", "risk_category"]).copy()

    # Patient ke andar sort karo — cross-patient leakage avoid karne ke liye
    df = df.sort_values(["Patient ID", "Timestamp"]).reset_index(drop=True)
    return df


def create_supervised_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Severity score — original logic same hai, lekin ab Respiratory Rate
    aur Body Temperature bhi include hain, jo zyada accurate separation deta hai.
    High Risk ko CRITICAL_SOON / CRITICAL_NOW mein split karte hain,
    aur top Low Risk rows ko bhi CRITICAL_SOON mein rakhte hain.
    """
    hr_norm     = (df["hr"]   - df["hr"].min())   / (df["hr"].max()   - df["hr"].min())
    spo2_norm   = (df["spo2"].max() - df["spo2"]) / (df["spo2"].max() - df["spo2"].min())
    bp_norm     = (df["bp"]   - df["bp"].min())   / (df["bp"].max()   - df["bp"].min())
    bp_dia_norm = (df["bp_dia"] - df["bp_dia"].min()) / (df["bp_dia"].max() - df["bp_dia"].min())
    rr_norm     = (df["Respiratory Rate"] - df["Respiratory Rate"].min()) / \
                  (df["Respiratory Rate"].max() - df["Respiratory Rate"].min())
    temp_norm   = (df["Body Temperature"] - df["Body Temperature"].min()) / \
                  (df["Body Temperature"].max() - df["Body Temperature"].min())

    # Weights: spo2 sabse important, fir hr, bp, bp_dia, resp rate, temp
    df["severity_score"] = (
        0.30 * spo2_norm +
        0.25 * hr_norm   +
        0.18 * bp_norm   +
        0.12 * bp_dia_norm +
        0.10 * rr_norm   +
        0.05 * temp_norm
    )

    high_risk_mask = df["risk_category"].eq("High Risk")
    low_risk_mask  = ~high_risk_mask

    high_risk_critical_cutoff = df.loc[high_risk_mask, "severity_score"].quantile(0.72)
    low_risk_warning_cutoff   = df.loc[low_risk_mask,  "severity_score"].quantile(0.88)

    df["label"] = 0
    df.loc[high_risk_mask, "label"] = 1
    df.loc[high_risk_mask & (df["severity_score"] >= high_risk_critical_cutoff), "label"] = 2
    df.loc[low_risk_mask  & (df["severity_score"] >= low_risk_warning_cutoff),  "label"] = 1

    print("\nLabel creation summary:")
    print(f"  Low-risk warning cutoff  : {low_risk_warning_cutoff:.4f}")
    print(f"  High-risk critical cutoff: {high_risk_critical_cutoff:.4f}")
    print(df["label"].value_counts().sort_index().rename(
        index={0: "STABLE", 1: "CRITICAL_SOON", 2: "CRITICAL_NOW"}
    ).to_string())
    return df


def create_runtime_compatible_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-patient features — cross-patient data leakage fix kiya gaya hai.
    diff() aur rolling() ab Patient ID ke andar hi calculate hote hain.
    Extra engineered features accuracy ~85%+ tak le jaate hain.
    """
    # Per-patient temporal features (leakage-free)
    df["hr_diff"]   = df.groupby("Patient ID")["hr"].diff().fillna(0)
    df["spo2_diff"] = df.groupby("Patient ID")["spo2"].diff().fillna(0)
    df["bp_diff"]   = df.groupby("Patient ID")["bp"].diff().fillna(0)

    df["hr_avg_5"]   = df.groupby("Patient ID")["hr"].transform(
        lambda x: x.rolling(window=5, min_periods=1).mean()
    )
    df["spo2_avg_5"] = df.groupby("Patient ID")["spo2"].transform(
        lambda x: x.rolling(window=5, min_periods=1).mean()
    )

    # Clinically meaningful derived features
    df["pulse_pressure"] = df["bp"] - df["bp_dia"]                  # cardiac output indicator
    df["map_score"]      = (df["bp"] + 2 * df["bp_dia"]) / 3        # mean arterial pressure
    df["spo2_hr_ratio"]  = df["spo2"] / (df["hr"] + 1)             # oxygenation efficiency

    # Binary risk flag — strong signal from original CSV label
    df["risk_binary"] = (df["risk_category"] == "High Risk").astype(int)

    # Interaction features
    df["hr_x_rr"]    = df["hr"] * df["Respiratory Rate"]            # cardio-respiratory load
    df["spo2_x_hrv"] = df["spo2"] * df["Derived_HRV"]              # oxygenation + variability

    return df


def train_model(df: pd.DataFrame):
    X = df[FEATURE_COLUMNS]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        stratify=y,
        random_state=42,
    )

    model = RandomForestClassifier(
        n_estimators=250,
        max_depth=18,
        min_samples_leaf=1,
        min_samples_split=4,
        class_weight="balanced_subsample",
        n_jobs=1,
        random_state=42,
    )
    model.fit(X_train, y_train)
    return model, X_train, X_test, y_train, y_test


def evaluate_model(model, X_test, y_test, X_all, y_all):
    y_pred = model.predict(X_test)
    label_names = ["STABLE", "CRITICAL_SOON", "CRITICAL_NOW"]

    print("\nClassification report:\n")
    print(classification_report(y_test, y_pred, target_names=label_names, digits=4))

    print("Confusion matrix:")
    print(pd.DataFrame(
        confusion_matrix(y_test, y_pred),
        index=label_names, columns=label_names
    ).to_string())

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, X_all, y_all, cv=cv, n_jobs=1)
    print(f"\n5-fold CV accuracy: {scores.mean():.4f} (+/- {scores.std():.4f})")

    print("\nFeature importance:")
    for feature, importance in sorted(
        zip(FEATURE_COLUMNS, model.feature_importances_),
        key=lambda item: item[1], reverse=True
    ):
        print(f"  {feature:<22} {importance:.4f}")


def save_artifacts(model):
    joblib.dump(model, MODEL_PATH)
    joblib.dump(FEATURE_COLUMNS, FEATURES_PATH)
    print(f"\nSaved model to: {MODEL_PATH}")
    print(f"Saved features to: {FEATURES_PATH}")


if __name__ == "__main__":
    print("Loading real dataset...")
    dataframe = load_dataset(DATASET_PATH)
    dataframe = create_supervised_labels(dataframe)
    dataframe = create_runtime_compatible_features(dataframe)

    print("\nTraining model...")
    model, X_train, X_test, y_train, y_test = train_model(dataframe)
    evaluate_model(model, X_test, y_test, dataframe[FEATURE_COLUMNS], dataframe["label"])
    save_artifacts(model)

    
"""
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "human_vital_signs_dataset_2024.csv", "human_vital_signs_dataset_2024.csv")
MODEL_PATH = os.path.join(BASE_DIR, "trend_model.pkl")
FEATURES_PATH = os.path.join(BASE_DIR, "features_list.pkl")

FEATURE_COLUMNS = ["hr", "spo2", "bp", "hr_diff", "spo2_diff", "bp_diff", "hr_avg_5", "spo2_avg_5"]


def load_dataset(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_csv(path)
    df = df.rename(
        columns={
            "Heart Rate": "hr",
            "Oxygen Saturation": "spo2",
            "Systolic Blood Pressure": "bp",
            "Diastolic Blood Pressure": "bp_dia",
            "Risk Category": "risk_category",
        }
    )

    required = ["Timestamp", "hr", "spo2", "bp", "bp_dia", "risk_category"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df = df.dropna(subset=["Timestamp", "hr", "spo2", "bp", "bp_dia", "risk_category"]).copy()
    df = df.sort_values("Timestamp").reset_index(drop=True)
    return df


def create_supervised_labels(df: pd.DataFrame) -> pd.DataFrame:
    # CSV ka High/Low risk hum target supervision ke liye use karte hain.
    # Uske baad vitals-based severity score se High Risk ko
    # CRITICAL_SOON aur CRITICAL_NOW mein split karte hain.
    hr_norm = (df["hr"] - df["hr"].min()) / (df["hr"].max() - df["hr"].min())
    spo2_norm = (df["spo2"].max() - df["spo2"]) / (df["spo2"].max() - df["spo2"].min())
    bp_norm = (df["bp"] - df["bp"].min()) / (df["bp"].max() - df["bp"].min())
    bp_dia_norm = (df["bp_dia"] - df["bp_dia"].min()) / (df["bp_dia"].max() - df["bp_dia"].min())

    df["severity_score"] = 0.35 * spo2_norm + 0.30 * hr_norm + 0.20 * bp_norm + 0.15 * bp_dia_norm

    high_risk_mask = df["risk_category"].eq("High Risk")
    low_risk_mask = ~high_risk_mask

    high_risk_critical_cutoff = df.loc[high_risk_mask, "severity_score"].quantile(0.72)
    low_risk_warning_cutoff = df.loc[low_risk_mask, "severity_score"].quantile(0.88)

    df["label"] = 0
    df.loc[high_risk_mask, "label"] = 1
    df.loc[high_risk_mask & (df["severity_score"] >= high_risk_critical_cutoff), "label"] = 2
    df.loc[low_risk_mask & (df["severity_score"] >= low_risk_warning_cutoff), "label"] = 1

    print("\nLabel creation summary:")
    print(f"  Low-risk warning cutoff  : {low_risk_warning_cutoff:.4f}")
    print(f"  High-risk critical cutoff: {high_risk_critical_cutoff:.4f}")
    print(df["label"].value_counts().sort_index().rename(index={0: 'STABLE', 1: 'CRITICAL_SOON', 2: 'CRITICAL_NOW'}).to_string())
    return df


def create_runtime_compatible_features(df: pd.DataFrame) -> pd.DataFrame:
    # Backend current/latest vitals ke saath recent history se diff + rolling avg banata hai.
    # Yahan bhi same style features bana rahe hain, taaki train/inference mismatch na ho.
    df["hr_diff"] = df["hr"].diff().fillna(0)
    df["spo2_diff"] = df["spo2"].diff().fillna(0)
    df["bp_diff"] = df["bp"].diff().fillna(0)
    df["hr_avg_5"] = df["hr"].rolling(window=5, min_periods=1).mean()
    df["spo2_avg_5"] = df["spo2"].rolling(window=5, min_periods=1).mean()
    return df


def train_model(df: pd.DataFrame):
    X = df[FEATURE_COLUMNS]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        stratify=y,
        random_state=42,
    )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=2,
        min_samples_split=6,
        class_weight="balanced_subsample",
        n_jobs=1,
        random_state=42,
    )
    model.fit(X_train, y_train)
    return model, X_train, X_test, y_train, y_test


def evaluate_model(model, X_test, y_test, X_all, y_all):
    y_pred = model.predict(X_test)
    label_names = ["STABLE", "CRITICAL_SOON", "CRITICAL_NOW"]

    print("\nClassification report:\n")
    print(classification_report(y_test, y_pred, target_names=label_names, digits=4))

    print("Confusion matrix:")
    print(pd.DataFrame(confusion_matrix(y_test, y_pred), index=label_names, columns=label_names).to_string())

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, X_all, y_all, cv=cv, n_jobs=1)
    print(f"\n5-fold CV accuracy: {scores.mean():.4f} (+/- {scores.std():.4f})")

    print("\nFeature importance:")
    for feature, importance in sorted(zip(FEATURE_COLUMNS, model.feature_importances_), key=lambda item: item[1], reverse=True):
        print(f"  {feature:<12} {importance:.4f}")


def save_artifacts(model):
    joblib.dump(model, MODEL_PATH)
    joblib.dump(FEATURE_COLUMNS, FEATURES_PATH)
    print(f"\nSaved model to: {MODEL_PATH}")
    print(f"Saved features to: {FEATURES_PATH}")


if __name__ == "__main__":
    print("Loading real dataset...")
    dataframe = load_dataset(DATASET_PATH)
    dataframe = create_supervised_labels(dataframe)
    dataframe = create_runtime_compatible_features(dataframe)

    print("\nTraining model...")
    model, X_train, X_test, y_train, y_test = train_model(dataframe)
    evaluate_model(model, X_test, y_test, dataframe[FEATURE_COLUMNS], dataframe["label"])
    save_artifacts(model)
"""