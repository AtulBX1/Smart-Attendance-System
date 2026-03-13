import sqlite3
import pandas as pd
import numpy as np
import pickle
import os

base_dir = os.path.dirname(os.path.dirname(__file__))

def get_db_connection():
    db_path = os.path.join(base_dir, "attendance_system.db")
    return sqlite3.connect(db_path)

def run_notifications_job():
    print("Starting Notification & Nudge Job...")
    conn = get_db_connection()
    
    # Load model for risk prediction
    model_path = os.path.join(base_dir, "models", "rf_model.pkl")
    if os.path.exists(model_path):
        model = pickle.load(open(model_path, "rb"))
    else:
        model = None
        print(f"Warning: Model not found at {model_path}")
        
    query = """
    SELECT a.*, a.rowid as db_id
    FROM attendance a
    INNER JOIN (
        SELECT StudentID, MAX(Date) as MaxDate
        FROM attendance
        GROUP BY StudentID
    ) b ON a.StudentID = b.StudentID AND a.Date = b.MaxDate
    WHERE (a.Parent_Notified = 0 OR a.Mentor_Nudged = 0)
    """
    
    try:
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"Data fetch error: {e}")
        conn.close()
        return

    if df.empty:
        print("No pending notifications needed.")
        conn.close()
        return

    cursor = conn.cursor()
    notifications_sent = 0
    nudges_sent = 0

    for _, row in df.iterrows():
        # Evaluate Risk
        features = np.array([[
            row["Rolling_Attendance"],
            row["Absence_Streak"],
            row["Semester_Attendance"],
            row["Attendance_Trend"]
        ]])

        probability = model.predict_proba(features)[0][1] if model else 0.0
        
        semester_att = row["Semester_Attendance"]
        trend = row["Attendance_Trend"]
        anomaly = row["Anomaly"]

        is_high_risk = False
        is_watchlist = False

        if semester_att < 0.75 or (semester_att < 0.80 and trend < -0.15):
            is_high_risk = True
        elif trend < -0.15 or probability > 0.85:
            is_watchlist = True

        # Send Parent SMS for High Risk or Anomaly
        if (is_high_risk or anomaly == 1) and row["Parent_Notified"] == 0:
            student_id = row["StudentID"]
            contact = row["Parent_Contact"]
            reason = "ANOMALY (Potential Emergency)" if anomaly == 1 else "Extremely Low Attendance"
            
            print(f"--> [SMS Dispatch] To Parent ({contact}): URGENT. Ward {student_id} marked as {reason}.")
            cursor.execute("UPDATE attendance SET Parent_Notified = 1 WHERE rowid = ?", (row["db_id"],))
            notifications_sent += 1

        # Nudge Mentor for Watchlist, High Risk, or Anomaly
        if (is_high_risk or is_watchlist or anomaly == 1) and row["Mentor_Nudged"] == 0:
            mentor = row["MentorID"]
            m_contact = row["Mentor_Contact"]
            student_id = row["StudentID"]
            
            print(f"--> [Nudge Dispatch] To Mentor {mentor} ({m_contact}): Student {student_id} requires intervention.")
            cursor.execute("UPDATE attendance SET Mentor_Nudged = 1 WHERE rowid = ?", (row["db_id"],))
            nudges_sent += 1

    conn.commit()
    conn.close()
    
    print(f"Job completed. Dispatched {notifications_sent} Parent SMS and {nudges_sent} Mentor Nudges.")

if __name__ == "__main__":
    run_notifications_job()
