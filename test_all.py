import sys
import os

# Add to path
sys.path.append(os.path.abspath('.'))

from backend.app import app

app.config['TESTING'] = True
client = app.test_client()

# Admin test
with client.session_transaction() as sess:
    sess['user_id'] = 9
    sess['username'] = 'admin'
    sess['role'] = 'admin'

r = client.get('/dashboard')
print("Dashboard Status:", r.status_code)

# Faculty Test
with client.session_transaction() as sess:
    sess['user_id'] = 15 # Mock faculty (e.g. math)
    sess['username'] = 'fac_math'
    sess['role'] = 'faculty'

rf = client.get('/faculty_dashboard')
print("Faculty Dashboard Status:", rf.status_code)

# Mentor test
with client.session_transaction() as sess:
    sess['user_id'] = 11
    sess['username'] = 'M001'
    sess['role'] = 'mentor'

rm = client.get('/mentor/M001')
print("Mentor Dashboard Status:", rm.status_code)

# API
rap = client.get('/api/predict')
print("API Predict Status:", rap.status_code)
print("Preview Predict:", rap.json['predictions'][:1] if rap.json else rap.data[:100])
