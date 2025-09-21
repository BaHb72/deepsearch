"""
DeepSearch 性能瓶颈分析工具

深度分析系统性能瓶颈，提供优化建议
"""
import asyncio
import json
import time
import psutil
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger


@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    value: float
    unit: str
    threshold: float
    status: str  # 'good', 'warning', 'critical'
    details: Dict[str, Any] = None


@dataclass 
class Bottleneck:
    """性能瓶颈"""
    component: str
    type: str  # 'latency', 'throughput', 'resource', 'error'
    severity: str  # 'low', 'medium', 'high', 'critical'
    current_value: float
    expected_value: float
    impact_score: float
    description: str
    solution: str
    code_snippet: str = None


class PerformanceAnalyzer:
    """性能分析器"""
    
    def __init__(self):
        self.metrics = []
        self.bottlenecks = []
        self.log_data = []
        self.monitor_data = {}
        
    async def load_monitoring_data(self):
        """加载监控数据"""
        # 加载监控日志
        log_file = "./data/logs/datasources/monitor_20250824.jsonl"
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        self.log_data.append(json.loads(line))
                    except:
                        pass
        
        # 加载性能报告
        perf_file = "./data/monitoring/exports/performance_report.json"
        if os.path.exists(perf_file):
            with open(perf_file, 'r', encoding='utf-8') as f:
                self.monitor_data['performance'] = json.load(f)
        
        # 加载错误模式
        error_file = "./data/monitoring/exports/error_patterns.json"
        if os.path.exists(error_file):
            with open(error_file, 'r', encoding='utf-8') as f:
                self.monitor_data['errors'] = json.load(f)
        
        logger.info(f"加载了 {len(self.log_data)} 条监控日志")
    
    async def analyze_latency_bottlenecks(self) -> List[Bottleneck]:
        """分析延迟瓶颈"""
        bottlenecks = []
        
        # 分析各数据源延迟
        source_latencies = defaultdict(list)
        for record in self.log_data:
            if 'performance' in record and 'latency_ms' in record['performance']:
                source = record.get('source_type', 'unknown')
                latency = record['performance']['latency_ms']
                source_latencies[source].append(latency)
        
        # 计算统计指标
        for source, latencies in source_latencies.items():
            if not latencies:
                continue
                
            avg_latency = statistics.mean(latencies)
            p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else max(latencies)
            p99_latency = statistics.quantiles(latencies, n=100)[98] if len(latencies) > 100 else max(latencies)
            
            # 检测延迟瓶颈
            if p95_latency > 200:  # P95延迟超过200ms
                severity = 'critical' if p95_latency > 500 else 'high' if p95_latency > 300 else 'medium'
                
                bottlenecks.append(Bottleneck(
                    component=f"DataSource_{source}",
                    type="latency",
                    severity=severity,
                    current_value=p95_latency,
                    expected_value=100,
                    impact_score=self._calculate_impact_score(p95_latency, 100, severity),
                    description=f"{source}数据源P95延迟达到{p95_latency:.0f}ms，严重影响用户体验",
                    solution=f"优化{source}连接池配置，增加缓存，或切换到更快的数据源",
                    code_snippet=self._generate_latency_optimization_code(source, avg_latency, p95_latency)
                ))
            
            # 记录性能指标
            self.metrics.append(PerformanceMetric(
                name=f"{source}_avg_latency",
                value=avg_latency,
                unit="ms",
                threshold=50,
                status=self._get_status(avg_latency, 50, 100),
                details={
                    "p50": statistics.median(latencies) if latencies else 0,
                    "p95": p95_latency,
                    "p99": p99_latency,
                    "sample_count": len(latencies)
                }
            ))
        
        return bottlenecks
    
    async def analyze_throughput_bottlenecks(self) -> List[Bottleneck]:
        """分析吞吐量瓶颈"""
        bottlenecks = []
        
        if 'performance' in self.monitor_data:
            perf_data = self.monitor_data['performance']
            
            # 分析1分钟吞吐量
            if 'aggregated' in perf_data and '1min' in perf_data['aggregated']:
                min_data = perf_data['aggregated']['1min']
                throughput = min_data.get('throughput_rps', 0)
                
                if throughput < 10:  # RPS低于10
                    bottlenecks.append(Bottleneck(
                        component="System",
                        type="throughput",
                        severity="high" if throughput < 5 else "medium",
                        current_value=throughput,
                        expected_value=50,
                        impact_score=self._calculate_impact_score(throughput, 50, "high"),
                        description=f"系统吞吐量仅{throughput:.1f} RPS，无法满足高频交易需求",
                        solution="实现请求批处理、连接复用和异步并发处理",
                        code_snippet=self._generate_throughput_optimization_code()
                    ))
        
        return bottlenecks
    
    async def analyze_error_bottlenecks(self) -> List[Bottleneck]:
        """分析错误瓶颈"""
        bottlenecks = []
        
        if 'errors' in self.monitor_data:
            error_data = self.monitor_data['errors']
            
            if 'report' in error_data:
                report = error_data['report']
                total_errors = report.get('total_errors', 0)
                
                # 分析错误类型
                by_type = report.get('by_type', {})
                for error_type, count in by_type.items():
                    error_rate = count / total_errors if total_errors > 0 else 0
                    
                    if error_rate > 0.2:  # 某类错误占比超过20%
                        severity = 'critical' if error_rate > 0.5 else 'high' if error_rate > 0.3 else 'medium'
                        
                        bottlenecks.append(Bottleneck(
                            component="ErrorHandling",
                            type="error",
                            severity=severity,
                            current_value=error_rate * 100,
                            expected_value=5,
                            impact_score=self._calculate_impact_score(error_rate * 100, 5, severity),
                            description=f"{error_type}错误占比达{error_rate*100:.1f}%，需要专门处理",
                            solution=self._get_error_solution(error_type),
                            code_snippet=self._generate_error_handling_code(error_type)
                        ))
        
        return bottlenecks
    
    async def analyze_resource_bottlenecks(self) -> List[Bottleneck]:
        """分析资源瓶颈"""
        bottlenecks = []
        
        # 获取当前系统资源使用情况
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('.')
        
        # CPU瓶颈
        if cpu_percent > 80:
            bottlenecks.append(Bottleneck(
                component="CPU",
                type="resource",
                severity="critical" if cpu_percent > 90 else "high",
                current_value=cpu_percent,
                expected_value=50,
                impact_score=self._calculate_impact_score(cpu_percent, 50, "high"),
                description=f"CPU使用率达{cpu_percent}%，可能导致系统响应缓慢",
                solution="优化算法复杂度，使用缓存，或升级硬件",
                code_snippet=self._generate_cpu_optimization_code()
            ))
        
        # 内存瓶颈
        if memory.percent > 85:
            bottlenecks.append(Bottleneck(
                component="Memory",
                type="resource",
                severity="critical" if memory.percent > 95 else "high",
                current_value=memory.percent,
                expected_value=60,
                impact_score=self._calculate_impact_score(memory.percent, 60, "high"),
                description=f"内存使用率达{memory.percent}%，可能触发OOM",
                solution="实现内存池，优化数据结构，增加内存上限",
                code_snippet=self._generate_memory_optimization_code()
            ))
        
        # 磁盘瓶颈
        if disk.percent > 90:
            bottlenecks.append(Bottleneck(
                component="Disk",
                type="resource",
                severity="high",
                current_value=disk.percent,
                expected_value=70,
                impact_score=self._calculate_impact_score(disk.percent, 70, "medium"),
                description=f"磁盘使用率达{disk.percent}%，需要清理或扩容",
                solution="清理日志文件，压缩历史数据，或增加存储空间",
                code_snippet=self._generate_disk_cleanup_code()
            ))
        
        # 记录资源指标
        self.metrics.extend([
            PerformanceMetric(
                name="cpu_usage",
                value=cpu_percent,
                unit="%",
                threshold=80,
                status=self._get_status(cpu_percent, 60, 80)
            ),
            PerformanceMetric(
                name="memory_usage",
                value=memory.percent,
                unit="%",
                threshold=85,
                status=self._get_status(memory.percent, 70, 85)
            ),
            PerformanceMetric(
                name="disk_usage",
                value=disk.percent,
                unit="%",
                threshold=90,
                status=self._get_status(disk.percent, 70, 90)
            )
        ])
        
        return bottlenecks
    
    def _calculate_impact_score(self, current: float, expected: float, severity: str) -> float:
        """计算影响分数"""
        severity_weight = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        deviation = abs(current - expected) / expected if expected > 0 else 10
        return deviation * severity_weight.get(severity, 1)
    
    def _get_status(self, value: float, warning_threshold: float, critical_threshold: float) -> str:
        """获取状态"""
        if value >= critical_threshold:
            return "critical"
        elif value >= warning_threshold:
            return "warning"
        return "good"
    
    def _get_error_solution(self, error_type: str) -> str:
        """获取错误解决方案"""
        solutions = {
            "network_error": "实现智能重试机制，增加连接池大小，优化网络配置",
            "timeout_error": "增加超时时间，实现请求缓存，使用更快的数据源",
            "auth_error": "实现token刷新机制，缓存认证信息，处理并发认证",
            "data_error": "增加数据验证，实现容错解析，记录异常数据"
        }
        return solutions.get(error_type, "实现通用错误处理机制")
    
    def _generate_latency_optimization_code(self, source: str, avg: float, p95: float) -> str:
        """生成延迟优化代码"""
        return f'''
# {source}延迟优化方案
class OptimizedDataSource:
    def __init__(self):
        # 1. 连接池优化
        self.pool = ConnectionPool(
            min_size=5,  # 增加最小连接数
            max_size=20,  # 增加最大连接数
            keepalive_time=300  # 保持连接5分钟
        )
        
        # 2. 智能缓存
        self.cache = LRUCache(
            max_size=10000,
            ttl=self._adaptive_ttl(avg_latency={avg:.0f})
        )
        
        # 3. 请求批处理
        self.batch_processor = BatchProcessor(
            batch_size=50,
            batch_timeout=0.05,  # 50ms批处理窗口
            max_latency=100  # 目标延迟100ms
        )
    
    def _adaptive_ttl(self, avg_latency):
        """根据延迟动态调整缓存时间"""
        if avg_latency > 200:
            return 300  # 高延迟时缓存5分钟
        elif avg_latency > 100:
            return 120  # 中延迟时缓存2分钟
        return 60  # 低延迟时缓存1分钟
    
    async def get_data(self, symbol):
        # 1. 尝试缓存
        if cached := self.cache.get(symbol):
            return cached
        
        # 2. 批处理请求
        return await self.batch_processor.process(symbol)
'''
    
    def _generate_throughput_optimization_code(self) -> str:
        """生成吞吐量优化代码"""
        return '''
# 吞吐量优化方案
class HighThroughputProcessor:
    def __init__(self):
        # 1. 异步并发处理
        self.semaphore = asyncio.Semaphore(100)  # 限制并发数
        self.executor = ThreadPoolExecutor(max_workers=20)
        
        # 2. 请求合并
        self.request_merger = RequestMerger(
            window_size=0.01,  # 10ms合并窗口
            max_batch=100  # 最大批次大小
        )
        
        # 3. 管道化处理
        self.pipeline = ProcessingPipeline([
            ValidationStage(),
            CacheCheckStage(),
            BatchFetchStage(),
            PostProcessStage()
        ])
    
    async def process_requests(self, requests):
        """高吞吐量处理请求"""
        # 1. 请求去重和合并
        merged = self.request_merger.merge(requests)
        
        # 2. 并发处理
        tasks = []
        for batch in self._chunk(merged, 100):
            tasks.append(self._process_batch(batch))
        
        # 3. 等待所有任务完成
        results = await asyncio.gather(*tasks)
        return self._flatten(results)
    
    async def _process_batch(self, batch):
        async with self.semaphore:
            return await self.pipeline.process(batch)
'''
    
    def _generate_error_handling_code(self, error_type: str) -> str:
        """生成错误处理代码"""
        if error_type == "timeout_error":
            return '''
# 超时错误处理
class TimeoutHandler:
    def __init__(self):
        self.timeout_config = {
            'realtime': 1.0,   # 实时数据1秒
            'historical': 5.0,  # 历史数据5秒
            'batch': 10.0      # 批量请求10秒
        }
        
    async def fetch_with_timeout(self, func, data_type='realtime'):
        timeout = self.timeout_config.get(data_type, 3.0)
        
        try:
            return await asyncio.wait_for(
                func(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            # 降级到缓存或备用数据源
            if cached := self.cache.get_stale(key):
                logger.warning(f"使用过期缓存数据")
                return cached
            
            # 尝试备用数据源
            if self.fallback_source:
                return await self.fallback_source.fetch()
            
            raise TimeoutError(f"请求超时且无可用备份")
'''
        
        elif error_type == "network_error":
            return '''
# 网络错误处理
class NetworkErrorHandler:
    def __init__(self):
        self.retry_config = ExponentialBackoff(
            base_delay=0.1,
            max_delay=10.0,
            max_retries=3
        )
        
    async def fetch_with_retry(self, func):
        last_error = None
        
        for attempt in range(self.retry_config.max_retries):
            try:
                return await func()
            except NetworkError as e:
                last_error = e
                delay = self.retry_config.get_delay(attempt)
                logger.warning(f"网络错误，{delay:.1f}秒后重试")
                await asyncio.sleep(delay)
        
        raise last_error
'''
        
        return '''
# 通用错误处理
class ErrorHandler:
    async def handle_error(self, error, context):
        # 记录错误
        logger.error(f"Error in {context}: {error}")
        
        # 降级处理
        if self.can_fallback():
            return await self.fallback()
        
        # 熔断保护
        if self.circuit_breaker.should_open():
            self.circuit_breaker.open()
            raise ServiceUnavailable()
        
        raise error
'''
    
    def _generate_cpu_optimization_code(self) -> str:
        """生成CPU优化代码"""
        return '''
# CPU优化方案
class CPUOptimizer:
    def __init__(self):
        # 1. 使用更高效的数据结构
        self.data_cache = {}  # 替换为 lru_cache
        
        # 2. 避免重复计算
        self.computation_cache = TTLCache(
            maxsize=1000,
            ttl=60
        )
        
    @lru_cache(maxsize=1000)
    def compute_indicators(self, data):
        """缓存计算结果避免重复计算"""
        return expensive_computation(data)
    
    def process_data_batch(self, data_list):
        """批量处理减少开销"""
        # 使用numpy向量化操作
        import numpy as np
        arr = np.array(data_list)
        return np.mean(arr, axis=0)  # 向量化计算
'''
    
    def _generate_memory_optimization_code(self) -> str:
        """生成内存优化代码"""
        return '''
# 内存优化方案
class MemoryOptimizer:
    def __init__(self):
        # 1. 使用对象池
        self.object_pool = ObjectPool(
            factory=DataObject,
            max_size=1000
        )
        
        # 2. 弱引用缓存
        self.weak_cache = weakref.WeakValueDictionary()
        
        # 3. 定期清理
        self.cleanup_interval = 300  # 5分钟
        asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(self.cleanup_interval)
            # 清理过期数据
            self._cleanup_expired_data()
            # 强制垃圾回收
            import gc
            gc.collect()
    
    def _cleanup_expired_data(self):
        """清理过期数据释放内存"""
        current_time = time.time()
        expired_keys = [
            k for k, v in self.cache.items()
            if current_time - v.timestamp > v.ttl
        ]
        for key in expired_keys:
            del self.cache[key]
'''
    
    def _generate_disk_cleanup_code(self) -> str:
        """生成磁盘清理代码"""
        return '''
# 磁盘清理方案
class DiskCleanup:
    def __init__(self):
        self.log_dir = "./logs"
        self.data_dir = "./data"
        self.retention_days = 7
        
    def cleanup_old_files(self):
        """清理旧文件"""
        import os
        from datetime import datetime, timedelta
        
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        
        for root, dirs, files in os.walk(self.log_dir):
            for file in files:
                filepath = os.path.join(root, file)
                if os.path.getmtime(filepath) < cutoff.timestamp():
                    os.remove(filepath)
                    logger.info(f"删除旧文件: {filepath}")
    
    def compress_logs(self):
        """压缩日志文件"""
        import gzip
        import shutil
        
        for file in glob.glob(f"{self.log_dir}/*.log"):
            with open(file, 'rb') as f_in:
                with gzip.open(f"{file}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.remove(file)
'''
    
    async def analyze_all(self):
        """执行所有分析"""
        await self.load_monitoring_data()
        
        # 并发执行各项分析
        tasks = [
            self.analyze_latency_bottlenecks(),
            self.analyze_throughput_bottlenecks(),
            self.analyze_error_bottlenecks(),
            self.analyze_resource_bottlenecks()
        ]
        
        results = await asyncio.gather(*tasks)
        
        # 合并所有瓶颈
        for bottlenecks in results:
            self.bottlenecks.extend(bottlenecks)
        
        # 按影响分数排序
        self.bottlenecks.sort(key=lambda x: x.impact_score, reverse=True)
    
    def generate_report(self) -> Dict[str, Any]:
        """生成分析报告"""
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_bottlenecks": len(self.bottlenecks),
                "critical_count": sum(1 for b in self.bottlenecks if b.severity == 'critical'),
                "high_count": sum(1 for b in self.bottlenecks if b.severity == 'high'),
                "medium_count": sum(1 for b in self.bottlenecks if b.severity == 'medium'),
                "low_count": sum(1 for b in self.bottlenecks if b.severity == 'low')
            },
            "metrics": [asdict(m) for m in self.metrics],
            "bottlenecks": [asdict(b) for b in self.bottlenecks],
            "top_priorities": self._get_top_priorities()
        }
    
    def _get_top_priorities(self) -> List[Dict[str, Any]]:
        """获取优先处理事项"""
        priorities = []
        
        for i, bottleneck in enumerate(self.bottlenecks[:5], 1):
            priorities.append({
                "priority": i,
                "component": bottleneck.component,
                "issue": bottleneck.description,
                "solution": bottleneck.solution,
                "impact_score": bottleneck.impact_score,
                "estimated_improvement": f"{(bottleneck.current_value - bottleneck.expected_value) / bottleneck.current_value * 100:.1f}%"
            })
        
        return priorities
    
    def print_summary(self):
        """打印分析摘要"""
        print("\n" + "="*80)
        print("DeepSearch 性能瓶颈分析报告")
        print("="*80)
        print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*80)
        
        # 打印性能指标
        print("\n📊 关键性能指标:")
        for metric in self.metrics[:10]:
            status_icon = {"good": "✅", "warning": "⚠️", "critical": "❌"}.get(metric.status, "❓")
            print(f"  {status_icon} {metric.name:30} {metric.value:10.2f} {metric.unit:5} "
                  f"(阈值: {metric.threshold:.0f})")
        
        # 打印瓶颈摘要
        print(f"\n🔍 发现 {len(self.bottlenecks)} 个性能瓶颈:")
        
        severity_counts = defaultdict(int)
        for b in self.bottlenecks:
            severity_counts[b.severity] += 1
        
        for severity in ['critical', 'high', 'medium', 'low']:
            count = severity_counts[severity]
            if count > 0:
                icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}[severity]
                print(f"  {icon} {severity.upper():8} : {count} 个")
        
        # 打印TOP 5瓶颈
        print("\n🎯 TOP 5 优先处理项:")
        for i, bottleneck in enumerate(self.bottlenecks[:5], 1):
            severity_icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}[bottleneck.severity]
            print(f"\n  {i}. {severity_icon} [{bottleneck.component}] {bottleneck.type.upper()}")
            print(f"     问题: {bottleneck.description}")
            print(f"     当前值: {bottleneck.current_value:.1f} | 期望值: {bottleneck.expected_value:.1f}")
            print(f"     影响分数: {bottleneck.impact_score:.1f}")
            print(f"     解决方案: {bottleneck.solution}")
        
        print("\n" + "="*80)


async def main():
    """主函数"""
    analyzer = PerformanceAnalyzer()
    
    # 执行分析
    await analyzer.analyze_all()
    
    # 打印摘要
    analyzer.print_summary()
    
    # 生成详细报告
    report = analyzer.generate_report()
    
    # 保存报告
    report_file = f"./data/monitoring/performance_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📁 详细报告已保存至: {report_file}")
    
    # 保存优化代码
    if analyzer.bottlenecks:
        code_file = f"./data/monitoring/optimization_code_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write("# DeepSearch 性能优化代码\n")
            f.write("# 自动生成的优化建议\n\n")
            
            for i, bottleneck in enumerate(analyzer.bottlenecks[:5], 1):
                if bottleneck.code_snippet:
                    f.write(f"\n# {i}. {bottleneck.component} - {bottleneck.description}\n")
                    f.write(bottleneck.code_snippet)
                    f.write("\n\n" + "-"*80 + "\n")
        
        print(f"💻 优化代码已保存至: {code_file}")


if __name__ == "__main__":
    # 设置日志
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")
    
    # 运行分析
    asyncio.run(main())