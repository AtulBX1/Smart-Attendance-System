import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

STUDENTS_PER_SECTION = 70
SECTIONS = ["A", "B", "C", "D"]
NUM_STUDENTS = STUDENTS_PER_SECTION * len(SECTIONS)  # 280 total
DAYS_PER_SEM = 120
SEMESTERS = [3, 4]

SUBJECTS = ["Math", "Physics", "Chemistry", "CS", "English", "History", "Biology"]

students = []

# Generate student profiles
first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Charles", "Joseph", "Thomas", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen"]
last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]

student_id_counter = 1
for section in SECTIONS:
    for _ in range(STUDENTS_PER_SECTION):
        students.append({
            "StudentID": f"S{student_id_counter:04}",
            "Student_Name": f"{random.choice(first_names)} {random.choice(last_names)}",
            "Gender": random.choice(["Male", "Female"]),
            "Hostler": random.choice(["Yes", "No"]),
            "Section": section
        })
        student_id_counter += 1

df_students = pd.DataFrame(students)

records = []

# Define semesters and date ranges
sem3_start = datetime(2025, 8, 1)
sem3_end = datetime(2026, 1, 3)

sem4_start = datetime(2026, 1, 15)
sem4_end = datetime(2026, 6, 8)

def get_weekdays(start, end):
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5: # Monday to Friday
            days.append(current)
        current += timedelta(days=1)
    return days

sem3_days = get_weekdays(sem3_start, sem3_end)
sem4_days = get_weekdays(sem4_start, sem4_end)

def is_exam_period(date, sem):
    if sem == 3:
        if date.month == 10 and 10 <= date.day <= 20: return True
        if (date.month == 12 and date.day >= 20) or (date.month == 1 and date.day <= 3): return True
    elif sem == 4:
        if date.month == 3 and 16 <= date.day <= 23: return True
        if (date.month == 5 and date.day >= 20) or (date.month == 6 and date.day <= 8): return True
    return False

semesters_data = [
    (3, sem3_days),
    (4, sem4_days)
]

for _, student in df_students.iterrows():
    for sem, days_list in semesters_data:
        for date in days_list:
            
            # Base attendance probability for the day
            day_base_prob = 0.88 if student["Hostler"] == "Yes" else 0.75
            if date.weekday() == 0: day_base_prob -= 0.05
            if is_exam_period(date, sem):
                day_base_prob -= 0.25 if student["Hostler"] == "No" else 0.15
            
            # Bounding
            day_base_prob = max(0.1, min(0.95, day_base_prob))
            
            # Generate 7 subject records for this specific day
            for subject in SUBJECTS:
                # Add minor random variance per subject
                subject_prob = max(0.05, min(0.98, day_base_prob + random.uniform(-0.1, 0.1)))
                present = np.random.choice([1, 0], p=[subject_prob, 1 - subject_prob])
                
                records.append({
                    "StudentID": student["StudentID"],
                    "Student_Name": student["Student_Name"],
                    "Section": student["Section"],
                    "Subject": subject,
                    "Gender": student["Gender"],
                    "Hostler": student["Hostler"],
                    "Date": date.strftime("%Y-%m-%d"),
                    "Semester": sem,
                    "Present": present
                })

df = pd.DataFrame(records)
df.to_csv("data/raw/student_attendance_dataset.csv", index=False)
print(f"Dataset generated successfully! ({len(df)} records for {NUM_STUDENTS} students)")