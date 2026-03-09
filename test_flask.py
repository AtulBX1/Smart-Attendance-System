import sys
import os
import traceback

# Add to path
sys.path.append(os.path.abspath('.'))

from backend.app import app

app.config['TESTING'] = True
client = app.test_client()

with client.session_transaction() as sess:
    sess['user_id'] = 9
    sess['username'] = 'admin'
    sess['role'] = 'admin'

try:
    response = client.get('/analytics')
    if response.status_code == 500:
        print("INTERNAL SERVER ERROR 500")
        # In testing mode, exceptions are not caught by the 500 handler unless PROPAGATE_EXCEPTIONS is False,
        # but actually Flask test client propagates exceptions directly by default.
        print(response.data.decode('utf-8')[:1000])
    else:
        print(f"Status Code: {response.status_code}")
except Exception as e:
    print("EXCEPTION CAUGHT:")
    traceback.print_exc()
