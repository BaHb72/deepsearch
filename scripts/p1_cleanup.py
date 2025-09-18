#!/usr/bin/env python3
"""
P1级深度清理脚本
执行前请确保已备份（git tag: cleanup-recovery-point-v1.0）
"""
import os
import shutil
from pathlib import Path
from datetime import datetime


class P1Cleanup:
    """P1级清理任务执行器"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.report = []
        self.dry_run = False  # 设为True进行模拟运行

    def log(self, message):
        """记录日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = f"[{timestamp}] {message}"
        print(msg)
        self.report.append(msg)

    def cleanup_installer_docs(self):
        """将installer中的文档移到docs/vendor"""
        self.log("=== 清理installer目录文档 ===")

        vendor_dir = self.project_root / "docs" / "vendor"
        installer_dir = self.project_root / "installer"

        if not self.dry_run:
            vendor_dir.mkdir(parents=True, exist_ok=True)

        docs_to_move = [
            ("35API接口详细内容.docx", "AmazingData_API_Details.docx"),
            ("AmazingData开发手册.pdf", "AmazingData_Developer_Manual.pdf")
        ]

        for src_name, dst_name in docs_to_move:
            src = installer_dir / src_name
            dst = vendor_dir / dst_name

            if src.exists():
                if not self.dry_run:
                    shutil.move(str(src), str(dst))
                self.log(f"移动文档: {src_name} -> docs/vendor/{dst_name}")

    def mark_experimental_files(self):
        """标记实验性文件"""
        self.log("=== 标记实验性文件 ===")

        experimental_files = [
            "deepsearch/core/runtime/engine_refactored.py",
            "deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_optimized.py",
            "deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py"
        ]

        for file_path in experimental_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                if not self.dry_run:
                    # 在文件开头添加EXPERIMENTAL标记
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    if not content.startswith("# EXPERIMENTAL"):
                        header = "# EXPERIMENTAL - 此文件为实验性版本，请谨慎使用\n# " + "="*50 + "\n\n"
                        with open(full_path, 'w', encoding='utf-8') as f:
                            f.write(header + content)

                self.log(f"标记为实验性: {file_path}")

    def analyze_component_migration(self):
        """分析组件迁移需求"""
        self.log("=== 分析组件迁移 ===")

        files_to_migrate = [
            "deepsearch/backtest/components/component.py",
            "deepsearch/core/components/infrastructure_components.py",
            "deepsearch/core/components/data_components.py"
        ]

        self.log("需要从async_component迁移到async_component_v2的文件：")
        for file_path in files_to_migrate:
            full_path = self.project_root / file_path
            if full_path.exists():
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if "from deepsearch.core.async_component import" in content:
                        self.log(f"  - {file_path}")

    def cleanup_unused_refactored(self):
        """清理未使用的refactored文件"""
        self.log("=== 清理未使用的refactored文件 ===")

        # 检查akshare_refactored是否被使用
        akshare_refactored = self.project_root / "deepsearch/infrastructure/providers/implementations/akshare/akshare_refactored.py"

        if akshare_refactored.exists():
            # 搜索是否有引用
            has_import = False
            for py_file in self.project_root.rglob("*.py"):
                if py_file != akshare_refactored:
                    try:
                        with open(py_file, 'r', encoding='utf-8') as f:
                            if "akshare_refactored" in f.read():
                                has_import = True
                                break
                    except:
                        pass

            if not has_import:
                if not self.dry_run:
                    akshare_refactored.unlink()
                self.log("删除未使用的文件: akshare_refactored.py")

    def generate_api_cleanup_list(self):
        """生成API清理清单"""
        self.log("=== 生成API清理清单 ===")

        # 这些是前端定义但后端未实现的API模块
        unused_api_modules = [
            "cache",
            "chart",
            "stockComment",
            "systemConfig（部分）"
        ]

        self.log("建议清理的前端API模块：")
        for module in unused_api_modules:
            self.log(f"  - {module}相关的所有接口")

        self.log("\n建议实现的核心后端API：")
        critical_apis = [
            "/api/database/status - 数据库状态",
            "/api/data-source/list - 数据源列表",
            "/api/cache/status - 缓存状态"
        ]
        for api in critical_apis:
            self.log(f"  - {api}")

    def create_gitignore_entries(self):
        """添加gitignore条目"""
        self.log("=== 更新.gitignore ===")

        gitignore_path = self.project_root / ".gitignore"
        new_entries = [
            "\n# Data files",
            "data/*.db",
            "data/*.duckdb",
            "data/*.parquet",
            "data/logs/*",
            "\n# Large installers",
            "installer/*.whl",
            "\n# Experimental",
            "*_refactored.py",
            "*_optimized.py",
            "*_extended.py"
        ]

        if not self.dry_run:
            with open(gitignore_path, 'a', encoding='utf-8') as f:
                for entry in new_entries:
                    f.write(entry + "\n")

        self.log(f"添加了{len(new_entries)}个.gitignore条目")

    def generate_todo_issues(self):
        """生成TODO的GitHub Issues"""
        self.log("=== 生成GitHub Issues建议 ===")

        todos = [
            ("集成外部告警系统", "provider_health.py:301", "enhancement"),
            ("获取数据提供者实例", "engine.py:314", "bug"),
            ("实现订阅恢复", "amazingdata.py:509", "enhancement")
        ]

        self.log("建议创建的GitHub Issues：")
        for title, location, label in todos:
            self.log(f"  - [{label}] {title} ({location})")

    def run(self, dry_run=False):
        """执行P1级清理"""
        self.dry_run = dry_run

        print("="*60)
        print("P1级深度清理" + (" - 模拟模式" if dry_run else ""))
        print("="*60)

        # 执行清理任务
        self.cleanup_installer_docs()
        self.mark_experimental_files()
        self.analyze_component_migration()
        self.cleanup_unused_refactored()
        self.generate_api_cleanup_list()
        self.create_gitignore_entries()
        self.generate_todo_issues()

        # 生成报告
        self.save_report()

    def save_report(self):
        """保存清理报告"""
        report_path = self.project_root / "docs" / "P1_CLEANUP_REPORT.md"

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# P1级清理执行报告\n\n")
            f.write(f"执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"模式：{'模拟' if self.dry_run else '实际执行'}\n\n")
            f.write("## 执行日志\n\n```\n")
            f.write("\n".join(self.report))
            f.write("\n```\n")

        self.log(f"\n报告已保存到: {report_path}")


if __name__ == "__main__":
    import sys

    # 检查命令行参数
    dry_run = "--dry-run" in sys.argv

    if not dry_run:
        print("⚠️  警告：即将执行实际清理操作！")
        print("建议先使用 --dry-run 参数进行模拟运行")
        response = input("确认执行？(y/N): ")
        if response.lower() != 'y':
            print("已取消")
            sys.exit(0)

    cleanup = P1Cleanup()
    cleanup.run(dry_run=dry_run)