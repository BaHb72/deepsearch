#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""探索InfoData可用方法"""

import sys

sys.path.insert(0, "d:/Stock/code/deepsearch")

import AmazingData as ad

# 登录
ad.login("212200038719", "212200038719@2025", "101.230.159.234", 8600)

# 创建InfoData实例
info = ad.InfoData()

# 列出所有公开方法
print("InfoData 所有公开方法:")
methods = [m for m in dir(info) if not m.startswith("_") and callable(getattr(info, m))]
for m in sorted(methods):
    print(f"  - {m}")

print(f"\n共 {len(methods)} 个方法")

# 登出
ad.logout("212200038719")
