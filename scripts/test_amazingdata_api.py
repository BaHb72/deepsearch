"""
AmazingData API 端点全量测试脚本
测试 Dask Worker 模式下所有 API 端点的可用性
"""

import asyncio
import time
from datetime import datetime

import httpx

BASE_URL = "http://127.0.0.1:8000/api/amazingdata"

# 测试端点列表：(模块, 端点, 方法, 参数)
ENDPOINTS = [
    # ===== Basic Data =====
    ("basic", "calendar", "GET", {}),
    ("basic", "code-info", "GET", {}),
    ("basic", "code-list", "GET", {}),
    ("basic", "stock-basic", "POST", {"code_list": ["600000.SH", "000001.SZ"]}),
    ("basic", "future-code-list", "GET", {}),
    ("basic", "bj-code-mapping", "GET", {}),
    # ===== History =====
    (
        "history",
        "query-kline",
        "POST",
        {
            "code_list": ["600000.SH"],  # 后缀格式 (SDK 原生格式)
            "begin_date": 20250101,
            "end_date": 20250110,
            "period": "daily",
        },
    ),
    (
        "history",
        "query-snapshot",
        "POST",
        {
            "code_list": ["600000.SH"],
            "begin_date": 20250106,
            "end_date": 20250107,
        },
    ),
    # ===== Financial =====
    ("financial", "profit-express", "POST", {"code_list": ["600000.SH"]}),
    ("financial", "profit-notice", "POST", {"code_list": ["600000.SH"]}),
    ("financial", "balance-sheet", "POST", {"code_list": ["600000.SH"]}),
    ("financial", "income", "POST", {"code_list": ["600000.SH"]}),
    ("financial", "cash-flow", "POST", {"code_list": ["600000.SH"]}),
    # ===== Shareholder =====
    ("shareholder", "share-holder", "POST", {"code": "600000.SH"}),
    ("shareholder", "holder-num", "POST", {"code": "600000.SH"}),
    ("shareholder", "equity-structure", "POST", {"code": "600000.SH"}),
    ("shareholder", "dividend", "POST", {"code": "600000.SH"}),
    # ===== Margin =====
    ("margin", "margin-summary", "GET", {}),  # GET 无参数
    ("margin", "margin-detail", "GET", {"code": "600000.SH"}),  # GET + Query 参数
    # ===== Realtime =====
    ("realtime", "subscription-status", "GET", {}),  # 改为可用端点
    # ===== Concept =====
    ("concept", "velocity", "GET", {}),  # 改为正确端点
    # ===== ETF =====
    ("etf", "pcf", "POST", {"code_list": ["510300.SH"]}),  # 后缀格式
]


async def test_endpoint(
    client: httpx.AsyncClient, module: str, endpoint: str, method: str, params: dict
) -> dict:
    """测试单个端点"""
    url = f"{BASE_URL}/{module}/{endpoint}"
    start = time.perf_counter()

    try:
        if method == "GET":
            resp = await client.get(url, params=params, timeout=30.0)
        else:
            resp = await client.post(url, json=params, timeout=30.0)

        elapsed = (time.perf_counter() - start) * 1000

        try:
            data = resp.json()
            success = data.get("success", False)
            error = data.get("error", "")
            count = (
                data.get("data", {}).get("count") if isinstance(data.get("data"), dict) else None
            )
        except:
            success = False
            error = f"HTTP {resp.status_code}"
            count = None

        return {
            "module": module,
            "endpoint": endpoint,
            "success": success,
            "status_code": resp.status_code,
            "latency_ms": round(elapsed, 1),
            "count": count,
            "error": error[:80] if error else None,
        }
    except httpx.TimeoutException:
        return {
            "module": module,
            "endpoint": endpoint,
            "success": False,
            "status_code": 0,
            "latency_ms": 30000,
            "count": None,
            "error": "TIMEOUT",
        }
    except Exception as e:
        return {
            "module": module,
            "endpoint": endpoint,
            "success": False,
            "status_code": 0,
            "latency_ms": 0,
            "count": None,
            "error": str(e)[:80],
        }


async def main():
    print(f"\n{'='*60}")
    print(f"AmazingData API 全量测试 - Dask Worker 模式")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    results = []
    async with httpx.AsyncClient() as client:
        for module, endpoint, method, params in ENDPOINTS:
            print(f"测试 [{module}/{endpoint}]...", end=" ", flush=True)
            result = await test_endpoint(client, module, endpoint, method, params)
            results.append(result)

            if result["success"]:
                count_str = f", count={result['count']}" if result["count"] else ""
                print(f"✅ OK ({result['latency_ms']}ms{count_str})")
            else:
                print(f"❌ FAIL: {result['error']}")

    # 统计
    success_count = sum(1 for r in results if r["success"])
    total = len(results)

    print(f"\n{'='*60}")
    print(f"测试结果: {success_count}/{total} 通过 ({success_count/total*100:.1f}%)")
    print(f"{'='*60}")

    # 失败列表
    failures = [r for r in results if not r["success"]]
    if failures:
        print(f"\n失败端点 ({len(failures)}):")
        for f in failures:
            print(f"  - {f['module']}/{f['endpoint']}: {f['error']}")


if __name__ == "__main__":
    asyncio.run(main())
