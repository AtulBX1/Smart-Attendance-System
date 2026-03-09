import urllib.request
import urllib.parse

from http.cookiejar import CookieJar

cj = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# 1. Login
login_data = urllib.parse.urlencode({'username': 'admin', 'password': '123'}).encode('utf-8')
login_req = urllib.request.Request("http://127.0.0.1:5000/login", data=login_data)
opener.open(login_req)

# 2. Get Dashboard
dash_req = urllib.request.Request("http://127.0.0.1:5000/dashboard")
try:
    response = opener.open(dash_req)
    print("Dashboard loaded successfully! Status:", response.status)
    content = response.read().decode('utf-8')
    if "admin" in content.lower():
        print("Success: Logged in and viewing dashboard.")
except urllib.error.HTTPError as e:
    print(f"Failed to load dashboard. HTTP Error: {e.code}")
    print(e.read().decode('utf-8'))
