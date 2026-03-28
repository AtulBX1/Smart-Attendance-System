import re

with open(r"d:\Semester4\CSE274\Smart-Attendance-System\backend\templates\faculty_dashboard.html", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Replace the entire CSS Block between <style> and </style>
new_css = """
        :root {
            --bg: #000000;
            --surface: #121212;
            --border: #1e1e1e;
            --text: #ffffff;
            --text-muted: #888888; 
            --primary: #8b5cf6;
            --secondary: #3b82f6;
            --red: #ff453a; --yellow: #ff9f0a; --green: #32d74b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
        body { background: var(--bg); color: var(--text); display: flex; height: 100vh; overflow: hidden; letter-spacing: -0.01em; }
        
        /* Layout Framework */
        .sidebar { width: 260px; background: var(--surface); border-right: 1px solid var(--border); padding: 2rem 1.5rem; display: flex; flex-direction: column; z-index: 10; }
        .sidebar-brand { font-size: 1.2rem; font-weight: 700; color: var(--text); margin-bottom: 2.5rem; display: flex; align-items: center; gap: 12px; }
        .sidebar-brand-icon { width: 32px; height: 32px; border-radius: 8px; background: var(--primary); display: inline-block; }
        .nav-item { display: flex; align-items: center; gap: 14px; padding: 12px 18px; border-radius: 8px; color: var(--text-muted); text-decoration: none; margin-bottom: 0.5rem; font-weight: 600; font-size: 0.95rem; transition: filter 0.2s ease, color 0.2s ease; cursor: pointer; border: 1px solid transparent; background: transparent; }
        .nav-item:hover { color: var(--text); filter: brightness(1.2); }
        .nav-item.active { background: var(--primary); color: #fff; }
        .sidebar-bottom { margin-top: auto; display: flex; align-items: center; gap: 12px; padding-top: 1.5rem; border-top: 1px solid var(--border); }
        .avatar { width: 40px; height: 40px; border-radius: 50%; background: var(--primary); display: flex; align-items: center; justify-content: center; color: #fff; font-weight: bold; font-size: 1.1rem; }
        
        .main-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: var(--bg); position: relative; }
        .navbar { display: flex; justify-content: space-between; align-items: center; padding: 1.25rem 2.5rem; border-bottom: 1px solid var(--border); background: var(--surface); z-index: 5; }
        .content-wrap { padding: 3rem; overflow-y: auto; flex: 1; }
        
        /* Components */
        .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 2rem; text-align: left; cursor: pointer; transition: filter 0.2s ease, border-color 0.2s; position: relative; overflow: hidden; }
        .card:hover { filter: brightness(1.2); border-color: #333; }
        .card.active { border: 1px solid var(--primary); }
        .card h3 { font-size: 1.15rem; color: var(--text); font-weight: 700; margin-bottom: 6px; }
        .card p { font-size: 0.9rem; color: var(--text-muted); font-weight: 500; }
        
        /* Attendance List & Radios */
        .attendance-form { display: none; background: var(--surface); padding: 2.5rem; border-radius: 12px; border: 1px solid var(--border); margin-top: 2rem; animation: fadeIn 0.4s ease; }
        .attendance-form.active { display: block; }
        .student-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-radius: 8px; border: 1px solid transparent; transition: filter 0.2s ease, border-color 0.2s; margin-bottom: 10px; background: #0a0a0a; }
        .student-row:nth-child(even) { background: #121212; }
        .student-row:hover { filter: brightness(1.2); border: 1px solid var(--border); }
        .student-name { font-weight: 600; color: #fff; font-size: 1rem; }
        .student-id { font-size: 0.85rem; color: var(--text-muted); display: block; margin-top: 4px; font-weight: 500; }
        
        .radio-group { display: flex; gap: 8px; }
        .radio-group label { cursor: pointer; padding: 8px 20px; border-radius: 6px; border: 1px solid var(--border); font-size: 0.85rem; font-weight: 600; color: var(--text-muted); transition: filter 0.2s ease; background: #0a0a0a; }
        .radio-group input[type="radio"] { display: none; }
        .radio-group input[type="radio"]:checked+label { border-color: transparent; }
        .radio-group input[type="radio"]:checked+label.p-label { background: var(--green); color: #000 !important; font-weight: 700 !important; }
        .radio-group input[type="radio"]:checked+label.a-label { background: var(--red); color: #000 !important; font-weight: 700 !important; }
        
        .btn-submit { background: var(--primary); color: #fff; border: none; padding: 14px 28px; border-radius: 8px; cursor: pointer; font-size: 1.05rem; font-weight: 700; width: 100%; margin-top: 2rem; transition: filter 0.2s ease; }
        .btn-submit:hover { filter: brightness(1.2); }
        
        /* Mentee Tracking */
        .summary-row { display: flex; gap: 1.25rem; margin-bottom: 2rem; flex-wrap: wrap; }
        .summary-card { border-radius: 12px; padding: 1.5rem; flex: 1; min-width: 150px; text-align: center; cursor: pointer; transition: filter 0.2s ease, border-color 0.2s; border: 1px solid var(--border); background: var(--surface); overflow: hidden; }
        .summary-card:hover { filter: brightness(1.2); border-color: #333; }
        .summary-card .count { font-size: 2.25rem; font-weight: 800; color: #fff; letter-spacing: -0.05em; }
        .summary-card .label { font-size: 0.85rem; margin-top: 6px; font-weight: 600; color: var(--text-muted); letter-spacing: 0.05em; }
        
        .risk-pills { display: flex; gap: 10px; margin-bottom: 2rem; flex-wrap: wrap; }
        .risk-pill { padding: 8px 20px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; cursor: pointer; border: 1px solid var(--border); background: var(--surface); color: var(--text-muted); transition: filter 0.2s ease; }
        .risk-pill:hover { filter: brightness(1.5); color: #fff; }
        .risk-pill.active { background: var(--primary); color: #fff; border: 1px solid var(--primary); }
        
        table { width: 100%; border-collapse: separate; border-spacing: 0 4px; text-align: left; }
        th { padding: 12px 20px; color: var(--text-muted); font-size: 0.75rem; letter-spacing: 0.05em; border: none; font-weight: 700; text-transform: uppercase; }
        td { padding: 16px 20px; font-size: 0.95rem; font-weight: 500; border: none; background: var(--surface); transition: filter 0.2s ease; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); color: #fff; }
        td:first-child { border-left: 1px solid var(--border); border-top-left-radius: 6px; border-bottom-left-radius: 6px; }
        td:last-child { border-right: 1px solid var(--border); border-top-right-radius: 6px; border-bottom-right-radius: 6px; }
        tr:hover td { filter: brightness(1.2); border-color: #333; }
        .clickable-name { color: var(--primary); cursor: pointer; font-weight: 600; text-decoration: none; display: inline-block; padding: 2px 0; transition: filter 0.2s; } .clickable-name:hover { filter: brightness(1.2); }
        
        .risk-badge { padding: 6px 14px; border-radius: 6px; font-size: 0.8rem; font-weight: 700; display: inline-block; border: none; }
        .badge-safe { background: #0a3d1b; color: var(--green); }
        .badge-watch { background: #3d2906; color: var(--yellow); }
        .badge-critical { background: #3d0e11; color: var(--red); }
        
        /* Modals */
        .modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 1000; justify-content: center; align-items: center; }
        .modal { background: var(--surface); padding: 2.5rem; border-radius: 12px; border: 1px solid var(--border); width: 480px; max-width: 90%; max-height: 90vh; overflow-y: auto; animation: scaleUp 0.15s ease-out; }
        .modal h3 { margin-bottom: 1.5rem; color: #fff; border-bottom: 1px solid var(--border); padding-bottom: 1rem; font-weight: 700; font-size: 1.25rem; }
        .modal ul { list-style: none; padding: 0; max-height: 150px; overflow-y: auto; color: var(--red); font-size: 0.9rem; background: #260a0a; padding: 16px; border-radius: 8px; border: 1px solid #3d0e11; font-weight: 500; }
        .modal ul li { padding: 6px 0; border-bottom: 1px solid #3d0e11; } .modal ul li:last-child { border-bottom: none; }
        .modal-input-group { margin-top: 1.5rem; display: flex; flex-direction: column; }
        .modal-input-group label { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 8px; font-weight: 600; letter-spacing: 0.05em; }
        .modal-input-group input { background: #000; color: #fff; border: 1px solid var(--border); padding: 12px 16px; border-radius: 6px; font-size: 1rem; font-weight: 500; outline: none; transition: border 0.2s ease; }
        .modal-input-group input:focus { border-color: var(--primary); }
        .modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 2rem; }
        
        @keyframes scaleUp { from { transform: scale(0.98); opacity: 0; } to { transform: scale(1); opacity: 1; } }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        
        /* Student Details Popup */
        .popup-modal { background: var(--surface); border-radius: 12px; border: 1px solid var(--border); width: 800px; max-width: 95%; max-height: 85vh; overflow-y: auto; position: relative; margin: auto; margin-top: 5vh; animation: scaleUp 0.15s ease-out; }
        .popup-header { display: flex; justify-content: space-between; align-items: center; padding: 2rem 2.5rem; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--surface); z-index: 10; }
        .popup-header h3 { font-size: 1.35rem; color: #fff; font-weight: 800; }
        .popup-close { background: none; border: none; color: var(--text-muted); font-size: 2rem; cursor: pointer; transition: color 0.2s ease; line-height: 1; margin-top: -4px; } .popup-close:hover { color: #fff; }
        .popup-body { padding: 2.5rem; }
        .popup-stat-row { display: flex; gap: 1.5rem; margin-bottom: 2rem; flex-wrap: wrap; }
        .popup-stat { flex: 1; min-width: 120px; background: #0a0a0a; border-radius: 8px; padding: 1.5rem; text-align: center; border: 1px solid var(--border); }
        .popup-stat .big { font-size: 2rem; font-weight: 800; color: var(--primary); letter-spacing: -0.05em; } .popup-stat .small { font-size: 0.8rem; color: var(--text-muted); margin-top: 6px; font-weight: 600; letter-spacing: 0.05em; }
        .subject-bar { display: flex; align-items: center; gap: 16px; padding: 16px 20px; background: #0a0a0a; border-radius: 8px; margin-bottom: 10px; border: 1px solid var(--border); }
        .subject-name { width: 140px; font-size: 0.95rem; font-weight: 700; color: #fff; }
        .bar-container { flex: 1; background: #1a1a1a; border-radius: 4px; height: 14px; overflow: hidden; }
        .bar-fill { height: 100%; transition: width 0.5s ease-out; background: var(--primary); }
        .action-item { padding: 12px 16px; background: #16102b; border-left: 4px solid var(--primary); border-radius: 4px; margin-bottom: 12px; font-size: 0.9rem; color: var(--primary); font-weight: 600; }
        .popup-btn { padding: 12px 24px; border-radius: 6px; font-size: 0.9rem; font-weight: 700; cursor: pointer; border: none; transition: filter 0.2s ease; } .popup-btn:hover { filter: brightness(1.2); }
        .btn-email { background: var(--secondary); color: #fff; }
        .btn-meeting { background: var(--primary); color: #fff; }
        
        .email-compose { display: none; margin-top: 1.5rem; padding: 2rem; background: #0a0a0a; border-radius: 8px; border: 1px solid var(--border); animation: fadeIn 0.2s ease; }
        .email-compose.active { display: block; }
        .email-compose textarea { width: 100%; height: 120px; background: #000; color: #fff; border: 1px solid var(--border); border-radius: 6px; padding: 16px; font-size: 0.95rem; resize: vertical; outline: none; margin-bottom: 16px; font-weight: 500; transition: border 0.2s ease; }
        .email-compose textarea:focus { border-color: var(--primary); }
        
        .alert { padding: 1.25rem 1.5rem; border-radius: 8px; margin-bottom: 2rem; font-weight: 700; background: #0a3d1b; border: 1px solid #10b981; color: var(--green); display: flex; align-items: center; gap: 12px; }
"""

# Extract the CSS block
head, css_and_body = text.split("<style>", 1)
old_css, body = css_and_body.split("</style>", 1)

# Replace the old Glassmorphism hardcoded CSS
new_text = head + "<style>\n" + new_css + "    </style>" + body

# 2. Fix the hardcoded inline styles in the HTML (The weekly schedule cards and input labels from Glassmorphism)
new_text = new_text.replace(
    'style="background: var(--glass-bg); backdrop-filter: blur(12px); border: 1px solid var(--glass-border); border-radius: 12px; overflow: hidden; box-shadow: 0 8px 32px rgba(0,0,0,0.2);"',
    'style="background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden;"'
)
new_text = new_text.replace(
    'style="background: rgba(0,0,0,0.3); padding: 8px; text-align: center; font-size: 0.75rem; font-weight: 700; color: var(--text-muted); border-bottom: 1px solid var(--glass-border); text-transform: uppercase;"',
    'style="background: #1a1a1a; padding: 8px; text-align: center; font-size: 0.75rem; font-weight: 700; color: var(--text-muted); border-bottom: 1px solid var(--border); text-transform: uppercase;"'
)
new_text = new_text.replace(
    'style="background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border); border-radius: 8px; padding: 8px; position: relative; transition: all 0.3s ease; cursor: pointer;" onmouseover="this.style.transform=\'translateY(-2px)\'; this.style.boxShadow=\'var(--glow-sm)\'" onmouseout="this.style.transform=\'none\'; this.style.boxShadow=\'none\'"',
    'style="background: #0a0a0a; border: 1px solid var(--border); border-radius: 6px; padding: 8px; position: relative; transition: filter 0.2s ease; cursor: pointer;" onmouseover="this.style.filter=\'brightness(1.5)\'" onmouseout="this.style.filter=\'none\'"'
)
new_text = new_text.replace(
    'style="background: var(--glass-bg); backdrop-filter: blur(12px); border: 1px dashed var(--glass-border); border-radius: 12px; padding: 2rem; text-align: center; margin-bottom: 2.5rem; color: var(--text-muted);"',
    'style="background: var(--surface); border: 1px dashed var(--border); border-radius: 8px; padding: 2rem; text-align: center; margin-bottom: 2.5rem; color: var(--text-muted);"'
)
new_text = new_text.replace(
    'style="background: rgba(0,0,0,0.2); border: 1px solid var(--glass-border); border-radius: 30px; padding: 6px 16px; display: flex; align-items: center; gap: 10px;"',
    'style="background: #000; border: 1px solid var(--border); border-radius: 20px; padding: 6px 16px; display: flex; align-items: center; gap: 10px;"'
)

with open(r"d:\Semester4\CSE274\Smart-Attendance-System\backend\templates\faculty_dashboard.html", "w", encoding="utf-8") as f:
    f.write(new_text)

print("AMOLED transformation complete.")
