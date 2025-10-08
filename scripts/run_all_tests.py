#!/usr/bin/env python
"""
DeepSearch 自动化测试运行器
一键启动所有测试，并生成完整的测试报告
"""
import argparse
import importlib.util
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ANSI颜色码
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class TestRunner:
    """测试运行器主类"""

    def __init__(self, args):
        self.root_dir = Path(__file__).parent.parent
        self.args = args
        self.results = {}
        self.start_time = None
        self.test_stats = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0}
        self.xdist_available = self._is_xdist_available()
        self.parallel_warning_emitted = False

    def print_banner(self):
        """打印欢迎横幅"""
        print(f"{Colors.HEADER}{Colors.BOLD}")
        print("=" * 80)
        print("   DeepSearch 自动化测试系统 v1.0   ")
        print("=" * 80)
        print(f"{Colors.ENDC}")

    def check_environment(self) -> bool:
        """检查测试环境"""
        print(f"{Colors.OKCYAN}[检查] 检查测试环境...{Colors.ENDC}")

        checks = [
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

    def _check_python_version(self) -> Tuple[bool, str]:
        """检查Python版本"""
        version = sys.version_info
        if version >= (3, 12):
            return True, f"Python {version.major}.{version.minor}.{version.micro}"
        return False, f"需要Python 3.12+, 当前: {version.major}.{version.minor}"

    def _check_pytest(self) -> Tuple[bool, str]:
        """检查pytest是否安装"""
        try:
            result = subprocess.run(["pytest", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.split()[1]
                return True, f"版本 {version}"
            return False, "pytest未正确安装"
        except FileNotFoundError:
            return False, "pytest未安装"

    def _check_dependencies(self) -> Tuple[bool, str]:
        """检查项目依赖"""
        try:

            if importlib.util.find_spec("deepsearch") is None:
                raise ImportError("deepsearch 未安装")

            return True, "所有依赖已安装"
        except ImportError as e:
            return False, f"缺少依赖: {e}"

    def _check_test_directories(self) -> Tuple[bool, str]:
        """检查测试目录"""
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

    def _apply_parallel_option(self, cmd: List[str], test_name: str, workers: str = "auto") -> None:
        if not self.args.parallel:
            return
        if self.xdist_available:
            cmd.extend(["-n", workers])
        elif not self.parallel_warning_emitted:
            print(f"  [WARN] 未检测到 pytest-xdist，{test_name} 将以串行模式运行")
            self.parallel_warning_emitted = True

    def run_unit_tests(self) -> bool:
        """运行单元测试"""
        print(f"\n{Colors.OKBLUE}[UNIT] 运行单元测试...{Colors.ENDC}")

        cmd = [
            "pytest",
            "tests/unit",
            "-v" if self.args.verbose else "-q",
            "--tb=short",
            "--cov=deepsearch",
            "--cov-report=term-missing:skip-covered",
            "--cov-report=html:htmlcov",
            "--cov-report=xml",
            "-m",
            "not slow",  # 跳过慢速测试
        ]

        self._apply_parallel_option(cmd, "单元测试")

        return self._run_test_command(cmd, "单元测试")

    def run_api_tests(self) -> bool:
        """运行API测试"""
        print(f"\n{Colors.OKBLUE}[API] 运行API接口测试...{Colors.ENDC}")

        cmd = ["pytest", "tests/api", "-v" if self.args.verbose else "-q", "--tb=short"]

        self._apply_parallel_option(cmd, "API测试", workers="4")

        return self._run_test_command(cmd, "API测试")

    def run_integration_tests(self) -> bool:
        """运行集成测试"""
        print(f"\n{Colors.OKBLUE}[集成] 运行集成测试...{Colors.ENDC}")

        cmd = [
            "pytest",
            "tests/integration",
            "-v" if self.args.verbose else "-q",
            "--tb=short",
            "-m",
            "integration",
        ]

        return self._run_test_command(cmd, "集成测试")

    def run_performance_tests(self) -> bool:
        """运行性能测试"""
        if not self.args.performance:
            print(f"\n{Colors.WARNING}[PERF] 跳过性能测试 (使用 --performance 启用){Colors.ENDC}")
            return True

        print(f"\n{Colors.OKBLUE}[PERF] 运行性能测试...{Colors.ENDC}")

        cmd = ["pytest", "tests/performance", "--benchmark-only", "--benchmark-json=benchmark.json"]

        return self._run_test_command(cmd, "性能测试")

    def run_security_tests(self) -> bool:
        """运行安全测试"""
        if not self.args.security:
            print(f"\n{Colors.WARNING}[安全] 跳过安全测试 (使用 --security 启用){Colors.ENDC}")
            return True

        print(f"\n{Colors.OKBLUE}[安全] 运行安全扫描...{Colors.ENDC}")

        # 运行bandit安全扫描
        cmd = ["bandit", "-r", "deepsearch", "-f", "json", "-o", "security_report.json"]

        subprocess.run(cmd, capture_output=True, text=True, check=False)

        # 解析结果
        if Path("security_report.json").exists():
            with open("security_report.json") as f:
                report = json.load(f)
                issues = report.get("results", [])
                if issues:
                    print(f"  [WARN]  发现 {len(issues)} 个安全问题")
                    for issue in issues[:5]:  # 只显示前5个
                        print(f"    - {issue['issue_text']}")
                    return False
                else:
                    print("  [PASS] 未发现安全问题")
                    return True
        return True

    def _run_test_command(self, cmd: List[str], test_name: str) -> bool:
        """运行测试命令并解析结果"""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )

            # 解析pytest输出
            output = result.stdout or ""
            error_output = result.stderr or ""
            if self.args.verbose:
                print(output)

            # 提取测试统计
            passed = failed = skipped = errors = 0
            for line in output.split("\n"):
                if "passed" in line and "failed" in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if "passed" in part and i > 0:
                            passed = int(parts[i - 1])
                        elif "failed" in part and i > 0:
                            failed = int(parts[i - 1])
                        elif "skipped" in part and i > 0:
                            skipped = int(parts[i - 1])
                        elif "error" in part and i > 0:
                            errors = int(parts[i - 1])

            # 更新统计
            self.test_stats["passed"] += passed
            self.test_stats["failed"] += failed
            self.test_stats["skipped"] += skipped
            self.test_stats["errors"] += errors
            self.test_stats["total"] += passed + failed + skipped

            exit_code = result.returncode
            no_tests_collected = exit_code == 5
            passed_flag = exit_code == 0 or no_tests_collected

            self.results[test_name] = {
                "passed": passed_flag,
                "stats": {"passed": passed, "failed": failed, "skipped": skipped, "errors": errors},
            }

            if no_tests_collected:
                print(f"  [SKIP] {test_name}未收集到测试用例（pytest exit code 5）")
                return True

            if exit_code == 0:
                print(f"  [PASS] {test_name}通过 ({passed} passed, {skipped} skipped)")
                return True

            print(f"  [FAIL] {test_name}失败 ({failed} failed, {errors} errors)")
            if not self.args.verbose:
                print("     使用 --verbose 查看详细信息")
            detail_source = error_output if error_output.strip() else output
            detail_lines = [line.strip() for line in detail_source.splitlines() if line.strip()]
            if detail_lines:
                print(f"     关键错误: {detail_lines[0]}")
            return False

        except Exception as e:
            print(f"  [FAIL] {test_name}执行出错: {e}")
            self.results[test_name] = {"passed": False, "error": str(e)}
            return False

    def run_linting(self) -> bool:
        """运行代码质量检查"""
        print(f"\n{Colors.OKBLUE}[LINT] 运行代码质量检查...{Colors.ENDC}")

        linters = [
            ("Black格式化", ["black", "--check", "deepsearch"]),
            ("isort导入排序", ["isort", "--check-only", "deepsearch"]),
            ("Ruff检查", ["ruff", "check", "deepsearch"]),
        ]

        all_passed = True
        for name, cmd in linters:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  [PASS] {name}通过")
            else:
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
                    subprocess.run(fix_cmd)
                all_passed = False

        return all_passed

    def generate_report(self):
        """生成测试报告"""
        print(f"\n{Colors.OKCYAN}[统计] 生成测试报告...{Colors.ENDC}")

        # HTML覆盖率报告
        if Path("htmlcov/index.html").exists():
            print(f"  [统计] 覆盖率报告: file://{Path('htmlcov/index.html').absolute()}")

        # JSON测试结果
        reports_dir = self.root_dir / "reports" / "test_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_file = reports_dir / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "duration": time.time() - self.start_time if self.start_time else 0,
            "stats": self.test_stats,
            "results": self.results,
            "environment": {
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "platform": sys.platform,
            },
        }

        with report_file.open("w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        relative_report_path = report_file.relative_to(self.root_dir)
        print(f"  [报告] 测试报告: {relative_report_path}")

    def print_summary(self):
        """打印测试摘要"""
        print(f"\n{Colors.HEADER}{'=' * 80}{Colors.ENDC}")
        print(f"{Colors.BOLD}测试执行摘要{Colors.ENDC}")
        print(f"{Colors.HEADER}{'=' * 80}{Colors.ENDC}")

        # 时间统计
        if self.start_time:
            duration = time.time() - self.start_time
            print(f"\n[TIME]  总耗时: {duration:.2f} 秒")

        # 测试统计
        print("\n[统计] 测试统计:")
        print(f"  - 总计: {self.test_stats['total']} 个测试")
        print(f"  - [PASS] 通过: {self.test_stats["passed"]}")
        print(f"  - [FAIL] 失败: {self.test_stats["failed"]}")
        print(f"  - [SKIP]  跳过: {self.test_stats["skipped"]}")
        print(f"  - [错误] 错误: {self.test_stats["errors"]}")

        # 覆盖率
        if Path("coverage.xml").exists():
            try:
                import xml.etree.ElementTree as ET

                tree = ET.parse("coverage.xml")
                root = tree.getroot()
                coverage = float(root.get("line-rate", 0)) * 100
                print(f"\n[统计] 代码覆盖率: {coverage:.1f}%")
            except Exception:
                pass

        # 各测试结果
        print("\n[详情] 详细结果:")
        for name, result in self.results.items():
            status = "[PASS]" if result["passed"] else "[FAIL]"
            print(f"  {status} {name}")

        # 最终结论
        all_passed = all(r["passed"] for r in self.results.values())
        if all_passed:
            print(f"\n{Colors.OKGREEN}{Colors.BOLD}[PASS] 所有测试通过！{Colors.ENDC}")
        else:
            print(f"\n{Colors.FAIL}{Colors.BOLD}[FAIL] 存在测试失败{Colors.ENDC}")

    def run_all(self) -> int:
        """运行所有测试"""
        self.start_time = time.time()
        self.print_banner()

        # 环境检查
        if not self.check_environment():
            print(f"\n{Colors.FAIL}环境检查失败，请修复问题后重试{Colors.ENDC}")
            return 1

        # 运行测试套件
        test_suites = [
            ("单元测试", self.run_unit_tests),
            ("API测试", self.run_api_tests),
            ("集成测试", self.run_integration_tests),
            ("性能测试", self.run_performance_tests),
            ("安全测试", self.run_security_tests),
            ("代码质量", self.run_linting),
        ]

        for name, test_func in test_suites:
            if self.args.skip and name in self.args.skip:
                print(f"\n{Colors.WARNING}[SKIP]  跳过 {name}{Colors.ENDC}")
                continue

            if self.args.only and name not in self.args.only:
                continue

            test_func()

            if self.args.fail_fast and self.test_stats["failed"] > 0:
                print(f"\n{Colors.FAIL}快速失败模式：检测到失败，停止执行{Colors.ENDC}")
                break

        # 生成报告
        self.generate_report()

        # 打印摘要
        self.print_summary()

        # 返回退出码
        return 0 if self.test_stats["failed"] == 0 else 1


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="DeepSearch 自动化测试运行器")

    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细输出")

    parser.add_argument("--parallel", "-p", action="store_true", help="并行运行测试")

    parser.add_argument("--performance", action="store_true", help="运行性能测试")

    parser.add_argument("--security", action="store_true", help="运行安全扫描")

    parser.add_argument("--fail-fast", "-x", action="store_true", help="首次失败后停止")

    parser.add_argument("--fix", action="store_true", help="自动修复代码格式问题")

    parser.add_argument("--skip", nargs="+", help="跳过指定的测试类型")

    parser.add_argument("--only", nargs="+", help="只运行指定的测试类型")

    parser.add_argument("--quick", action="store_true", help="快速测试模式（跳过慢速测试）")

    args = parser.parse_args()

    # 快速模式设置
    if args.quick:
        args.skip = ["性能测试", "安全测试"]
        args.parallel = True

    # 运行测试
    runner = TestRunner(args)
    sys.exit(runner.run_all())


if __name__ == "__main__":
    main()
