#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""探索SubscribeData可用方法"""

import sys

sys.path.insert(0, "d:/Stock/code/deepsearch")

import AmazingData as ad

# 登录
ad.login("212200038719", "212200038719@2025", "101.230.159.234", 8600)

# 创建SubscribeData实例
try:
    subscribe = ad.SubscribeData()

    # 列出所有公开方法
    print("SubscribeData 所有公开方法:")
    methods = [
        m for m in dir(subscribe) if not m.startswith("_") and callable(getattr(subscribe, m))
    ]
    for m in sorted(methods):
        print(f"  - {m}")

    print(f"\n共 {len(methods)} 个方法")
except Exception as e:
    print(f"创建SubscribeData失败: {e}")
    print("\n尝试查看类定义...")
    if hasattr(ad, "SubscribeData"):
        print("SubscribeData类存在")
        methods = [m for m in dir(ad.SubscribeData) if not m.startswith("_")]
        for m in sorted(methods):
            print(f"  - {m}")

# 登出
ad.logout("212200038719")
