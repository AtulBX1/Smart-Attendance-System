"""
Email utility for sending OTP codes to faculty/mentors.
Reads SMTP settings from the database. Falls back to console output when SMTP is not configured.
"""

import os
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

base_dir = os.path.dirname(os.path.dirname(__file__))


def get_smtp_config():
    """Read SMTP settings from the smtp_config table in the database."""
    db_path = os.path.join(base_dir, "attendance_system.db")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM smtp_config WHERE id = 1").fetchone()
        conn.close()
        if row and row["smtp_host"] and row["smtp_user"] and row["smtp_pass"]:
            return {
                "host": row["smtp_host"],
                "port": row["smtp_port"] or 587,
                "user": row["smtp_user"],
                "pass": row["smtp_pass"],
            }
    except Exception as e:
        print(f"[SMTP CONFIG] Could not read from DB: {e}")
    return None


def _send_email(to_email, subject, body_html, smtp_cfg=None):
    """
    Send an HTML email via SMTP. Falls back to console when SMTP is not configured.
    Returns: (success: bool, message: str)
    """
    if smtp_cfg is None:
        smtp_cfg = get_smtp_config()

    if smtp_cfg:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = smtp_cfg["user"]
            msg["To"] = to_email
            msg.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"]) as server:
                server.starttls()
                server.login(smtp_cfg["user"], smtp_cfg["pass"])
                server.sendmail(smtp_cfg["user"], to_email, msg.as_string())

            return True, f"Email sent to {to_email}"
        except Exception as e:
            print(f"[EMAIL ERROR] Failed to send to {to_email}: {e}")
            return False, f"SMTP error: {e}"
    else:
        return False, "SMTP not configured"


def send_otp_email(to_email, otp_code, username):
    """
    Send a login OTP email. Falls back to console when SMTP is not configured.
    Returns: (success: bool, message: str)
    """
    subject = "Your Login OTP – Smart Attendance System"
    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: auto;
                padding: 30px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #1e293b; text-align: center;">Smart Attendance System</h2>
        <p>Hello <strong>{username}</strong>,</p>
        <p>Your one-time login code is:</p>
        <div style="text-align: center; margin: 25px 0;">
            <span style="font-size: 32px; letter-spacing: 6px; font-weight: bold;
                         color: #4CAF50; background: #e8f5e9; padding: 12px 24px;
                         border-radius: 8px;">{otp_code}</span>
        </div>
        <p style="color: #666;">This code is valid for <strong>10 minutes</strong>.
           Do not share it with anyone.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #999; text-align: center;">
            If you did not request this code, please contact your administrator.
        </p>
    </div>
    """

    smtp_cfg = get_smtp_config()
    if smtp_cfg:
        success, msg = _send_email(to_email, subject, body_html, smtp_cfg)
        if success:
            return True, msg
        # If SMTP failed, fall through to console
        print(f"[EMAIL] SMTP failed, using console fallback: {msg}")

    return _console_fallback(to_email, otp_code, username)


def send_welcome_email(to_email, full_name, username, otp_code):
    """
    Send a welcome email with login credentials when a faculty account is created.
    Falls back to console when SMTP is not configured.
    Returns: (success: bool, message: str)
    """
    subject = "Welcome to Smart Attendance System – Your Login Credentials"
    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: auto;
                padding: 30px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #1e293b; text-align: center;">🎓 Smart Attendance System</h2>
        <p>Dear <strong>{full_name}</strong>,</p>
        <p>Your faculty account has been created. Here are your login details:</p>
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <tr style="background: #f8fafc;">
                <td style="padding: 10px 15px; border: 1px solid #e2e8f0; font-weight: bold; color: #475569;">Username</td>
                <td style="padding: 10px 15px; border: 1px solid #e2e8f0; font-family: monospace; font-size: 16px;">{username}</td>
            </tr>
            <tr>
                <td style="padding: 10px 15px; border: 1px solid #e2e8f0; font-weight: bold; color: #475569;">Login OTP</td>
                <td style="padding: 10px 15px; border: 1px solid #e2e8f0;">
                    <span style="font-size: 24px; letter-spacing: 4px; font-weight: bold;
                                 color: #4CAF50; background: #e8f5e9; padding: 6px 14px;
                                 border-radius: 6px;">{otp_code}</span>
                </td>
            </tr>
        </table>
        <p style="color: #666;">
            <strong>How to login:</strong><br>
            1. Go to the login page<br>
            2. Enter your username: <code>{username}</code><br>
            3. Enter the OTP above<br>
            4. This OTP is valid for <strong>10 minutes</strong>
        </p>
        <p style="color: #999; font-size: 13px;">
            After the OTP expires, ask your admin to resend a new one from the Manage Users page.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #999; text-align: center;">
            Smart Attendance System — Automated Faculty Onboarding
        </p>
    </div>
    """

    smtp_cfg = get_smtp_config()
    if smtp_cfg:
        success, msg = _send_email(to_email, subject, body_html, smtp_cfg)
        if success:
            return True, msg
        print(f"[EMAIL] SMTP failed, using console fallback: {msg}")

    return _console_fallback_welcome(to_email, full_name, username, otp_code)


def test_smtp_connection(host, port, user, password):
    """Test SMTP connection with given settings. Returns (success, message)."""
    try:
        with smtplib.SMTP(host, int(port)) as server:
            server.starttls()
            server.login(user, password)
        return True, "SMTP connection successful!"
    except Exception as e:
        return False, f"Connection failed: {e}"


def _console_fallback(to_email, otp_code, username):
    """Print OTP to console when SMTP is not configured."""
    print("=" * 60)
    print("  📧  EMAIL OTP (Console Fallback — SMTP not configured)")
    print("=" * 60)
    print(f"  To:       {to_email}")
    print(f"  User:     {username}")
    print(f"  OTP Code: {otp_code}")
    print(f"  Expires:  10 minutes")
    print("=" * 60)
    return True, f"OTP printed to console (SMTP not configured). Code: {otp_code}"


def _console_fallback_welcome(to_email, full_name, username, otp_code):
    """Print welcome email to console when SMTP is not configured."""
    print("=" * 60)
    print("  📧  WELCOME EMAIL (Console Fallback — SMTP not configured)")
    print("=" * 60)
    print(f"  To:       {to_email}")
    print(f"  Name:     {full_name}")
    print(f"  Username: {username}")
    print(f"  OTP Code: {otp_code}")
    print(f"  Expires:  10 minutes")
    print("=" * 60)
    return True, f"Welcome email printed to console. Username: {username}, OTP: {otp_code}"
