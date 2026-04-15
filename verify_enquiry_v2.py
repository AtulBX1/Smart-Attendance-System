import sqlite3
import os

db_path = "attendance_system.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get a student ID
cursor.execute("SELECT registration_no FROM students LIMIT 1")
row = cursor.fetchone()
student_id = row[0] if row else "TEST_STUDENT"

print(f"Testing database insertion for student: {student_id}")

try:
    cursor.execute(
        "INSERT INTO attendance_enquiry (student_id, mentor_id) VALUES (?, ?)",
        (student_id, "MENTOR_TEST")
    )
    conn.commit()
    print("SUCCESS: Database insertion works.")
    
    # Check
    cursor.execute("SELECT * FROM attendance_enquiry WHERE student_id = ? AND mentor_id = ?", (student_id, "MENTOR_TEST"))
    result = cursor.fetchone()
    print(f"Row: {result}")
    
    # Cleanup
    cursor.execute("DELETE FROM attendance_enquiry WHERE student_id = ? AND mentor_id = ?", (student_id, "MENTOR_TEST"))
    conn.commit()
except Exception as e:
    print(f"FAILURE: {e}")

conn.close()
