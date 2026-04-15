import sqlite3
import pandas as pd

def check_mentor_alignment():
    conn = sqlite3.connect('attendance_system.db')
    
    # Check users
    users_query = "SELECT username, role FROM users WHERE role='mentor'"
    mentors_users = pd.read_sql_query(users_query, conn)
    print("Mentors in 'users' table:")
    print(mentors_users)

    # Check students' mentor_name
    students_query = "SELECT DISTINCT mentor_name FROM students"
    mentors_students = pd.read_sql_query(students_query, conn)
    print("\nMentor names in 'students' table:")
    print(mentors_students)

    # Check attendance data for a mentor
    if not mentors_users.empty:
        test_id = mentors_users.iloc[0]['username']
        # The app.py filters students by s.mentor_name = mentor_id (username)
        print(f"\nChecking students for mentor_id: {test_id}")
        check_query = "SELECT COUNT(*) FROM students WHERE mentor_name = ?"
        count = conn.execute(check_query, (test_id,)).fetchone()[0]
        print(f"Count of students linked to username '{test_id}': {count}")
        
        # Check actual mentor names in students table
        student_check_query = "SELECT registration_no, mentor_name FROM students LIMIT 10"
        print("\nSample students with mentor_name:")
        print(pd.read_sql_query(student_check_query, conn))
        
    conn.close()

if __name__ == "__main__":
    check_mentor_alignment()
