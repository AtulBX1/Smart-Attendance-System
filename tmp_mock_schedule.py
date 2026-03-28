import requests
import json

base_url = "http://127.0.0.1:5000"

# Note: Since I don't have a session cookie, I'll insert directly into the DB for testing the student dashboard display
import sqlite3

db_path = "attendance_system.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get a student ID from the database
cursor.execute("SELECT registration_no FROM students LIMIT 1")
row = cursor.fetchone()
if row:
    student_id = row[0]
    print(f"Testing with Student ID: {student_id}")
    
    # Insert a mock counselling session
    cursor.execute(
        "INSERT INTO counselling_sessions (student_id, faculty_id, meeting_time, message) VALUES (?, ?, ?, ?)",
        (student_id, "Prof. X", "Monday 10:00 AM", "Discussion on recent attendance drop.")
    )
    conn.commit()
    print("Mock counselling session inserted.")
else:
    print("No students found in DB.")

conn.close()
