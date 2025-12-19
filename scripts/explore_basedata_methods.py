#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""探索BaseData可用方法"""

import sys
sys.path.insert(0, "d:/Stock/code/deepsearch")

import AmazingData as ad

# 登录
ad.login("212200038719", "212200038719@2025", "101.230.159.234", 8600)

# 创建BaseData实例
base = ad.BaseData()

# 列出所有公开方法（不含下划线开头的）
print("BaseData 所有公开方法:")
methods = [m for m in dir(base) if not m.startswith('_') and callable(getattr(base, m))]
for m in sorted(methods):
    print(f"  - {m}")

# 查找包含"stock"或"basic"的方法
print("\n包含'stock'或'basic'的方法:")
related = [m for m in methods if 'stock' in m.lower() or 'basic' in m.lower()]
print(related)

# 登出
ad.logout("212200038719")
