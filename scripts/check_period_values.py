#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""查看Period枚举值"""

import sys
sys.path.insert(0, "d:/Stock/code/deepsearch")

import AmazingData as ad

ad.login(
    "212200038719",
    "212200038719@2025",
    "101.230.159.234",
    8600
)

p = ad.constant.Period
print("Period枚举值:")
for k in dir(p):
    if not k.startswith('_'):
        attr = getattr(p, k, None)
        val = getattr(attr, 'value', attr)
        print(f"  {k}: {val}")

ad.logout("212200038719")
