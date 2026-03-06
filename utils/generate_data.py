import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

NUM_STUDENTS = 1000
DAYS_PER_SEM = 120
SEMESTERS = [3, 4]

students = []

# Generate student profiles
sections = ["A", "B", "C", "D"]
first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Charles", "Joseph", "Thomas", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen"]
last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]

for i in range(1, NUM_STUDENTS + 1):
    students.append({
        "StudentID": f"S{i:04}",
        "Student_Name": f"{random.choice(first_names)} {random.choice(last_names)}",
        "Gender": random.choice(["Male", "Female"]),
        "Hostler": random.choice(["Yes", "No"]),
        "Section": random.choice(sections)
    })

df_students = pd.DataFrame(students)

records = []

# Define semesters and date ranges
# Sem 3: Aug 1, 2025 to Jan 3, 2026
sem3_start = datetime(2025, 8, 1)
sem3_end = datetime(2026, 1, 3)

# Sem 4: Jan 15, 2026 to June 8, 2026
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
        # Mid term in October (assume 10th to 20th)
        if date.month == 10 and 10 <= date.day <= 20:
            return True
        # End term Dec 20 to Jan 3
        if (date.month == 12 and date.day >= 20) or (date.month == 1 and date.day <= 3):
            return True
    elif sem == 4:
        # Mid term March 16 to 23
        if date.month == 3 and 16 <= date.day <= 23:
            return True
        # End term May 20 to June 8
        if (date.month == 5 and date.day >= 20) or (date.month == 6 and date.day <= 8):
            return True
    return False

semesters_data = [
    (3, sem3_days),
    (4, sem4_days)
]

for _, student in df_students.iterrows():
    for sem, days_list in semesters_data:
        for date in days_list:
            # Base attendance probability
            base_prob = 0.88 if student["Hostler"] == "Yes" else 0.75

            # Monday lower attendance
            if date.weekday() == 0:
                base_prob -= 0.05
                
            # Drop attendance significantly near/during exams
            if is_exam_period(date, sem):
                # Day scholars might drop more, hostlers also drop
                base_prob -= 0.25 if student["Hostler"] == "No" else 0.15

            # Ensure probability stays within bounds
            base_prob = max(0.1, min(0.95, base_prob))

            present = np.random.choice([1, 0], p=[base_prob, 1 - base_prob])

            records.append({
                "StudentID": student["StudentID"],
                "Student_Name": student["Student_Name"],
                "Section": student["Section"],
                "Gender": student["Gender"],
                "Hostler": student["Hostler"],
                "Date": date.strftime("%Y-%m-%d"),
                "Semester": sem,
                "Present": present
            })

df = pd.DataFrame(records)

df.to_csv("data/raw/student_attendance_dataset.csv", index=False)

print("Dataset generated successfully!")