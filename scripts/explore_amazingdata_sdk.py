#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData SDK 接口探测脚本
"""

import sys

sys.path.insert(0, "d:/Stock/code/deepsearch")


def explore_sdk():
    """探测 AmazingData SDK 实际接口"""
    print("=" * 60)
    print("AmazingData SDK 接口探测")
    print("=" * 60)

    # 导入SDK
    try:
        import AmazingData as ad

        print("[OK] SDK 导入成功\n")
    except ImportError as e:
        print(f"[FAIL] SDK 导入失败: {e}")
        return

    # 登录
    print("[1] 登录...")
    try:
        result = ad.login("212200038719", "212200038719@2025", "101.230.159.234", 8600)
        if result == 0 or result is True:
            print("  [OK] 登录成功\n")
        else:
            print(f"  [FAIL] 登录失败: {result}")
            return
    except Exception as e:
        print(f"  [FAIL] 登录异常: {e}")
        return

    # 探测模块
    print("[2] 探测顶层模块...")
    for name in dir(ad):
        if not name.startswith("_"):
            obj = getattr(ad, name)
            obj_type = type(obj).__name__
            print(f"  {name}: {obj_type}")

    # 探测BaseData
    print("\n[3] 探测 BaseData 类...")
    if hasattr(ad, "BaseData"):
        for name in dir(ad.BaseData):
            if not name.startswith("_"):
                print(f"  BaseData.{name}")

    # 探测MarketData
    print("\n[4] 探测 MarketData 类...")
    if hasattr(ad, "MarketData"):
        for name in dir(ad.MarketData):
            if not name.startswith("_"):
                print(f"  MarketData.{name}")

    # 探测InfoData
    print("\n[5] 探测 InfoData 类...")
    if hasattr(ad, "InfoData"):
        for name in dir(ad.InfoData):
            if not name.startswith("_"):
                print(f"  InfoData.{name}")

    # 探测SubscribeData
    print("\n[6] 探测 SubscribeData 类...")
    if hasattr(ad, "SubscribeData"):
        for name in dir(ad.SubscribeData):
            if not name.startswith("_"):
                print(f"  SubscribeData.{name}")

    # 登出
    try:
        ad.logout("212200038719")
    except:
        pass

    print("\n" + "=" * 60)
    print("探测完成")
    print("=" * 60)


if __name__ == "__main__":
    explore_sdk()
