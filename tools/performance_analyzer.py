"""
性能瓶颈分析工具
分析API响应时间、内存使用、代码复杂度等性能指标
"""

import time
import psutil
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, List, Tuple
import json
import ast
from collections import defaultdict

class PerformanceAnalyzer:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.results = {
            'api_response_times': {},
            'memory_usage': {},
            'code_complexity': {},
            'database_queries': {},
            'cache_hits': {},
            'bottlenecks': []
        }

    async def analyze(self):
        """执行全面的性能分析"""
        print("="*60)
        print("性能瓶颈分析")
        print("="*60)

        # 1. 分析API响应时间
        await self.analyze_api_response_times()

        # 2. 分析内存使用
        self.analyze_memory_usage()

        # 3. 分析代码复杂度
        self.analyze_code_complexity()

        # 4. 识别性能瓶颈
        self.identify_bottlenecks()

        # 5. 生成优化建议
        self.generate_optimization_suggestions()

        # 6. 保存报告
        self.save_report()

    async def analyze_api_response_times(self):
        """分析API响应时间"""
        print("\n[+] 分析API响应时间...")

        # 定义要测试的API端点
        test_endpoints = [
            # 数据类API
            ('/api/market/quote/000001', 'GET', None, '实时行情'),
            ('/api/market/kline/000001', 'GET', {'period': 'daily'}, 'K线数据'),
            ('/api/data/stock_list', 'GET', None, '股票列表'),
            ('/api/data/realtime_quotes', 'GET', None, '实时报价'),

            # 系统类API
            ('/api/health', 'GET', None, '健康检查'),
            ('/api/system/status', 'GET', None, '系统状态'),
            ('/api/system/config', 'GET', None, '系统配置'),

            # 数据源API
            ('/api/data-source/status', 'GET', None, '数据源状态'),
            ('/api/data-source/capabilities', 'GET', None, '数据源能力'),

            # 监控API
            ('/api/monitoring/metrics', 'GET', None, '监控指标'),
            ('/api/monitoring/cache/stats', 'GET', None, '缓存统计'),
        ]

        async with aiohttp.ClientSession() as session:
            for endpoint, method, params, description in test_endpoints:
                try:
                    # 测试3次取平均值
                    times = []
                    for _ in range(3):
                        start = time.time()
                        url = f"{self.base_url}{endpoint}"

                        if method == 'GET':
                            async with session.get(url, params=params, timeout=10) as resp:
                                await resp.text()
                                status = resp.status

                        elapsed = (time.time() - start) * 1000  # 转换为毫秒
                        times.append(elapsed)

                    avg_time = sum(times) / len(times)
                    self.results['api_response_times'][endpoint] = {
                        'description': description,
                        'avg_time_ms': round(avg_time, 2),
                        'min_time_ms': round(min(times), 2),
                        'max_time_ms': round(max(times), 2),
                        'status': 'SLOW' if avg_time > 200 else 'OK'
                    }

                    print(f"  [{description}] {endpoint}: {avg_time:.2f}ms")

                except Exception as e:
                    self.results['api_response_times'][endpoint] = {
                        'description': description,
                        'error': str(e),
                        'status': 'ERROR'
                    }
                    print(f"  [ERROR] {endpoint}: {e}")

    def analyze_memory_usage(self):
        """分析内存使用情况"""
        print("\n[+] 分析内存使用...")

        process = psutil.Process()
        memory_info = process.memory_info()

        self.results['memory_usage'] = {
            'rss_mb': round(memory_info.rss / 1024 / 1024, 2),
            'vms_mb': round(memory_info.vms / 1024 / 1024, 2),
            'percent': round(process.memory_percent(), 2),
            'available_mb': round(psutil.virtual_memory().available / 1024 / 1024, 2)
        }

        print(f"  内存使用: {self.results['memory_usage']['rss_mb']}MB")
        print(f"  内存占比: {self.results['memory_usage']['percent']}%")

    def analyze_code_complexity(self):
        """分析代码复杂度"""
        print("\n[+] 分析代码复杂度...")

        complex_files = []
        large_files = []

        # 分析主要模块的复杂度
        modules_to_analyze = [
            'deepsearch/core',
            'deepsearch/webui/api',
            'deepsearch/infrastructure',
            'deepsearch/application'
        ]

        for module_path in modules_to_analyze:
            path = Path(module_path)
            if not path.exists():
                continue

            for py_file in path.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue

                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = len(content.splitlines())

                        # 检查文件大小
                        if lines > 500:
                            large_files.append({
                                'file': str(py_file),
                                'lines': lines
                            })

                        # 分析圈复杂度
                        tree = ast.parse(content)
                        complexity = self._calculate_complexity(tree)

                        if complexity > 10:
                            complex_files.append({
                                'file': str(py_file),
                                'complexity': complexity
                            })

                except Exception:
                    pass

        self.results['code_complexity'] = {
            'complex_files': sorted(complex_files, key=lambda x: x['complexity'], reverse=True)[:10],
            'large_files': sorted(large_files, key=lambda x: x['lines'], reverse=True)[:10]
        }

        print(f"  高复杂度文件: {len(complex_files)}个")
        print(f"  超大文件(>500行): {len(large_files)}个")

    def _calculate_complexity(self, tree) -> int:
        """计算代码圈复杂度"""
        complexity = 1

        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1

        return complexity

    def identify_bottlenecks(self):
        """识别性能瓶颈"""
        print("\n[+] 识别性能瓶颈...")

        bottlenecks = []

        # 1. 慢API检测
        for endpoint, data in self.results['api_response_times'].items():
            if data.get('status') == 'SLOW':
                bottlenecks.append({
                    'type': 'SLOW_API',
                    'severity': 'HIGH',
                    'endpoint': endpoint,
                    'response_time': data.get('avg_time_ms'),
                    'description': f"API响应时间过长: {data.get('avg_time_ms')}ms"
                })

        # 2. 内存问题检测
        if self.results['memory_usage']['rss_mb'] > 500:
            bottlenecks.append({
                'type': 'HIGH_MEMORY',
                'severity': 'MEDIUM',
                'memory_mb': self.results['memory_usage']['rss_mb'],
                'description': f"内存使用过高: {self.results['memory_usage']['rss_mb']}MB"
            })

        # 3. 代码复杂度问题
        complex_files = self.results['code_complexity'].get('complex_files', [])
        for file_info in complex_files[:3]:  # 只报告前3个最复杂的
            bottlenecks.append({
                'type': 'HIGH_COMPLEXITY',
                'severity': 'LOW',
                'file': file_info['file'],
                'complexity': file_info['complexity'],
                'description': f"代码复杂度过高: {file_info['complexity']}"
            })

        self.results['bottlenecks'] = bottlenecks

        print(f"  发现 {len(bottlenecks)} 个性能瓶颈")

    def generate_optimization_suggestions(self):
        """生成优化建议"""
        print("\n" + "="*60)
        print("优化建议")
        print("="*60)

        suggestions = []

        # 基于API响应时间的建议
        slow_apis = [api for api, data in self.results['api_response_times'].items()
                    if data.get('status') == 'SLOW']

        if slow_apis:
            suggestions.append({
                'category': 'API优化',
                'priority': 'HIGH',
                'suggestions': [
                    '1. 实现Redis缓存层，缓存频繁访问的数据',
                    '2. 使用异步并发处理，减少串行等待时间',
                    '3. 优化数据库查询，添加适当的索引',
                    '4. 实现请求批处理，减少网络往返',
                    '5. 使用连接池管理数据库和HTTP连接'
                ],
                'affected_apis': slow_apis[:5]
            })

        # 基于内存使用的建议
        if self.results['memory_usage']['rss_mb'] > 300:
            suggestions.append({
                'category': '内存优化',
                'priority': 'MEDIUM',
                'suggestions': [
                    '1. 实现对象池，复用频繁创建的对象',
                    '2. 使用弱引用避免循环引用',
                    '3. 及时清理不需要的缓存数据',
                    '4. 使用生成器处理大数据集',
                    '5. 定期进行垃圾回收'
                ]
            })

        # 基于代码复杂度的建议
        if len(self.results['code_complexity'].get('complex_files', [])) > 5:
            suggestions.append({
                'category': '代码重构',
                'priority': 'LOW',
                'suggestions': [
                    '1. 拆分复杂函数，遵循单一职责原则',
                    '2. 提取重复代码到公共方法',
                    '3. 使用设计模式简化复杂逻辑',
                    '4. 减少嵌套层级，提前返回',
                    '5. 使用策略模式替代复杂的if-else链'
                ]
            })

        # 通用优化建议
        suggestions.append({
            'category': '架构优化',
            'priority': 'MEDIUM',
            'suggestions': [
                '1. 实现CQRS模式，分离读写操作',
                '2. 使用事件驱动架构，解耦组件',
                '3. 实现微批处理，提高吞吐量',
                '4. 使用CDN加速静态资源',
                '5. 实现服务降级和熔断机制'
            ]
        })

        self.results['suggestions'] = suggestions

        # 打印建议
        for suggestion in suggestions:
            print(f"\n[{suggestion['priority']}] {suggestion['category']}:")
            for s in suggestion['suggestions']:
                print(f"  {s}")

    def save_report(self):
        """保存性能分析报告"""
        # 保存JSON格式
        with open('performance_analysis_report.json', 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        # 保存Markdown格式
        self._save_markdown_report()

        print(f"\n[*] 报告已保存到:")
        print(f"  - performance_analysis_report.json")
        print(f"  - performance_analysis_report.md")

    def _save_markdown_report(self):
        """保存Markdown格式的报告"""
        md_content = f"""# 性能分析报告

生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}

## API响应时间分析

| 端点 | 描述 | 平均响应时间(ms) | 状态 |
|------|------|-----------------|------|
"""
        for endpoint, data in self.results['api_response_times'].items():
            if 'error' not in data:
                md_content += f"| {endpoint} | {data['description']} | {data['avg_time_ms']} | {data['status']} |\n"

        md_content += f"""

## 内存使用情况

- RSS内存: {self.results['memory_usage']['rss_mb']}MB
- 内存占比: {self.results['memory_usage']['percent']}%
- 可用内存: {self.results['memory_usage']['available_mb']}MB

## 性能瓶颈

"""
        for bottleneck in self.results['bottlenecks']:
            md_content += f"- **[{bottleneck['severity']}]** {bottleneck['description']}\n"

        md_content += "\n## 优化建议\n\n"

        for suggestion in self.results['suggestions']:
            md_content += f"### {suggestion['category']} (优先级: {suggestion['priority']})\n\n"
            for s in suggestion['suggestions']:
                md_content += f"- {s}\n"
            md_content += "\n"

        with open('performance_analysis_report.md', 'w', encoding='utf-8') as f:
            f.write(md_content)


async def main():
    analyzer = PerformanceAnalyzer()
    await analyzer.analyze()


if __name__ == "__main__":
    # 注意：需要先启动后端服务才能测试API
    print("[!] 注意：此工具需要后端服务运行在 http://localhost:8000")
    print("[!] 如果服务未运行，API测试将失败")

    asyncio.run(main())