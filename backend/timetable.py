"""
timetable.py
Flask Blueprint for the Master Timetable feature.
Routes: upload page, generate, view, download CSV per section.
"""

import os
import sys
import csv
import io
import sqlite3
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, session

# Resolve base directory
base_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(__file__))

from timetable_generator import (
    generate_master_timetable,
    build_teacher_view,
    DAYS,
    SLOTS,
)

timetable_bp = Blueprint("timetable", __name__, url_prefix="/timetable")


def _get_db():
    db_path = os.path.join(base_dir, "attendance_system.db")
    return sqlite3.connect(db_path)


# ---- helper: require admin login ---- #
def _require_admin(fn):
    import functools

    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        if "user_id" not in session or session.get("role") != "admin":
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapped


# -----------------------------------------------------------------------
# GET /timetable/  — upload page
# -----------------------------------------------------------------------
@timetable_bp.route("/")
@_require_admin
def index():
    conn = _get_db()
    credits_df = pd.read_sql_query("SELECT * FROM subject_credits", conn)
    conn.close()
    
    credits_data = credits_df.to_dict(orient="records") if not credits_df.empty else []
    return render_template("timetable/index.html", credits_data=credits_data)

# -----------------------------------------------------------------------
# POST /timetable/upload_credits  — subject credits upload
# -----------------------------------------------------------------------
@timetable_bp.route("/upload_credits", methods=["POST"])
@_require_admin
def upload_credits():
    if "file" not in request.files:
        flash("❌ No file uploaded.")
        return redirect(url_for("timetable.index"))

    file = request.files["file"]
    if not file.filename.endswith(".csv"):
        flash("❌ Please upload a CSV file.")
        return redirect(url_for("timetable.index"))

    try:
        raw = file.stream.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(raw))
        if reader.fieldnames:
            reader.fieldnames = [f.strip() for f in reader.fieldnames]

        required = {"subject", "credits"}
        if not required.issubset(set(reader.fieldnames or [])):
            flash(f"❌ Missing columns. Required: subject, credits.")
            return redirect(url_for("timetable.index"))

        conn = _get_db()
        cursor = conn.cursor()
        
        # We can either replace all or update. Let's replace all for a clean slate
        cursor.execute("DELETE FROM subject_credits")
        
        count = 0
        for row in reader:
            subj = row["subject"].strip()
            # Default to 3 credits if missing or invalid
            try:
                c_val = int(row["credits"].strip())
            except ValueError:
                c_val = 3
                
            cursor.execute(
                "INSERT INTO subject_credits (subject, credits) VALUES (?, ?)", 
                (subj, c_val)
            )
            count += 1
            
        conn.commit()
        conn.close()
        flash(f"✅ Successfully uploaded and mapped {count} subject credits.")
    except Exception as e:
        flash(f"❌ Error uploading credits: {str(e)}")

    return redirect(url_for("timetable.index"))


# -----------------------------------------------------------------------
# POST /timetable/generate  — run scheduler, show results
# -----------------------------------------------------------------------
@timetable_bp.route("/generate", methods=["POST"])
@_require_admin
def generate():
    try:
        conn = _get_db()
        timetables = generate_master_timetable(conn)
        teacher_view = build_teacher_view(conn)
        conn.close()

        sections = sorted(timetables.keys())
        return render_template(
            "timetable/result.html",
            timetables=timetables,
            teacher_view=teacher_view,
            sections=sections,
            days=DAYS,
            slots=SLOTS,
        )
    except Exception as e:
        flash(f"❌ Timetable Generation Error: {str(e)}")
        return redirect(url_for("timetable.index"))


# -----------------------------------------------------------------------
# GET /timetable/view  — view last-generated timetable from DB
# -----------------------------------------------------------------------
@timetable_bp.route("/view")
@_require_admin
def view():
    conn = _get_db()

    tt_df = pd.read_sql_query("SELECT * FROM master_timetable", conn)
    if tt_df.empty:
        conn.close()
        flash("⚠️ No timetable found. Please generate one first.")
        return redirect(url_for("timetable.index"))

    # Rebuild the timetable dict from DB rows
    timetables = {}
    for _, row in tt_df.iterrows():
        sec = row["section"]
        day = row["day_of_week"]
        slot = row["time_slot"]
        timetables.setdefault(sec, {}).setdefault(day, {})[slot] = {
            "subject": row["subject"],
            "teacher": row["teacher"],
        }

    teacher_view = build_teacher_view(conn)
    conn.close()
    sections = sorted(timetables.keys())

    return render_template(
        "timetable/result.html",
        timetables=timetables,
        teacher_view=teacher_view,
        sections=sections,
        days=DAYS,
        slots=SLOTS,
    )


# -----------------------------------------------------------------------
# GET /timetable/download/section/<section>  — CSV download
# -----------------------------------------------------------------------
@timetable_bp.route("/download/section/<section>")
@_require_admin
def download_section(section):
    conn = _get_db()
    tt_df = pd.read_sql_query(
        "SELECT * FROM master_timetable WHERE section = ?",
        conn,
        params=(section,),
    )
    conn.close()

    if tt_df.empty:
        flash(f"⚠️ No timetable data for Section {section}.")
        return redirect(url_for("timetable.view"))

    # Build grid: rows = slots, cols = days
    output = io.StringIO()
    writer = csv.writer(output)

    header = ["Time Slot"] + DAYS
    writer.writerow(header)

    for slot in SLOTS:
        row = [slot]
        for day in DAYS:
            match = tt_df[(tt_df["time_slot"] == slot) & (tt_df["day_of_week"] == day)]
            if not match.empty:
                subj = match.iloc[0]["subject"]
                teacher = match.iloc[0]["teacher"]
                row.append(f"{subj} ({teacher})")
            else:
                row.append("—")
        writer.writerow(row)

    csv_bytes = output.getvalue()
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=timetable_section_{section}.csv"
        },
    )
