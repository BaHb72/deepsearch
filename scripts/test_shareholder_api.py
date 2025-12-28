import json

import requests

url = "http://localhost:8000/api/amazingdata/shareholder/share-holder"
payload = {"code": "600519.SH", "top_n": 10}
headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print("Response Body:")
    try:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except:
        print(response.text)
except Exception as e:
    print(f"Error: {e}")
