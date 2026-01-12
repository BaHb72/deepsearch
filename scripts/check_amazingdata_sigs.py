#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查 AmazingData SDK 接口签名
"""

import inspect
import sys

sys.path.insert(0, "d:/Stock/code/deepsearch")


def check_signatures():
    """检查SDK方法签名"""
    print("=" * 60)
    print("AmazingData SDK 接口签名检查")
    print("=" * 60)

    import AmazingData as ad

    # BaseData
    print("\n[BaseData]")
    for name in ["get_calendar", "get_code_list", "get_code_info", "get_adj_factor"]:
        if hasattr(ad.BaseData, name):
            method = getattr(ad.BaseData, name)
            try:
                sig = inspect.signature(method)
                print(f"  {name}{sig}")
            except Exception as e:
                print(f"  {name}: 无法获取签名 - {e}")

    # MarketData
    print("\n[MarketData]")
    for name in ["query_kline", "query_snapshot"]:
        if hasattr(ad.MarketData, name):
            method = getattr(ad.MarketData, name)
            try:
                sig = inspect.signature(method)
                print(f"  {name}{sig}")
            except Exception as e:
                print(f"  {name}: 无法获取签名 - {e}")

    # InfoData
    print("\n[InfoData]")
    for name in [
        "get_long_hu_bang",
        "get_block_trading",
        "get_share_holder",
        "get_balance_sheet",
        "get_income",
        "get_index_constituent",
    ]:
        if hasattr(ad.InfoData, name):
            method = getattr(ad.InfoData, name)
            try:
                sig = inspect.signature(method)
                print(f"  {name}{sig}")
            except Exception as e:
                print(f"  {name}: 无法获取签名 - {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    check_signatures()
