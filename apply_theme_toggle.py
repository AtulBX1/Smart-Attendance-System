import os
import re

base_dir = r"d:\Semester4\CSE274\Smart-Attendance-System\backend\templates"
files_to_modify = ["dashboard.html", "faculty_dashboard.html", "student_dashboard.html"]

theme_script = r"""
    <script>
        const THEME_KEY = 'lumina_theme';
        if (localStorage.getItem(THEME_KEY) === 'light') {
            document.documentElement.classList.add('light-mode');
        }
        function toggleTheme() {
            document.documentElement.classList.toggle('light-mode');
            const isLight = document.documentElement.classList.contains('light-mode');
            localStorage.setItem(THEME_KEY, isLight ? 'light' : 'dark');
            document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
                btn.innerText = isLight ? '☀️' : '🌙';
            });
        }
        window.addEventListener('DOMContentLoaded', () => {
            const isLight = document.documentElement.classList.contains('light-mode');
            document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
                btn.innerText = isLight ? '☀️' : '🌙';
            });
        });
    </script>
"""

btn_html = '<button onclick="toggleTheme()" class="theme-toggle-btn" style="background:transparent; border:none; font-size:1.2rem; cursor:pointer; outline:none; transition: transform 0.3s; margin-right: 10px;" onmouseover="this.style.transform=\'scale(1.1)\'" onmouseout="this.style.transform=\'scale(1)\'">🌙</button>'

for filename in files_to_modify:
    path = os.path.join(base_dir, filename)
    if not os.path.exists(path):
        continue
    
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Inject Head Script (Right before </head>)
    if 'THEME_KEY' not in content:
        content = content.replace("</head>", theme_script + "\n</head>")

    if filename == "faculty_dashboard.html":
        # We find <div style="display: flex; gap: 1rem; align-items: center;"> and insert right after it
        if "theme-toggle-btn" not in content:
            content = content.replace(
                '<div style="display: flex; gap: 1rem; align-items: center;">',
                f'<div style="display: flex; gap: 1rem; align-items: center;">\n                {btn_html}'
            )
        faculty_css = r"""
        html.light-mode body {
            --bg: #f5f7fa;
            --surface: #ffffff;
            --border: #e2e8f0;
            --text: #1e293b;
            --text-muted: #64748b;
        }
        html.light-mode .btn-submit, html.light-mode .nav-item.active { color: #fff !important; }
        """
        if "html.light-mode" not in content:
            content = content.replace("    </style>", faculty_css + "    </style>")

    elif filename == "dashboard.html":
        if "theme-toggle-btn" not in content:
            content = content.replace(
                '<div class="nav-actions">',
                f'<div class="nav-actions">\n                {btn_html}'
            )
        admin_css = r"""
        html.light-mode body {
            --bg: #f5f7fa; 
            --surface: #ffffff; 
            --overlay: #e2e8f0;
            --text: #1e293b; 
            --text-muted: #64748b; 
            --surface-hover: #f1f5f9;
        }
        html.light-mode .btn-teal { color: #fff; }
        html.light-mode .btn-lavender { color: #fff; }
        html.light-mode .btn-mauve { color: #fff; }
        html.light-mode .btn-red { color: #fff; }
        html.light-mode td { background: transparent; }
        """
        if "html.light-mode" not in content:
            content = content.replace("    </style>", admin_css + "    </style>")

    elif filename == "student_dashboard.html":
        if "theme-toggle-btn" not in content:
            content = content.replace(
                '<div class="flex items-center gap-4">',
                f'<div class="flex items-center gap-4">\n            {btn_html}'
            )
        student_css = r"""
        html.light-mode body {
            background-color: #f5f7fa !important;
            color: #1e293b !important;
        }
        html.light-mode header,
        html.light-mode .bg-surface-container, 
        html.light-mode .bg-surface-container-high, 
        html.light-mode .bg-surface-container-lowest {
            background-color: #ffffff !important;
            border-color: #e2e8f0 !important;
        }
        html.light-mode .text-on-surface-variant { color: #64748b !important; }
        html.light-mode .text-white, html.light-mode .text-\[\#e5e2e1\] { color: #1e293b !important; }
        html.light-mode .bg-primary\/5 { background-color: rgba(59, 130, 246, 0.1) !important; }
        html.light-mode th { background-color: #f8fafc !important; }
        html.light-mode tr:hover td { background-color: #f1f5f9 !important; }
        """
        if "html.light-mode" not in content:
            content = content.replace("    </style>", student_css + "    </style>")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

print("Theme toggle logic deployed across all dashboards.")
