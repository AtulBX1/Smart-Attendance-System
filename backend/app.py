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
from utils.email_sender import send_otp_email, send_welcome_email, test_smtp_connection, get_smtp_config
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
        msg = f"Successfully marked attendance for {success_count} students in Section {section} for {subject}."
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
        
        # We query the distinct students using a subquery that finds their latest record structure for this Subject
        students_query = f"""
        SELECT a.StudentID, a.Student_Name, a.Section 
        FROM attendance a
        INNER JOIN (
            SELECT StudentID, MAX(Date) as MaxDate
            FROM attendance
            WHERE Section IN ({placeholders}) AND Subject = ?
            GROUP BY StudentID
        ) b ON a.StudentID = b.StudentID AND a.Date = b.MaxDate
        WHERE a.Subject = ?
        ORDER BY a.StudentID ASC
        """
        params = list(sections) + [subject, subject]
        students_df = pd.read_sql_query(students_query, conn, params=params)
        students = students_df.to_dict(orient="records")

        # ---- Mentor View: Compute risk summary for students in these sections ----
        mentor_query = f"""
        SELECT a.*
        FROM attendance a
        INNER JOIN (
            SELECT StudentID, Subject, MAX(Date) as MaxDate
            FROM attendance
            WHERE Section IN ({placeholders})
            GROUP BY StudentID, Subject
        ) b ON a.StudentID = b.StudentID AND a.Subject = b.Subject AND a.Date = b.MaxDate
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

                avg_prob = np.mean(subject_probs)
                avg_semester_att = group["Semester_Attendance"].mean()
                avg_trend = group["Attendance_Trend"].mean()
                has_anomaly = group["Anomaly"].max() == 1
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
                    action = "URGENT (ANOMALY): Verify Medical/Emergency"
                elif risk_level == "High Risk" and avg_trend < -0.3:
                    action = "URGENT: Contact Parent + Meeting"
                elif risk_level == "High Risk":
                    action = "Schedule Counseling Session"
                elif risk_level == "Watchlist":
                    action = "Send Advisory Warning"
                else:
                    action = "No Action Required"

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
    
    # Base query for latest records per student (now 7 records per student, 1 for each subject)
    query = """
    SELECT a.*
    FROM attendance a
    INNER JOIN (
        SELECT StudentID, Subject, MAX(Date) as MaxDate
        FROM attendance
        GROUP BY StudentID, Subject
    ) b ON a.StudentID = b.StudentID AND a.Subject = b.Subject AND a.Date = b.MaxDate
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

            # Average metrics across all 7 subjects
            avg_prob = np.mean(subject_probs)
            avg_semester_att = group["Semester_Attendance"].mean()
            avg_trend = group["Attendance_Trend"].mean()
            has_anomaly = group["Anomaly"].max() == 1
            has_notified = group["Parent_Notified"].max() == 1

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
                action = "URGENT (ANOMALY): Verify Medical/Emergency"
            elif risk_level == "High Risk" and avg_trend < -0.3:
                action = "URGENT: Contact Parent + Mentor Meeting"
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
        SELECT StudentID, Subject, MAX(Date) as MaxDate
        FROM attendance
        WHERE MentorID = ?
        GROUP BY StudentID, Subject
    ) b ON a.StudentID = b.StudentID AND a.Subject = b.Subject AND a.Date = b.MaxDate
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

            avg_prob = np.mean(subject_probs)
            avg_semester_att = group["Semester_Attendance"].mean()
            avg_trend = group["Attendance_Trend"].mean()
            has_anomaly = group["Anomaly"].max() == 1
            has_nudged = group["Mentor_Nudged"].max() == 1

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

if __name__ == "__main__":
    app.run(debug=True)