#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新data_providers迁移后的import语句
"""
import re
from pathlib import Path
from typing import List


def update_imports_in_file(file_path: Path) -> bool:
    """更新单个文件中的import语句"""

    # 定义替换规则
    replacements = [
        # data_providers.implementations -> infrastructure.providers.implementations
        (
            r"from deepsearch\.data_providers\.implementations",
            "from deepsearch.infrastructure.providers.implementations",
        ),
        (
            r"import deepsearch\.data_providers\.implementations",
            "import deepsearch.infrastructure.providers.implementations",
        ),
        # data_providers.managers -> infrastructure.providers.managers
        (
            r"from deepsearch\.data_providers\.managers",
            "from deepsearch.infrastructure.providers.managers",
        ),
        (
            r"import deepsearch\.data_providers\.managers",
            "import deepsearch.infrastructure.providers.managers",
        ),
        # data_providers.datafeed -> infrastructure.providers.datafeed
        (
            r"from deepsearch\.data_providers\.datafeed",
            "from deepsearch.infrastructure.providers.datafeed",
        ),
        (
            r"import deepsearch\.data_providers\.datafeed",
            "import deepsearch.infrastructure.providers.datafeed",
        ),
        # data_providers.interfaces -> domain.interfaces.providers
        (
            r"from deepsearch\.data_providers\.interfaces",
            "from deepsearch.infrastructure.providers.interfaces.providers",
        ),
        (
            r"import deepsearch\.data_providers\.interfaces",
            "import deepsearch.domain.interfaces.providers",
        ),
        # data_providers.proxy -> infrastructure.providers.proxy
        (
            r"from deepsearch\.data_providers\.proxy",
            "from deepsearch.infrastructure.providers.proxy",
        ),
        (
            r"import deepsearch\.data_providers\.proxy",
            "import deepsearch.infrastructure.providers.proxy",
        ),
        # data_providers.utils -> infrastructure.providers.utils
        (
            r"from deepsearch\.data_providers\.utils",
            "from deepsearch.infrastructure.providers.utils",
        ),
        (
            r"import deepsearch\.data_providers\.utils",
            "import deepsearch.infrastructure.providers.utils",
        ),
        # data_providers根目录文件 -> infrastructure.providers
        (
            r"from deepsearch\.data_providers\.([a-z_]+) import",
            r"from deepsearch.infrastructure.providers.\1 import",
        ),
        (
            r"import deepsearch\.data_providers\.([a-z_]+)$",
            r"import deepsearch.infrastructure.providers.\1",
        ),
        # 通用data_providers -> infrastructure.providers
        (
            r"from deepsearch\.data_providers import",
            "from deepsearch.infrastructure.providers import",
        ),
        (r"import deepsearch\.data_providers$", "import deepsearch.infrastructure.providers"),
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
            return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def find_python_files(root_dir: Path) -> List[Path]:
    """查找所有Python文件"""
    python_files = []
    for file_path in root_dir.glob("**/*.py"):
        # 跳过旧的data_providers目录
        if "data_providers" in str(file_path) and "infrastructure" not in str(file_path):
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

    # 特别处理infrastructure/providers内部的相对导入
    print("\nChecking infrastructure/providers internal imports...")
    providers_path = deepsearch_root / "infrastructure" / "providers"
    if providers_path.exists():
        for file_path in providers_path.glob("**/*.py"):
            update_internal_imports(file_path)


def update_internal_imports(file_path: Path) -> bool:
    """更新infrastructure/providers内部的相对导入"""

    replacements = [
        # 内部相对导入修正
        (r"from deepsearch\.data_providers\.", "from deepsearch.infrastructure.providers."),
        (r"from \.\.interfaces", "from deepsearch.infrastructure.providers.interfaces.providers"),
        (r"from data_providers\.", "from deepsearch.infrastructure.providers."),
    ]

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)

        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Updated internal imports: {file_path.name}")
            return True

    except Exception as e:
        print(f"Error updating internal imports in {file_path}: {e}")
        return False


if __name__ == "__main__":
    main()
