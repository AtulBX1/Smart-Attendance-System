import requests
import json
import sqlite3

# Define target
url = "http://127.0.0.1:5000/mentor/trigger_enquiry"
# We need a student ID from the database
db_path = "attendance_system.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT registration_no FROM students LIMIT 1")
row = cursor.fetchone()
student_id = row[0] if row else "TEST123"
conn.close()

print(f"Testing enquiry trigger for student: {student_id}")

# Since we can't easily mock a session over HTTP requests to a running Flask app without a cookie,
# we'll test the logic by calling the database directly and then checking if the route exists.

# Let's check if the route is defined in app.py
with open("backend/app.py", "r") as f:
    content = f.read()
    if "/mentor/trigger_enquiry" in content:
        print("SUCCESS: Route '/mentor/trigger_enquiry' exists in app.py")
    else:
        print("FAILURE: Route '/mentor/trigger_enquiry' NOT found in app.py")

# Mock the database insertion to verify table compatibility
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO attendance_enquiry (student_id, mentor_id) VALUES (?, ?)",
        (student_id, "MOCK_MENTOR")
    )
    conn.commit()
    print("SUCCESS: Database insertion into 'attendance_enquiry' works.")
    
    # Check the row
    cursor.execute("SELECT * FROM attendance_enquiry WHERE student_id = ? AND mentor_id = ?", (student_id, "MOCK_MENTOR"))
    result = cursor.fetchone()
    print(f"Table row created: {result}")
    
    # Cleanup
    cursor.execute("DELETE FROM attendance_enquiry WHERE student_id = ? AND mentor_id = ?", (student_id, "MOCK_MENTOR"))
    conn.commit()
    conn.close()
except Exception as e:
    print(f"FAILURE: Database error: {e}")
