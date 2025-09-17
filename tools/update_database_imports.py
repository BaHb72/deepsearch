#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新database迁移后的import语句
"""
import os
import re
from pathlib import Path
from typing import List

def update_imports_in_file(file_path: Path) -> bool:
    """更新单个文件中的import语句"""

    # 定义替换规则
    replacements = [
        # database.models -> domain.entities
        (r'from deepsearch\.database\.models\.', 'from deepsearch.infrastructure.providers.entities.'),
        (r'import deepsearch\.database\.models\.', 'import deepsearch.domain.entities.'),
        (r'from deepsearch\.database\.models import', 'from deepsearch.infrastructure.providers.entities import'),

        # database.migrations -> infrastructure.persistence.migrations
        (r'from deepsearch\.database\.migrations', 'from deepsearch.infrastructure.persistence.migrations'),
        (r'import deepsearch\.database\.migrations', 'import deepsearch.infrastructure.persistence.migrations'),

        # database其他文件 -> infrastructure.persistence
        (r'from deepsearch\.database\.database', 'from deepsearch.infrastructure.persistence.database'),
        (r'from deepsearch\.database\.pool', 'from deepsearch.infrastructure.persistence.pool'),
        (r'from deepsearch\.database\.analytics', 'from deepsearch.infrastructure.persistence.analytics'),
        (r'from deepsearch\.database\.duckdb_analytics', 'from deepsearch.infrastructure.persistence.duckdb_analytics'),
        (r'from deepsearch\.database\.sync_database', 'from deepsearch.infrastructure.persistence.sync_database'),
        (r'from deepsearch\.database\.timeseries', 'from deepsearch.infrastructure.persistence.timeseries'),
        (r'from deepsearch\.database\.query_optimizer', 'from deepsearch.infrastructure.persistence.query_optimizer'),

        # database通用导入 -> infrastructure.persistence
        (r'from deepsearch\.database import', 'from deepsearch.infrastructure.persistence import'),
        (r'import deepsearch\.database$', 'import deepsearch.infrastructure.persistence'),
    ]

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # 应用所有替换规则
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)

        # 如果内容有变化，写回文件
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated: {file_path}")
            return True
        else:
            return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def find_python_files(root_dir: Path) -> List[Path]:
    """查找所有Python文件"""
    python_files = []
    for file_path in root_dir.glob("**/*.py"):
        # 跳过旧的database目录
        if 'database' in str(file_path) and 'infrastructure' not in str(file_path) and 'domain' not in str(file_path):
            continue
        python_files.append(file_path)
    return python_files

def main():
    """主函数"""
    project_root = Path("D:/Stock/code/deepsearch")
    deepsearch_root = project_root / "deepsearch"

    # 查找所有Python文件
    python_files = find_python_files(deepsearch_root)
    print(f"Found {len(python_files)} Python files to check")

    # 更新每个文件
    updated_count = 0
    for file_path in python_files:
        if update_imports_in_file(file_path):
            updated_count += 1

    print(f"\nSummary: Updated {updated_count} files")

if __name__ == "__main__":
    main()