#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Safe Architecture Migration Tool
安全的架构迁移工具，用于将代码迁移到六边形架构
"""
import ast
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple


class SafeArchitectureMigration:
    """安全架构迁移工具"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.deepsearch_root = self.project_root / "deepsearch"
        self.backup_dir = self.project_root / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.migration_log: List[str] = []
        self.errors: List[str] = []

        # 定义迁移映射
        self.migration_map: Dict[str, str] = {
            # services -> application/services
            "services/market": "application/services/market",
            "services/data": "application/services/data",
            "services/cache": "application/services/cache",
            "services/interfaces": "application/interfaces",
            # data_providers -> infrastructure/providers
            "data_providers/implementations": "infrastructure/providers",
            "data_providers/managers": "infrastructure/providers/managers",
            "data_providers/interfaces": "domain/interfaces/providers",
            "data_providers/datafeed": "infrastructure/datafeed",
            # database/models -> domain/entities
            "database/models": "domain/entities",
        }

        # 需要保留的目录（不迁移）
        self.preserve_dirs: Set[str] = {
            "webui",  # Web界面暂时保留
            "config",  # 配置文件保留
            "event",  # 事件系统保留
            "messaging",  # 消息系统保留
            "gateway",  # 网关保留
            "cli",  # CLI保留
        }

        # 废弃的目录（准备删除）
        self.deprecated_dirs: Set[str] = {
            "storage",  # 已迁移到database
            "backtest_old",  # 旧的回测系统
            "core_old",  # 旧的核心引擎
        }

    def analyze_dependencies(self, file_path: Path) -> Set[str]:
        """分析文件的依赖关系"""
        dependencies = set()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        dependencies.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        dependencies.add(node.module)
        except Exception as e:
            self.errors.append(f"Error analyzing {file_path}: {e}")

        return dependencies

    def update_imports(self, content: str, import_map: Dict[str, str]) -> str:
        """更新文件中的import语句"""
        lines = content.split("\n")
        updated_lines = []

        for line in lines:
            updated_line = line
            for old_import, new_import in import_map.items():
                # 处理 from ... import 语句
                pattern1 = f"from {old_import}"
                replacement1 = f"from {new_import}"
                updated_line = re.sub(pattern1, replacement1, updated_line)

                # 处理 import ... 语句
                pattern2 = f"import {old_import}"
                replacement2 = f"import {new_import}"
                updated_line = re.sub(pattern2, replacement2, updated_line)

            updated_lines.append(updated_line)

        return "\n".join(updated_lines)

    def backup_file(self, file_path: Path):
        """备份文件"""
        relative_path = file_path.relative_to(self.project_root)
        backup_path = self.backup_dir / relative_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, backup_path)
        self.migration_log.append(f"Backed up: {relative_path}")

    def migrate_file(self, src_path: Path, dest_path: Path, update_imports: bool = True):
        """迁移单个文件"""
        try:
            # 备份原文件
            self.backup_file(src_path)

            # 读取文件内容
            with open(src_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 更新imports
            if update_imports:
                import_map = self.generate_import_map()
                content = self.update_imports(content, import_map)

            # 创建目标目录
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入新文件
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(content)

            # 删除原文件
            src_path.unlink()

            self.migration_log.append(f"Migrated: {src_path} -> {dest_path}")
            return True

        except Exception as e:
            self.errors.append(f"Error migrating {src_path}: {e}")
            return False

    def generate_import_map(self) -> Dict[str, str]:
        """生成import映射表"""
        import_map: Dict[str, str] = {}

        for old_path, new_path in self.migration_map.items():
            old_module = f"deepsearch.{old_path.replace('/', '.')}"
            new_module = f"deepsearch.{new_path.replace('/', '.')}"
            import_map[old_module] = new_module

        return import_map

    def find_files_to_migrate(self) -> List[Tuple[Path, Path]]:
        """查找需要迁移的文件"""
        files_to_migrate: List[Tuple[Path, Path]] = []

        for old_dir, new_dir in self.migration_map.items():
            old_path = self.deepsearch_root / old_dir
            new_path = self.deepsearch_root / new_dir

            if old_path.exists():
                for file_path in old_path.glob("**/*.py"):
                    relative_path = file_path.relative_to(old_path)
                    dest_path = new_path / relative_path
                    files_to_migrate.append((file_path, dest_path))

        return files_to_migrate

    def find_deprecated_files(self) -> List[Path]:
        """查找废弃的文件"""
        deprecated_files: List[Path] = []

        for deprecated_dir in self.deprecated_dirs:
            dir_path = self.deepsearch_root / deprecated_dir
            if dir_path.exists():
                for file_path in dir_path.glob("**/*.py"):
                    deprecated_files.append(file_path)

        return deprecated_files

    def clean_empty_dirs(self):
        """清理空目录"""
        for root, dirs, files in os.walk(self.deepsearch_root, topdown=False):
            if not files and not dirs:
                try:
                    os.rmdir(root)
                    self.migration_log.append(f"Removed empty dir: {root}")
                except Exception as e:
                    self.errors.append(f"Error removing {root}: {e}")

    def generate_report(self) -> str:
        """生成迁移报告"""
        report: List[str] = []
        report.append("=" * 60)
        report.append("Architecture Migration Report")
        report.append("=" * 60)
        report.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Backup Directory: {self.backup_dir}")
        report.append("")

        report.append("Migration Log:")
        report.append("-" * 40)
        for log in self.migration_log[-20:]:  # 显示最后20条
            report.append(f"  {log}")

        if self.errors:
            report.append("")
            report.append("Errors:")
            report.append("-" * 40)
            for error in self.errors:
                report.append(f"  [ERROR] {error}")

        report.append("")
        report.append(f"Total: {len(self.migration_log)} operations, {len(self.errors)} errors")

        return "\n".join(report)

    def execute_migration(self, dry_run: bool = False):
        """执行迁移"""
        print("Starting architecture migration...")

        if dry_run:
            print("[DRY RUN MODE] No files will be modified")

        # 1. 查找需要迁移的文件
        files_to_migrate = self.find_files_to_migrate()
        print(f"Found {len(files_to_migrate)} files to migrate")

        # 显示前10个将要迁移的文件
        if files_to_migrate:
            print("\nFiles to migrate (showing first 10):")
            for src, dest in files_to_migrate[:10]:
                print(
                    f"  {src.relative_to(self.project_root)} -> {dest.relative_to(self.project_root)}"
                )

        # 2. 查找废弃的文件
        deprecated_files = self.find_deprecated_files()
        print(f"\nFound {len(deprecated_files)} deprecated files")

        if not dry_run:
            # 3. 创建备份目录
            self.backup_dir.mkdir(parents=True, exist_ok=True)

            # 4. 执行文件迁移
            for src_path, dest_path in files_to_migrate[:5]:  # 先迁移5个文件测试
                self.migrate_file(src_path, dest_path)

            # 5. 删除废弃文件
            for file_path in deprecated_files[:5]:  # 先删除5个文件测试
                self.backup_file(file_path)
                file_path.unlink()
                self.migration_log.append(f"Deleted deprecated: {file_path}")

            # 6. 清理空目录
            self.clean_empty_dirs()

        # 7. 生成报告
        report = self.generate_report()
        print(report)

        # 8. 保存报告
        report_path = (
            self.project_root / f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report saved to: {report_path}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="安全架构迁移工具")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行，不实际修改文件")
    parser.add_argument("--project-root", default="D:/Stock/code/deepsearch", help="项目根目录")

    args = parser.parse_args()

    migrator = SafeArchitectureMigration(args.project_root)
    migrator.execute_migration(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
