#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""探索复权因子接口"""

import sys

sys.path.insert(0, "d:/Stock/code/deepsearch")

import AmazingData as ad

# 登录
ad.login("212200038719", "212200038719@2025", "101.230.159.234", 8600)

# 创建BaseData实例
base = ad.BaseData()

# 探索可用方法
print("BaseData 可用方法:")
methods = [m for m in dir(base) if not m.startswith("_") and "adjust" in m.lower()]
print(methods)

# 尝试调用复权因子接口
print("\n测试复权因子接口:")
try:
    # 测试后复权
    if hasattr(base, "get_adjust_factor"):
        result = base.get_adjust_factor(["000001.SZ"], begin_date=20241201, end_date=20241213)
        print(f"get_adjust_factor: {type(result)}")
        if result:
            print(f"  Keys: {list(result.keys())[:3]}")
            if "000001.SZ" in result:
                print(
                    f"  Sample: {result['000001.SZ'][:3] if hasattr(result['000001.SZ'], '__getitem__') else result['000001.SZ']}"
                )
except Exception as e:
    print(f"  Error: {e}")

# 登出
ad.logout("212200038719")
