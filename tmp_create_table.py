import sqlite3
import os

db_path = "attendance_system.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create counselling_sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS counselling_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        faculty_id TEXT NOT NULL,
        meeting_time TEXT NOT NULL,
        message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'Scheduled'
    );
    """)
    
    conn.commit()
    print("Table 'counselling_sessions' created successfully.")
    conn.close()
else:
    print(f"Database not found at {db_path}")
