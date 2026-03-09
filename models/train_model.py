import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from xgboost import XGBClassifier
import joblib
import numpy as np

# Load processed data
df = pd.read_csv("data/processed/processed_attendance.csv")

# Create risk label
attendance_summary = df.groupby("StudentID")["Present"].mean()
risk_students = attendance_summary[attendance_summary < 0.75].index
df["Risk"] = df["StudentID"].apply(lambda x: 1 if x in risk_students else 0)

features = [
    "Rolling_Attendance",
    "Absence_Streak",
    "Semester_Attendance",
    "Attendance_Trend"
]
X = df[features]
y = df["Risk"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Random Forest
rf_model = RandomForestClassifier(
    n_estimators=100,
    class_weight="balanced",
    random_state=42
)
rf_model.fit(X_train, y_train)

# XGBoost
xgb_model = XGBClassifier(
    n_estimators=100,
    eval_metric="logloss",
    use_label_encoder=False
)
xgb_model.fit(X_train, y_train)

# Individual Model Reports
print("Random Forest Report:")
print(classification_report(y_test, rf_model.predict(X_test)))

print("XGBoost Report:")
print(classification_report(y_test, xgb_model.predict(X_test)))

# ===== Ensemble Model (Average Probability) =====
rf_probs = rf_model.predict_proba(X_test)[:, 1]
xgb_probs = xgb_model.predict_proba(X_test)[:, 1]

ensemble_probs = (rf_probs + xgb_probs) / 2
ensemble_preds = (ensemble_probs > 0.5).astype(int)

print("Ensemble Model Report:")
print(classification_report(y_test, ensemble_preds))

# Save individual models
joblib.dump(rf_model, "models/rf_model.pkl")
joblib.dump(xgb_model, "models/xgb_model.pkl")

print("Models trained and saved successfully!")