 initfrom flask import Flask, render_template_string
import json

app = Flask(__name__)

template = """
<script id="analytics-data" type="application/json">
    {
        "labels": {{ labels | tojson }},
        "hostlerData": {{ hostler_data | tojson }},
        "dayScholarData": {{ day_scholar_data | tojson }},
        "hostlerRate": {{ hostler_rate | default(0) }},
        "scholarRate": {{ scholar_rate | default(0) }}
    }
</script>
"""

@app.route("/")
def index():
    return render_template_string(template, 
        labels=['a', 'b'], hostler_data=[1, 2], day_scholar_data=[3, 4],
        hostler_rate=50, scholar_rate=60.5)

if __name__ == "__main__":
    with app.app_context():
        res = index()
        import re
        match = re.search(r'<script.*?>\s*(.*?)\s*</script>', res, re.DOTALL)
        if match:
            content = match.group(1)
            print("RENDERED JSON:")
            print(content)
            print("IS VALID JSON?", isinstance(json.loads(content), dict))
