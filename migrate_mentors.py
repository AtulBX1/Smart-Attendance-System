import sqlite3
import pandas as pd

def migrate_mentors():
    conn = sqlite3.connect('attendance_system.db')
    cursor = conn.cursor()

    # Get all unique mentor names from the students table
    students_df = pd.read_sql_query("SELECT DISTINCT mentor_name FROM students WHERE mentor_name IS NOT NULL", conn)
    mentor_names = students_df['mentor_name'].tolist()
    
    print(f"Found {len(mentor_names)} unique mentors in 'students' table.")

    # Insert into users table if they don't exist
    mentors_created = 0
    for name in mentor_names:
        # Check if mentor already exists as a user
        cursor.execute("SELECT 1 FROM users WHERE username = ?", (name,))
        if not cursor.fetchone():
            # Default password for all mentors: password123
            # In a real app, this should be hashed.
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (name, "password123", "mentor")
            )
            mentors_created += 1
            print(f"Created mentor user: {name}")

    conn.commit()
    print(f"\nMigration complete. Integrated {mentors_created} new mentor accounts into 'users' table.")
    conn.close()

if __name__ == "__main__":
    migrate_mentors()
