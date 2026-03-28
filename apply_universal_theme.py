import os
import glob

TEMPLATE_DIR = r"d:\Semester4\CSE274\Smart-Attendance-System\backend\templates"

FOUC_SCRIPT = """
    <!-- Anti-FOUC Theme Check -->
    <script>
        (function() {
            try {
                var savedTheme = localStorage.getItem('lumina_theme');
                if (savedTheme === 'light') {
                    document.documentElement.classList.add('light-mode');
                } else if (savedTheme === 'dark') {
                    document.documentElement.classList.remove('light-mode');
                }
            } catch (e) {}
        })();
    </script>
"""

TOGGLE_FAB = """
    <!-- Universal Floating Theme Toggle -->
    <button onclick="toggleGlobalTheme()" id="global-theme-toggle" style="position: fixed; bottom: 25px; right: 25px; background: rgba(0,0,0,0.7); border: 1px solid rgba(255,255,255,0.15); color: #fff; width: 50px; height: 50px; border-radius: 50%; font-size: 1.5rem; cursor: pointer; display: flex; justify-content: center; align-items: center; z-index: 999999; box-shadow: 0 4px 16px rgba(0,0,0,0.4); backdrop-filter: blur(8px); transition: transform 0.2s ease, background 0.2s ease;" onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform='scale(1)'" title="Toggle Light/Dark Theme">
        <span id="global-theme-icon" style="line-height:1;margin-top:-2px;"></span>
    </button>

    <script>
        function updateGlobalThemeIcon() {
            var icon = document.getElementById('global-theme-icon');
            var btn = document.getElementById('global-theme-toggle');
            if (!icon) return;
            if (document.documentElement.classList.contains('light-mode')) {
                icon.innerText = '☀️';
                btn.style.background = 'rgba(255,255,255,0.8)';
                btn.style.border = '1px solid rgba(0,0,0,0.1)';
                btn.style.color = '#1f2937';
                btn.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
            } else {
                icon.innerText = '🌙';
                btn.style.background = 'rgba(0,0,0,0.7)';
                btn.style.border = '1px solid rgba(255,255,255,0.15)';
                btn.style.color = '#fff';
                btn.style.boxShadow = '0 4px 16px rgba(0,0,0,0.4)';
            }
        }

        function toggleGlobalTheme() {
            document.documentElement.classList.toggle('light-mode');
            if (document.documentElement.classList.contains('light-mode')) {
                localStorage.setItem('lumina_theme', 'light');
            } else {
                localStorage.setItem('lumina_theme', 'dark');
            }
            updateGlobalThemeIcon();
        }

        // Initialize icon immediately and wait for load
        updateGlobalThemeIcon();
        document.addEventListener('DOMContentLoaded', updateGlobalThemeIcon);
        
        // Remove duplicate old static togglers if any
        setTimeout(() => {
            const oldTogglers = document.querySelectorAll('.theme-toggle-btn');
            oldTogglers.forEach(btn => btn.style.display = 'none');
        }, 100);
    </script>
"""

FALLBACK_CSS = """
    <!-- Global Light Mode Fallback -->
    <style>
        html.light-mode body { background-color: #f0fdf4 !important; color: #1f2937 !important; }
        html.light-mode .navbar, html.light-mode .card, html.light-mode .container, html.light-mode .upload-section, html.light-mode .form-card, html.light-mode .data-section, html.light-mode .login-card, html.light-mode .right-pane { background-color: #ffffff !important; border-color: rgba(0,0,0,0.05) !important; color: #1f2937 !important; box-shadow: 0 4px 16px rgba(0,0,0,0.04) !important; }
        html.light-mode input, html.light-mode select, html.light-mode textarea { background-color: #f9fafb !important; color: #1f2937 !important; border-color: rgba(0,0,0,0.1) !important; text-shadow: none !important; }
        html.light-mode h1, html.light-mode h2, html.light-mode h3, html.light-mode h4, html.light-mode .desc, html.light-mode label, html.light-mode table, html.light-mode th, html.light-mode td { color: #1f2937 !important; }
        html.light-mode .btn-back { background: #e5e7eb !important; color: #374151 !important; }
        html.light-mode .hint, html.light-mode .empty-msg { background: #f0fdf4 !important; border-color: rgba(0,0,0,0.05) !important; color: #4b5563 !important; }
        html.light-mode .left-pane { background: linear-gradient(135deg, #f0fdf4 0%, #e0f2fe 50%, #eff6ff 100%) !important; }
        html.light-mode .tagline h1, html.light-mode .tagline p { color: #0f172a !important; }
        html.light-mode .alert { background: #dcfce7 !important; color: #16a34a !important; border-color: #86efac !important; }
    </style>
"""

def update_files():
    search_path = os.path.join(TEMPLATE_DIR, "**", "*.html")
    files = glob.glob(search_path, recursive=True)
    
    modified_count = 0
    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        changed = False

        if "<!-- Anti-FOUC Theme Check -->" not in content:
            if "<head>" in content:
                content = content.replace("<head>", "<head>\n" + FOUC_SCRIPT, 1)
                changed = True

        if "<!-- Universal Floating Theme Toggle -->" not in content:
            if "</body>" in content:
                content = content.replace("</body>", TOGGLE_FAB + "\n</body>", 1)
                changed = True

        if "<!-- Global Light Mode Fallback -->" not in content and "html.light-mode body" not in content:
            # Inject fallback CSS right before </head> if the file has no light mode rules
            if "</head>" in content:
                content = content.replace("</head>", FALLBACK_CSS + "\n</head>", 1)
                changed = True

        if changed:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            modified_count += 1
            print(f"Updated: {os.path.basename(file_path)}")

    print(f"Total HTML files updated: {modified_count}/{len(files)}")

if __name__ == "__main__":
    update_files()
