#!/usr/bin/env python
"""数据源模块分析脚本"""

import os
import glob
from pathlib import Path
from collections import defaultdict

def analyze_data_source_module():
    """分析数据源模块的文件结构和代码质量"""

    # 统计文件
    files = glob.glob('deepsearch/infrastructure/providers/**/*.py', recursive=True)
    print(f"总文件数: {len(files)}")

    # 分类统计
    categories = defaultdict(list)
    for file in files:
        parts = Path(file).parts
        if 'managers' in parts:
            categories['managers'].append(file)
        elif 'implementations' in parts:
            if 'akshare' in parts:
                categories['akshare'].append(file)
            elif 'amazingdata' in parts:
                categories['amazingdata'].append(file)
            elif 'cloudflare' in parts:
                categories['cloudflare'].append(file)
            elif 'qmt' in parts:
                categories['qmt'].append(file)
        elif 'utils' in parts:
            categories['utils'].append(file)
        elif 'interfaces' in parts:
            categories['interfaces'].append(file)

    # 打印统计结果
    print("\n文件分类统计:")
    for category, file_list in categories.items():
        print(f"\n{category.upper()} ({len(file_list)} files):")
        for file in file_list:
            print(f"  - {os.path.basename(file)}")

    # 识别重复模式
    print("\n潜在的重复实现:")

    # 检查管理器重复
    managers = categories['managers']
    if len(managers) > 1:
        print("\n多个管理器实现:")
        for m in managers:
            name = os.path.basename(m)
            size = os.path.getsize(m)
            lines = sum(1 for _ in open(m, 'r', encoding='utf-8'))
            print(f"  - {name}: {lines} lines, {size} bytes")

    # 检查AkShare重复
    akshare_files = categories['akshare']
    if len(akshare_files) > 1:
        print("\n多个AkShare实现:")
        for f in akshare_files:
            name = os.path.basename(f)
            if 'akshare' in name.lower() and '.py' in name:
                try:
                    lines = sum(1 for _ in open(f, 'r', encoding='utf-8'))
                    print(f"  - {name}: {lines} lines")
                except:
                    pass

    # 检查AmazingData重复
    amazingdata_files = categories['amazingdata']
    if len(amazingdata_files) > 1:
        print("\n多个AmazingData实现:")
        for f in amazingdata_files:
            name = os.path.basename(f)
            if 'amazingdata' in name.lower() and '.py' in name:
                try:
                    lines = sum(1 for _ in open(f, 'r', encoding='utf-8'))
                    print(f"  - {name}: {lines} lines")
                except:
                    pass

    return categories

if __name__ == "__main__":
    analyze_data_source_module()