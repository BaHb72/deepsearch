import json
import urllib.request

# Test board overview API - this fetches data with more details
try:
    r = urllib.request.urlopen(
        "http://localhost:8000/api/market/live/board-overview?type=concept&window=1m&limit=10",
        timeout=20,
    )
    d = json.loads(r.read())
    print("=== Board Overview API ===")
    print("mode:", d.get("mode"))
    print("is_trading_hours:", d.get("is_trading_hours"))
    print("stale:", d.get("stale"))
    print("detail:", d.get("detail", {}))
    items = d.get("items", [])
    print(f"items count: {len(items)}")
    for i in items[:5]:
        board = i.get("board", "N/A")
        net = i.get("inflow_net")
        speed = i.get("inflow_speed")
        stock_count = i.get("stock_count")
        print(f"  {board}: inflow_net={net}, inflow_speed={speed}, stock_count={stock_count}")
except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
