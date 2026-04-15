import sqlite3
conn=sqlite3.connect('attendance_system.db')
cursor=conn.cursor()

print("MENTORS in users table:")
cursor.execute("SELECT username, name FROM users WHERE role='mentor'")
[print(row) for row in cursor.fetchall()]

print("\nSTUDENTS mentor_name sample:")
cursor.execute("SELECT DISTINCT mentor_name FROM students LIMIT 10")
[print(row) for row in cursor.fetchall()]

conn.close()
