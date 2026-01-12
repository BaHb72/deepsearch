import json
import time

import requests

BASE_URL = "http://localhost:8000/api/system/memory"


def run_diagnosis():
    print("=== Memory Leak Diagnosis ===")

    # 1. Get Initial Stats
    try:
        print("\n[1] Fetching Initial Stats...")
        resp = requests.get(f"{BASE_URL}/stats", timeout=5)
        if resp.status_code == 200:
            data = resp.json()["data"]["current_process"]
            print(f"    RSS: {data['rss_mb']:.2f} MB")
            print(f"    Objects: {data['python_objects']}")
        else:
            print(f"    Failed: {resp.status_code}")
    except Exception as e:
        print(f"    Error: {e}")

    # 2. Trigger Full GC
    print("\n[2] Triggering Full GC (Generation 0, 1, 2)...")
    try:
        t0 = time.time()
        resp = requests.post(f"{BASE_URL}/gc?full=true", timeout=30)
        dt = time.time() - t0
        if resp.status_code == 200:
            result = resp.json()
            print(f"    Status: {result.get('message', 'OK')}")
            # print(json.dumps(result, indent=2))
        else:
            print(f"    Failed: {resp.status_code}")
        print(f"    Time taken: {dt:.2f}s")
    except Exception as e:
        print(f"    Error: {e}")

    # 3. Get Post-GC Stats
    try:
        print("\n[3] Fetching Post-GC Stats...")
        time.sleep(2)  # Wait for OS to potentially reclaim pages
        resp = requests.get(f"{BASE_URL}/stats", timeout=5)
        if resp.status_code == 200:
            data = resp.json()["data"]["current_process"]
            print(f"    RSS: {data['rss_mb']:.2f} MB")
            print(f"    Objects: {data['python_objects']}")
        else:
            print(f"    Failed: {resp.status_code}")
    except Exception as e:
        print(f"    Error: {e}")

    print("\n=== Analysis ===")
    print("If RSS did not decrease significantly, we have a STRONG REFERENCE LEAK.")
    print("Likely culprits: Global Caches, Pandas DataFrames, or accumulated large objects.")


if __name__ == "__main__":
    run_diagnosis()
