import re

filepath = r"d:\Semester4\CSE274\Smart-Attendance-System\backend\templates\faculty_dashboard.html"
with open(filepath, "r", encoding="utf-8") as f:
    text = f.read()

# Remove transitions and transforms to stop 'blinking'
text = re.sub(r'transition:[^;\}]+;', 'transition: none !important;', text)
text = re.sub(r'transform:[^;\}]+;', 'transform: none !important;', text)

# Remove all box shadows that cause pop-out blinking
text = re.sub(r'box-shadow:[^;\}]+;', 'box-shadow: none !important;', text)

# Kill any remaining hover background colors from CSS rules
text = re.sub(r':hover\s*\{[^}]*\}', ':hover { background: transparent !important; color: inherit !important; border: 1px solid transparent !important; transform: none !important; box-shadow: none !important; }', text)

# Kill any .active class background colors that might flash bright
text = re.sub(r'\.active\s*\{[^}]*\}', '.active { background: rgba(0,0,0,0.2) !important; color: inherit; border: 1px solid rgba(255,255,255,0.1); transform: none !important; box-shadow: none !important; }', text)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(text)

print("Done wiping hover effects and animations.")
