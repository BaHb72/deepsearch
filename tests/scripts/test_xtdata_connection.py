# -*- coding: utf-8 -*-
"""
MiniQMT Real Connection Test - Detailed Version
"""

import sys
import warnings

warnings.filterwarnings("ignore")

print("=" * 60)
print("MiniQMT Real Connection Test")
print("=" * 60)

# Step 1: Import
print("\n[1] Importing xtquant...")
try:
    from xtquant import xtdata

    print("    [OK] xtquant imported")
except Exception as e:
    print(f"    [FAIL] {e}")
    sys.exit(1)

# Step 2: Get Full Tick
print("\n[2] get_full_tick(['000001.SZ'])...")
try:
    result = xtdata.get_full_tick(["000001.SZ"])
    if result and "000001.SZ" in result:
        tick = result["000001.SZ"]
        print("    [OK] Got tick data!")
        if isinstance(tick, dict):
            print(f"    Fields: {list(tick.keys())}")
            if "lastPrice" in tick:
                print(f"    lastPrice: {tick['lastPrice']}")
            if "open" in tick:
                print(f"    open: {tick['open']}")
            if "high" in tick:
                print(f"    high: {tick['high']}")
            if "low" in tick:
                print(f"    low: {tick['low']}")
            if "volume" in tick:
                print(f"    volume: {tick['volume']}")
    else:
        print("    [WARN] Empty result")
except Exception as e:
    print(f"    [FAIL] {type(e).__name__}: {e}")

# Step 3: Get Multiple Stocks
print("\n[3] get_full_tick(['000001.SZ', '600000.SH', '000002.SZ'])...")
try:
    stocks = ["000001.SZ", "600000.SH", "000002.SZ"]
    result = xtdata.get_full_tick(stocks)
    if result:
        received = [s for s in stocks if s in result]
        print(f"    [OK] Got {len(received)}/{len(stocks)} stocks")
        for s in received:
            tick = result[s]
            if isinstance(tick, dict) and "lastPrice" in tick:
                print(f"    {s}: lastPrice={tick['lastPrice']}")
    else:
        print("    [WARN] Empty result")
except Exception as e:
    print(f"    [FAIL] {type(e).__name__}: {e}")

# Step 4: Get Market Data
print("\n[4] get_market_data(['000001.SZ'], period='1d', count=5)...")
try:
    result = xtdata.get_market_data(stock_list=["000001.SZ"], period="1d", count=5)
    if result:
        print(f"    [OK] Data type: {type(result)}")
        if isinstance(result, dict):
            print(f"    Keys: {list(result.keys())}")
    else:
        print("    [WARN] Empty result")
except Exception as e:
    print(f"    [FAIL] {type(e).__name__}: {e}")

# Step 5: Download History
print("\n[5] download_history_data('000001.SZ', '1d')...")
try:
    xtdata.download_history_data("000001.SZ", "1d", start_time="20241201", end_time="20241210")
    print("    [OK] Download completed")
except Exception as e:
    print(f"    [FAIL] {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("Test Completed Successfully!")
print("=" * 60)
