import urllib.request
import urllib.parse
from http.cookiejar import CookieJar

cj = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# Login
login_url = 'http://127.0.0.1:5000/login'
data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'}).encode('ascii')
req = urllib.request.Request(login_url, data)
opener.open(req)

# Get Analytics
analytics_url = 'http://127.0.0.1:5000/analytics'
try:
    resp = opener.open(analytics_url)
    print(f"Status Code: {resp.getcode()}")
    print("Content preview:")
    print(resp.read().decode('utf-8')[:500])
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    html = e.read().decode('utf-8')
    if 'class="traceback"' in html:
        import re
        tb = re.search(r'<div class="traceback".*?>(.*?)</div>', html, re.DOTALL)
        if tb:
            # Need to clean up HTML tags if found, or just print raw html of traceback
            print("TRACEBACK FOUND IN HTML:")
            print(tb.group(1)[:2000])
        else:
            print("TRACEBACK CLASS FOUND BUT RE FAILED")
            print(html[:2000])
    else:
        print("NO TRACEBACK FOUND, HTML:")
        print(html[:2000])
