"""
AkShare API 全面验证脚本
系统地测试所有AkShare API接口，记录成功/失败状态和性能指标
"""

import inspect
import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    import akshare as ak
    import pandas as pd
    from loguru import logger
    from tqdm import tqdm
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please install: pip install akshare pandas tqdm loguru")
    sys.exit(1)


class AkShareAPIValidator:
    """AkShare API 验证器"""

    def __init__(self, checkpoint_file: str = "akshare_validation_checkpoint.json"):
        self.checkpoint_file = checkpoint_file
        self.results = []
        self.checkpoint_data = self.load_checkpoint()
        self.start_time = datetime.now()

        # 配置日志
        logger.remove()
        logger.add(
            "akshare_validation_{time}.log",
            rotation="100 MB",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            encoding="utf-8",
        )
        logger.add(
            sys.stdout,
            level="INFO",
            format="{time:HH:mm:ss} | {level} | {message}",
            colorize=False,  # 避免Windows控制台编码问题
        )

        # API分类
        self.api_categories = {
            "stock": [],  # 股票
            "index": [],  # 指数
            "fund": [],  # 基金
            "bond": [],  # 债券
            "futures": [],  # 期货
            "option": [],  # 期权
            "forex": [],  # 外汇
            "crypto": [],  # 加密货币
            "macro": [],  # 宏观经济
            "bank": [],  # 银行
            "article": [],  # 文章
            "nlp": [],  # NLP
            "tool": [],  # 工具
            "other": [],  # 其他
        }

        # 测试参数配置
        self.test_params = {
            # 股票相关默认参数
            "symbol": "000001",
            "stock": "000001",
            "code": "000001",
            # 日期相关参数
            "date": datetime.now().strftime("%Y%m%d"),
            "start_date": (datetime.now() - timedelta(days=30)).strftime("%Y%m%d"),
            "end_date": datetime.now().strftime("%Y%m%d"),
            "trade_date": datetime.now().strftime("%Y%m%d"),
            # 周期参数
            "period": "daily",
            "frequency": "daily",
            "interval": "1",
            # 复权参数
            "adjust": "",
            "adj": "",
            # 指数参数
            "index": "000001",
            "index_type": "000001",
            # 基金参数
            "fund": "000001",
            # 限制参数
            "limit": 100,
            "page": 1,
            "pagesize": 100,
            # 分类参数
            "indicator": "全部",
            "market": "全部",
            "exchange": "全部",
            # 板块参数
            "sector": "银行",
            "industry": "银行",
            "concept": "人工智能",
        }

    def load_checkpoint(self) -> Dict:
        """加载检查点数据"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load checkpoint: {e}")
        return {"tested": [], "results": []}

    def save_checkpoint(self):
        """保存检查点数据"""
        try:
            self.checkpoint_data["tested"] = [r["function_name"] for r in self.results]
            self.checkpoint_data["results"] = self.results
            self.checkpoint_data["last_update"] = datetime.now().isoformat()

            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(self.checkpoint_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def discover_apis(self) -> Dict[str, List[str]]:
        """发现所有AkShare API函数"""
        logger.info("Discovering AkShare APIs...")

        # 获取所有akshare模块的成员
        all_members = dir(ak)

        # 按类别分组
        for member_name in all_members:
            if member_name.startswith("_"):
                continue

            # 获取成员对象
            try:
                member = getattr(ak, member_name)
                if not callable(member):
                    continue
            except Exception:
                continue

            # 分类
            if member_name.startswith("stock_"):
                self.api_categories["stock"].append(member_name)
            elif member_name.startswith("index_"):
                self.api_categories["index"].append(member_name)
            elif member_name.startswith("fund_"):
                self.api_categories["fund"].append(member_name)
            elif member_name.startswith("bond_"):
                self.api_categories["bond"].append(member_name)
            elif member_name.startswith("futures_"):
                self.api_categories["futures"].append(member_name)
            elif member_name.startswith("option_"):
                self.api_categories["option"].append(member_name)
            elif member_name.startswith("forex_") or member_name.startswith("currency_"):
                self.api_categories["forex"].append(member_name)
            elif member_name.startswith("crypto_"):
                self.api_categories["crypto"].append(member_name)
            elif member_name.startswith("macro_"):
                self.api_categories["macro"].append(member_name)
            elif member_name.startswith("bank_"):
                self.api_categories["bank"].append(member_name)
            elif member_name.startswith("article_") or member_name.startswith("news_"):
                self.api_categories["article"].append(member_name)
            elif member_name.startswith("nlp_"):
                self.api_categories["nlp"].append(member_name)
            elif member_name.startswith("tool_"):
                self.api_categories["tool"].append(member_name)
            else:
                # 其他可能的API函数
                if any(
                    keyword in member_name
                    for keyword in ["get", "fetch", "download", "query", "search", "find"]
                ):
                    self.api_categories["other"].append(member_name)

        # 统计
        total_apis = sum(len(apis) for apis in self.api_categories.values())
        logger.info(f"Found {total_apis} API functions")
        for category, apis in self.api_categories.items():
            if apis:
                logger.info(f"  {category}: {len(apis)} APIs")

        return self.api_categories

    def get_function_params(self, func_name: str) -> Tuple[List[str], Dict[str, Any]]:
        """获取函数参数信息"""
        try:
            func = getattr(ak, func_name)
            sig = inspect.signature(func)

            required_params = []
            optional_params = {}

            for param_name, param in sig.parameters.items():
                if param.default == inspect.Parameter.empty:
                    required_params.append(param_name)
                else:
                    optional_params[param_name] = param.default

            return required_params, optional_params
        except Exception as e:
            logger.debug(f"Failed to get params for {func_name}: {e}")
            return [], {}

    def generate_test_params(self, func_name: str, required_params: List[str]) -> Dict[str, Any]:
        """生成测试参数"""
        test_params = {}

        for param in required_params:
            # 尝试从预定义参数中匹配
            if param in self.test_params:
                test_params[param] = self.test_params[param]
            else:
                # 智能推断参数值
                param_lower = param.lower()

                # 日期类参数
                if any(word in param_lower for word in ["date", "time", "day"]):
                    if "start" in param_lower:
                        test_params[param] = self.test_params["start_date"]
                    elif "end" in param_lower:
                        test_params[param] = self.test_params["end_date"]
                    else:
                        test_params[param] = self.test_params["date"]

                # 股票代码类参数
                elif any(word in param_lower for word in ["symbol", "stock", "code", "ticker"]):
                    test_params[param] = "000001"

                # 周期类参数
                elif any(word in param_lower for word in ["period", "freq", "interval"]):
                    test_params[param] = "daily"

                # 页码类参数
                elif any(word in param_lower for word in ["page", "offset"]):
                    test_params[param] = 1

                # 数量限制类参数
                elif any(word in param_lower for word in ["limit", "size", "count", "num"]):
                    test_params[param] = 100

                # 市场类参数
                elif any(word in param_lower for word in ["market", "exchange"]):
                    test_params[param] = "全部"

                # 布尔类参数
                elif any(word in param_lower for word in ["is_", "has_", "enable", "flag"]):
                    test_params[param] = True

                # 默认字符串
                else:
                    test_params[param] = "test"

        return test_params

    def test_single_api(self, func_name: str, category: str) -> Dict:
        """测试单个API"""
        result = {
            "function_name": func_name,
            "category": category,
            "status": "unknown",
            "error": None,
            "response_time": None,
            "data_shape": None,
            "data_sample": None,
            "params_used": None,
            "timestamp": datetime.now().isoformat(),
        }

        # 检查是否已测试（断点续测）
        if func_name in self.checkpoint_data.get("tested", []):
            # 从检查点加载之前的结果
            for prev_result in self.checkpoint_data.get("results", []):
                if prev_result["function_name"] == func_name:
                    logger.info(f"Skipping {func_name} (already tested)")
                    return prev_result

        try:
            # 获取函数
            func = getattr(ak, func_name)

            # 获取参数信息
            required_params, optional_params = self.get_function_params(func_name)

            # 生成测试参数
            test_params = self.generate_test_params(func_name, required_params)
            result["params_used"] = test_params

            # 执行API调用
            logger.info(f"Testing {func_name} with params: {test_params}")
            start_time = time.time()

            # 设置超时
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError("API call timed out")

            # Windows不支持SIGALRM，使用线程超时
            if os.name == "nt":
                from concurrent.futures import (
                    ThreadPoolExecutor,
                )
                from concurrent.futures import TimeoutError as FutureTimeoutError

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(func, **test_params)
                    try:
                        data = future.result(timeout=30)  # 30秒超时
                    except FutureTimeoutError:
                        raise TimeoutError("API call timed out")
            else:
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)  # 30秒超时
                try:
                    data = func(**test_params)
                finally:
                    signal.alarm(0)

            response_time = time.time() - start_time
            result["response_time"] = round(response_time, 3)

            # 分析返回数据
            if data is not None:
                if isinstance(data, pd.DataFrame):
                    result["data_shape"] = list(data.shape)
                    result["status"] = "success"

                    # 保存数据样本（前5行）
                    if not data.empty:
                        sample = data.head(5).to_dict("records")
                        # 转换numpy类型为Python原生类型
                        result["data_sample"] = json.loads(
                            pd.DataFrame(sample).to_json(orient="records", force_ascii=False)
                        )
                elif isinstance(data, (list, dict)):
                    result["status"] = "success"
                    result["data_shape"] = len(data) if isinstance(data, list) else "dict"
                    result["data_sample"] = str(data)[:500]  # 限制长度
                else:
                    result["status"] = "success"
                    result["data_shape"] = type(data).__name__
                    result["data_sample"] = str(data)[:500]
            else:
                result["status"] = "empty"
                result["error"] = "Returned None or empty data"

            logger.success(f"Success: {func_name} succeeded in {response_time:.2f}s")

        except TimeoutError:
            result["status"] = "timeout"
            result["error"] = "API call timed out (30s)"
            logger.warning(f"Timeout: {func_name} timed out")

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            result["traceback"] = traceback.format_exc()
            logger.error(f"Failed: {func_name} failed: {str(e)[:100]}")

        return result

    def run_validation(self, categories: List[str] = None, max_workers: int = 5):
        """运行验证测试"""
        # 发现所有API
        self.discover_apis()

        # 确定要测试的类别
        if categories:
            test_categories = {k: v for k, v in self.api_categories.items() if k in categories}
        else:
            test_categories = self.api_categories

        # 统计总数
        total_apis = sum(len(apis) for apis in test_categories.values())
        logger.info(f"Starting validation of {total_apis} APIs...")

        # 使用进度条
        with tqdm(total=total_apis, desc="Testing APIs") as pbar:
            # 串行执行，避免并发问题
            for category, api_list in test_categories.items():
                if not api_list:
                    continue

                logger.info(f"\nTesting {category} APIs ({len(api_list)} functions)...")

                for func_name in api_list:
                    result = self.test_single_api(func_name, category)
                    self.results.append(result)

                    # 保存检查点
                    if len(self.results) % 10 == 0:
                        self.save_checkpoint()

                    pbar.update(1)
                    pbar.set_postfix(
                        {
                            "current": func_name,
                            "success": sum(1 for r in self.results if r["status"] == "success"),
                            "failed": sum(1 for r in self.results if r["status"] == "failed"),
                        }
                    )

                    # 避免请求过快
                    time.sleep(0.5)

        # 最终保存
        self.save_checkpoint()
        logger.info("Validation completed!")

    def generate_report(self) -> str:
        """生成验证报告"""
        report_lines = []

        # 报告标题
        report_lines.append("# AkShare API Validation Report")
        report_lines.append(f"\n**Generated at**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"**Total APIs Tested**: {len(self.results)}")
        report_lines.append(
            f"**Test Duration**: {(datetime.now() - self.start_time).total_seconds():.1f} seconds\n"
        )

        # 总体统计
        report_lines.append("## Overall Statistics\n")

        success_count = sum(1 for r in self.results if r["status"] == "success")
        failed_count = sum(1 for r in self.results if r["status"] == "failed")
        empty_count = sum(1 for r in self.results if r["status"] == "empty")
        timeout_count = sum(1 for r in self.results if r["status"] == "timeout")

        success_rate = (success_count / len(self.results) * 100) if self.results else 0

        report_lines.append(f"- **Success**: {success_count} ({success_rate:.1f}%)")
        report_lines.append(f"- **Failed**: {failed_count}")
        report_lines.append(f"- **Empty Response**: {empty_count}")
        report_lines.append(f"- **Timeout**: {timeout_count}")

        # 按类别统计
        report_lines.append("\n## Statistics by Category\n")

        category_stats = {}
        for result in self.results:
            category = result["category"]
            if category not in category_stats:
                category_stats[category] = {
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "empty": 0,
                    "timeout": 0,
                }

            category_stats[category]["total"] += 1
            if result["status"] == "success":
                category_stats[category]["success"] += 1
            elif result["status"] == "failed":
                category_stats[category]["failed"] += 1
            elif result["status"] == "empty":
                category_stats[category]["empty"] += 1
            elif result["status"] == "timeout":
                category_stats[category]["timeout"] += 1

        report_lines.append(
            "| Category | Total | Success | Failed | Empty | Timeout | Success Rate |"
        )
        report_lines.append(
            "|----------|-------|---------|--------|-------|---------|--------------|"
        )

        for category, stats in sorted(category_stats.items()):
            success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
            report_lines.append(
                f"| {category} | {stats['total']} | {stats['success']} | "
                f"{stats['failed']} | {stats['empty']} | {stats['timeout']} | {success_rate:.1f}% |"
            )

        # 性能分析
        report_lines.append("\n## Performance Analysis\n")

        successful_apis = [
            r for r in self.results if r["status"] == "success" and r["response_time"]
        ]
        if successful_apis:
            response_times = [r["response_time"] for r in successful_apis]
            avg_time = sum(response_times) / len(response_times)
            min_time = min(response_times)
            max_time = max(response_times)

            report_lines.append(f"- **Average Response Time**: {avg_time:.3f}s")
            report_lines.append(f"- **Fastest API**: {min_time:.3f}s")
            report_lines.append(f"- **Slowest API**: {max_time:.3f}s")

            # 找出最快和最慢的API
            fastest = min(successful_apis, key=lambda x: x["response_time"])
            slowest = max(successful_apis, key=lambda x: x["response_time"])

            report_lines.append(
                f"- **Fastest Function**: `{fastest['function_name']}` ({fastest['response_time']:.3f}s)"
            )
            report_lines.append(
                f"- **Slowest Function**: `{slowest['function_name']}` ({slowest['response_time']:.3f}s)"
            )

        # 失败的API详情
        failed_apis = [r for r in self.results if r["status"] == "failed"]
        if failed_apis:
            report_lines.append("\n## Failed APIs\n")

            # 按错误类型分组
            error_types = {}
            for api in failed_apis:
                error_type = api.get("error_type", "Unknown")
                if error_type not in error_types:
                    error_types[error_type] = []
                error_types[error_type].append(api)

            for error_type, apis in sorted(error_types.items()):
                report_lines.append(f"\n### {error_type} ({len(apis)} APIs)\n")
                for api in apis[:5]:  # 只显示前5个
                    report_lines.append(f"- **{api['function_name']}**: {api['error'][:100]}")
                if len(apis) > 5:
                    report_lines.append(f"- ... and {len(apis) - 5} more")

        # 推荐的可用API列表
        report_lines.append("\n## Recommended Available APIs\n")

        # 按类别组织成功的API
        for category in ["stock", "index", "fund", "macro"]:
            category_success = [
                r for r in self.results if r["category"] == category and r["status"] == "success"
            ]

            if category_success:
                report_lines.append(
                    f"\n### {category.capitalize()} APIs ({len(category_success)} available)\n"
                )

                # 按响应时间排序，推荐最快的
                category_success.sort(key=lambda x: x.get("response_time", float("inf")))

                for api in category_success[:10]:  # 显示前10个
                    params = api.get("params_used", {})
                    param_str = (
                        ", ".join([f"{k}={v}" for k, v in params.items()])
                        if params
                        else "no params"
                    )
                    report_lines.append(
                        f"- **{api['function_name']}** - {api.get('response_time', 'N/A')}s - ({param_str})"
                    )

                if len(category_success) > 10:
                    report_lines.append(f"- ... and {len(category_success) - 10} more")

        # 详细结果表格（可选）
        report_lines.append("\n## Detailed Results\n")
        report_lines.append("\n<details>")
        report_lines.append("<summary>Click to expand full API test results</summary>\n")
        report_lines.append("| Function | Category | Status | Response Time | Error |")
        report_lines.append("|----------|----------|--------|---------------|-------|")

        for result in sorted(self.results, key=lambda x: x["function_name"]):
            response_time = f"{result['response_time']:.3f}s" if result["response_time"] else "N/A"
            error = (
                result["error"][:50] + "..."
                if result["error"] and len(result["error"]) > 50
                else (result["error"] or "")
            )
            error = error.replace("|", "\\|").replace("\n", " ")

            report_lines.append(
                f"| {result['function_name']} | {result['category']} | "
                f"{result['status']} | {response_time} | {error} |"
            )

        report_lines.append("\n</details>")

        # 建议和注意事项
        report_lines.append("\n## Recommendations\n")
        report_lines.append(
            "1. **Use cached data** for frequently accessed APIs to reduce server load"
        )
        report_lines.append("2. **Implement retry logic** for failed APIs with exponential backoff")
        report_lines.append("3. **Monitor API changes** regularly as some endpoints may be updated")
        report_lines.append("4. **Use batch requests** where possible to improve efficiency")
        report_lines.append("5. **Respect rate limits** to avoid being blocked")

        return "\n".join(report_lines)

    def save_report(self, filename: str = None):
        """保存报告到文件"""
        if filename is None:
            filename = (
                f"AKSHARE_API_VALIDATION_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            )

        report_content = self.generate_report()

        with open(filename, "w", encoding="utf-8") as f:
            f.write(report_content)

        logger.info(f"Report saved to {filename}")

        # 同时保存JSON格式的详细结果
        json_filename = filename.replace(".md", ".json")
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "metadata": {
                        "test_time": datetime.now().isoformat(),
                        "total_apis": len(self.results),
                        "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
                    },
                    "results": self.results,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        logger.info(f"Detailed results saved to {json_filename}")


def main():
    """主函数"""
    print("=" * 60)
    print("AkShare API Comprehensive Validation Tool")
    print("=" * 60)

    validator = AkShareAPIValidator()

    # 检查命令行参数
    import sys

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "all":
            categories = None
        elif arg == "stock":
            categories = ["stock"]
        elif arg == "index":
            categories = ["index"]
        elif arg == "fund":
            categories = ["fund"]
        elif arg == "macro":
            categories = ["macro"]
        elif arg == "quick":
            categories = ["stock", "index"]
        else:
            categories = ["stock", "index"]  # 默认快速测试
    else:
        # 默认运行快速测试（股票和指数）
        categories = ["stock", "index"]
        print("\nRunning quick test (stock + index APIs)")
        print("To test all APIs, run: python validate_akshare_apis.py all")

    # 运行验证
    print("\nStarting validation...")
    validator.run_validation(categories=categories)

    # 生成并保存报告
    print("\nGenerating report...")
    validator.save_report()

    print("\nValidation completed successfully!")
    print(f"Total APIs tested: {len(validator.results)}")
    if validator.results:
        print(
            f"Success rate: {sum(1 for r in validator.results if r['status'] == 'success') / len(validator.results) * 100:.1f}%"
        )


if __name__ == "__main__":
    main()
