import json
from pathlib import Path

from fastapi.testclient import TestClient

from deepsearch.webui.server import app

client = TestClient(app)

CASES = [
    ("GET", "/api/data-sources/status", None, None, "data_sources_status"),
    ("GET", "/api/data-sources/list", None, None, "data_sources_list"),
    ("GET", "/api/data/source/status", None, None, "deprecated_status"),
    (
        "PUT",
        "/api/data-sources/config/amazingdata",
        None,
        {"enabled": True, "priority": 1, "config": {"timeout": 5000}},
        "update_amazingdata_config",
    ),
    ("GET", "/api/data/stock/000001", None, None, "stock_info"),
    (
        "GET",
        "/api/data/kline",
        {"symbol": "000001", "period": "1d", "start_date": "2025-09-01", "end_date": "2025-09-16"},
        None,
        "kline_range",
    ),
    (
        "GET",
        "/api/data/kline",
        {"symbol": "000001", "period": "1m", "limit": 100},
        None,
        "kline_1m",
    ),
    ("GET", "/api/data/realtime/000001", None, None, "realtime_single"),
    (
        "POST",
        "/api/data/realtime/batch",
        None,
        {"symbols": ["000001", "000002", "600000"]},
        "realtime_batch",
    ),
    ("GET", "/api/data/market/overview", None, None, "market_overview"),
    ("GET", "/api/data/market/top-gainers", None, None, "top_gainers"),
    ("GET", "/api/data/market/top-losers", None, None, "top_losers"),
]

results = []
for method, path, params, payload, name in CASES:
    request = getattr(client, method.lower())
    if method in {"GET", "DELETE"}:
        response = request(path, params=params)
    else:
        response = request(path, params=params, json=payload)
    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}
    result = {
        "name": name,
        "method": method,
        "path": path,
        "params": params,
        "payload": payload,
        "status_code": response.status_code,
        "body": body,
    }
    results.append(result)
    print(f"=== {name} ===")
    print(f"status_code={response.status_code}")

project_root = Path(__file__).resolve().parents[2]
output_dir = project_root / "reports" / "probes"
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "api_probe_results.json"
output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Saved results to {output_path}")
