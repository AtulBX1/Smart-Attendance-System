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

# ---- Drop and recreate tables to apply schema updates ----
cursor = conn.cursor()
cursor.execute('DROP TABLE IF EXISTS users')
cursor.execute('DROP TABLE IF EXISTS faculty_classes')
cursor.execute('DROP TABLE IF EXISTS otp_requests')
cursor.execute('DROP TABLE IF EXISTS login_otps')
cursor.execute('DROP TABLE IF EXISTS smtp_config')

# ---- Create Users Table ----
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        email TEXT,
        full_name TEXT
    )
''')

# ---- Create Faculty Classes Table ----
cursor.execute('''
    CREATE TABLE IF NOT EXISTS faculty_classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        faculty_username TEXT NOT NULL,
        subject TEXT NOT NULL,
        section TEXT NOT NULL,
        time_slot TEXT NOT NULL
    )
''')

# ---- Create OTP Requests Table (for credential changes) ----
cursor.execute('''
    CREATE TABLE IF NOT EXISTS otp_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        otp_code TEXT NOT NULL,
        created_at TEXT NOT NULL,
        used INTEGER DEFAULT 0
    )
''')

# ---- Create Login OTPs Table (for OTP-based login) ----
cursor.execute('''
    CREATE TABLE IF NOT EXISTS login_otps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        otp_code TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used INTEGER DEFAULT 0
    )
''')

# ---- Create SMTP Config Table ----
cursor.execute('''
    CREATE TABLE IF NOT EXISTS smtp_config (
        id INTEGER PRIMARY KEY,
        smtp_host TEXT,
        smtp_port INTEGER DEFAULT 587,
        smtp_user TEXT,
        smtp_pass TEXT
    )
''')

# Insert default empty SMTP config row
cursor.execute('INSERT INTO smtp_config (id, smtp_host, smtp_port, smtp_user, smtp_pass) VALUES (1, "", 587, "", "")')

# Insert admin user
cursor.execute('INSERT INTO users (username, password, role, email, full_name) VALUES (?, ?, ?, ?, ?)',
               ("admin", "admin123", "admin", "admin@school.edu", "Administrator"))

# Insert mock faculty users (each faculty is also a mentor)
SUBJECTS = ["Math", "Physics", "Chemistry", "CS", "English", "History", "Biology"]
SECTIONS = ["A", "B", "C", "D"]

faculty_names = {
    "Math": "Rahul Sharma",
    "Physics": "Priya Gupta",
    "Chemistry": "Amit Kumar",
    "CS": "Sneha Reddy",
    "English": "Deepak Patel",
    "History": "Kavita Singh",
    "Biology": "Suresh Nair"
}

time_slots = {
    "Math": "09:00 AM - 10:00 AM",
    "Physics": "10:00 AM - 11:00 AM",
    "Chemistry": "11:30 AM - 12:30 PM",
    "CS": "01:30 PM - 02:30 PM",
    "English": "02:30 PM - 03:30 PM",
    "History": "03:45 PM - 04:45 PM",
    "Biology": "04:45 PM - 05:45 PM"
}

mock_classes = []

for subject in SUBJECTS:
    name = faculty_names[subject]
    username = name.lower().replace(" ", "_")
    email = f"{username}@school.edu"
    ts = time_slots[subject]

    # Each faculty is also a mentor (role = faculty)
    cursor.execute(
        'INSERT INTO users (username, password, role, email, full_name) VALUES (?, ?, ?, ?, ?)',
        (username, "otp_only", "faculty", email, name)
    )

    for section in SECTIONS:
        mock_classes.append((username, subject, section, ts))

cursor.executemany(
    'INSERT INTO faculty_classes (faculty_username, subject, section, time_slot) VALUES (?, ?, ?, ?)',
    mock_classes
)

conn.commit()
conn.close()

print("Database created with SMTP config table, faculty (with names/emails), and all tables seeded!")