#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量更新import语句工具
"""
import re
from pathlib import Path
from typing import List


def update_imports_in_file(file_path: Path) -> bool:
    """更新单个文件中的import语句"""

    # 定义替换规则
    replacements = [
        # services.market -> application.services.market
        (r"from deepsearch\.services\.market\.", "from deepsearch.application.services.market."),
        (
            r"import deepsearch\.services\.market\.",
            "import deepsearch.application.services.market.",
        ),
        # services.data -> application.services.data
        (
            r"from deepsearch\.services\.data\.",
            "from deepsearch.infrastructure.providers.managers.",
        ),
        (r"import deepsearch\.services\.data\.", "import deepsearch.application.services.data."),
        # services.cache -> application.services.cache
        (r"from deepsearch\.services\.cache\.", "from deepsearch.application.services.cache."),
        (r"import deepsearch\.services\.cache\.", "import deepsearch.application.services.cache."),
        # services.interfaces -> application.interfaces
        (
            r"from deepsearch\.services\.interfaces\.",
            "from deepsearch.infrastructure.providers.interfaces.",
        ),
        (r"import deepsearch\.services\.interfaces\.", "import deepsearch.application.interfaces."),
    ]

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # 应用所有替换规则
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)

        # 如果内容有变化，写回文件
        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Updated: {file_path}")
            return True
        else:
            print(f"No changes: {file_path}")
            return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def find_python_files(root_dir: Path) -> List[Path]:
    """查找所有Python文件"""
    python_files = []
    for file_path in root_dir.glob("**/*.py"):
        python_files.append(file_path)
    return python_files


def main():
    """主函数"""
    project_root = Path("D:/Stock/code/deepsearch")
    deepsearch_root = project_root / "deepsearch"

    # 查找所有Python文件
    python_files = find_python_files(deepsearch_root)
    print(f"Found {len(python_files)} Python files")

    # 更新每个文件
    updated_count = 0
    for file_path in python_files:
        if update_imports_in_file(file_path):
            updated_count += 1

    print(f"\nSummary: Updated {updated_count} files")


if __name__ == "__main__":
    main()
