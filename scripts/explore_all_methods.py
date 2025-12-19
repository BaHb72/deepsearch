#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""全面探索所有AmazingData模块的方法"""

import sys
sys.path.insert(0, "d:/Stock/code/deepsearch")

import AmazingData as ad

# 登录
ad.login("212200038719", "212200038719@2025", "101.230.159.234", 8600)

print("=" * 60)
print("全面探索AmazingData所有模块方法")
print("=" * 60)

# BaseData
print("\n### BaseData ###")
base = ad.BaseData()
base_methods = [m for m in dir(base) if not m.startswith('_') and callable(getattr(base, m))]
print(f"总计: {len(base_methods)} 个方法")
for m in sorted(base_methods):
    print(f"  - {m}")

# MarketData
print("\n### MarketData ###")
market_methods = []
try:
    calendar = ad.get_calendar_cached()
    market = ad.MarketData(calendar)
    market_methods = [m for m in dir(market) if not m.startswith('_') and callable(getattr(market, m))]
    print(f"总计: {len(market_methods)} 个方法")
    for m in sorted(market_methods):
        print(f"  - {m}")
except Exception as e:
    print(f"创建失败: {e}")
    market_methods = []

# InfoData
print("\n### InfoData ###")
info = ad.InfoData()
info_methods = [m for m in dir(info) if not m.startswith('_') and callable(getattr(info, m))]
print(f"总计: {len(info_methods)} 个方法")
for m in sorted(info_methods):
    print(f"  - {m}")

# SubscribeData
print("\n### SubscribeData ###")
subscribe = ad.SubscribeData()
subscribe_methods = [m for m in dir(subscribe) if not m.startswith('_') and callable(getattr(subscribe, m))]
print(f"总计: {len(subscribe_methods)} 个方法")
for m in sorted(subscribe_methods):
    print(f"  - {m}")

print("\n" + "=" * 60)
print(f"总方法数: {len(base_methods) + len(market_methods) + len(info_methods) + len(subscribe_methods)}")
print("=" * 60)

# 登出
ad.logout("212200038719")
