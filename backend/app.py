from flask import Flask, render_template, request, session, redirect, url_for, flash
import pandas as pd
import pickle
import numpy as np
import sqlite3
import os
import functools
import sys

# Resolve base directory relative to this file
base_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.append(base_dir)

from models.anomaly_detection import run_anomaly_detection
from utils.notifications import run_notifications_job

app = Flask(__name__)
app.secret_key = 'super_secret_attendance_key'

# Load model
model_path = os.path.join(base_dir, "models", "rf_model.pkl")
if os.path.exists(model_path):
    model = pickle.load(open(model_path, "rb"))
else:
    model = None
    print(f"Warning: Model not found at {model_path}")

def get_db_connection():
    db_path = os.path.join(base_dir, "attendance_system.db")
    return sqlite3.connect(db_path)

# ---- RBAC Decorator ---- #
def login_required(role=None):
    def wrapper(fn):
        @functools.wraps(fn)
        def decorated_view(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                return "Unauthorized Access. You do not have the right permissions.", 403
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

# ---- AUTH ROUTES ---- #
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        conn = get_db_connection()
        user = pd.read_sql_query("SELECT * FROM users WHERE username = ? AND password = ?", conn, params=(username, password))
        conn.close()
        
        if not user.empty:
            session["user_id"] = int(user.iloc[0]["id"])
            session["username"] = user.iloc[0]["username"]
            session["role"] = user.iloc[0]["role"]
            
            if session["role"] == "admin":
                return redirect(url_for("dashboard"))
            elif session["role"] == "faculty":
                return redirect(url_for("faculty_dashboard"))
            elif session["role"] == "mentor":
                return redirect(url_for("mentor_dashboard", mentor_id=session["username"]))
        else:
            return render_template("login.html", error="Invalid credentials")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---- MAIN APP ROUTES ---- #
@app.route("/")
def home():
    if "user_id" in session:
        if session["role"] == "admin":
            return redirect(url_for("dashboard"))
        elif session["role"] == "faculty":
            return redirect(url_for("faculty_dashboard"))
        elif session["role"] == "mentor":
            return redirect(url_for("mentor_dashboard", mentor_id=session["username"]))
    return redirect(url_for("login"))


@app.route("/run_pipeline", methods=["POST"])
@login_required(role="admin")
def run_pipeline():
    try:
        run_anomaly_detection()
        run_notifications_job()
        return "Pipeline Executed Successfully", 200
    except Exception as e:
        return f"Pipeline Error: {e}", 500


@app.route("/faculty_dashboard", methods=["GET", "POST"])
@login_required(role="faculty")
def faculty_dashboard():
    faculty_user = session.get("username")
    conn = get_db_connection()
    
    # Process Bulk Form Submission
    if request.method == "POST":
        section = request.form.get("section")
        date = request.form.get("date")
        
        cursor = conn.cursor()
        success_count = 0
        
        # Iterate over all form data looking for 'status_SXXXX'
        for key, value in request.form.items():
            if key.startswith("status_"):
                student_id = key.split("_")[1]
                present_val = int(value)
                
                prev_data = pd.read_sql_query("SELECT * FROM attendance WHERE StudentID = ? ORDER BY Date DESC LIMIT 1", conn, params=(student_id,))
                
                if not prev_data.empty:
                    row = prev_data.iloc[0].to_dict()
                    row["Date"] = date
                    row["Present"] = present_val
                    
                    row["Absence_Streak"] = 0 if present_val == 1 else row["Absence_Streak"] + 1
                    row["Rolling_Attendance"] = ((row["Rolling_Attendance"] * 9) + present_val) / 10
                    
                    # Reset ML markers for the new day
                    row["Anomaly"] = 0
                    row["Parent_Notified"] = 0
                    row["Mentor_Nudged"] = 0
                    
                    # Remove the row ID if present in the dict so sqlite handles AI correctly
                    if "id" in row: del row["id"]
                    if "db_id" in row: del row["db_id"] 
                    
                    cols = ", ".join(row.keys())
                    placeholders = ", ".join(["?"] * len(row))
                    values = tuple(row.values())
                    
                    cursor.execute(f"INSERT INTO attendance ({cols}) VALUES ({placeholders})", values)
                    success_count += 1
                    
        conn.commit()
        msg = f"Successfully marked attendance for {success_count} students in Section {section}."
    else:
        msg = None

    # Retrieve allotted classes for the logged-in faculty
    classes_df = pd.read_sql_query("SELECT section, time_slot FROM faculty_classes WHERE faculty_username = ?", conn, params=(faculty_user,))
    classes = classes_df.to_dict(orient="records")
    
    # Retrieve all student names and sections relevant to these classes
    if not classes_df.empty:
        sections = tuple(classes_df["section"].tolist())
        # Use simple string formatting since it's an internal admin tool, or generate parameterized `?, ?` string
        placeholders = ','.join('?' * len(sections))
        
        # We query the distinct students using a subquery that finds their latest record structure
        students_query = f"""
        SELECT a.StudentID, a.Student_Name, a.Section 
        FROM attendance a
        INNER JOIN (
            SELECT StudentID, MAX(Date) as MaxDate
            FROM attendance
            WHERE Section IN ({placeholders})
            GROUP BY StudentID
        ) b ON a.StudentID = b.StudentID AND a.Date = b.MaxDate
        ORDER BY a.StudentID ASC
        """
        students_df = pd.read_sql_query(students_query, conn, params=sections)
        students = students_df.to_dict(orient="records")
    else:
        students = []

    conn.close()
    return render_template("faculty_dashboard.html", faculty_id=faculty_user, classes=classes, all_students=students, message=msg)


@app.route("/dashboard")
@login_required(role="admin")
def dashboard():
    conn = get_db_connection()
    
    # Get available sections
    try:
        sections_df = pd.read_sql_query("SELECT DISTINCT Section FROM attendance ORDER BY Section", conn)
        available_sections = sections_df['Section'].dropna().tolist()
    except Exception as e:
        available_sections = []
        
    selected_section = request.args.get("section")
    if selected_section == "All":
        selected_section = None
    
    # Base query for latest records per student
    query = """
    SELECT a.*
    FROM attendance a
    INNER JOIN (
        SELECT StudentID, MAX(Date) as MaxDate
        FROM attendance
        GROUP BY StudentID
    ) b ON a.StudentID = b.StudentID AND a.Date = b.MaxDate
    """
    
    params = ()
    if selected_section:
        query += " WHERE a.Section = ?"
        params = (selected_section,)
        
    try:
        latest_df = pd.read_sql_query(query, conn, params=params)
    except Exception as e:
        print(f"Error querying DB: {e}")
        latest_df = pd.DataFrame()
    finally:
        conn.close()

    risk_summary = []

    for _, row in latest_df.iterrows():
        features = np.array([[
            row.get("Rolling_Attendance", 0),
            row.get("Absence_Streak", 0),
            row.get("Semester_Attendance", 0),
            row.get("Attendance_Trend", 0)
        ]])

        probability = model.predict_proba(features)[0][1] if model else 0.0

        semester_att = row["Semester_Attendance"]
        trend = row["Attendance_Trend"]
        anomaly = row.get("Anomaly", 0)
        notified = row.get("Parent_Notified", 0)

        # ---- Determine Risk Level ----
        if semester_att < 0.70:
            risk_level = "High Risk"
        elif semester_att < 0.75 and trend < -0.15:
            risk_level = "High Risk"
        elif trend < -0.15:
            risk_level = "Watchlist"
        elif probability > 0.85:
            risk_level = "Watchlist"
        else:
            risk_level = "Safe"

        # ---- Determine Recommended Action ----
        if anomaly == 1:
            action = "URGENT (ANOMALY): Verify Medical/Emergency"
        elif risk_level == "High Risk" and trend < -0.3:
            action = "URGENT: Contact Parent + Mentor Meeting"
        elif risk_level == "High Risk":
            action = "Schedule Counseling Session"
        elif risk_level == "Watchlist":
            action = "Send Advisory Warning"
        else:
            action = "No Action Required"

        risk_summary.append({
            "StudentID": row["StudentID"],
            "Semester_Attendance": round(semester_att, 2),
            "Trend": round(trend, 3),
            "Probability": round(probability, 2),
            "Risk_Level": risk_level,
            "Anomaly": bool(anomaly),
            "Notified": "Yes" if notified else "No",
            "Action": action
        })

    risk_df = pd.DataFrame(risk_summary) if risk_summary else pd.DataFrame(columns=["Risk_Level"])

    high_risk = risk_df[risk_df["Risk_Level"] == "High Risk"]
    watchlist = risk_df[risk_df["Risk_Level"] == "Watchlist"]
    safe = risk_df[risk_df["Risk_Level"] == "Safe"]
    anomalies = risk_df[risk_df["Anomaly"] == True]

    return render_template(
        "dashboard.html",
        high_risk=high_risk.to_dict(orient="records") if not high_risk.empty else [],
        watchlist=watchlist.to_dict(orient="records") if not watchlist.empty else [],
        anomalies=anomalies.to_dict(orient="records") if not anomalies.empty else [],
        safe_count=len(safe),
        sections=available_sections,
        selected_section=selected_section
    )

@app.route("/analytics")
@login_required(role="admin")
def analytics():
    conn = get_db_connection()
    
    # Get available semesters
    try:
        semesters_df = pd.read_sql_query("SELECT DISTINCT Semester FROM attendance ORDER BY Semester", conn)
        available_semesters = semesters_df['Semester'].tolist()
    except Exception as e:
        available_semesters = []
        
    selected_semester = request.args.get("semester")
    if not selected_semester and available_semesters:
        selected_semester = str(available_semesters[0])
    elif selected_semester and selected_semester.isdigit():
        selected_semester = int(selected_semester)
    
    # 1. Line Chart: Daily Trends
    query_line = """
    SELECT Date, Hostler, 
           SUM(Present) as Total_Present, 
           COUNT(*) as Total_Students
    FROM attendance
    """
    params = ()
    if selected_semester:
        query_line += " WHERE Semester = ?"
        params = (selected_semester,)
        
    query_line += " GROUP BY Date, Hostler ORDER BY Date ASC"
    
    # 2. Bar Chart: Average Attendance by Section
    query_bar = """
    SELECT Section, SUM(Present)*100.0/COUNT(*) as Avg_Attendance
    FROM attendance
    """
    if selected_semester:
        query_bar += " WHERE Semester = ?"
    query_bar += " GROUP BY Section ORDER BY Section"

    # 3. Scatter Plot & Histogram: Student Level Aggregation
    query_student = """
    SELECT StudentID, Section, Hostler,
           MAX(Absence_Streak) as Max_Absence_Streak,
           SUM(Present)*100.0/COUNT(*) as Semester_Attendance
    FROM attendance
    """
    if selected_semester:
        query_student += " WHERE Semester = ?"
    query_student += " GROUP BY StudentID, Section, Hostler"

    # Fetch Data
    try:
        df_line = pd.read_sql_query(query_line, conn, params=params)
        df_bar = pd.read_sql_query(query_bar, conn, params=params)
        df_student = pd.read_sql_query(query_student, conn, params=params)
    except Exception as e:
        print(f"Error querying DB for analytics: {e}")
        df_line = pd.DataFrame()
        df_bar = pd.DataFrame()
        df_student = pd.DataFrame()
    finally:
        conn.close()

    if df_line.empty or df_student.empty:
        return render_template("analytics.html", semesters=available_semesters, selected_sem=selected_semester)
    
    # --- 1. Line Chart Data ---
    df_line["Attendance_Rate"] = (df_line["Total_Present"] / df_line["Total_Students"]) * 100
    dates = sorted(df_line["Date"].unique().tolist())
    hostler_df = df_line[df_line["Hostler"] == "Yes"].set_index("Date")
    day_scholar_df = df_line[df_line["Hostler"] == "No"].set_index("Date")
    
    hostler_data = [round(hostler_df.loc[d, "Attendance_Rate"], 2) if d in hostler_df.index else None for d in dates]
    day_scholar_data = [round(day_scholar_df.loc[d, "Attendance_Rate"], 2) if d in day_scholar_df.index else None for d in dates]
    
    # --- 2. Bar Chart Data ---
    bar_labels = df_bar["Section"].tolist()
    bar_data = [round(val, 2) for val in df_bar["Avg_Attendance"].tolist()]

    # --- 3. Donut Chart Data ---
    total_hostlers = len(df_student[df_student["Hostler"] == "Yes"])
    total_scholars = len(df_student[df_student["Hostler"] == "No"])
    donut_data = [total_hostlers, total_scholars]

    # --- 4. Scatter Plot Data ---
    # format: [{x: Absence_Streak, y: Semester_Attendance}, ...]
    scatter_data = []
    for _, row in df_student.iterrows():
        scatter_data.append({"x": float(row["Max_Absence_Streak"]), "y": round(float(row["Semester_Attendance"]), 2)})

    # --- 5. Histogram Data ---
    # Bins: 0-20, 20-40, 40-60, 60-80, 80-100
    bins = [0, 20, 40, 60, 80, 100]
    hist_counts, _ = np.histogram(df_student["Semester_Attendance"], bins=bins)
    hist_labels = ["0-20%", "21-40%", "41-60%", "61-80%", "81-100%"]
    hist_data = hist_counts.tolist()

    # --- 6. Funnel Chart Data (Simulated Drop-off) ---
    # Total Enrolled -> Attended first 10% of days -> Attended middle 10% -> Attended last 10%
    dates_list = sorted(list(set(dates)))
    total_enrolled = len(df_student)
    
    if len(dates_list) >= 3:
        start_date = dates_list[0]
        mid_date = dates_list[len(dates_list)//2]
        end_date = dates_list[-1]
        
        start_att = int(df_line[df_line["Date"] == start_date]["Total_Present"].sum())
        mid_att = int(df_line[df_line["Date"] == mid_date]["Total_Present"].sum())
        end_att = int(df_line[df_line["Date"] == end_date]["Total_Present"].sum())
    else:
        start_att = mid_att = end_att = total_enrolled

    funnel_labels = ["Total Enrolled", "Attended Start", "Attended Midterm", "Attended Endterm"]
    funnel_data = [total_enrolled, start_att, mid_att, end_att]

    # --- 7. Treemap Data ---
    # format: [{name: 'Section A - Hostler', value: 20}, ...]
    treemap_data = []
    tree_grouped = df_student.groupby(["Section", "Hostler"]).size().reset_index(name="Count")
    for _, row in tree_grouped.iterrows():
        hostler_label = "Hostler" if row["Hostler"] == "Yes" else "Day Scholar"
        treemap_data.append({
            "name": f"Sec {row['Section']} - {hostler_label}",
            "value": int(row["Count"]),
            "section": row["Section"]
        })

    # --- 8. Bullet / Gauge Data ---
    overall_avg = round(df_student["Semester_Attendance"].mean(), 2) if not df_student.empty else 0

    return render_template(
        "analytics.html",
        semesters=available_semesters,
        selected_sem=selected_semester,
        # 1. Line
        line_labels=dates, line_hostler=hostler_data, line_scholar=day_scholar_data,
        # 2. Bar
        bar_labels=bar_labels, bar_data=bar_data,
        # 3. Donut
        donut_data=donut_data,
        # 4. Scatter
        scatter_data=scatter_data,
        # 5. Histogram
        hist_labels=hist_labels, hist_data=hist_data,
        # 6. Funnel
        funnel_labels=funnel_labels, funnel_data=funnel_data,
        # 7. Treemap
        treemap_data=treemap_data,
        # 8. Bullet / Gauge
        overall_avg=overall_avg
    )

@app.route("/mentor/<mentor_id>")
@login_required(role="mentor")
def mentor_dashboard(mentor_id):
    if session.get("username") != mentor_id:
        return "Unauthorized to view other mentor's dashboard", 403

    conn = get_db_connection()
    query = """
    SELECT a.*
    FROM attendance a
    INNER JOIN (
        SELECT StudentID, MAX(Date) as MaxDate
        FROM attendance
        WHERE MentorID = ?
        GROUP BY StudentID
    ) b ON a.StudentID = b.StudentID AND a.Date = b.MaxDate
    """
    try:
        mentor_students = pd.read_sql_query(query, conn, params=(mentor_id,))
    except Exception as e:
        print(f"Error querying DB: {e}")
        mentor_students = pd.DataFrame()
    finally:
        conn.close()

    risk_summary = []

    for _, row in mentor_students.iterrows():
        features = np.array([[
            row["Rolling_Attendance"],
            row["Absence_Streak"],
            row["Semester_Attendance"],
            row["Attendance_Trend"]
        ]])

        probability = model.predict_proba(features)[0][1] if model else 0.0

        semester_att = row["Semester_Attendance"]
        trend = row["Attendance_Trend"]
        anomaly = row.get("Anomaly", 0)
        nudged = row.get("Mentor_Nudged", 0)

        if semester_att < 0.70:
            risk_level = "High Risk"
        elif semester_att < 0.75 and trend < -0.15:
            risk_level = "High Risk"
        elif trend < -0.15:
            risk_level = "Watchlist"
        elif probability > 0.85:
            risk_level = "Watchlist"
        else:
            risk_level = "Safe"

        if anomaly == 1:
            action = "URGENT (ANOMALY): Please coordinate with parents immediately."
        elif nudged == 1:
            action = "ACTION REQUIRED: Automated Intervention Triggered. Please check in with student."
        elif risk_level == "High Risk" and trend < -0.3:
            action = "URGENT: Schedule Meeting"
        elif risk_level == "High Risk":
            action = "Schedule Counseling Session"
        elif risk_level == "Watchlist":
            action = "Send Advisory Warning"
        else:
            action = "No Action Required"

        risk_summary.append({
            "StudentID": row["StudentID"],
            "Semester_Attendance": round(row["Semester_Attendance"], 2),
            "Trend": round(row["Attendance_Trend"], 3),
            "Probability": round(probability, 2),
            "Risk_Level": risk_level,
            "Anomaly": bool(anomaly),
            "Nudged": bool(nudged),
            "Action": action   
        })

    return render_template(
        "mentor_dashboard.html",
        mentor_id=mentor_id,
        students=risk_summary
    )

@app.route("/student/<student_id>")
def student_detail(student_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    query = "SELECT Date, Rolling_Attendance FROM attendance WHERE StudentID = ? ORDER BY Date ASC"
    student_data = pd.read_sql_query(query, conn, params=(student_id,))
    conn.close()

    if student_data.empty:
        return "Student not found", 404

    dates = student_data["Date"].tolist()
    attendance = student_data["Rolling_Attendance"].tolist()

    return render_template(
        "student_detail.html",
        student_id=student_id,
        dates=dates,
        attendance=attendance
    )

if __name__ == "__main__":
    app.run(debug=True)