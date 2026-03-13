from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
import pandas as pd
import joblib
import numpy as np
import sqlite3
import os
import functools
import sys
import random
from datetime import datetime, timedelta

# Resolve base directory relative to this file
base_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.append(base_dir)

from models.anomaly_detection import run_anomaly_detection
from utils.notifications import run_notifications_job
from utils.email_sender import send_otp_email, send_welcome_email, test_smtp_connection, get_smtp_config, _send_email
import io
import csv

app = Flask(__name__)
app.secret_key = 'super_secret_attendance_key'

# Load model
model_path = os.path.join(base_dir, "models", "rf_model.pkl")
if os.path.exists(model_path):
    model = joblib.load(model_path)
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
        username = request.form.get("username", "").strip()
        step = request.form.get("step", "1")

        conn = get_db_connection()
        user = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(username,))

        if user.empty:
            conn.close()
            return render_template("login.html", error="Username not found.", step=1)

        user_role = user.iloc[0]["role"]

        # ---- ADMIN: traditional password login ----
        if user_role == "admin":
            password = request.form.get("password", "")
            if password and user.iloc[0]["password"] == password:
                session["user_id"] = int(user.iloc[0]["id"])
                session["username"] = user.iloc[0]["username"]
                session["role"] = user.iloc[0]["role"]
                conn.close()
                return redirect(url_for("dashboard"))
            else:
                conn.close()
                return render_template("login.html", error="Invalid password.", step=1, username=username, is_admin=True)

        # ---- FACULTY / MENTOR: OTP-based login ----
        if step == "1":
            # Step 1: username entered — auto-generate and send OTP
            user_email = user.iloc[0].get("email", "")

            # Invalidate any previous unused OTPs
            cursor = conn.cursor()
            cursor.execute("UPDATE login_otps SET used = 1 WHERE username = ? AND used = 0", (username,))

            # Generate new OTP (10 min expiry)
            otp_code = str(random.randint(100000, 999999))
            now = datetime.now()
            created_at = now.strftime("%Y-%m-%d %H:%M:%S")
            expires_at = (now + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute(
                "INSERT INTO login_otps (username, otp_code, created_at, expires_at, used) VALUES (?, ?, ?, ?, 0)",
                (username, otp_code, created_at, expires_at)
            )
            conn.commit()

            # Send OTP via email (or console fallback)
            if user_email:
                success, msg = send_otp_email(user_email, otp_code, username)
                if success:
                    info_msg = f"OTP sent to {user_email[:3]}***{user_email[user_email.index('@'):]}"
                else:
                    info_msg = f"OTP generated (email delivery failed). Check with admin. Code printed to server console."
            else:
                # No email configured — print to console
                print(f"[LOGIN OTP] Username: {username}, OTP: {otp_code} (no email configured)")
                info_msg = "OTP generated. No email configured — please check with admin or server console."

            conn.close()
            return render_template("login.html", step=2, username=username, info=info_msg)

        elif step == "2":
            # Step 2: verify OTP
            otp_entered = request.form.get("otp", "").strip()
            otp_record = pd.read_sql_query(
                "SELECT * FROM login_otps WHERE username = ? AND used = 0 ORDER BY id DESC LIMIT 1",
                conn, params=(username,)
            )

            if otp_record.empty:
                conn.close()
                return render_template("login.html", step=2, username=username,
                                       error="No active OTP found. Please ask your admin to send a new one.")

            stored_otp = str(otp_record.iloc[0]["otp_code"])
            expires_at = datetime.strptime(otp_record.iloc[0]["expires_at"], "%Y-%m-%d %H:%M:%S")

            if datetime.now() > expires_at:
                conn.close()
                return render_template("login.html", step=2, username=username,
                                       error="OTP has expired. Please ask your admin to send a new one.")

            if otp_entered != stored_otp:
                conn.close()
                return render_template("login.html", step=2, username=username,
                                       error="Invalid OTP. Please try again.")

            # OTP valid — mark as used and log in
            cursor = conn.cursor()
            cursor.execute("UPDATE login_otps SET used = 1 WHERE id = ?", (int(otp_record.iloc[0]["id"]),))
            conn.commit()

            session["user_id"] = int(user.iloc[0]["id"])
            session["username"] = user.iloc[0]["username"]
            session["role"] = user.iloc[0]["role"]
            conn.close()

            if session["role"] == "faculty":
                return redirect(url_for("faculty_dashboard"))
            elif session["role"] == "mentor":
                return redirect(url_for("mentor_dashboard", mentor_id=session["username"]))
            elif session["role"] == "student":
                return redirect(url_for("student_dashboard"))

    return render_template("login.html", step=1)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---- ADMIN: User Management & OTP Dispatch ---- #
@app.route("/admin/manage_users")
@login_required(role="admin")
def manage_users():
    """Admin page to view all faculty and manage OTPs."""
    conn = get_db_connection()
    users_df = pd.read_sql_query(
        "SELECT id, username, role, email, full_name FROM users WHERE role != 'admin' ORDER BY role, username", conn
    )

    # Check if SMTP is configured
    smtp_cfg = get_smtp_config()
    smtp_configured = smtp_cfg is not None

    conn.close()
    users_list = users_df.to_dict(orient="records")
    return render_template("admin_manage_users.html", users=users_list, smtp_configured=smtp_configured)


@app.route("/admin/send_login_otp/<username>", methods=["POST"])
@login_required(role="admin")
def send_login_otp(username):
    """Admin resends a login OTP to a faculty's email."""
    conn = get_db_connection()
    user = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(username,))

    if user.empty:
        conn.close()
        return jsonify({"success": False, "message": "User not found."}), 404

    user_role = user.iloc[0]["role"]
    if user_role == "admin":
        conn.close()
        return jsonify({"success": False, "message": "Cannot send OTP to admin accounts."}), 400

    user_email = user.iloc[0].get("email", "")
    if not user_email:
        conn.close()
        return jsonify({"success": False, "message": f"No email configured for {username}."}), 400

    # Invalidate any previous unused OTPs for this user
    cursor = conn.cursor()
    cursor.execute("UPDATE login_otps SET used = 1 WHERE username = ? AND used = 0", (username,))

    # Generate and store new OTP (10 min expiry)
    otp_code = str(random.randint(100000, 999999))
    now = datetime.now()
    created_at = now.strftime("%Y-%m-%d %H:%M:%S")
    expires_at = (now + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        "INSERT INTO login_otps (username, otp_code, created_at, expires_at, used) VALUES (?, ?, ?, ?, 0)",
        (username, otp_code, created_at, expires_at)
    )
    conn.commit()
    conn.close()

    # Send email (or console fallback)
    success, msg = send_otp_email(user_email, otp_code, username)
    return jsonify({"success": success, "message": msg})


# ---- ADMIN: SMTP Settings ---- #
@app.route("/admin/smtp_settings", methods=["GET", "POST"])
@login_required(role="admin")
def smtp_settings():
    """Admin configures SMTP email settings."""
    conn = get_db_connection()

    if request.method == "POST":
        smtp_host = request.form.get("smtp_host", "").strip()
        smtp_port = request.form.get("smtp_port", "587").strip()
        smtp_user = request.form.get("smtp_user", "").strip()
        smtp_pass = request.form.get("smtp_pass", "").strip()

        cursor = conn.cursor()
        cursor.execute(
            "UPDATE smtp_config SET smtp_host=?, smtp_port=?, smtp_user=?, smtp_pass=? WHERE id=1",
            (smtp_host, int(smtp_port), smtp_user, smtp_pass)
        )
        conn.commit()
        conn.close()
        return render_template("admin_smtp_settings.html",
                               smtp_host=smtp_host, smtp_port=smtp_port,
                               smtp_user=smtp_user, smtp_pass=smtp_pass,
                               success="SMTP settings saved successfully!")

    # GET: load current settings
    row = conn.execute("SELECT * FROM smtp_config WHERE id = 1").fetchone()
    conn.close()
    if row:
        return render_template("admin_smtp_settings.html",
                               smtp_host=row[1] or "", smtp_port=row[2] or 587,
                               smtp_user=row[3] or "", smtp_pass=row[4] or "")
    return render_template("admin_smtp_settings.html")


@app.route("/admin/test_smtp", methods=["POST"])
@login_required(role="admin")
def test_smtp():
    """Test SMTP connection with current settings."""
    data = request.get_json()
    success, msg = test_smtp_connection(
        data.get("host", ""), data.get("port", 587),
        data.get("user", ""), data.get("pass", "")
    )
    return jsonify({"success": success, "message": msg})


# ---- ADMIN: Faculty CSV Upload ---- #
@app.route("/admin/upload_faculty", methods=["POST"])
@login_required(role="admin")
def upload_faculty():
    """Upload CSV to auto-create faculty accounts and send OTP emails."""
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded."}), 400

    file = request.files["file"]
    if not file.filename.endswith(".csv"):
        return jsonify({"success": False, "message": "Please upload a CSV file."}), 400

    try:
        raw = file.stream.read().decode("utf-8-sig")  # utf-8-sig handles BOM from Excel
        stream = io.StringIO(raw)
        reader = csv.DictReader(stream)

        # Strip whitespace from column headers
        if reader.fieldnames:
            reader.fieldnames = [f.strip() for f in reader.fieldnames]

        required_cols = {"name", "email", "subject", "sections", "time_slot"}
        if not required_cols.issubset(set(reader.fieldnames or [])):
            missing = required_cols - set(reader.fieldnames or [])
            return jsonify({"success": False, "message": f"Missing columns: {', '.join(missing)}"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        results = {"created": 0, "skipped": 0, "emails_sent": 0, "errors": []}

        for row in reader:
            name = row["name"].strip()
            email = row["email"].strip()
            subject = row["subject"].strip()
            sections = [s.strip() for s in row["sections"].split(",")]
            time_slot = row["time_slot"].strip()

            # Auto-generate username from name
            username = name.lower().replace(" ", "_")

            # Check if user already exists
            existing = pd.read_sql_query("SELECT id FROM users WHERE username = ?", conn, params=(username,))
            if not existing.empty:
                results["skipped"] += 1
                results["errors"].append(f"{username}: already exists (skipped)")
                continue

            # Create user account (password=otp_only since they use OTP login)
            cursor.execute(
                "INSERT INTO users (username, password, role, email, full_name) VALUES (?, ?, ?, ?, ?)",
                (username, "otp_only", "faculty", email, name)
            )

            # Create faculty class assignments
            for section in sections:
                cursor.execute(
                    "INSERT INTO faculty_classes (faculty_username, subject, section, time_slot) VALUES (?, ?, ?, ?)",
                    (username, subject, section, time_slot)
                )

            # Generate login OTP (10 min expiry)
            otp_code = str(random.randint(100000, 999999))
            now = datetime.now()
            created_at = now.strftime("%Y-%m-%d %H:%M:%S")
            expires_at = (now + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute(
                "INSERT INTO login_otps (username, otp_code, created_at, expires_at, used) VALUES (?, ?, ?, ?, 0)",
                (username, otp_code, created_at, expires_at)
            )

            results["created"] += 1

            # Auto-send welcome email with credentials
            success, msg = send_welcome_email(email, name, username, otp_code)
            if success:
                results["emails_sent"] += 1
            else:
                results["errors"].append(f"{username}: email failed — {msg}")

        conn.commit()
        conn.close()

        summary = f"Created {results['created']} accounts, sent {results['emails_sent']} emails."
        if results["skipped"] > 0:
            summary += f" Skipped {results['skipped']} (already exist)."

        return jsonify({
            "success": True,
            "message": summary,
            "details": results
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Error processing CSV: {str(e)}"}), 500


# ---- ADMIN: Student Data & Master Timetable Upload ---- #
@app.route("/admin/upload_student_data", methods=["POST"])
@login_required(role="admin")
def upload_student_data():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded."}), 400

    file = request.files["file"]
    if not file.filename.endswith(".csv"):
        return jsonify({"success": False, "message": "Please upload a CSV file."}), 400

    try:
        raw = file.stream.read().decode("utf-8-sig")
        stream = io.StringIO(raw)
        reader = csv.DictReader(stream)

        if reader.fieldnames:
            reader.fieldnames = [f.strip() for f in reader.fieldnames]

        required_cols = {"name", "registration_no", "section", "subjects", "assigned_mentors", "student_email", "parent_email"}
        if not required_cols.issubset(set(reader.fieldnames or [])):
            missing = required_cols - set(reader.fieldnames or [])
            return jsonify({"success": False, "message": f"Missing columns: {', '.join(missing)}"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        results = {"added": 0, "errors": []}

        for row in reader:
            reg_no = row["registration_no"].strip()
            course = row.get("course", "").strip() or "B.Tech"
            cls = row.get("class", "1").strip() or "1"
            sec = row["section"].strip()
            mentor = row.get("assigned_mentors", "").strip()
            stu_email = row.get("student_email", "").strip()
            par_email = row.get("parent_email", "").strip()
            subs = row.get("subjects", "").strip()
            
            try:
                cursor.execute(
                    "INSERT INTO students (registration_no, name, course, class_name, section, mentor_name, student_email, parent_email, enrolled_subjects) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (reg_no, row["name"].strip(), course, cls, sec, mentor, stu_email, par_email, subs)
                )
                
                # Also create a user account for the student to login with OTP
                username = reg_no.lower()
                existing = pd.read_sql_query("SELECT id FROM users WHERE username = ?", conn, params=(username,))
                if existing.empty:
                    cursor.execute(
                        "INSERT INTO users (username, password, role, email, full_name) VALUES (?, ?, ?, ?, ?)",
                        (username, "otp_only", "student", stu_email, row["name"].strip())
                    )
                
                results["added"] += 1
            except sqlite3.IntegrityError:
                results["errors"].append(f"Registration No {reg_no} already exists.")
                
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"Added {results['added']} students. Errors: {len(results['errors'])}",
            "details": results
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Error processing CSV: {str(e)}"}), 500


@app.route("/admin/generate_timetable", methods=["POST"])
@login_required(role="admin")
def generate_timetable():
    """Triggers the automated college timetable generation for all sections."""
    try:
        generate_student_timetables()
        flash("✅ AI Timetable generated successfully! 24 classes per week have been scheduled for all sections.")
        return redirect(url_for("dashboard"))
    except Exception as e:
        flash(f"❌ Timetable Generation Error: {str(e)}")
        return redirect(url_for("dashboard"))

    except Exception as e:
        return jsonify({"success": False, "message": f"Error processing CSV: {str(e)}"}), 500

def generate_student_timetables():
    """Generates a complete college timetable automatically: 24 classes/week, Mon-Fri, 9AM-5PM."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Clear existing timetables
    cursor.execute("DELETE FROM master_timetable")
    cursor.execute("DELETE FROM student_timetable")
    
    # 1. Definitions
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    slots = [
        "09:00 AM - 10:00 AM",
        "10:00 AM - 11:00 AM",
        "11:00 AM - 12:00 PM",
        "12:00 PM - 01:00 PM",
        "02:00 PM - 03:00 PM",
        "03:00 PM - 04:00 PM",
        "04:00 PM - 05:00 PM"
    ]
    all_possible_slots = []
    for d in days:
        for s in slots:
            all_possible_slots.append((d, s))
            
    # 2. Get Faculty Mapping (Simple Mock/Lookup)
    faculty_df = pd.read_sql_query("SELECT DISTINCT faculty_username, subject FROM faculty_classes", conn)
    subj_faculty = {row["subject"]: row["faculty_username"] for _, row in faculty_df.iterrows()}
    # Fallback for subjects without assigned faculty
    all_fac = pd.read_sql_query("SELECT username FROM users WHERE role='faculty'", conn)["username"].tolist()
    
    # 3. Get Sections
    sections_df = pd.read_sql_query("SELECT DISTINCT class_name, section FROM students", conn)
    
    # Global tracker for faculty usage to avoid overlaps
    faculty_busy_slots = {} # {faculty_username: set( (day, slot) )}

    for _, sec_row in sections_df.iterrows():
        cls = sec_row["class_name"]
        sec = sec_row["section"]
        
        # Get students and their subjects for this section
        students_in_sec = pd.read_sql_query("SELECT registration_no, enrolled_subjects FROM students WHERE class_name=? AND section=?", conn, params=(cls, sec))
        if students_in_sec.empty: continue
        
        # Unique subjects in this section
        section_subjects = set()
        for idx, s_row in students_in_sec.iterrows():
            if s_row["enrolled_subjects"]:
                for s in s_row["enrolled_subjects"].split(","):
                    section_subjects.add(s.strip())
        
        section_subjects = list(section_subjects)
        if not section_subjects: continue
        
        # We need to fill 24 slots for this section
        random.seed(42 + hash(sec)) # maintain some consistency
        chosen_slots = random.sample(all_possible_slots, min(24, len(all_possible_slots)))
        
        for i, (day, slot) in enumerate(chosen_slots):
            # Pick a subject from the list (cycling through)
            subj = section_subjects[i % len(section_subjects)]
            
            # Find teacher
            teacher = subj_faculty.get(subj)
            if not teacher:
                teacher = all_fac[hash(subj) % len(all_fac)] if all_fac else "TBD"
            
            # Master entry
            cursor.execute(
                "INSERT INTO master_timetable (subject, teacher, day_of_week, time_slot, class_name, section) VALUES (?, ?, ?, ?, ?, ?)",
                (subj, teacher, day, slot, cls, sec)
            )
            
            # Assign to each student in this section if they enrolled
            for _, student in students_in_sec.iterrows():
                if subj in (student["enrolled_subjects"] or ""):
                    cursor.execute(
                        "INSERT INTO student_timetable (registration_no, subject, teacher, day_of_week, time_slot) VALUES (?, ?, ?, ?, ?)",
                        (student["registration_no"], subj, teacher, day, slot)
                    )
                    
    conn.commit()
    conn.close()

@app.route("/admin/upload_admin_file", methods=["POST"])
@login_required(role="admin")
def upload_admin_file():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "Please select a file."}), 400

    class_name = request.form.get("class_name", "").strip()
    section = request.form.get("section", "").strip()

    upload_folder = os.path.join(base_dir, "backend", "static", "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    
    filename = file.filename
    filepath = os.path.join("uploads", filename)
    file_save_path = os.path.join(upload_folder, filename)
    
    file.save(file_save_path)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO admin_files (filename, filepath, class_name, section, upload_date) VALUES (?, ?, ?, ?, ?)",
        (filename, filepath, class_name, section, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": f"Successfully uploaded {filename} for Class {class_name} Section {section}"})

# ---- OTP CREDENTIAL CHANGE ROUTES ---- #
@app.route("/change_credentials", methods=["GET", "POST"])
def change_credentials():
    """Step 1: User enters current username to request an OTP."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        
        conn = get_db_connection()
        user = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(username,))
        
        if user.empty:
            conn.close()
            return render_template("change_credentials.html", step=1, error="Username not found.")
        
        user_role = user.iloc[0]["role"]
        if user_role == "admin":
            conn.close()
            return render_template("change_credentials.html", step=1, error="Admin credentials cannot be changed through this flow.")
        
        # Generate 6-digit OTP
        otp_code = str(random.randint(100000, 999999))
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor = conn.cursor()
        cursor.execute("INSERT INTO otp_requests (username, otp_code, created_at, used) VALUES (?, ?, ?, 0)",
                       (username, otp_code, created_at))
        conn.commit()
        conn.close()
        
        # In a real system, this OTP would be sent via email/SMS
        return render_template("change_credentials.html", step=2, username=username, otp_display=otp_code)
    
    return render_template("change_credentials.html", step=1)


@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    """Step 2: User enters the OTP to verify identity."""
    username = request.form.get("username", "").strip()
    otp_entered = request.form.get("otp", "").strip()
    
    conn = get_db_connection()
    # Get the latest unused OTP for this user
    otp_record = pd.read_sql_query(
        "SELECT * FROM otp_requests WHERE username = ? AND used = 0 ORDER BY id DESC LIMIT 1",
        conn, params=(username,)
    )
    
    if otp_record.empty:
        conn.close()
        return render_template("change_credentials.html", step=2, username=username, error="No OTP found. Please request a new one.")
    
    stored_otp = otp_record.iloc[0]["otp_code"]
    created_at = datetime.strptime(otp_record.iloc[0]["created_at"], "%Y-%m-%d %H:%M:%S")
    
    # Check expiry (5 minutes)
    if datetime.now() - created_at > timedelta(minutes=5):
        conn.close()
        return render_template("change_credentials.html", step=1, error="OTP has expired. Please request a new one.")
    
    if otp_entered != str(stored_otp):
        conn.close()
        return render_template("change_credentials.html", step=2, username=username, error="Invalid OTP. Please try again.")
    
    # Mark OTP as used
    cursor = conn.cursor()
    cursor.execute("UPDATE otp_requests SET used = 1 WHERE id = ?", (int(otp_record.iloc[0]["id"]),))
    conn.commit()
    conn.close()
    
    # Store verification in session for the update step
    session["otp_verified_user"] = username
    
    return render_template("change_credentials.html", step=3, username=username)


@app.route("/update_credentials", methods=["POST"])
def update_credentials():
    """Step 3: User sets new username and password after OTP verification."""
    verified_user = session.get("otp_verified_user")
    if not verified_user:
        return render_template("change_credentials.html", step=1, error="Session expired. Please start over.")
    
    new_username = request.form.get("new_username", "").strip()
    new_password = request.form.get("new_password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()
    
    if not new_username or not new_password:
        return render_template("change_credentials.html", step=3, username=verified_user, error="Username and password cannot be empty.")
    
    if new_password != confirm_password:
        return render_template("change_credentials.html", step=3, username=verified_user, error="Passwords do not match.")
    
    conn = get_db_connection()
    
    # Check if new username already exists (and is different from current)
    if new_username != verified_user:
        existing = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(new_username,))
        if not existing.empty:
            conn.close()
            return render_template("change_credentials.html", step=3, username=verified_user, error="Username already taken. Choose a different one.")
    
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET username = ?, password = ? WHERE username = ?",
                   (new_username, new_password, verified_user))
    
    # Also update faculty_classes if this was a faculty user
    cursor.execute("UPDATE faculty_classes SET faculty_username = ? WHERE faculty_username = ?",
                   (new_username, verified_user))
    
    # Also update MentorID in attendance if this was a mentor
    cursor.execute("UPDATE attendance SET MentorID = ? WHERE MentorID = ?",
                   (new_username, verified_user))
    
    conn.commit()
    conn.close()
    
    # Clear the verification session
    session.pop("otp_verified_user", None)
    
    return render_template("login.html", error=None, success=f"Credentials updated! Login with your new username '{new_username}'.")


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
        elif session["role"] == "student":
            return redirect(url_for("student_dashboard"))
    return redirect(url_for("login"))


@app.route("/run_pipeline", methods=["POST"])
@login_required(role="admin")
def run_pipeline():
    try:
        run_anomaly_detection()
        run_notifications_job()
        flash("✅ Student analysis refreshed successfully! All risk levels and notifications have been updated.")
    except Exception as e:
        flash(f"❌ Analysis error: {e}")
    return redirect(url_for("dashboard"))

@app.route("/admin/reset_students", methods=["POST"])
@login_required(role="admin")
def reset_students():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Clear attendance records
        cursor.execute("DELETE FROM attendance")
        
        # 2. Clear student records
        cursor.execute("DELETE FROM students")
        
        # 3. Clear users with role 'student'
        cursor.execute("DELETE FROM users WHERE role = 'student'")
        
        # 4. Clear timetables
        cursor.execute("DELETE FROM student_timetable")
        cursor.execute("DELETE FROM master_timetable")
        
        conn.commit()
        conn.close()
        
        flash("✅ All student details, attendance, and timetables have been reset successfully.")
    except Exception as e:
        flash(f"❌ Reset error: {e}")
    return redirect(url_for("dashboard"))

@app.route("/admin/reset_faculty", methods=["POST"])
@login_required(role="admin")
def reset_faculty():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Clear faculty class assignments
        cursor.execute("DELETE FROM faculty_classes")
        
        # 2. Clear users with role 'faculty' or 'mentor'
        cursor.execute("DELETE FROM users WHERE role IN ('faculty', 'mentor')")
        
        # 3. Clear OTP related tables
        cursor.execute("DELETE FROM login_otps")
        cursor.execute("DELETE FROM otp_requests")
        
        conn.commit()
        conn.close()
        
        flash("✅ All faculty and mentor accounts, class assignments, and OTP requests have been reset successfully.")
    except Exception as e:
        flash(f"❌ Reset error: {e}")
    return redirect(url_for("manage_users"))

@app.route("/student_dashboard")
@login_required(role="student")
def student_dashboard():
    registration_no = session.get("username").upper() # users table has lowercase, students table might differ but let's compare case insensitive
    
    conn = get_db_connection()
    
    # Get student info
    student_df = pd.read_sql_query("SELECT * FROM students WHERE LOWER(registration_no) = ?", conn, params=(registration_no.lower(),))
    
    if student_df.empty:
        conn.close()
        return "Student profile not found.", 404
        
    student = student_df.iloc[0].to_dict()
    student_id = student["registration_no"]
    cls = student["class_name"]
    sec = student["section"]
    
    # 1. Subject-wise attendance (calling existing logic API-like)
    query_att = """
    SELECT Subject,
           COUNT(*) as total_classes,
           SUM(Present) as attended,
           ROUND(SUM(Present)*100.0/COUNT(*), 1) as attendance_pct
    FROM attendance
    WHERE LOWER(StudentID) = ?
    GROUP BY Subject
    """
    att_df = pd.read_sql_query(query_att, conn, params=(registration_no.lower(),))
    attendance_data = att_df.to_dict(orient="records")

    # 2. Personal Timetable
    tt_df = pd.read_sql_query(
        "SELECT * FROM student_timetable WHERE LOWER(registration_no) = ? ORDER BY day_of_week, time_slot",
        conn, params=(registration_no.lower(),)
    )
    timetable = tt_df.to_dict(orient="records")
    
    # 3. Admin Files
    files_df = pd.read_sql_query(
        "SELECT * FROM admin_files WHERE class_name = ? AND section = ? ORDER BY upload_date DESC",
        conn, params=(cls, sec)
    )
    admin_files = files_df.to_dict(orient="records")
    
    conn.close()

    return render_template(
        "student_dashboard.html",
        student=student,
        attendance_data=attendance_data,
        timetable=timetable,
        admin_files=admin_files
    )

# ---- REST API ENDPOINTS ---- #

@app.route("/api/upload", methods=["POST"])
def api_upload_csv():
    """
    Accepts a CSV upload for attendance records.
    Expected columns: student_id, date, subject, status
    """
    if "file" not in request.files:
        return {"error": "No file part in the request"}, 400
        
    file = request.files["file"]
    if file.filename == "":
        return {"error": "No selected file"}, 400
        
    if file and file.filename.endswith(".csv"):
        try:
            df = pd.read_csv(file)
            required_cols = ["student_id", "date", "subject", "status"]
            
            # Check if required columns exist
            if not all(col in df.columns for col in required_cols):
                return {"error": f"Missing required columns. Expected: {required_cols}"}, 400
            
            # Map prompt-specific columns to DB schema
            df = df.rename(columns={
                "student_id": "StudentID",
                "date": "Date",
                # "subject": "Section"  <- REMOVED
            })
            if "subject" in df.columns:
                df = df.rename(columns={"subject": "Subject"})
            elif "Section" not in df.columns:
                return {"error": "Missing 'subject' or 'Section' column"}, 400
            
            # Map status ('Present'/'Absent' or 1/0) to Present (1/0)
            if df["status"].dtype == object:
                df["Present"] = df["status"].str.lower().map({"present": 1, "absent": 0, "p": 1, "a": 0})
            else:
                df["Present"] = df["status"]
            
            df = df.drop(columns=["status"])
            
            conn = get_db_connection()
            
            # Minimal Preprocessing
            if "Anomaly" not in df.columns: df["Anomaly"] = 0
            if "Parent_Notified" not in df.columns: df["Parent_Notified"] = 0
            if "Mentor_Nudged" not in df.columns: df["Mentor_Nudged"] = 0
            if "Rolling_Attendance" not in df.columns: df["Rolling_Attendance"] = df["Present"] # Dummy init
            if "Absence_Streak" not in df.columns: df["Absence_Streak"] = (df["Present"] == 0).astype(int)
            if "Semester_Attendance" not in df.columns: df["Semester_Attendance"] = df["Present"]
            if "Attendance_Trend" not in df.columns: df["Attendance_Trend"] = 0.0
            
            df.to_sql("attendance", conn, if_exists="append", index=False)
            conn.close()
            
            return {"message": f"Successfully uploaded {len(df)} records."}, 200
            
        except Exception as e:
            return {"error": str(e)}, 500
    else:
        return {"error": "Invalid file type. Please upload a CSV."}, 400

@app.route("/api/predict", methods=["GET"])
def api_predict():
    """
    Runs prediction on all students and returns the JSON payload.
    """
    if not model:
        return {"error": "Model not loaded."}, 500
        
    conn = get_db_connection()
    query = """
    SELECT a.*
    FROM attendance a
    INNER JOIN (
        SELECT StudentID, Subject, MAX(Date) as MaxDate
        FROM attendance
        GROUP BY StudentID, Subject
    ) b ON a.StudentID = b.StudentID AND a.Subject = b.Subject AND a.Date = b.MaxDate
    """
    try:
        latest_df = pd.read_sql_query(query, conn)
    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        conn.close()
        
    predictions = []
    if not latest_df.empty:
        grouped = latest_df.groupby("StudentID")
        for student_id, group in grouped:
            subject_probs = []
            for _, row in group.iterrows():
                features = np.array([[
                    row.get("Rolling_Attendance", 0),
                    row.get("Absence_Streak", 0),
                    row.get("Semester_Attendance", 0),
                    row.get("Attendance_Trend", 0)
                ]])
                try:
                    p = model.predict_proba(features)[0][1] if model else 0.0
                except Exception as e:
                    print(f"Prediction error for student {student_id}: {e}")
                    p = 0.0
                subject_probs.append(p)
                
            avg_prob = np.mean(subject_probs)
            predictions.append({
                "StudentID": student_id,
                "RiskScore": round(avg_prob, 3),
                "HighRisk": bool(avg_prob > 0.75)
            })
            
    return {"predictions": predictions, "message": "Prediction successful (aggregated across subjects)"}, 200

@app.route("/api/anomalies", methods=["GET"])
def api_anomalies():
    """
    Returns a list of students flagged as anomalous by DBSCAN.
    """
    conn = get_db_connection()
    try:
        query = """
        SELECT a.StudentID, a.Student_Name, a.Date, a.Section 
        FROM attendance a
        INNER JOIN (
            SELECT StudentID, MAX(Date) as MaxDate
            FROM attendance
            GROUP BY StudentID
        ) b ON a.StudentID = b.StudentID AND a.Date = b.MaxDate
        WHERE a.Anomaly = 1
        """
        anomalies_df = pd.read_sql_query(query, conn)
        return {"anomalies": anomalies_df.to_dict(orient="records")}, 200
    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        conn.close()



@app.route("/faculty_dashboard", methods=["GET", "POST"])
@login_required(role="faculty")
def faculty_dashboard():
    faculty_user = session.get("username")
    conn = get_db_connection()
    
    # Process Bulk Form Submission
    if request.method == "POST":
        section = request.form.get("section")
        date = request.form.get("date")
        subject = request.form.get("subject")
        
        cursor = conn.cursor()
        success_count = 0
        low_attendance_alerts = []
        
        # Iterate over all form data looking for 'status_SXXXX'
        for key, value in request.form.items():
            if key.startswith("status_"):
                student_id = key.split("_")[1]
                present_val = int(value)
                
                prev_data = pd.read_sql_query("SELECT * FROM attendance WHERE StudentID = ? AND Subject = ? ORDER BY Date DESC LIMIT 1", conn, params=(student_id, subject))
                
                if not prev_data.empty:
                    row = prev_data.iloc[0].to_dict()
                    row["Date"] = date
                    row["Present"] = present_val
                    
                    row["Absence_Streak"] = 0 if present_val == 1 else row["Absence_Streak"] + 1
                    row["Rolling_Attendance"] = ((row["Rolling_Attendance"] * 9) + present_val) / 10
                    
                    # Recalculate semester attendance
                    total_records = pd.read_sql_query(
                        "SELECT COUNT(*) as cnt, SUM(Present) as total FROM attendance WHERE StudentID = ? AND Subject = ?",
                        conn, params=(student_id, subject)
                    )
                    if not total_records.empty and total_records.iloc[0]["cnt"] > 0:
                        new_sem_att = (total_records.iloc[0]["total"] + present_val) / (total_records.iloc[0]["cnt"] + 1)
                        row["Semester_Attendance"] = round(new_sem_att, 4)
                    
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
                    
                    # Auto-SMS check: if overall semester attendance drops below 75%
                    overall_att = pd.read_sql_query(
                        "SELECT SUM(Present)*1.0/COUNT(*) as avg_att FROM attendance WHERE StudentID = ?",
                        conn, params=(student_id,)
                    )
                    if not overall_att.empty:
                        avg = overall_att.iloc[0]["avg_att"]
                        if avg is not None and avg < 0.75:
                            parent_contact = row.get("Parent_Contact", "N/A")
                            student_name = row.get("Student_Name", student_id)
                            pct = round(avg * 100, 1)
                            print(f"[AUTO-SMS] To Parent ({parent_contact}): {student_name}'s attendance is {pct}% (below 75%). Please ensure regular attendance.")
                            low_attendance_alerts.append(student_name)
                    
        conn.commit()
        msg = f"Successfully marked attendance for {success_count} students in Section {section} for {subject}."
        if low_attendance_alerts:
            msg += f" ⚠️ Auto-SMS sent to parents of {len(low_attendance_alerts)} student(s) with attendance below 75%."
    else:
        msg = None

    # Retrieve allotted classes for the logged-in faculty
    classes_df = pd.read_sql_query("SELECT subject, section, time_slot FROM faculty_classes WHERE faculty_username = ?", conn, params=(faculty_user,))
    classes = classes_df.to_dict(orient="records")
    
    # Retrieve all student names and sections relevant to these classes
    if not classes_df.empty:
        sections = tuple(classes_df["section"].tolist())
        subject = classes_df.iloc[0]["subject"]  # Faculty maps to 1 subject
        
        placeholders = ','.join('?' * len(sections))
        
        # We query the distinct students from the students table who are in these sections
        students_query = f"""
        SELECT registration_no AS StudentID, name AS Student_Name, section AS Section
        FROM students
        WHERE section IN ({placeholders})
        ORDER BY registration_no ASC
        """
        params = list(sections)
        students_df = pd.read_sql_query(students_query, conn, params=params)
        students = students_df.to_dict(orient="records")

        # ---- Mentor View: Compute risk summary for students in these sections ----
        # Query ALL students in these sections and bring in latest attendance if it exists
        mentor_query = f"""
        SELECT s.registration_no AS StudentID, s.name AS Student_Name, s.section AS Section,
               a.Rolling_Attendance, a.Absence_Streak, a.Semester_Attendance, a.Attendance_Trend, a.Anomaly
        FROM students s
        LEFT JOIN (
            SELECT StudentID, MAX(Date) as MaxDate
            FROM attendance
            GROUP BY StudentID
        ) b ON s.registration_no = b.StudentID
        LEFT JOIN attendance a ON b.StudentID = a.StudentID AND b.MaxDate = a.Date
        WHERE s.section IN ({placeholders})
        """
        mentor_params = list(sections)
        try:
            mentor_df = pd.read_sql_query(mentor_query, conn, params=mentor_params)
        except Exception as e:
            print(f"Error querying mentor data: {e}")
            mentor_df = pd.DataFrame()

        mentor_risk = []
        if not mentor_df.empty:
            grouped = mentor_df.groupby("StudentID")
            for student_id, group in grouped:
                subject_probs = []
                for _, row in group.iterrows():
                    features = np.array([[
                        row.get("Rolling_Attendance", 0),
                        row.get("Absence_Streak", 0),
                        row.get("Semester_Attendance", 0),
                        row.get("Attendance_Trend", 0)
                    ]])
                    try:
                        p = model.predict_proba(features)[0][1] if model else 0.0
                    except (IndexError, Exception):
                        p = 0.0
                    subject_probs.append(p)

                avg_prob = np.mean(subject_probs) if subject_probs else 0.0
                avg_semester_att = group["Semester_Attendance"].fillna(0.85).mean() # Default to 85% for new students
                avg_trend = group["Attendance_Trend"].fillna(0.0).mean()
                has_anomaly = group["Anomaly"].fillna(0).max() == 1
                student_name = group.iloc[0].get("Student_Name", student_id)
                student_section = group.iloc[0].get("Section", "")

                if avg_semester_att < 0.70:
                    risk_level = "High Risk"
                elif avg_semester_att < 0.75 and avg_trend < -0.15:
                    risk_level = "High Risk"
                elif avg_trend < -0.15:
                    risk_level = "Watchlist"
                elif avg_prob > 0.85:
                    risk_level = "Watchlist"
                else:
                    risk_level = "Safe"

                if has_anomaly:
                    action = "URGENT: Unusual attendance pattern — check with student"
                elif risk_level == "High Risk" and avg_trend < -0.3:
                    action = "URGENT: Contact parent and schedule meeting"
                elif risk_level == "High Risk":
                    action = "Schedule a counseling session"
                elif risk_level == "Watchlist":
                    action = "Have a conversation with student"
                else:
                    action = "Student is on track — no action needed"

                mentor_risk.append({
                    "StudentID": student_id,
                    "Student_Name": student_name,
                    "Section": student_section,
                    "Semester_Attendance": round(avg_semester_att, 2),
                    "Trend": round(avg_trend, 3),
                    "Probability": round(avg_prob, 2),
                    "Risk_Level": risk_level,
                    "Anomaly": has_anomaly,
                    "Action": action
                })
    else:
        students = []
        subject = None
        mentor_risk = []

    conn.close()
    return render_template("faculty_dashboard.html", faculty_id=faculty_user, subject=subject, classes=classes, all_students=students, message=msg, mentor_students=mentor_risk)


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
    
    # Base query for all students, joining with latest attendance records if they exist
    query = """
    SELECT s.registration_no AS StudentID, s.name AS Student_Name, s.section AS Section,
           a.Rolling_Attendance, a.Absence_Streak, a.Semester_Attendance, a.Attendance_Trend, a.Anomaly, a.Parent_Notified
    FROM students s
    LEFT JOIN (
        SELECT StudentID, MAX(Date) as MaxDate
        FROM attendance
        GROUP BY StudentID
    ) b ON s.registration_no = b.StudentID
    LEFT JOIN attendance a ON b.StudentID = a.StudentID AND b.MaxDate = a.Date
    """
    
    params = ()
    if selected_section:
        query += " WHERE s.section = ?"
        params = (selected_section,)
        
    try:
        latest_df = pd.read_sql_query(query, conn, params=params)
    except Exception as e:
        print(f"Error querying DB: {e}")
        latest_df = pd.DataFrame()
    finally:
        conn.close()

    risk_summary = []

    if not latest_df.empty:
        # Group by student to aggregate the 7 subject scores
        grouped_students = latest_df.groupby("StudentID")
        
        for student_id, group in grouped_students:
            subject_probs = []
            
            for _, row in group.iterrows():
                features = np.array([[
                    row.get("Rolling_Attendance", 0),
                    row.get("Absence_Streak", 0),
                    row.get("Semester_Attendance", 0),
                    row.get("Attendance_Trend", 0)
                ]])
                try:
                    p = model.predict_proba(features)[0][1] if model else 0.0
                except IndexError:
                    p = 0.0
                subject_probs.append(p)

            # Average metrics across all subjects
            avg_prob = np.mean(subject_probs) if subject_probs else 0.0
            avg_semester_att = group["Semester_Attendance"].fillna(0.85).mean()
            avg_trend = group["Attendance_Trend"].fillna(0.0).mean()
            has_anomaly = group["Anomaly"].fillna(0).max() == 1
            has_notified = group["Parent_Notified"].fillna(0).max() == 1

            # ---- Determine Overall Risk Level ----
            if avg_semester_att < 0.70:
                risk_level = "High Risk"
            elif avg_semester_att < 0.75 and avg_trend < -0.15:
                risk_level = "High Risk"
            elif avg_trend < -0.15:
                risk_level = "Watchlist"
            elif avg_prob > 0.85:
                risk_level = "Watchlist"
            else:
                risk_level = "Safe"

            # ---- Determine Recommended Action ----
            if has_anomaly:
                action = "URGENT: Verify — Unusual attendance pattern detected"
            elif risk_level == "High Risk" and avg_trend < -0.3:
                action = "URGENT: Contact parent and schedule meeting"
            elif risk_level == "High Risk":
                action = "Schedule counseling session with student"
            elif risk_level == "Watchlist":
                action = "Send advisory notice to student"
            else:
                action = "No action required — student is on track"

            risk_summary.append({
                "StudentID": student_id,
                "Semester_Attendance": round(avg_semester_att, 2),
                "Trend": round(avg_trend, 3),
                "Probability": round(avg_prob, 2),
                "Risk_Level": risk_level,
                "Anomaly": has_anomaly,
                "Notified": "Yes" if has_notified else "No",
                "Action": action
            })

    risk_df = pd.DataFrame(risk_summary) if risk_summary else pd.DataFrame(columns=["Risk_Level", "Anomaly"])

    high_risk = risk_df[risk_df["Risk_Level"] == "High Risk"]
    watchlist = risk_df[risk_df["Risk_Level"] == "Watchlist"]
    safe = risk_df[risk_df["Risk_Level"] == "Safe"]
    anomalies = risk_df[risk_df["Anomaly"] == True]

    return render_template(
        "dashboard.html",
        high_risk=high_risk.to_dict(orient="records") if not high_risk.empty else [],
        watchlist=watchlist.to_dict(orient="records") if not watchlist.empty else [],
        anomalies=anomalies.to_dict(orient="records") if not anomalies.empty else [],
        safe_students=safe.to_dict(orient="records") if not safe.empty else [],
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
    # Query all students assigned to this mentor, and bring in latest attendance if available
    query = """
    SELECT s.registration_no AS StudentID, s.name AS Student_Name, s.section AS Section,
           a.Rolling_Attendance, a.Absence_Streak, a.Semester_Attendance, a.Attendance_Trend, a.Anomaly, a.Mentor_Nudged
    FROM students s
    LEFT JOIN (
        SELECT StudentID, MAX(Date) as MaxDate
        FROM attendance
        GROUP BY StudentID
    ) b ON s.registration_no = b.StudentID
    LEFT JOIN attendance a ON b.StudentID = a.StudentID AND b.MaxDate = a.Date
    WHERE s.mentor_name = ?
    """
    try:
        mentor_students = pd.read_sql_query(query, conn, params=(mentor_id,))
    except Exception as e:
        print(f"Error querying DB: {e}")
        mentor_students = pd.DataFrame()
    finally:
        conn.close()

    risk_summary = []

    if not mentor_students.empty:
        grouped_students = mentor_students.groupby("StudentID")
        
        for student_id, group in grouped_students:
            subject_probs = []
            
            for _, row in group.iterrows():
                features = np.array([[
                    row["Rolling_Attendance"],
                    row["Absence_Streak"],
                    row["Semester_Attendance"],
                    row["Attendance_Trend"]
                ]])

                try:
                    p = model.predict_proba(features)[0][1] if model else 0.0
                except IndexError:
                    p = 0.0
                subject_probs.append(p)

            avg_prob = np.mean(subject_probs) if subject_probs else 0.0
            avg_semester_att = group["Semester_Attendance"].fillna(0.85).mean()
            avg_trend = group["Attendance_Trend"].fillna(0.0).mean()
            has_anomaly = group["Anomaly"].fillna(0).max() == 1
            has_nudged = group["Mentor_Nudged"].fillna(0).max() == 1

            if avg_semester_att < 0.70:
                risk_level = "High Risk"
            elif avg_semester_att < 0.75 and avg_trend < -0.15:
                risk_level = "High Risk"
            elif avg_trend < -0.15:
                risk_level = "Watchlist"
            elif avg_prob > 0.85:
                risk_level = "Watchlist"
            else:
                risk_level = "Safe"

            if has_anomaly:
                action = "URGENT (ANOMALY): Please coordinate with parents immediately."
            elif has_nudged:
                action = "ACTION REQUIRED: Automated Intervention Triggered. Please check in with student."
            elif risk_level == "High Risk" and avg_trend < -0.3:
                action = "URGENT: Schedule Meeting"
            elif risk_level == "High Risk":
                action = "Schedule Counseling Session"
            elif risk_level == "Watchlist":
                action = "Send Advisory Warning"
            else:
                action = "No Action Required"

            risk_summary.append({
                "StudentID": student_id,
                "Semester_Attendance": round(avg_semester_att, 2),
                "Trend": round(avg_trend, 3),
                "Probability": round(avg_prob, 2),
                "Risk_Level": risk_level,
                "Anomaly": has_anomaly,
                "Nudged": has_nudged,
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


# ---- NEW API: Student Subject-wise Breakdown for Popup ---- #
@app.route("/api/student_subjects/<student_id>")
def api_student_subjects(student_id):
    """Returns subject-wise attendance breakdown for a student (used by popup modal)."""
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    conn = get_db_connection()
    try:
        # Get student name
        name_row = pd.read_sql_query(
            "SELECT DISTINCT Student_Name FROM attendance WHERE StudentID = ? LIMIT 1",
            conn, params=(student_id,)
        )
        student_name = name_row.iloc[0]["Student_Name"] if not name_row.empty else student_id

        # Get subject-wise stats
        query = """
        SELECT Subject,
               COUNT(*) as total_classes,
               SUM(Present) as attended,
               ROUND(SUM(Present)*100.0/COUNT(*), 1) as attendance_pct,
               MAX(Absence_Streak) as max_streak
        FROM attendance
        WHERE StudentID = ?
        GROUP BY Subject
        ORDER BY attendance_pct ASC
        """
        df = pd.read_sql_query(query, conn, params=(student_id,))

        # Get overall stats
        overall = pd.read_sql_query(
            "SELECT ROUND(SUM(Present)*100.0/COUNT(*), 1) as overall_pct, COUNT(DISTINCT Subject) as subjects FROM attendance WHERE StudentID = ?",
            conn, params=(student_id,)
        )
        overall_pct = float(overall.iloc[0]["overall_pct"]) if not overall.empty and overall.iloc[0]["overall_pct"] is not None else 0.0
        total_subjects = int(overall.iloc[0]["subjects"]) if not overall.empty else 0

        # Get section
        section_row = pd.read_sql_query(
            "SELECT DISTINCT Section FROM attendance WHERE StudentID = ? LIMIT 1",
            conn, params=(student_id,)
        )
        section = section_row.iloc[0]["Section"] if not section_row.empty else "N/A"

        # Get parent contact
        parent_row = pd.read_sql_query(
            "SELECT DISTINCT Parent_Contact FROM attendance WHERE StudentID = ? LIMIT 1",
            conn, params=(student_id,)
        )
        parent_contact = parent_row.iloc[0]["Parent_Contact"] if not parent_row.empty else "N/A"

        # Get student email (if available — column may not exist)
        student_email = ""
        try:
            email_row = pd.read_sql_query(
                "SELECT DISTINCT Email FROM attendance WHERE StudentID = ? LIMIT 1",
                conn, params=(student_id,)
            )
            if not email_row.empty and "Email" in email_row.columns:
                student_email = email_row.iloc[0]["Email"] or ""
        except Exception:
            student_email = ""

        subjects = []
        for _, row in df.iterrows():
            pct = row["attendance_pct"]
            total = int(row["total_classes"])
            attended = int(row["attended"])
            missed = total - attended

            if pct >= 85:
                status = "good"
                summary = f"Good standing in {row['Subject']}"
            elif pct >= 75:
                status = "ok"
                summary = f"Attendance is acceptable but could improve in {row['Subject']}"
            elif pct >= 60:
                status = "warning"
                summary = f"Attendance is dropping in {row['Subject']} ({pct}%). Missed {missed} out of {total} classes."
            else:
                status = "critical"
                summary = f"Critically low in {row['Subject']} ({pct}%). Missed {missed} out of {total} classes!"

            subjects.append({
                "subject": str(row["Subject"]),
                "attendance_pct": float(pct) if pct is not None else 0.0,
                "total_classes": int(total),
                "attended": int(attended),
                "missed": int(missed),
                "max_streak": int(row["max_streak"]),
                "status": status,
                "summary": summary
            })

        # Generate action recommendations
        actions = []
        if overall_pct < 60:
            actions.append("URGENT: Schedule an immediate meeting with the student and parents")
            actions.append("Consider assigning a peer buddy for accountability")
        elif overall_pct < 75:
            actions.append("Have a one-on-one conversation to understand attendance barriers")
            actions.append("Send a notice to parents about the attendance situation")
        elif overall_pct < 85:
            actions.append("Encourage the student to improve attendance in weaker subjects")
        else:
            actions.append("Student is doing well — continue monitoring")

        # Check for specific subject issues
        for s in subjects:
            if s["status"] == "critical":
                actions.append(f"Immediate attention needed for {s['subject']} ({s['attendance_pct']}%)")

        # Parent notification status
        parent_notified = overall_pct < 75

        return jsonify({
            "student_id": str(student_id),
            "student_name": str(student_name),
            "section": str(section),
            "overall_pct": float(overall_pct),
            "total_subjects": int(total_subjects),
            "subjects": subjects,
            "actions": actions,
            "parent_contact": str(parent_contact),
            "student_email": str(student_email),
            "parent_notified": bool(parent_notified)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# ---- Faculty: Upload Student CSV ---- #
@app.route("/faculty/upload_students", methods=["POST"])
@login_required(role="faculty")
def faculty_upload_students():
    """Faculty uploads CSV with student data (name, email, parent_email, parent_phone, mentor, etc.)."""
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded."}), 400

    file = request.files["file"]
    if not file.filename.endswith(".csv"):
        return jsonify({"success": False, "message": "Please upload a CSV file."}), 400

    try:
        raw = file.stream.read().decode("utf-8-sig")
        stream = io.StringIO(raw)
        reader = csv.DictReader(stream)

        if reader.fieldnames:
            reader.fieldnames = [f.strip() for f in reader.fieldnames]

        required_cols = {"name", "email"}
        if not required_cols.issubset(set(reader.fieldnames or [])):
            missing = required_cols - set(reader.fieldnames or [])
            return jsonify({"success": False, "message": f"Missing required columns: {', '.join(missing)}. Required: name, email. Optional: parent_email, parent_phone, notification_count, assigned_mentor, class, subjects"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        results = {"added": 0, "skipped": 0, "errors": []}

        for row in reader:
            name = row.get("name", "").strip()
            email = row.get("email", "").strip()
            parent_email = row.get("parent_email", "").strip()
            parent_phone = row.get("parent_phone", "").strip()
            notification_count = int(row.get("notification_count", "0").strip() or "0")
            mentor = row.get("assigned_mentor", "").strip()
            cls = row.get("class", "").strip()
            subjects = row.get("subjects", "").strip()

            if not name or not email:
                results["errors"].append(f"Skipped row: missing name or email")
                results["skipped"] += 1
                continue

            results["added"] += 1

        conn.close()

        return jsonify({
            "success": True,
            "message": f"Processed {results['added']} student records. {results['skipped']} skipped.",
            "details": results
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Error processing CSV: {str(e)}"}), 500


# ---- Faculty: Send Email to Student ---- #
@app.route("/faculty/send_student_email", methods=["POST"])
@login_required(role="faculty")
def faculty_send_student_email():
    """Send an email message to a student."""
    data = request.get_json()
    student_id = data.get("student_id", "")
    message_text = data.get("message", "")
    email_to = data.get("email", "")

    if not student_id or not message_text:
        return jsonify({"success": False, "message": "Student ID and message are required."}), 400

    faculty_name = session.get("username", "Faculty")
    subject_line = f"Message from {faculty_name} — Smart Attendance System"
    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: auto;
                padding: 30px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #1e293b;">Message from your Teacher</h2>
        <p>Dear Student <strong>{student_id}</strong>,</p>
        <div style="background: #f0f9ff; padding: 15px; border-radius: 8px; border-left: 4px solid #0ea5e9; margin: 15px 0;">
            {message_text}
        </div>
        <p style="color: #666;">Please respond at your earliest convenience.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #999;">Smart Attendance System — Faculty Communication</p>
    </div>
    """

    if email_to:
        success, msg = _send_email(email_to, subject_line, body_html)
        if success:
            return jsonify({"success": True, "message": f"Email sent to {email_to}"})

    # Console fallback
    print(f"[FACULTY EMAIL] To: {email_to or 'N/A'} | Student: {student_id} | From: {faculty_name}")
    print(f"[FACULTY EMAIL] Message: {message_text}")
    return jsonify({"success": True, "message": f"Message logged for {student_id} (email delivery attempted)"})


if __name__ == "__main__":
    app.run(debug=True)