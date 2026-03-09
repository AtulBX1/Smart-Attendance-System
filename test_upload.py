import requests

url = "http://127.0.0.1:5000/api/upload"
file_path = "data/raw/student_attendance_dataset.csv"

try:
    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(url, files=files)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
