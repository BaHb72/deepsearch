#!/usr/bin/env python
"""
DeepSearch 自动化测试运行器。

默认运行可重复、可本地快速验证的测试；真实外部集成测试必须显式开启。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import psutil

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


SUMMARY_PATTERN = re.compile(r"(?P<count>\d+)\s+(?P<status>passed|failed|skipped|errors|error)")
DEFAULT_SUITE_TIMEOUTS = {
    "单元测试": 900,
    "API测试": 900,
    "集成测试": 600,
    "性能测试": 900,
    "安全测试": 600,
    "代码质量": 600,
}


class TestRunner:
    """测试运行器主类。"""

    def __init__(self, args: argparse.Namespace):
        self.root_dir = Path(__file__).parent.parent.resolve()
        self.args = args
        self.results: dict[str, dict[str, object]] = {}
        self.start_time: float | None = None
        self.suite_failures = 0
        self.test_stats = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0}
        self.xdist_available = self._is_xdist_available()
        self.parallel_warning_emitted = False

    def print_banner(self) -> None:
        print(f"{Colors.HEADER}{Colors.BOLD}")
        print("=" * 80)
        print("   DeepSearch 自动化测试系统 v1.1   ")
        print("=" * 80)
        print(f"{Colors.ENDC}")

    def check_environment(self) -> bool:
        print(f"{Colors.OKCYAN}[检查] 检查测试环境...{Colors.ENDC}")

        checks: list[tuple[str, Callable[[], tuple[bool, str]]]] = [
            ("Python版本", self._check_python_version),
            ("Pytest安装", self._check_pytest),
            ("项目依赖", self._check_dependencies),
            ("测试目录", self._check_test_directories),
        ]

        all_passed = True
        for name, check_func in checks:
            passed, message = check_func()
            if passed:
                print(f"  [PASS] {name}: {message}")
            else:
                print(f"  [FAIL] {name}: {message}")
                all_passed = False

        return all_passed

    def _check_python_version(self) -> tuple[bool, str]:
        version = sys.version_info
        if version >= (3, 14):
            return True, f"Python {version.major}.{version.minor}.{version.micro}"
        return False, f"需要 Python 3.14, 当前: {version.major}.{version.minor}"

    def _check_pytest(self) -> tuple[bool, str]:
        result = self._run_process(
            [sys.executable, "-m", "pytest", "--version"],
            "环境检查",
            timeout=30,
        )
        if result.returncode == 0:
            version = result.stdout.split()[1] if result.stdout.split() else "unknown"
            return True, f"版本 {version}"
        return False, "pytest 未正确安装"

    def _check_dependencies(self) -> tuple[bool, str]:
        try:
            if importlib.util.find_spec("core") is None:
                raise ImportError("core 未安装")
            return True, "所有依赖已安装"
        except ImportError as exc:
            return False, f"缺少依赖: {exc}"

    def _check_test_directories(self) -> tuple[bool, str]:
        test_dir = self.root_dir / "tests"
        if test_dir.exists():
            test_files = list(test_dir.glob("**/*.py"))
            return True, f"找到 {len(test_files)} 个测试文件"
        return False, "测试目录不存在"

    def _is_xdist_available(self) -> bool:
        try:
            return importlib.util.find_spec("xdist") is not None
        except Exception:
            return False

    def _test_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["APP__ENV"] = "test"
        return env

    def _suite_timeout(self, suite_name: str) -> int:
        if self.args.suite_timeout and self.args.suite_timeout > 0:
            return self.args.suite_timeout
        return DEFAULT_SUITE_TIMEOUTS.get(suite_name, 600)

    def _pytest_cmd(self, *args: str) -> list[str]:
        return [sys.executable, "-m", "pytest", *args]

    def _apply_parallel_option(self, cmd: list[str], test_name: str, workers: str = "auto") -> None:
        if not self.args.parallel:
            return
        if self.xdist_available:
            cmd.extend(["-n", workers])
        elif not self.parallel_warning_emitted:
            print(f"  [WARN] 未检测到 pytest-xdist，{test_name} 将以串行模式运行")
            self.parallel_warning_emitted = True

    def _terminate_process_tree(self, process: subprocess.Popen[str]) -> None:
        try:
            parent = psutil.Process(process.pid)
            processes = parent.children(recursive=True)
            processes.append(parent)
            for proc in processes:
                try:
                    proc.terminate()
                except psutil.Error:
                    continue
            _, alive = psutil.wait_procs(processes, timeout=5)
            for proc in alive:
                try:
                    proc.kill()
                except psutil.Error:
                    continue
        except psutil.Error:
            if process.poll() is None:
                process.kill()

    def _run_process(
        self,
        cmd: list[str],
        suite_name: str,
        *,
        timeout: int | None = None,
    ) -> CommandResult:
        timeout_seconds = timeout if timeout is not None else self._suite_timeout(suite_name)
        process = subprocess.Popen(
            cmd,
            cwd=self.root_dir,
            env=self._test_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            return CommandResult(process.returncode, stdout or "", stderr or "")
        except subprocess.TimeoutExpired:
            self._terminate_process_tree(process)
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stdout, stderr = "", ""
            return CommandResult(
                returncode=124,
                stdout=stdout or "",
                stderr=stderr or "",
                timed_out=True,
            )

    def run_unit_tests(self) -> bool:
        print(f"\n{Colors.OKBLUE}[UNIT] 运行单元测试...{Colors.ENDC}")
        cmd = self._pytest_cmd(
            "tests/unit",
            "-v" if self.args.verbose else "-q",
            "--tb=short",
            "--cov=core",
            "--cov-report=term-missing:skip-covered",
            "--cov-report=html:htmlcov",
            "--cov-report=xml",
            "-m",
            "not slow",
        )
        self._apply_parallel_option(cmd, "单元测试")
        return self._run_test_command(cmd, "单元测试")

    def run_api_tests(self) -> bool:
        print(f"\n{Colors.OKBLUE}[API] 运行 API 接口测试...{Colors.ENDC}")
        cmd = self._pytest_cmd(
            "tests/api",
            "-v" if self.args.verbose else "-q",
            "--tb=short",
            "--no-cov",
        )
        self._apply_parallel_option(cmd, "API测试", workers="4")
        return self._run_test_command(cmd, "API测试")

    def run_integration_tests(self) -> bool:
        print(f"\n{Colors.OKBLUE}[集成] 运行集成测试...{Colors.ENDC}")
        markers = ["integration"]
        if not self.args.include_external:
            markers.append("not external")
        if not self.args.include_manual:
            markers.append("not manual")

        cmd = self._pytest_cmd(
            "tests/integration",
            "-v" if self.args.verbose else "-q",
            "--tb=short",
            "--no-cov",
            "-m",
            " and ".join(markers),
        )
        return self._run_test_command(cmd, "集成测试")

    def run_performance_tests(self) -> bool:
        if not self.args.performance:
            print(f"\n{Colors.WARNING}[PERF] 跳过性能测试 (使用 --performance 启用){Colors.ENDC}")
            return True

        print(f"\n{Colors.OKBLUE}[PERF] 运行性能测试...{Colors.ENDC}")
        cmd = self._pytest_cmd(
            "tests/performance", "--benchmark-only", "--benchmark-json=benchmark.json"
        )
        return self._run_test_command(cmd, "性能测试")

    def run_security_tests(self) -> bool:
        if not self.args.security:
            print(f"\n{Colors.WARNING}[安全] 跳过安全测试 (使用 --security 启用){Colors.ENDC}")
            return True

        print(f"\n{Colors.OKBLUE}[安全] 运行安全扫描...{Colors.ENDC}")
        report_path = self.root_dir / "security_report.json"
        cmd = [
            sys.executable,
            "-m",
            "bandit",
            "-r",
            "packages/core",
            "-f",
            "json",
            "-o",
            str(report_path),
        ]
        result = self._run_process(cmd, "安全测试")

        if result.timed_out:
            print("  [FAIL] 安全扫描超时，已清理子进程")
            return False
        if result.returncode not in {0, 1}:
            print("  [FAIL] 安全扫描执行失败")
            return False

        if report_path.exists():
            with report_path.open(encoding="utf-8") as file:
                report = json.load(file)
            issues = report.get("results", [])
            if issues:
                print(f"  [WARN] 发现 {len(issues)} 个安全问题")
                for issue in issues[:5]:
                    print(f"    - {issue['issue_text']}")
                return False
            print("  [PASS] 未发现安全问题")
            return True
        return result.returncode == 0

    def _parse_pytest_stats(self, output: str) -> dict[str, int]:
        stats = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
        for match in SUMMARY_PATTERN.finditer(output):
            count = int(match.group("count"))
            status = match.group("status")
            if status == "error":
                status = "errors"
            stats[status] += count
        return stats

    def _run_test_command(self, cmd: list[str], test_name: str) -> bool:
        result = self._run_process(cmd, test_name)
        output = result.stdout or ""
        error_output = result.stderr or ""

        if self.args.verbose:
            print(output)
            if error_output:
                print(error_output)

        stats = self._parse_pytest_stats(output)
        self.test_stats["passed"] += stats["passed"]
        self.test_stats["failed"] += stats["failed"]
        self.test_stats["skipped"] += stats["skipped"]
        self.test_stats["errors"] += stats["errors"]
        self.test_stats["total"] += stats["passed"] + stats["failed"] + stats["skipped"]

        no_tests_collected = result.returncode == 5
        passed_flag = result.returncode == 0 or no_tests_collected
        self.results[test_name] = {
            "passed": passed_flag,
            "stats": stats,
            "timed_out": result.timed_out,
        }

        if result.timed_out:
            print(f"  [FAIL] {test_name}超过 {self._suite_timeout(test_name)} 秒，已清理子进程树")
            return False

        if no_tests_collected:
            print(f"  [SKIP] {test_name}未收集到测试用例（pytest exit code 5）")
            return True

        if result.returncode == 0:
            print(
                f"  [PASS] {test_name}通过 ({stats['passed']} passed, {stats['skipped']} skipped)"
            )
            return True

        print(f"  [FAIL] {test_name}失败 ({stats['failed']} failed, {stats['errors']} errors)")
        if not self.args.verbose:
            print("     使用 --verbose 查看详细信息")
        detail_source = error_output if error_output.strip() else output
        detail_lines = [line.strip() for line in detail_source.splitlines() if line.strip()]
        if detail_lines:
            print(f"     关键错误: {detail_lines[0]}")
        return False

    def run_linting(self) -> bool:
        print(f"\n{Colors.OKBLUE}[LINT] 运行代码质量检查...{Colors.ENDC}")
        linters = [
            ("Black格式化", [sys.executable, "-m", "black", "--check", "packages/core", "apps"]),
            (
                "isort导入排序",
                [sys.executable, "-m", "isort", "--check-only", "packages/core", "apps"],
            ),
            ("Ruff检查", [sys.executable, "-m", "ruff", "check", "packages/core", "apps"]),
        ]

        all_passed = True
        for name, cmd in linters:
            result = self._run_process(cmd, "代码质量")
            if result.timed_out:
                print(f"  [FAIL] {name}超时，已清理子进程")
                all_passed = False
                continue
            if result.returncode == 0:
                print(f"  [PASS] {name}通过")
                continue

            print(f"  [FAIL] {name}失败")
            if self.args.fix:
                print("     尝试自动修复...")
                fix_cmd = cmd.copy()
                if "--check" in fix_cmd:
                    fix_cmd.remove("--check")
                if "--check-only" in fix_cmd:
                    fix_cmd.remove("--check-only")
                if "ruff" in fix_cmd:
                    fix_cmd.append("--fix")
                self._run_process(fix_cmd, "代码质量")
            all_passed = False

        self.results["代码质量"] = {"passed": all_passed}
        return all_passed

    def generate_report(self) -> None:
        print(f"\n{Colors.OKCYAN}[统计] 生成测试报告...{Colors.ENDC}")

        coverage_index = self.root_dir / "htmlcov" / "index.html"
        if coverage_index.exists():
            print(f"  [统计] 覆盖率报告: {coverage_index}")

        reports_dir = self.root_dir / "reports" / "test_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_file = reports_dir / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "duration": time.time() - self.start_time if self.start_time else 0,
            "stats": self.test_stats,
            "results": self.results,
            "environment": {
                "python_version": (
                    f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
                ),
                "platform": sys.platform,
                "app_env": "test",
            },
        }

        with report_file.open("w", encoding="utf-8") as file:
            json.dump(report_data, file, indent=2, ensure_ascii=False)

        relative_report_path = report_file.relative_to(self.root_dir)
        print(f"  [报告] 测试报告: {relative_report_path}")

    def print_summary(self) -> None:
        print(f"\n{Colors.HEADER}{'=' * 80}{Colors.ENDC}")
        print(f"{Colors.BOLD}测试执行摘要{Colors.ENDC}")
        print(f"{Colors.HEADER}{'=' * 80}{Colors.ENDC}")

        if self.start_time:
            duration = time.time() - self.start_time
            print(f"\n[TIME] 总耗时: {duration:.2f} 秒")

        print("\n[统计] 测试统计:")
        print(f"  - 总计: {self.test_stats['total']} 个测试")
        print(f"  - [PASS] 通过: {self.test_stats['passed']}")
        print(f"  - [FAIL] 失败: {self.test_stats['failed']}")
        print(f"  - [SKIP] 跳过: {self.test_stats['skipped']}")
        print(f"  - [错误] 错误: {self.test_stats['errors']}")

        coverage_file = self.root_dir / "coverage.xml"
        if coverage_file.exists():
            try:
                import xml.etree.ElementTree as ET

                tree = ET.parse(coverage_file)
                root = tree.getroot()
                coverage = float(root.get("line-rate", 0)) * 100
                print(f"\n[统计] 代码覆盖率: {coverage:.1f}%")
            except Exception:
                pass

        print("\n[详情] 详细结果:")
        for name, result in self.results.items():
            status = "[PASS]" if result["passed"] else "[FAIL]"
            print(f"  {status} {name}")

        if self.suite_failures == 0:
            print(f"\n{Colors.OKGREEN}{Colors.BOLD}[PASS] 所有测试通过{Colors.ENDC}")
        else:
            print(f"\n{Colors.FAIL}{Colors.BOLD}[FAIL] 存在测试失败{Colors.ENDC}")

    def run_all(self) -> int:
        self.start_time = time.time()
        self.print_banner()

        if not self.check_environment():
            print(f"\n{Colors.FAIL}环境检查失败，请修复问题后重试{Colors.ENDC}")
            return 1

        test_suites: list[tuple[str, Callable[[], bool]]] = [
            ("单元测试", self.run_unit_tests),
            ("API测试", self.run_api_tests),
            ("集成测试", self.run_integration_tests),
            ("性能测试", self.run_performance_tests),
            ("安全测试", self.run_security_tests),
            ("代码质量", self.run_linting),
        ]

        for name, test_func in test_suites:
            if self.args.skip and name in self.args.skip:
                print(f"\n{Colors.WARNING}[SKIP] 跳过 {name}{Colors.ENDC}")
                continue
            if self.args.only and name not in self.args.only:
                continue

            suite_passed = bool(test_func())
            if name not in self.results:
                self.results[name] = {"passed": suite_passed}
            else:
                self.results[name]["passed"] = (
                    bool(self.results[name].get("passed", False)) and suite_passed
                )

            if not suite_passed:
                self.suite_failures += 1

            if self.args.fail_fast and self.suite_failures > 0:
                print(f"\n{Colors.FAIL}快速失败模式：检测到失败，停止执行{Colors.ENDC}")
                break

        self.generate_report()
        self.print_summary()
        return 0 if self.suite_failures == 0 else 1


def _merge_skip(existing: list[str] | None, additions: list[str]) -> list[str]:
    ordered = list(existing or [])
    for item in additions:
        if item not in ordered:
            ordered.append(item)
    return ordered


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepSearch 自动化测试运行器")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细输出")
    parser.add_argument("--parallel", "-p", action="store_true", help="并行运行测试")
    parser.add_argument("--performance", action="store_true", help="运行性能测试")
    parser.add_argument("--security", action="store_true", help="运行安全扫描")
    parser.add_argument("--fail-fast", "-x", action="store_true", help="首次失败后停止")
    parser.add_argument("--fix", action="store_true", help="自动修复代码格式问题")
    parser.add_argument("--skip", nargs="+", help="跳过指定的测试类型")
    parser.add_argument("--only", nargs="+", help="只运行指定的测试类型")
    parser.add_argument("--quick", action="store_true", help="快速测试模式（跳过性能和安全测试）")
    parser.add_argument(
        "--include-external",
        action="store_true",
        help="允许运行 external 集成测试",
    )
    parser.add_argument(
        "--include-manual",
        action="store_true",
        help="允许运行 manual 集成测试",
    )
    parser.add_argument(
        "--suite-timeout",
        type=int,
        default=None,
        help="覆盖单个测试 suite 的兜底超时秒数",
    )

    args = parser.parse_args()
    if args.quick:
        args.skip = _merge_skip(args.skip, ["性能测试", "安全测试"])
        args.parallel = True

    runner = TestRunner(args)
    sys.exit(runner.run_all())


if __name__ == "__main__":
    main()
