import sqlite3
import os

db_path = 'd:/Semester4/CSE274/Smart-Attendance-System/attendance_system.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. students
cursor.execute('''
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    class_name TEXT NOT NULL,
    section TEXT NOT NULL,
    mentor_name TEXT,
    parent_email TEXT,
    enrolled_subjects TEXT
)
''')

# 2. master_timetable
cursor.execute('''
CREATE TABLE IF NOT EXISTS master_timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    teacher TEXT NOT NULL,
    day_of_week TEXT NOT NULL,
    time_slot TEXT NOT NULL,
    class_name TEXT NOT NULL,
    section TEXT NOT NULL
)
''')

# 3. student_timetable
cursor.execute('''
CREATE TABLE IF NOT EXISTS student_timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_roll_no TEXT NOT NULL,
    subject TEXT NOT NULL,
    teacher TEXT NOT NULL,
    day_of_week TEXT NOT NULL,
    time_slot TEXT NOT NULL,
    FOREIGN KEY(student_roll_no) REFERENCES students(roll_no)
)
''')

# 4. admin_files
cursor.execute('''
CREATE TABLE IF NOT EXISTS admin_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    class_name TEXT,
    section TEXT,
    upload_date TEXT NOT NULL
)
''')

conn.commit()
conn.close()
print("Migration applied successfully.")
