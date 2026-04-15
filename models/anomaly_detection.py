import sqlite3
import pandas as pd
import numpy as np
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

def generate_dbscan_synthetic_data(seed=42):
    """
    Generate synthetic 2D attendance data with circular cluster structure for DBSCAN visualization.
    Returns dict with 'core_points' and 'anomaly_points' arrays ready for Chart.js.
    
    - ~120 normal students in a tight circular/elliptical cluster (attendance_rate ~75-90%, consistency ~70-85%)
    - ~18 anomaly students scattered in low-attendance / low-consistency corners
    - DBSCAN with eps=0.4, min_samples=5 (on StandardScaler-normalized data) separates them cleanly
    """
    np.random.seed(seed)
    
    # --- Core cluster: ~120 students tightly packed ---
    n_core = 120
    # Center around (82% attendance, 78% consistency)
    core_attendance = np.random.normal(loc=82, scale=4.5, size=n_core)
    core_consistency = np.random.normal(loc=78, scale=4.0, size=n_core)
    # Clip to realistic ranges
    core_attendance = np.clip(core_attendance, 68, 95)
    core_consistency = np.clip(core_consistency, 62, 92)
    
    # --- Anomaly points: ~18 students scattered outside ---
    n_anomaly = 18
    anomaly_reasons = [
        "Sudden drop in attendance",
        "Irregular pattern detected",
        "Multiple consecutive absences",
        "Attendance below threshold"
    ]
    
    # Scatter anomalies in several low-performance corners (well separated from core)
    anomaly_attendance = np.concatenate([
        np.random.uniform(28, 45, size=6),   # very low attendance
        np.random.uniform(40, 55, size=5),   # low-mid attendance
        np.random.uniform(50, 62, size=4),   # mid attendance, but very low consistency
        np.random.uniform(32, 50, size=3),   # scattered low
    ])
    anomaly_consistency = np.concatenate([
        np.random.uniform(20, 38, size=6),   # very low consistency
        np.random.uniform(25, 42, size=5),   # low consistency
        np.random.uniform(18, 35, size=4),   # very low consistency
        np.random.uniform(42, 55, size=3),   # moderate consistency but low attendance
    ])
    
    # Combine all points
    all_attendance = np.concatenate([core_attendance, anomaly_attendance])
    all_consistency = np.concatenate([core_consistency, anomaly_consistency])
    X = np.column_stack([all_attendance, all_consistency])
    
    # Scale features before DBSCAN (standard ML practice)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Run DBSCAN on scaled data — eps=0.4, min_samples=5 cleanly separates dense core from scattered outliers
    from sklearn.cluster import DBSCAN as DBSCAN_Cluster
    dbscan_model = DBSCAN_Cluster(eps=0.4, min_samples=5)
    labels = dbscan_model.fit_predict(X_scaled)
    
    core_points = []
    anomaly_points = []
    
    for i in range(len(X)):
        att_rate = round(float(X[i, 0]), 1)
        cons_score = round(float(X[i, 1]), 1)
        # Derive missed days from attendance rate (assume 120 total class days)
        total_days = 120
        missed = int(total_days * (1 - att_rate / 100))
        student_id = f"S{i+1:04d}"
        
        point = {
            "x": att_rate,
            "y": cons_score,
            "studentId": student_id,
            "attendanceRate": att_rate,
            "missedDays": missed,
        }
        
        if labels[i] == -1:
            # Anomaly
            point["anomalyReason"] = anomaly_reasons[i % len(anomaly_reasons)]
            anomaly_points.append(point)
        else:
            point["status"] = "Normal Pattern"
            core_points.append(point)
    
    return {
        "core_points": core_points,
        "anomaly_points": anomaly_points,
        "cluster_stats": {
            "total_points": len(X),
            "core_count": len(core_points),
            "anomaly_count": len(anomaly_points),
            "eps": 0.4,
            "min_samples": 5
        }
    }


if __name__ == "__main__":
    run_anomaly_detection()