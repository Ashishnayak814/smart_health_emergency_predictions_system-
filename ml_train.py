import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
import joblib

# -------------------------------
# 1. GENERATE REALISTIC SEQUENTIAL DATA
# -------------------------------
def generate_sequential_data(n_patients=150, readings_per_patient=60):
    np.random.seed(42)
    all_data = []

    for p in range(n_patients):
        hr, spo2, bp = 75, 98, 120

        for t in range(readings_per_patient):
            # Normal fluctuations
            hr += np.random.randint(-2, 3)
            spo2 += np.random.uniform(-0.5, 0.5)
            bp += np.random.randint(-1, 2)

            # Emergency trend (30% patients)
            if p < int(n_patients * 0.3) and t > 40:
                hr += 4
                spo2 -= 1
                bp += 3

            # Labeling (3 classes)
            if spo2 < 90 or hr > 130:
                label = 2  # CRITICAL
            elif spo2 < 94 or hr > 110:
                label = 1  # CRITICAL_SOON
            else:
                label = 0  # STABLE

            all_data.append([p, hr, spo2, bp, label])

    return pd.DataFrame(all_data, columns=['patient_id','hr','spo2','bp','label'])


# -------------------------------
# 2. FEATURE ENGINEERING (TREND BASED)
# -------------------------------
def create_trend_features(df):

    # Change between readings
    df['hr_diff'] = df.groupby('patient_id')['hr'].diff().fillna(0)
    df['spo2_diff'] = df.groupby('patient_id')['spo2'].diff().fillna(0)
    df['bp_diff'] = df.groupby('patient_id')['bp'].diff().fillna(0)

    # Rolling averages (smooth trend)
    df['hr_avg_5'] = df.groupby('patient_id')['hr'].transform(
        lambda x: x.rolling(5).mean()).fillna(df['hr'])

    df['spo2_avg_5'] = df.groupby('patient_id')['spo2'].transform(
        lambda x: x.rolling(5).mean()).fillna(df['spo2'])

    return df


# -------------------------------
# 3. LOAD + PROCESS DATA
# -------------------------------
df = generate_sequential_data()
df = create_trend_features(df)

features = [
    'hr', 'spo2', 'bp',
    'hr_diff', 'spo2_diff', 'bp_diff',
    'hr_avg_5', 'spo2_avg_5'
]

X = df[features]
y = df['label']

# -------------------------------
# 4. TRAIN TEST SPLIT
# -------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

# -------------------------------
# 5. MODEL TRAINING
# -------------------------------
model = RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    min_samples_split=5,
    class_weight='balanced',
    random_state=42
)

model.fit(X_train, y_train)

# -------------------------------
# 6. EVALUATION
# -------------------------------
y_pred = model.predict(X_test)

print("\n📊 Classification Report:\n")
print(classification_report(y_test, y_pred))

print("\n📊 Confusion Matrix:\n")
print(confusion_matrix(y_test, y_pred))

cv_scores = cross_val_score(model, X, y, cv=5)
print("\n✅ Cross Validation Accuracy:", np.mean(cv_scores))

# -------------------------------
# 7. SAVE MODEL
# -------------------------------
joblib.dump(model, 'trend_model.pkl')
joblib.dump(features, 'features_list.pkl')

print("\n FINAL MODEL SAVED: trend_model.pkl")