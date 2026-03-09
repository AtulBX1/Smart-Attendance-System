import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
import joblib

print("1. Imports OK")

try:
    df = pd.read_csv("data/processed/processed_attendance.csv")
    print("2. Data Load OK")
    
    attendance_summary = df.groupby("StudentID")["Present"].mean()
    risk_students = attendance_summary[attendance_summary < 0.75].index
    df["Risk"] = df["StudentID"].apply(lambda x: 1 if x in risk_students else 0)
    
    X = df[["Rolling_Attendance", "Absence_Streak", "Semester_Attendance", "Attendance_Trend"]].head(100)
    y = df["Risk"].head(100)
    print("3. Preprocessing OK")
    
    rf = RandomForestClassifier(n_estimators=10, random_state=42)
    rf.fit(X, y)
    print("4. RF Fit OK")
    
    joblib.dump(rf, "models/rf_test.pkl")
    print("5. RF Save OK")
    
    xgb = XGBClassifier(n_estimators=10, use_label_encoder=False, eval_metric="logloss")
    xgb.fit(X, y)
    print("6. XGB Fit OK")
    
    joblib.dump(xgb, "models/xgb_test.pkl")
    print("7. XGB Save OK")
except Exception as e:
    print(f"Error: {e}")
