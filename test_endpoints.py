import urllib.request
import json

def test_endpoint(url):
    print(f"Testing {url}...")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print(f"Status: {response.status}")
            
            if "predictions" in data:
                print(f"Predictions returned: {len(data['predictions'])}")
                if len(data['predictions']) > 0:
                    print("Sample:", data['predictions'][0])
                    
            if "anomalies" in data:
                print(f"Anomalies returned: {len(data['anomalies'])}")
                
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        print(e.read().decode())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_endpoint("http://127.0.0.1:5000/api/predict")
    test_endpoint("http://127.0.0.1:5000/api/anomalies")
