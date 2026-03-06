import sqlite3
import pandas as pd

# Load processed CSV
df = pd.read_csv("data/processed/processed_attendance.csv")

# Add missing columns with default values
df["Anomaly"] = 0
df["Parent_Notified"] = False
df["Mentor_Nudged"] = False

# Create SQLite database
conn = sqlite3.connect("attendance_system.db")

# Insert data into SQL table
df.to_sql("attendance", conn, if_exists="replace", index=False)

# ---- Create Users Table ----
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
''')

# ---- Create Faculty Classes Table ----
cursor.execute('''
    CREATE TABLE IF NOT EXISTS faculty_classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        faculty_username TEXT NOT NULL,
        section TEXT NOT NULL,
        time_slot TEXT NOT NULL
    )
''')

# Clear existing tables to prevent Unique Constraint errors on re-run
cursor.execute('DELETE FROM users')
cursor.execute('DELETE FROM faculty_classes')

# Insert mock users
mock_users = [
    ("admin", "admin123", "admin"),
    ("faculty", "faculty123", "faculty"),
    ("M001", "mentor123", "mentor"),  # Mock mentor login
    ("M002", "mentor123", "mentor")
]
cursor.executemany('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', mock_users)

# Insert mock faculty class schedule mapping
# Giving our test 'faculty' user 4 distinct classes to match the prompt request
mock_classes = [
    ("faculty", "A", "09:00 AM - 10:00 AM"),
    ("faculty", "B", "10:00 AM - 11:00 AM"),
    ("faculty", "C", "11:30 AM - 12:30 PM"),
    ("faculty", "D", "02:00 PM - 03:00 PM")
]
cursor.executemany('INSERT INTO faculty_classes (faculty_username, section, time_slot) VALUES (?, ?, ?)', mock_classes)

conn.commit()
conn.close()

print("Database created, tables seeded (including faculty_classes), and data inserted successfully!")