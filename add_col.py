import sqlite3

try:
    conn = sqlite3.connect('attendance_system.db')
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE students ADD COLUMN hostler TEXT DEFAULT 'No'")
    conn.commit()
    print("Column added successfully.")
except sqlite3.OperationalError as e:
    print("OperationalError:", e)
finally:
    conn.close()
