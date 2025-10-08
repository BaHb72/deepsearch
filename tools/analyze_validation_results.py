"""
分析AkShare API验证结果并生成报告
"""

import json
from collections import defaultdict
from datetime import datetime


def analyze_checkpoint():
    """分析检查点数据"""
    with open("akshare_validation_checkpoint.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", [])

    # 统计
    stats = {"total": len(results), "success": 0, "failed": 0, "empty": 0, "timeout": 0}

    # 按类别统计
    category_stats = defaultdict(lambda: {"total": 0, "success": 0, "failed": 0})

    # 错误类型统计
    error_types = defaultdict(list)

    # 成功的API列表
    successful_apis = []
    failed_apis = []

    for result in results:
        status = result.get("status")
        category = result.get("category", "unknown")
        func_name = result.get("function_name")

        category_stats[category]["total"] += 1

        if status == "success":
            stats["success"] += 1
            category_stats[category]["success"] += 1
            successful_apis.append(
                {
                    "name": func_name,
                    "category": category,
                    "response_time": result.get("response_time"),
                    "data_shape": result.get("data_shape"),
                }
            )
        elif status == "failed":
            stats["failed"] += 1
            category_stats[category]["failed"] += 1
            error_type = result.get("error_type", "Unknown")
            error_types[error_type].append(func_name)
            failed_apis.append(
                {
                    "name": func_name,
                    "category": category,
                    "error": result.get("error"),
                    "error_type": error_type,
                }
            )
        elif status == "empty":
            stats["empty"] += 1
        elif status == "timeout":
            stats["timeout"] += 1

    return {
        "stats": stats,
        "category_stats": dict(category_stats),
        "error_types": dict(error_types),
        "successful_apis": successful_apis,
        "failed_apis": failed_apis,
    }


def generate_report(analysis):
    """生成Markdown报告"""
    report = []

    # 标题
    report.append("# AkShare API Validation Report")
    report.append(f"\n**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    # 总体统计
    stats = analysis["stats"]
    success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0

    report.append("## Overall Statistics")
    report.append("")
    report.append(f"- **Total APIs Tested**: {stats['total']}")
    report.append(f"- **Success**: {stats['success']} ({success_rate:.1f}%)")
    report.append(f"- **Failed**: {stats['failed']}")
    report.append(f"- **Empty Response**: {stats['empty']}")
    report.append(f"- **Timeout**: {stats['timeout']}")
    report.append("")

    # 按类别统计
    report.append("## Statistics by Category")
    report.append("")
    report.append("| Category | Total | Success | Failed | Success Rate |")
    report.append("|----------|-------|---------|--------|--------------|")

    for category, cat_stats in sorted(analysis["category_stats"].items()):
        total = cat_stats["total"]
        success = cat_stats["success"]
        failed = cat_stats["failed"]
        rate = (success / total * 100) if total > 0 else 0
        report.append(f"| {category} | {total} | {success} | {failed} | {rate:.1f}% |")

    report.append("")

    # 错误类型分析
    if analysis["error_types"]:
        report.append("## Error Analysis")
        report.append("")
        for error_type, apis in sorted(
            analysis["error_types"].items(), key=lambda x: len(x[1]), reverse=True
        ):
            report.append(f"### {error_type} ({len(apis)} APIs)")
            for api in apis[:5]:  # 只显示前5个
                report.append(f"- {api}")
            if len(apis) > 5:
                report.append(f"- ... and {len(apis) - 5} more")
            report.append("")

    # 成功的API示例
    report.append("## Successful APIs (Top 20)")
    report.append("")
    report.append("| API Name | Category | Response Time |")
    report.append("|----------|----------|---------------|")

    # 按响应时间排序
    successful_sorted = sorted(
        [api for api in analysis["successful_apis"] if api["response_time"] is not None],
        key=lambda x: x["response_time"],
    )

    for api in successful_sorted[:20]:
        report.append(f"| {api['name']} | {api['category']} | {api['response_time']:.2f}s |")

    report.append("")

    # 建议
    report.append("## Recommendations")
    report.append("")
    report.append(
        "1. **Priority APIs**: Focus on APIs with high success rates and fast response times"
    )
    report.append("2. **Error Handling**: Implement specific error handling for common error types")
    report.append("3. **Caching Strategy**: Cache frequently used APIs to reduce server load")
    report.append("4. **Fallback Mechanism**: Use alternative data sources when APIs fail")
    report.append("5. **Rate Limiting**: Implement rate limiting to avoid being blocked")

    return "\n".join(report)


def main():
    print("Analyzing validation results...")

    try:
        analysis = analyze_checkpoint()
        report = generate_report(analysis)

        # 保存报告
        report_file = f"AKSHARE_API_VALIDATION_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"Report saved to: {report_file}")

        # 打印摘要
        stats = analysis["stats"]
        print("\nSummary:")
        print(f"  Total tested: {stats['total']}")
        print(f"  Success: {stats['success']}")
        print(f"  Failed: {stats['failed']}")
        print(
            f"  Success rate: {(stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0:.1f}%"
        )

    except FileNotFoundError:
        print("Error: akshare_validation_checkpoint.json not found")
        print("Please run the validation script first")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
