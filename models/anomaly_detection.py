import sqlite3
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
import os

base_dir = os.path.dirname(os.path.dirname(__file__))

def get_db_connection():
    db_path = os.path.join(base_dir, "attendance_system.db")
    return sqlite3.connect(db_path)

def run_anomaly_detection():
    print("Starting Anomaly Detection Job...")
    conn = get_db_connection()
    
    # Use latest record per student
    query = """
    SELECT a.*, a.rowid as db_id
    FROM attendance a
    INNER JOIN (
        SELECT StudentID, MAX(Date) as MaxDate
        FROM attendance
        GROUP BY StudentID
    ) b ON a.StudentID = b.StudentID AND a.Date = b.MaxDate
    """
    
    latest_df = pd.read_sql_query(query, conn)
    
    if latest_df.empty:
        print("No attendance data found.")
        conn.close()
        return

    features = ["Rolling_Attendance", "Absence_Streak", "Semester_Attendance"]
    X = latest_df[features]

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Apply DBSCAN
    dbscan = DBSCAN(eps=0.8, min_samples=10)
    clusters = dbscan.fit_predict(X_scaled)
    
    latest_df["Anomaly"] = [1 if c == -1 else 0 for c in clusters]

    anomalies = latest_df[latest_df["Anomaly"] == 1]
    
    print(f"Total Students: {len(latest_df)}")
    print(f"Anomalies Detected: {len(anomalies)}")

    # Update SQLite records
    cursor = conn.cursor()
    # Reset anomalies first (optional, but good practice for daily jobs)
    cursor.execute("UPDATE attendance SET Anomaly = 0")
    
    if not anomalies.empty:
        # We update the Anomaly column for the specific rowid to True (1)
        update_data = [(1, row["db_id"]) for _, row in anomalies.iterrows()]
        cursor.executemany("UPDATE attendance SET Anomaly = ? WHERE rowid = ?", update_data)
        
    conn.commit()
    conn.close()
    
    print("Anomaly detection completed and database updated.")

if __name__ == "__main__":
    run_anomaly_detection()