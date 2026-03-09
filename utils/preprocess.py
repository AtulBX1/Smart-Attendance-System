import pandas as pd

def preprocess_data(input_path, output_path):
    df = pd.read_csv(input_path)

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values(["StudentID", "Subject", "Date"]).reset_index(drop=True)

    # Rolling 10-day attendance average per subject
    df["Rolling_Attendance"] = (
        df.groupby(["StudentID", "Subject"])["Present"]
        .rolling(window=10, min_periods=1)
        .mean()
        .reset_index(level=[0, 1], drop=True)
    )

    # Calculate attendance trend per subject
    df["Rolling_Attendance_Prev"] = (
        df.groupby(["StudentID", "Subject"])["Rolling_Attendance"]
        .shift(10)
    )

    df["Attendance_Trend"] = (
        df["Rolling_Attendance"] - df["Rolling_Attendance_Prev"]
    )

    # Fill missing trend values
    df["Attendance_Trend"] = df["Attendance_Trend"].fillna(0)

    # Absence streak per subject
    df["Absence_Streak"] = 0

    # A faster vectorized way or optimized grouping
    def calc_streak(group):
        streak = 0
        streak_list = []
        for val in group:
            if val == 0:
                streak += 1
            else:
                streak = 0
            streak_list.append(streak)
        return streak_list

    df["Absence_Streak"] = df.groupby(["StudentID", "Subject"])["Present"].transform(calc_streak)

    # Semester attendance per subject
    df["Semester_Attendance"] = (
        df.groupby(["StudentID", "Subject", "Semester"])["Present"]
        .expanding()
        .mean()
        .reset_index(level=[0, 1, 2], drop=True)
    )

    import numpy as np

    # Simulate mentor assignment
    mentor_ids = [f"M{str(i).zfill(3)}" for i in range(1, 201)]

    student_mentor_map = {}
    student_parent_map = {}

    import random

    for student in df["StudentID"].unique():
        student_mentor_map[student] = np.random.choice(mentor_ids)
        # Mocking parent contact (10 digit string)
        student_parent_map[student] = "+1" + "".join([str(random.randint(0, 9)) for _ in range(10)])

    df["MentorID"] = df["StudentID"].map(student_mentor_map)
    df["Parent_Contact"] = df["StudentID"].map(student_parent_map)
    
    # Mocking mentor contact - mapping MentorID to a phone number
    mentor_contact_map = {m: "+1" + "".join([str(random.randint(0, 9)) for _ in range(10)]) for m in mentor_ids}
    df["Mentor_Contact"] = df["MentorID"].map(mentor_contact_map)

    df.to_csv(output_path, index=False)
    print("Preprocessing completed successfully!")


if __name__ == "__main__":
    preprocess_data(
        "data/raw/student_attendance_dataset.csv",
        "data/processed/processed_attendance.csv"
    )