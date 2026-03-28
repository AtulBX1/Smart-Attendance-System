import re

with open(r"d:\Semester4\CSE274\Smart-Attendance-System\backend\templates\faculty_dashboard.html", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Replace the entire CSS Block between <style> and </style>
new_css = """
        :root {
            --bg-gradient: linear-gradient(135deg, #0f172a, #2e1065, #000000);
            --glass-bg: rgba(255, 255, 255, 0.03);
            --glass-border: rgba(255, 255, 255, 0.08);
            --glass-hover: rgba(255, 255, 255, 0.08);
            --text: #ffffff;
            --text-muted: #94a3b8; 
            --primary: #8b5cf6; --primary-hover: #a78bfa; --secondary: #3b82f6;
            --red: #f43f5e; --yellow: #f59e0b; --green: #10b981;
            --glow: 0 0 20px rgba(139, 92, 246, 0.3);
            --glow-sm: 0 0 10px rgba(139, 92, 246, 0.2);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
        body { background: var(--bg-gradient); color: var(--text); display: flex; height: 100vh; overflow: hidden; letter-spacing: -0.01em; }
        
        /* Layout Framework */
        .sidebar { width: 260px; background: rgba(0,0,0,0.2); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border-right: 1px solid var(--glass-border); padding: 2rem 1.5rem; display: flex; flex-direction: column; z-index: 10; }
        .sidebar-brand { font-size: 1.2rem; font-weight: 700; color: var(--text); margin-bottom: 2.5rem; display: flex; align-items: center; gap: 12px; }
        .sidebar-brand-icon { width: 32px; height: 32px; border-radius: 8px; background: linear-gradient(135deg, var(--primary), var(--secondary)); display: inline-block; box-shadow: var(--glow-sm); }
        .nav-item { display: flex; align-items: center; gap: 14px; padding: 12px 18px; border-radius: 8px; color: var(--text-muted); text-decoration: none; margin-bottom: 0.5rem; font-weight: 600; font-size: 0.95rem; transition: all 0.3s ease; cursor: pointer; border: 1px solid transparent; background: transparent; }
        .nav-item:hover { background: var(--glass-hover); color: var(--text); }
        .nav-item.active { background: rgba(139, 92, 246, 0.15); color: #fff; border: 1px solid rgba(139, 92, 246, 0.3); box-shadow: var(--glow-sm); }
        .sidebar-bottom { margin-top: auto; display: flex; align-items: center; gap: 12px; padding-top: 1.5rem; border-top: 1px solid var(--glass-border); }
        .avatar { width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--secondary)); display: flex; align-items: center; justify-content: center; color: #fff; font-weight: bold; font-size: 1.1rem; box-shadow: var(--glow-sm); }
        
        .main-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: transparent; position: relative; }
        .navbar { display: flex; justify-content: space-between; align-items: center; padding: 1.25rem 2.5rem; border-bottom: 1px solid var(--glass-border); background: var(--glass-bg); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); z-index: 5; }
        .content-wrap { padding: 3rem; overflow-y: auto; flex: 1; }
        
        /* Components */
        .card { background: var(--glass-bg); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid var(--glass-border); border-radius: 16px; padding: 2rem; text-align: left; cursor: pointer; transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); position: relative; overflow: hidden; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2); }
        .card:hover { transform: translateY(-4px); box-shadow: var(--glow); border-color: rgba(139, 92, 246, 0.5); background: var(--glass-hover); }
        .card.active { border: 1px solid var(--primary); background: rgba(139, 92, 246, 0.1); box-shadow: var(--glow); }
        .card h3 { font-size: 1.15rem; color: var(--text); font-weight: 700; margin-bottom: 6px; }
        .card p { font-size: 0.9rem; color: var(--text-muted); font-weight: 500; }
        
        /* Attendance List & Radios */
        .attendance-form { display: none; background: var(--glass-bg); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); padding: 2.5rem; border-radius: 16px; border: 1px solid var(--glass-border); margin-top: 2rem; animation: fadeIn 0.4s ease; box-shadow: 0 8px 32px rgba(0,0,0,0.3); }
        .attendance-form.active { display: block; }
        .student-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-radius: 8px; border: 1px solid transparent; transition: all 0.2s ease; margin-bottom: 10px; background: rgba(0,0,0,0.1); }
        .student-row:nth-child(even) { background: rgba(255,255,255,0.02); }
        .student-row:hover { background: var(--glass-hover); border: 1px solid var(--glass-border); box-shadow: 0 4px 12px rgba(0,0,0,0.1); transform: translateX(4px); }
        .student-name { font-weight: 600; color: #fff; font-size: 1rem; }
        .student-id { font-size: 0.85rem; color: var(--text-muted); display: block; margin-top: 4px; font-weight: 500; }
        
        .radio-group { display: flex; gap: 8px; }
        .radio-group label { cursor: pointer; padding: 8px 20px; border-radius: 20px; border: 1px solid var(--glass-border); font-size: 0.85rem; font-weight: 600; color: var(--text-muted); transition: all 0.2s ease; background: rgba(0,0,0,0.2); }
        .radio-group input[type="radio"] { display: none; }
        .radio-group input[type="radio"]:checked+label { border-color: transparent; }
        .radio-group input[type="radio"]:checked+label.p-label { background: var(--green); color: #fff !important; font-weight: 600 !important; box-shadow: 0 0 15px rgba(16, 185, 129, 0.4); text-shadow: 0 1px 2px rgba(0,0,0,0.2); }
        .radio-group input[type="radio"]:checked+label.a-label { background: var(--red); color: #fff !important; font-weight: 600 !important; box-shadow: 0 0 15px rgba(244, 63, 94, 0.4); text-shadow: 0 1px 2px rgba(0,0,0,0.2); }
        
        .btn-submit { background: linear-gradient(135deg, var(--primary), var(--secondary)); color: #fff; border: 1px solid rgba(255,255,255,0.2); padding: 14px 28px; border-radius: 12px; cursor: pointer; font-size: 1.05rem; font-weight: 700; width: 100%; margin-top: 2rem; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(139, 92, 246, 0.3); }
        .btn-submit:hover { transform: translateY(-2px); box-shadow: var(--glow); filter: brightness(1.1); }
        
        /* Mentee Tracking */
        .summary-row { display: flex; gap: 1.25rem; margin-bottom: 2rem; flex-wrap: wrap; }
        .summary-card { border-radius: 16px; padding: 1.5rem; flex: 1; min-width: 150px; text-align: center; cursor: pointer; transition: all 0.3s ease; border: 1px solid var(--glass-border); background: var(--glass-bg); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); position: relative; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
        .summary-card:hover { transform: translateY(-4px); box-shadow: var(--glow); border-color: rgba(139, 92, 246, 0.3); background: var(--glass-hover); }
        .summary-card .count { font-size: 2.25rem; font-weight: 800; color: #fff; letter-spacing: -0.05em; text-shadow: 0 2px 4px rgba(0,0,0,0.3); }
        .summary-card .label { font-size: 0.85rem; margin-top: 6px; font-weight: 600; color: var(--text-muted); letter-spacing: 0.05em; }
        
        .risk-pills { display: flex; gap: 10px; margin-bottom: 2rem; flex-wrap: wrap; }
        .risk-pill { padding: 8px 20px; border-radius: 24px; font-size: 0.85rem; font-weight: 600; cursor: pointer; border: 1px solid var(--glass-border); background: var(--glass-bg); backdrop-filter: blur(4px); color: var(--text-muted); transition: all 0.2s ease; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .risk-pill:hover { background: var(--glass-hover); color: #fff; border-color: rgba(255,255,255,0.2); }
        .risk-pill.active { background: rgba(139, 92, 246, 0.15); color: #fff; border: 1px solid rgba(139, 92, 246, 0.3); box-shadow: var(--glow-sm); }
        
        table { width: 100%; border-collapse: separate; border-spacing: 0 8px; text-align: left; }
        th { padding: 12px 20px; color: var(--text-muted); font-size: 0.75rem; letter-spacing: 0.05em; border: none; font-weight: 700; text-transform: uppercase; }
        td { padding: 16px 20px; font-size: 0.95rem; font-weight: 500; border: none; background: var(--glass-bg); backdrop-filter: blur(4px); transition: all 0.2s ease; border-top: 1px solid var(--glass-border); border-bottom: 1px solid var(--glass-border); color: #fff; }
        td:first-child { border-left: 1px solid var(--glass-border); border-top-left-radius: 12px; border-bottom-left-radius: 12px; }
        td:last-child { border-right: 1px solid var(--glass-border); border-top-right-radius: 12px; border-bottom-right-radius: 12px; }
        tr:hover td { background: var(--glass-hover); border-color: rgba(255,255,255,0.2); transform: scale(1.01); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        .clickable-name { color: var(--primary); cursor: pointer; font-weight: 600; text-decoration: none; display: inline-block; padding: 2px 0; transition: all 0.2s; } .clickable-name:hover { color: var(--primary-hover); text-shadow: var(--glow-sm); }
        
        .risk-badge { padding: 6px 14px; border-radius: 20px; font-size: 0.8rem; font-weight: 700; display: inline-block; border: 1px solid transparent; backdrop-filter: blur(4px); }
        .badge-safe { background: rgba(16, 185, 129, 0.15); color: var(--green); border-color: rgba(16, 185, 129, 0.3); }
        .badge-watch { background: rgba(245, 158, 11, 0.15); color: var(--yellow); border-color: rgba(245, 158, 11, 0.3); }
        .badge-critical { background: rgba(244, 63, 94, 0.15); color: var(--red); border-color: rgba(244, 63, 94, 0.3); }
        
        /* Modals */
        .modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); z-index: 1000; justify-content: center; align-items: center; }
        .modal { background: rgba(30,30,40,0.6); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px); padding: 2.5rem; border-radius: 20px; border: 1px solid var(--glass-border); width: 480px; max-width: 90%; max-height: 90vh; overflow-y: auto; box-shadow: 0 25px 50px rgba(0,0,0,0.5); animation: scaleUp 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
        .modal h3 { margin-bottom: 1.5rem; color: #fff; border-bottom: 1px solid var(--glass-border); padding-bottom: 1rem; font-weight: 700; font-size: 1.25rem; }
        .modal ul { list-style: none; padding: 0; max-height: 150px; overflow-y: auto; color: var(--red); font-size: 0.9rem; background: rgba(244, 63, 94, 0.1); padding: 16px; border-radius: 12px; border: 1px solid rgba(244, 63, 94, 0.2); font-weight: 500; }
        .modal ul li { padding: 6px 0; border-bottom: 1px solid rgba(244, 63, 94, 0.1); } .modal ul li:last-child { border-bottom: none; }
        .modal-input-group { margin-top: 1.5rem; display: flex; flex-direction: column; }
        .modal-input-group label { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 8px; font-weight: 600; letter-spacing: 0.05em; }
        .modal-input-group input { background: rgba(0,0,0,0.2); color: #fff; border: 1px solid var(--glass-border); padding: 12px 16px; border-radius: 10px; font-size: 1rem; font-weight: 500; outline: none; transition: all 0.3s ease; }
        .modal-input-group input:focus { border-color: var(--primary); box-shadow: var(--glow-sm); background: rgba(0,0,0,0.4); }
        .modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 2rem; }
        
        @keyframes scaleUp { from { transform: scale(0.95); opacity: 0; } to { transform: scale(1); opacity: 1; } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        /* Student Details Popup */
        .popup-modal { background: rgba(30,30,40,0.7); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px); border-radius: 20px; border: 1px solid var(--glass-border); width: 800px; max-width: 95%; max-height: 85vh; overflow-y: auto; position: relative; margin: auto; margin-top: 5vh; box-shadow: 0 25px 50px rgba(0,0,0,0.5); animation: scaleUp 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
        .popup-header { display: flex; justify-content: space-between; align-items: center; padding: 2rem 2.5rem; border-bottom: 1px solid var(--glass-border); position: sticky; top: 0; background: rgba(30,30,40,0.5); backdrop-filter: blur(12px); z-index: 10; }
        .popup-header h3 { font-size: 1.35rem; color: #fff; font-weight: 800; }
        .popup-close { background: none; border: none; color: var(--text-muted); font-size: 2rem; cursor: pointer; transition: color 0.2s ease; line-height: 1; margin-top: -4px; } .popup-close:hover { color: #fff; filter: drop-shadow(0 0 8px rgba(255,255,255,0.5)); }
        .popup-body { padding: 2.5rem; }
        .popup-stat-row { display: flex; gap: 1.5rem; margin-bottom: 2rem; flex-wrap: wrap; }
        .popup-stat { flex: 1; min-width: 120px; background: rgba(0,0,0,0.2); border-radius: 16px; padding: 1.5rem; text-align: center; border: 1px solid var(--glass-border); box-shadow: inset 0 2px 10px rgba(0,0,0,0.1); }
        .popup-stat .big { font-size: 2rem; font-weight: 800; color: var(--primary); letter-spacing: -0.05em; text-shadow: var(--glow-sm); } .popup-stat .small { font-size: 0.8rem; color: var(--text-muted); margin-top: 6px; font-weight: 600; letter-spacing: 0.05em; }
        .subject-bar { display: flex; align-items: center; gap: 16px; padding: 16px 20px; background: var(--glass-bg); border-radius: 12px; margin-bottom: 10px; border: 1px solid var(--glass-border); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        .subject-name { width: 140px; font-size: 0.95rem; font-weight: 700; color: #fff; }
        .bar-container { flex: 1; background: rgba(0,0,0,0.3); border-radius: 12px; height: 14px; overflow: hidden; border: 1px solid var(--glass-border); }
        .bar-fill { height: 100%; border-radius: 12px; transition: width 1s ease-out; box-shadow: 0 0 10px rgba(255,255,255,0.2) inset; }
        .action-item { padding: 12px 16px; background: rgba(139, 92, 246, 0.1); border-left: 4px solid var(--primary); border-radius: 8px; margin-bottom: 12px; font-size: 0.9rem; color: #a78bfa; font-weight: 600; box-shadow: var(--glow-sm); }
        .popup-btn { padding: 12px 24px; border-radius: 10px; font-size: 0.9rem; font-weight: 700; cursor: pointer; border: 1px solid rgba(255,255,255,0.1); transition: all 0.3s ease; } .popup-btn:hover { transform: translateY(-2px); filter: brightness(1.1); box-shadow: var(--glow); }
        .btn-email { background: linear-gradient(135deg, var(--secondary), #2563eb); color: #fff; }
        .btn-meeting { background: linear-gradient(135deg, var(--primary), #7c3aed); color: #fff; }
        
        .email-compose { display: none; margin-top: 1.5rem; padding: 2rem; background: rgba(0,0,0,0.2); border-radius: 16px; border: 1px solid var(--glass-border); animation: fadeIn 0.4s ease; box-shadow: inset 0 4px 15px rgba(0,0,0,0.2); }
        .email-compose.active { display: block; }
        .email-compose textarea { width: 100%; height: 120px; background: rgba(0,0,0,0.3); color: #fff; border: 1px solid var(--glass-border); border-radius: 10px; padding: 16px; font-size: 0.95rem; resize: vertical; outline: none; margin-bottom: 16px; font-weight: 500; transition: border 0.3s ease; }
        .email-compose textarea:focus { border-color: var(--secondary); box-shadow: 0 0 10px rgba(59, 130, 246, 0.3); }
        
        .alert { padding: 1.25rem 1.5rem; border-radius: 12px; margin-bottom: 2rem; font-weight: 700; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); color: var(--green); box-shadow: 0 4px 15px rgba(16, 185, 129, 0.1); display: flex; align-items: center; gap: 12px; backdrop-filter: blur(8px); }
"""

# Extract the CSS block
head, css_and_body = text.split("<style>", 1)
old_css, body = css_and_body.split("</style>", 1)

# Replace the old hardcoded CSS
new_text = head + "<style>\n" + new_css + "    </style>" + body

# 2. Fix the hardcoded inline styles in the HTML (e.g. Weekly Schedule Cards)
new_text = new_text.replace(
    'style="background: #181825; border: 1px solid #45475a; border-radius: 12px; overflow: hidden;"',
    'style="background: var(--glass-bg); backdrop-filter: blur(12px); border: 1px solid var(--glass-border); border-radius: 12px; overflow: hidden; box-shadow: 0 8px 32px rgba(0,0,0,0.2);"'
)
new_text = new_text.replace(
    'style="background: #313244; padding: 8px; text-align: center; font-size: 0.75rem; font-weight: 700; color: #cdd6f4; border-bottom: 1px solid var(--overlay); text-transform: none !important;"',
    'style="background: rgba(0,0,0,0.3); padding: 8px; text-align: center; font-size: 0.75rem; font-weight: 700; color: var(--text-muted); border-bottom: 1px solid var(--glass-border); text-transform: uppercase;"'
)
new_text = new_text.replace(
    'style="background: #1e1e2e; border: 1px solid #45475a; border-radius: 8px; padding: 8px; position: relative;"',
    'style="background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border); border-radius: 8px; padding: 8px; position: relative; transition: all 0.3s ease; cursor: pointer;" onmouseover="this.style.transform=\'translateY(-2px)\'; this.style.boxShadow=\'var(--glow-sm)\'" onmouseout="this.style.transform=\'none\'; this.style.boxShadow=\'none\'"'
)
new_text = new_text.replace(
    'style="font-size: 0.75rem; font-weight: 700; color: #cdd6f4; padding-left: 6px;"',
    'style="font-size: 0.75rem; font-weight: 700; color: #fff; padding-left: 6px;"'
)
new_text = new_text.replace(
    'style="font-size: 0.7rem; color: #cdd6f4; margin-top: 2px; padding-left: 6px;"',
    'style="font-size: 0.7rem; color: var(--text-muted); margin-top: 2px; padding-left: 6px;"'
)
new_text = new_text.replace(
    'style="text-align: center; color: var(--overlay); font-size: 0.75rem; margin-top: 10px;"',
    'style="text-align: center; color: var(--text-muted); font-size: 0.75rem; margin-top: 10px;"'
)
new_text = new_text.replace(
    'style="background: var(--surface); border: 1px dashed var(--overlay); border-radius: 12px; padding: 2rem; text-align: center; margin-bottom: 2.5rem; color: var(--text-muted);"',
    'style="background: var(--glass-bg); backdrop-filter: blur(12px); border: 1px dashed var(--glass-border); border-radius: 12px; padding: 2rem; text-align: center; margin-bottom: 2.5rem; color: var(--text-muted);"'
)
new_text = new_text.replace(
    'style="background: var(--surface); border: 1px solid var(--overlay); border-radius: 30px; padding: 6px 16px; display: flex; align-items: center; gap: 10px;"',
    'style="background: rgba(0,0,0,0.2); border: 1px solid var(--glass-border); border-radius: 30px; padding: 6px 16px; display: flex; align-items: center; gap: 10px;"'
)

with open(r"d:\Semester4\CSE274\Smart-Attendance-System\backend\templates\faculty_dashboard.html", "w", encoding="utf-8") as f:
    f.write(new_text)

print("Glassmorphism transformation complete.")
