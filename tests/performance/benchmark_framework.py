#!/usr/bin/env python
"""
Performance Benchmark Framework for DeepSearch

This framework measures performance metrics before and after architecture migration.
It provides comprehensive benchmarks for cache, database, API, and overall system performance.
"""

import asyncio
import csv
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import matplotlib.pyplot as plt
import numpy as np
import psutil

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    duration: float  # seconds
    operations: int
    throughput: float  # ops/sec
    latency_p50: float  # milliseconds
    latency_p95: float
    latency_p99: float
    memory_used: float  # MB
    cpu_percent: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkSuite:
    """Collection of benchmark results."""

    name: str
    results: List[BenchmarkResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    def add_result(self, result: BenchmarkResult):
        """Add a benchmark result."""
        self.results.append(result)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        if not self.results:
            return {}

        throughputs = [r.throughput for r in self.results]
        latencies_p50 = [r.latency_p50 for r in self.results]
        latencies_p95 = [r.latency_p95 for r in self.results]

        return {
            "total_benchmarks": len(self.results),
            "avg_throughput": statistics.mean(throughputs),
            "max_throughput": max(throughputs),
            "min_throughput": min(throughputs),
            "avg_latency_p50": statistics.mean(latencies_p50),
            "avg_latency_p95": statistics.mean(latencies_p95),
        }


class PerformanceMonitor:
    """Monitors system resources during benchmark."""

    def __init__(self):
        self.process = psutil.Process()
        self.samples = []
        self.monitoring = False

    async def start_monitoring(self, interval: float = 0.1):
        """Start resource monitoring."""
        self.monitoring = True
        while self.monitoring:
            sample = {
                "timestamp": time.time(),
                "cpu_percent": self.process.cpu_percent(),
                "memory_mb": self.process.memory_info().rss / 1024 / 1024,
                "num_threads": self.process.num_threads(),
            }
            self.samples.append(sample)
            await asyncio.sleep(interval)

    def stop_monitoring(self):
        """Stop resource monitoring."""
        self.monitoring = False

    def get_stats(self) -> Dict[str, float]:
        """Get resource usage statistics."""
        if not self.samples:
            return {}

        cpu_values = [s["cpu_percent"] for s in self.samples]
        memory_values = [s["memory_mb"] for s in self.samples]

        return {
            "avg_cpu": statistics.mean(cpu_values),
            "max_cpu": max(cpu_values),
            "avg_memory_mb": statistics.mean(memory_values),
            "max_memory_mb": max(memory_values),
        }


class CacheBenchmark:
    """Benchmarks for cache performance."""

    def __init__(self):
        self.cache = None  # Will be injected

    async def benchmark_cache_operations(self, num_operations: int = 10000) -> BenchmarkResult:
        """Benchmark basic cache operations."""
        from infrastructure.cache import CacheManager

        # Initialize cache
        cache = CacheManager(l1_max_size=1000, l1_ttl=300)

        latencies = []
        monitor = PerformanceMonitor()
        monitor_task = asyncio.create_task(monitor.start_monitoring())

        start_time = time.time()

        # Write operations
        for i in range(num_operations // 2):
            op_start = time.time()
            await cache.set(f"key_{i}", f"value_{i}")
            latencies.append((time.time() - op_start) * 1000)

        # Read operations
        for i in range(num_operations // 2):
            op_start = time.time()
            await cache.get(f"key_{i % (num_operations // 4)}")
            latencies.append((time.time() - op_start) * 1000)

        duration = time.time() - start_time
        monitor.stop_monitoring()
        await monitor_task

        stats = monitor.get_stats()
        cache_stats = cache.get_stats()

        return BenchmarkResult(
            name="cache_operations",
            duration=duration,
            operations=num_operations,
            throughput=num_operations / duration,
            latency_p50=np.percentile(latencies, 50),
            latency_p95=np.percentile(latencies, 95),
            latency_p99=np.percentile(latencies, 99),
            memory_used=stats.get("avg_memory_mb", 0),
            cpu_percent=stats.get("avg_cpu", 0),
            metadata={"cache_stats": cache_stats},
        )

    async def benchmark_cache_hit_rate(self, num_operations: int = 5000) -> BenchmarkResult:
        """Benchmark cache hit rate with realistic access patterns."""
        from infrastructure.cache import CacheManager

        cache = CacheManager(l1_max_size=500, l1_ttl=60)

        # Simulate Zipf distribution (80/20 rule)
        keys = [f"key_{i}" for i in range(1000)]
        weights = [1 / (i + 1) for i in range(1000)]

        latencies = []
        start_time = time.time()

        # Warm up cache
        for i in range(100):
            await cache.set(f"key_{i}", f"value_{i}")

        # Benchmark with realistic access pattern
        for _ in range(num_operations):
            key = np.random.choice(keys, p=weights / sum(weights))
            op_start = time.time()
            value = await cache.get(key)
            if value is None:
                await cache.set(key, f"value_for_{key}")
            latencies.append((time.time() - op_start) * 1000)

        duration = time.time() - start_time
        cache_stats = cache.get_stats()

        return BenchmarkResult(
            name="cache_hit_rate",
            duration=duration,
            operations=num_operations,
            throughput=num_operations / duration,
            latency_p50=np.percentile(latencies, 50),
            latency_p95=np.percentile(latencies, 95),
            latency_p99=np.percentile(latencies, 99),
            memory_used=0,
            cpu_percent=0,
            metadata={
                "hit_rate": cache_stats.get("overall_hit_rate", 0),
                "l1_hit_rate": cache_stats.get("l1_hit_rate", 0),
            },
        )


class DatabaseBenchmark:
    """Benchmarks for database operations."""

    async def benchmark_query_performance(self, num_queries: int = 1000) -> BenchmarkResult:
        """Benchmark database query performance."""
        # This would connect to actual database
        # For now, simulate with delays

        latencies = []
        monitor = PerformanceMonitor()
        monitor_task = asyncio.create_task(monitor.start_monitoring())

        start_time = time.time()

        for i in range(num_queries):
            op_start = time.time()
            # Simulate database query
            await asyncio.sleep(0.001 + np.random.exponential(0.002))
            latencies.append((time.time() - op_start) * 1000)

        duration = time.time() - start_time
        monitor.stop_monitoring()
        await monitor_task

        stats = monitor.get_stats()

        return BenchmarkResult(
            name="database_queries",
            duration=duration,
            operations=num_queries,
            throughput=num_queries / duration,
            latency_p50=np.percentile(latencies, 50),
            latency_p95=np.percentile(latencies, 95),
            latency_p99=np.percentile(latencies, 99),
            memory_used=stats.get("avg_memory_mb", 0),
            cpu_percent=stats.get("avg_cpu", 0),
        )

    async def benchmark_connection_pool(self, num_connections: int = 100) -> BenchmarkResult:
        """Benchmark connection pool performance."""
        # Simulate connection pool behavior

        latencies = []
        start_time = time.time()

        async def simulate_connection():
            conn_start = time.time()
            await asyncio.sleep(0.01 + np.random.exponential(0.005))
            return (time.time() - conn_start) * 1000

        # Concurrent connections
        tasks = [simulate_connection() for _ in range(num_connections)]
        latencies = await asyncio.gather(*tasks)

        duration = time.time() - start_time

        return BenchmarkResult(
            name="connection_pool",
            duration=duration,
            operations=num_connections,
            throughput=num_connections / duration,
            latency_p50=np.percentile(latencies, 50),
            latency_p95=np.percentile(latencies, 95),
            latency_p99=np.percentile(latencies, 99),
            memory_used=0,
            cpu_percent=0,
        )


class APIBenchmark:
    """Benchmarks for API endpoints."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    async def benchmark_api_endpoint(
        self, endpoint: str, method: str = "GET", num_requests: int = 1000, concurrent: int = 10
    ) -> BenchmarkResult:
        """Benchmark a specific API endpoint."""

        latencies = []
        errors = 0

        async def make_request(session):
            try:
                start = time.time()
                async with session.request(method, f"{self.base_url}{endpoint}") as response:
                    await response.text()
                    latency = (time.time() - start) * 1000
                    return latency
            except Exception:
                return None

        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            # Warm up
            for _ in range(10):
                await make_request(session)

            # Benchmark with concurrency
            for batch in range(0, num_requests, concurrent):
                batch_size = min(concurrent, num_requests - batch)
                tasks = [make_request(session) for _ in range(batch_size)]
                results = await asyncio.gather(*tasks)

                for result in results:
                    if result is not None:
                        latencies.append(result)
                    else:
                        errors += 1

        duration = time.time() - start_time

        return BenchmarkResult(
            name=f"api_{endpoint}",
            duration=duration,
            operations=num_requests,
            throughput=(num_requests - errors) / duration,
            latency_p50=np.percentile(latencies, 50) if latencies else 0,
            latency_p95=np.percentile(latencies, 95) if latencies else 0,
            latency_p99=np.percentile(latencies, 99) if latencies else 0,
            memory_used=0,
            cpu_percent=0,
            metadata={"errors": errors, "error_rate": errors / num_requests},
        )


class ArchitectureBenchmark:
    """Benchmarks comparing old vs new architecture."""

    async def benchmark_service_layer(self) -> BenchmarkResult:
        """Benchmark service layer performance."""
        # Compare old service implementation vs new application layer

        latencies = []
        start_time = time.time()

        for i in range(1000):
            op_start = time.time()
            # Simulate service call
            await asyncio.sleep(0.001)
            latencies.append((time.time() - op_start) * 1000)

        duration = time.time() - start_time

        return BenchmarkResult(
            name="service_layer",
            duration=duration,
            operations=1000,
            throughput=1000 / duration,
            latency_p50=np.percentile(latencies, 50),
            latency_p95=np.percentile(latencies, 95),
            latency_p99=np.percentile(latencies, 99),
            memory_used=0,
            cpu_percent=0,
        )

    async def benchmark_dependency_injection(self) -> BenchmarkResult:
        """Benchmark dependency injection overhead."""

        # Measure DI container resolution time
        latencies = []
        start_time = time.time()

        for _ in range(10000):
            op_start = time.time()
            # Simulate DI resolution
            await asyncio.sleep(0.0001)
            latencies.append((time.time() - op_start) * 1000)

        duration = time.time() - start_time

        return BenchmarkResult(
            name="dependency_injection",
            duration=duration,
            operations=10000,
            throughput=10000 / duration,
            latency_p50=np.percentile(latencies, 50),
            latency_p95=np.percentile(latencies, 95),
            latency_p99=np.percentile(latencies, 99),
            memory_used=0,
            cpu_percent=0,
        )


class BenchmarkRunner:
    """Runs benchmark suites and generates reports."""

    def __init__(self, output_dir: Path = Path("benchmark_results")):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.suites: List[BenchmarkSuite] = []

    async def run_all_benchmarks(self) -> BenchmarkSuite:
        """Run all benchmark suites."""
        suite = BenchmarkSuite(name="Complete Benchmark Suite")

        # Cache benchmarks
        print("Running cache benchmarks...")
        cache_bench = CacheBenchmark()
        suite.add_result(await cache_bench.benchmark_cache_operations())
        suite.add_result(await cache_bench.benchmark_cache_hit_rate())

        # Database benchmarks
        print("Running database benchmarks...")
        db_bench = DatabaseBenchmark()
        suite.add_result(await db_bench.benchmark_query_performance())
        suite.add_result(await db_bench.benchmark_connection_pool())

        # Architecture benchmarks
        print("Running architecture benchmarks...")
        arch_bench = ArchitectureBenchmark()
        suite.add_result(await arch_bench.benchmark_service_layer())
        suite.add_result(await arch_bench.benchmark_dependency_injection())

        suite.end_time = datetime.now()
        self.suites.append(suite)

        return suite

    def compare_results(self, before: BenchmarkSuite, after: BenchmarkSuite) -> Dict[str, Any]:
        """Compare benchmark results before and after migration."""
        comparison = {}

        # Create lookup maps
        before_map = {r.name: r for r in before.results}
        after_map = {r.name: r for r in after.results}

        for name in before_map:
            if name in after_map:
                before_result = before_map[name]
                after_result = after_map[name]

                comparison[name] = {
                    "throughput_change": (after_result.throughput - before_result.throughput)
                    / before_result.throughput
                    * 100,
                    "latency_p50_change": (after_result.latency_p50 - before_result.latency_p50)
                    / before_result.latency_p50
                    * 100,
                    "latency_p95_change": (after_result.latency_p95 - before_result.latency_p95)
                    / before_result.latency_p95
                    * 100,
                    "memory_change": (
                        (after_result.memory_used - before_result.memory_used)
                        / before_result.memory_used
                        * 100
                        if before_result.memory_used > 0
                        else 0
                    ),
                }

        return comparison

    def save_results(self, suite: BenchmarkSuite):
        """Save benchmark results to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save JSON
        json_file = self.output_dir / f"benchmark_{timestamp}.json"
        with open(json_file, "w") as f:
            results_data = [
                {
                    "name": r.name,
                    "duration": r.duration,
                    "operations": r.operations,
                    "throughput": r.throughput,
                    "latency_p50": r.latency_p50,
                    "latency_p95": r.latency_p95,
                    "latency_p99": r.latency_p99,
                    "memory_used": r.memory_used,
                    "cpu_percent": r.cpu_percent,
                    "metadata": r.metadata,
                }
                for r in suite.results
            ]
            json.dump(results_data, f, indent=2)

        # Save CSV
        csv_file = self.output_dir / f"benchmark_{timestamp}.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Name",
                    "Throughput",
                    "Latency P50",
                    "Latency P95",
                    "Latency P99",
                    "Memory (MB)",
                    "CPU %",
                ]
            )
            for r in suite.results:
                writer.writerow(
                    [
                        r.name,
                        f"{r.throughput:.2f}",
                        f"{r.latency_p50:.2f}",
                        f"{r.latency_p95:.2f}",
                        f"{r.latency_p99:.2f}",
                        f"{r.memory_used:.2f}",
                        f"{r.cpu_percent:.2f}",
                    ]
                )

        print(f"Results saved to {json_file} and {csv_file}")

    def generate_report(self, suite: BenchmarkSuite):
        """Generate HTML report with charts."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create charts
        self._create_charts(suite, timestamp)

        # Generate HTML
        html_file = self.output_dir / f"report_{timestamp}.html"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Benchmark Report - {timestamp}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                .chart {{ margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>Performance Benchmark Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <h2>Summary</h2>
            <p>Total benchmarks: {len(suite.results)}</p>
            <p>Total duration: {(suite.end_time - suite.start_time).total_seconds():.2f} seconds</p>
            
            <h2>Results</h2>
            <table>
                <tr>
                    <th>Benchmark</th>
                    <th>Throughput (ops/sec)</th>
                    <th>P50 Latency (ms)</th>
                    <th>P95 Latency (ms)</th>
                    <th>P99 Latency (ms)</th>
                </tr>
        """

        for r in suite.results:
            html_content += f"""
                <tr>
                    <td>{r.name}</td>
                    <td>{r.throughput:.2f}</td>
                    <td>{r.latency_p50:.2f}</td>
                    <td>{r.latency_p95:.2f}</td>
                    <td>{r.latency_p99:.2f}</td>
                </tr>
            """

        html_content += """
            </table>
            
            <h2>Charts</h2>
            <div class="chart">
                <img src="throughput_chart.png" alt="Throughput Chart">
            </div>
            <div class="chart">
                <img src="latency_chart.png" alt="Latency Chart">
            </div>
        </body>
        </html>
        """

        with open(html_file, "w") as f:
            f.write(html_content)

        print(f"Report generated: {html_file}")

    def _create_charts(self, suite: BenchmarkSuite, timestamp: str):
        """Create performance charts."""
        # Throughput chart
        plt.figure(figsize=(12, 6))

        names = [r.name for r in suite.results]
        throughputs = [r.throughput for r in suite.results]

        plt.subplot(1, 2, 1)
        plt.bar(names, throughputs, color="green")
        plt.xlabel("Benchmark")
        plt.ylabel("Throughput (ops/sec)")
        plt.title("Throughput Comparison")
        plt.xticks(rotation=45, ha="right")

        # Latency chart
        plt.subplot(1, 2, 2)
        x = np.arange(len(names))
        width = 0.25

        p50 = [r.latency_p50 for r in suite.results]
        p95 = [r.latency_p95 for r in suite.results]
        p99 = [r.latency_p99 for r in suite.results]

        plt.bar(x - width, p50, width, label="P50", color="blue")
        plt.bar(x, p95, width, label="P95", color="orange")
        plt.bar(x + width, p99, width, label="P99", color="red")

        plt.xlabel("Benchmark")
        plt.ylabel("Latency (ms)")
        plt.title("Latency Comparison")
        plt.xticks(x, names, rotation=45, ha="right")
        plt.legend()

        plt.tight_layout()
        plt.savefig(self.output_dir / "performance_charts.png")
        plt.close()


async def main():
    """Run benchmark suite."""
    runner = BenchmarkRunner()

    print("Starting benchmark suite...")
    print("=" * 50)

    # Run benchmarks
    suite = await runner.run_all_benchmarks()

    # Save results
    runner.save_results(suite)

    # Generate report
    runner.generate_report(suite)

    # Print summary
    print("\n" + "=" * 50)
    print("Benchmark Summary")
    print("=" * 50)

    summary = suite.get_summary()
    for key, value in summary.items():
        print(f"{key}: {value:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
