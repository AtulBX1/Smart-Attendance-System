"""
timetable_generator.py
Standalone scheduling module for the Smart Attendance System.
Generates a conflict-free master timetable for all sections.

Rules:
  - 5 days/week (Mon-Fri)
  - 9 time slots per day (9AM - 6PM)
  - 1 floating lunch break per section per day (random within 12PM-3PM)
  - Each subject appears ~3 times per week per section
  - No teacher double-booking across sections in the same slot
  - No section double-booking (one subject per slot)
  - Teacher max 4 hours/day
"""

import csv
import io
import random
from collections import defaultdict


DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
SLOTS = [
    "09:00 AM - 10:00 AM",
    "10:00 AM - 11:00 AM",
    "11:00 AM - 12:00 PM",
    "12:00 PM - 01:00 PM",
    "01:00 PM - 02:00 PM",
    "02:00 PM - 03:00 PM",
    "03:00 PM - 04:00 PM",
    "04:00 PM - 05:00 PM",
]
# Indices of slots eligible for the floating lunch break (12PM-3PM)
LUNCH_ELIGIBLE = [3, 4, 5]  # slots at 12-1, 1-2, 2-3


# ---------------------------------------------------------------------------
# CSV Parsers
# ---------------------------------------------------------------------------

def parse_teacher_csv(file_stream):
    """
    Parse teacher CSV with columns: name, email, subject, sections
    Returns: list of dicts [{name, email, subject, sections: [str]}]
    """
    raw = file_stream.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    if reader.fieldnames:
        reader.fieldnames = [f.strip() for f in reader.fieldnames]

    teachers = []
    for row in reader:
        teachers.append({
            "name": row["name"].strip(),
            "email": row["email"].strip(),
            "subject": row["subject"].strip(),
            "sections": [s.strip() for s in row["sections"].split(",")],
        })
    return teachers


def parse_student_csv(file_stream):
    """
    Parse student CSV with columns: name, registration_no, section, subjects
    Returns: list of dicts [{name, registration_no, section, subjects: [str]}]
    """
    raw = file_stream.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    if reader.fieldnames:
        reader.fieldnames = [f.strip() for f in reader.fieldnames]

    students = []
    for row in reader:
        students.append({
            "name": row["name"].strip(),
            "registration_no": row["registration_no"].strip(),
            "section": row["section"].strip(),
            "subjects": [s.strip() for s in row["subjects"].split(",")],
        })
    return students


# ---------------------------------------------------------------------------
# Main Scheduler  (greedy with shuffle-retry)
# ---------------------------------------------------------------------------

def generate_master_timetable(conn):
    """
    Generate a master timetable for all sections using data from the DB.
    Writes results into master_timetable and student_timetable tables.

    Returns: dict  {section: {day: {slot: {subject, teacher}}}}
    """
    import pandas as pd

    cursor = conn.cursor()

    # Clear previous timetable data
    cursor.execute("DELETE FROM master_timetable")
    cursor.execute("DELETE FROM student_timetable")

    # ---------- Fetch Subject Credits ----------
    credits_df = pd.read_sql_query("SELECT subject, credits FROM subject_credits", conn)
    credits_map = {str(row["subject"]).strip().upper(): int(row["credits"]) for _, row in credits_df.iterrows()}

    # ---------- Fetch Faculty Mapping ----------
    faculty_df = pd.read_sql_query(
        "SELECT DISTINCT faculty_username, subject FROM faculty_classes", conn
    )
    # subject (uppercased) -> faculty_username
    subj_faculty = {}
    for _, row in faculty_df.iterrows():
        subj_key = str(row["subject"]).strip().upper()
        subj_faculty[subj_key] = row["faculty_username"]

    # ---------- Fetch Sections ----------
    sections_df = pd.read_sql_query(
        "SELECT DISTINCT class_name, section FROM students", conn
    )

    # Pre-calculate total expected classes per teacher across all sections
    # to know if they have enough (>= 10) to mandate 2 classes/day across 5 days.
    teacher_total_classes = defaultdict(int)
    for _, sec_row in sections_df.iterrows():
        cls, sec = sec_row["class_name"], sec_row["section"]
        students_in_sec = pd.read_sql_query("SELECT enrolled_subjects FROM students WHERE class_name=? AND section=?", conn, params=(cls, sec))
        if not students_in_sec.empty:
            sec_subjs = set()
            for _, s_row in students_in_sec.iterrows():
                if s_row["enrolled_subjects"]:
                    for s in s_row["enrolled_subjects"].split(","):
                        sec_subjs.add(s.strip())
            for subj in sec_subjs:
                subj_upper = subj.upper()
                if subj_upper not in credits_map:
                    continue
                t = subj_faculty.get(subj_upper, "TBD")
                if t != "TBD":
                    teacher_total_classes[t] += credits_map[subj_upper]

    # Global trackers
    teacher_busy = defaultdict(set)         # teacher -> set of (day, slot_str)
    teacher_day_hours = defaultdict(lambda: defaultdict(int))  # teacher -> {day: count}

    all_timetables = {}  # section -> {day -> {slot_str -> {subject, teacher}}}

    for _, sec_row in sections_df.iterrows():
        cls = sec_row["class_name"]
        sec = sec_row["section"]

        # Students and their subjects for this section
        students_in_sec = pd.read_sql_query(
            "SELECT registration_no, enrolled_subjects FROM students "
            "WHERE class_name=? AND section=?",
            conn, params=(cls, sec),
        )
        if students_in_sec.empty:
            continue

        # Unique subjects in this section
        section_subjects = set()
        for _, s_row in students_in_sec.iterrows():
            if s_row["enrolled_subjects"]:
                for s in s_row["enrolled_subjects"].split(","):
                    section_subjects.add(s.strip())
        section_subjects = sorted(section_subjects)
        if not section_subjects:
            continue

        # ---------- Build target: classes per subject based on credits ----------
        # Logic: N classes for N credit subject.
        # Only schedule subjects explicitly uploaded in the credits map.
        classes_to_schedule = []
        for subj in section_subjects:
            subj_upper = subj.upper()
            if subj_upper not in credits_map:
                continue
            classes_per_subject = credits_map[subj_upper]
            classes_to_schedule.extend([subj] * classes_per_subject)

        # ---------- Assign lunch breaks ----------
        rng = random.Random(42 + hash(sec))
        lunch_slots = {}
        for day in DAYS:
            lunch_slots[day] = rng.choice(LUNCH_ELIGIBLE)

        # ---------- Build list of usable (day, slot_index) pairs ----------
        usable_positions = []
        for day in DAYS:
            for s_idx in range(len(SLOTS)):
                if s_idx == lunch_slots[day]:
                    continue  # skip lunch
                usable_positions.append((day, s_idx))
        # 8 usable slots/day × 5 days = 40 positions

        # ---------- Greedy assignment with shuffle-retry ----------
        best_assignment = {}
        best_count = 0

        for attempt in range(20):
            rng_attempt = random.Random(42 + hash(sec) + attempt * 7)
            remaining = classes_to_schedule.copy()
            rng_attempt.shuffle(remaining)

            assignment = {}          # pos_index -> subject
            section_used = set()     # set of pos_index already used
            subj_day_count = defaultdict(lambda: defaultdict(int))  # subj -> {day: count}

            for subj in remaining:
                teacher = subj_faculty.get(subj.upper(), "TBD")

                # Find best slot for this subject
                placed = False
                # Shuffle position order for variety
                pos_order = list(range(len(usable_positions)))
                rng_attempt.shuffle(pos_order)

                best_pos = None
                best_score = -9999

                for pos_idx in pos_order:
                    if pos_idx in section_used:
                        continue

                    day, s_idx = usable_positions[pos_idx]
                    slot_str = SLOTS[s_idx]

                    # Constraint 1: No teacher double-booking
                    if teacher != "TBD" and (day, slot_str) in teacher_busy[teacher]:
                        continue

                    # Count tentative hours for same teacher & day
                    tentative_hours = teacher_day_hours[teacher][day] if teacher != "TBD" else 0
                    if teacher != "TBD":
                        for pi, as_subj in assignment.items():
                            d2, _ = usable_positions[pi]
                            t2 = subj_faculty.get(as_subj.upper(), "TBD")
                            if t2 == teacher and d2 == day:
                                tentative_hours += 1

                    # Constraint 2: Teacher max 4 hours/day
                    if teacher != "TBD" and tentative_hours >= 4:
                        continue

                    # Constraint 3: Max 2 same subject per day
                    if subj_day_count[subj][day] >= 2:
                        continue

                    # Soft Constraint: Enforce 5 days/week and Minimum 2 classes/day
                    score = 0
                    
                    # Back-to-back constraint: if this subject is already on this day, it MUST be adjacent
                    if subj_day_count[subj][day] > 0:
                        existing_s_indices = []
                        for pi, as_subj in assignment.items():
                            d2, si2 = usable_positions[pi]
                            if as_subj == subj and d2 == day:
                                existing_s_indices.append(si2)
                        
                        if existing_s_indices:
                            if any(abs(si2 - s_idx) == 1 for si2 in existing_s_indices):
                                score += 5000  # Massive priority to be back-to-back
                            else:
                                score -= 5000  # Massive penalty to prevent same-day gaps

                    if teacher != "TBD":
                        total_expected = teacher_total_classes[teacher]
                        if total_expected >= 10:
                            # They have enough classes to fulfill 5 days x 2 classes
                            if tentative_hours == 0:
                                score += 1000 # Massive priority to establish their presence on this new day
                            elif tentative_hours == 1:
                                score += 500  # High priority to finish the 2-per-day minimum
                            elif tentative_hours >= 2:
                                score -= 10   # Slight penalty for clumping beyond 2 before filling other days
                        else:
                            # Not mathematically possible to have 5 days of 2 classes.
                            # Prioritize reaching 2 classes per day on the days they DO teach.
                            if tentative_hours == 0:
                                score -= 10   # Discourage spreading to new days unnecessarily
                            elif tentative_hours == 1:
                                score += 100  # Highly encourage reaching the 2-class minimum
                            elif tentative_hours >= 2:
                                score -= 50   # Discourage >2 classes if they struggle to hit minimums elsewhere


                    if score > best_score:
                        best_score = score
                        best_pos = pos_idx

                if best_pos is not None:
                    # Place it
                    assignment[best_pos] = subj
                    section_used.add(best_pos)
                    
                    b_day, _ = usable_positions[best_pos]
                    subj_day_count[subj][b_day] += 1
                    placed = True

                # If we couldn't place this class, skip it

            if len(assignment) > best_count:
                best_assignment = assignment.copy()
                best_count = len(assignment)

            # If we placed everything, no need to retry
            if best_count >= len(classes_to_schedule):
                break

        # ---------- Commit best assignment ----------
        section_tt = {}
        for pos_idx, subj in best_assignment.items():
            day, s_idx = usable_positions[pos_idx]
            slot_str = SLOTS[s_idx]
            teacher = subj_faculty.get(subj.upper(), "TBD")

            # Update global trackers
            if teacher != "TBD":
                teacher_busy[teacher].add((day, slot_str))
                teacher_day_hours[teacher][day] += 1

            # Insert into master_timetable
            cursor.execute(
                "INSERT INTO master_timetable "
                "(subject, teacher, day_of_week, time_slot, class_name, section) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (subj, teacher, day, slot_str, cls, sec),
            )

            # Insert into student_timetable for each enrolled student
            for _, student in students_in_sec.iterrows():
                enrolled = student["enrolled_subjects"] or ""
                if subj in enrolled:
                    cursor.execute(
                        "INSERT INTO student_timetable "
                        "(registration_no, subject, teacher, day_of_week, time_slot) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (student["registration_no"], subj, teacher, day, slot_str),
                    )

            # Build in-memory timetable structure
            section_tt.setdefault(day, {})[slot_str] = {
                "subject": subj,
                "teacher": teacher,
            }

        # Mark lunch slots
        for day in DAYS:
            lunch_str = SLOTS[lunch_slots[day]]
            section_tt.setdefault(day, {})[lunch_str] = {
                "subject": "LUNCH",
                "teacher": "",
            }

        all_timetables[sec] = section_tt
        print(f"  Section {sec}: placed {len(best_assignment)}/{len(classes_to_schedule)} classes")

    conn.commit()
    return all_timetables


# ---------------------------------------------------------------------------
# Teacher View Builder
# ---------------------------------------------------------------------------

def build_teacher_view(conn):
    """
    Build a per-teacher schedule from the master_timetable table.
    Returns: {teacher_username: {day: [{slot, subject, section}]}}
    """
    import pandas as pd

    tt_df = pd.read_sql_query("SELECT * FROM master_timetable", conn)
    teacher_view = {}

    for _, row in tt_df.iterrows():
        teacher = row["teacher"]
        if teacher == "TBD":
            continue
        day = row["day_of_week"]
        entry = {
            "slot": row["time_slot"],
            "subject": row["subject"],
            "section": row["section"],
        }
        teacher_view.setdefault(teacher, {}).setdefault(day, []).append(entry)

    # Sort each day's entries by slot
    for teacher in teacher_view:
        for day in teacher_view[teacher]:
            teacher_view[teacher][day].sort(key=lambda x: x["slot"])

    return teacher_view
