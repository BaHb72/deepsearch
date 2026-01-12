#!/usr/bin/env python
"""
消息总线延迟基准测试

比较 ZeroMQ 和 RabbitMQ 的实时消息延迟，用于决定实时订阅使用哪个消息总线。

用法:
    uv run python scripts/benchmark_message_bus_latency.py
"""

from __future__ import annotations

import asyncio
import statistics
import time
from typing import Any

from loguru import logger


async def benchmark_zeromq(iterations: int = 100) -> dict[str, float]:
    """测试 ZeroMQ 往返延迟

    Args:
        iterations: 测试迭代次数

    Returns:
        延迟统计: avg_ms, p50_ms, p99_ms, min_ms, max_ms
    """
    try:
        from deepsearch.messaging import MessageBusFactory
    except ImportError:
        logger.error("无法导入 messaging 模块")
        return {"error": True, "message": "Import failed"}

    latencies: list[float] = []
    received = asyncio.Event()
    received_data: dict[str, Any] = {}

    def on_message(topic: str, data: dict):
        nonlocal received_data
        received_data = data
        received.set()

    try:
        bus = MessageBusFactory.create(
            "zmq",
            {
                "host": "127.0.0.1",
                "pub_port": 15556,  # 使用不同端口避免冲突
                "sub_port": 15557,
            },
        )
        bus.start()

        # 订阅测试主题
        bus.subscribe("benchmark.test", on_message)

        await asyncio.sleep(0.5)  # 等待连接建立

        for i in range(iterations):
            received.clear()
            start = time.perf_counter()

            # 发布消息
            bus.publish("benchmark.test", {"seq": i, "ts": start})

            # 等待接收
            try:
                await asyncio.wait_for(received.wait(), timeout=1.0)
                end = time.perf_counter()
                latency_ms = (end - start) * 1000
                latencies.append(latency_ms)
            except asyncio.TimeoutError:
                logger.warning(f"ZeroMQ iter {i}: timeout")
                latencies.append(1000)  # 超时记录为 1000ms

        bus.stop()

    except Exception as e:
        logger.error(f"ZeroMQ 测试失败: {e}")
        return {"error": True, "message": str(e)}

    if not latencies:
        return {"error": True, "message": "No data collected"}

    return {
        "avg_ms": statistics.mean(latencies),
        "p50_ms": statistics.median(latencies),
        "p99_ms": (
            statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies)
        ),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "stddev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
        "samples": len(latencies),
    }


async def benchmark_rabbitmq(iterations: int = 100) -> dict[str, float]:
    """测试 RabbitMQ 往返延迟

    Args:
        iterations: 测试迭代次数

    Returns:
        延迟统计
    """
    try:
        from deepsearch.messaging import MessageBusFactory
    except ImportError:
        logger.error("无法导入 messaging 模块")
        return {"error": True, "message": "Import failed"}

    latencies: list[float] = []
    received = asyncio.Event()
    received_data: dict[str, Any] = {}

    def on_message(topic: str, data: dict):
        nonlocal received_data
        received_data = data
        received.set()

    try:
        bus = MessageBusFactory.create(
            "rabbitmq",
            {
                "host": "127.0.0.1",
                "port": 5672,
                "username": "deepsearch",
                "password": "deepsearch123",
                "exchange": "deepsearch.benchmark",
            },
        )
        bus.start()

        # 订阅测试主题
        bus.subscribe("benchmark.test", on_message)

        await asyncio.sleep(1.0)  # RabbitMQ 需要更多时间建立连接

        for i in range(iterations):
            received.clear()
            start = time.perf_counter()

            # 发布消息
            bus.publish("benchmark.test", {"seq": i, "ts": start})

            # 等待接收
            try:
                await asyncio.wait_for(received.wait(), timeout=1.0)
                end = time.perf_counter()
                latency_ms = (end - start) * 1000
                latencies.append(latency_ms)
            except asyncio.TimeoutError:
                logger.warning(f"RabbitMQ iter {i}: timeout")
                latencies.append(1000)

        bus.stop()

    except Exception as e:
        logger.error(f"RabbitMQ 测试失败: {e}")
        return {"error": True, "message": str(e)}

    if not latencies:
        return {"error": True, "message": "No data collected"}

    return {
        "avg_ms": statistics.mean(latencies),
        "p50_ms": statistics.median(latencies),
        "p99_ms": (
            statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies)
        ),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "stddev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
        "samples": len(latencies),
    }


async def main():
    """运行基准测试"""
    print("=" * 60)
    print("消息总线延迟基准测试")
    print("=" * 60)

    iterations = 100

    # 测试 ZeroMQ
    print("\n[1/2] 测试 ZeroMQ...")
    zeromq_results = await benchmark_zeromq(iterations)

    if "error" in zeromq_results:
        print(f"  ❌ ZeroMQ 测试失败: {zeromq_results.get('message')}")
    else:
        print(f"  ✅ ZeroMQ 延迟统计:")
        print(f"     平均: {zeromq_results['avg_ms']:.2f} ms")
        print(f"     P50:  {zeromq_results['p50_ms']:.2f} ms")
        print(f"     P99:  {zeromq_results['p99_ms']:.2f} ms")
        print(f"     最小: {zeromq_results['min_ms']:.2f} ms")
        print(f"     最大: {zeromq_results['max_ms']:.2f} ms")

    # 测试 RabbitMQ
    print("\n[2/2] 测试 RabbitMQ...")
    rabbitmq_results = await benchmark_rabbitmq(iterations)

    if "error" in rabbitmq_results:
        print(f"  ❌ RabbitMQ 测试失败: {rabbitmq_results.get('message')}")
    else:
        print(f"  ✅ RabbitMQ 延迟统计:")
        print(f"     平均: {rabbitmq_results['avg_ms']:.2f} ms")
        print(f"     P50:  {rabbitmq_results['p50_ms']:.2f} ms")
        print(f"     P99:  {rabbitmq_results['p99_ms']:.2f} ms")
        print(f"     最小: {rabbitmq_results['min_ms']:.2f} ms")
        print(f"     最大: {rabbitmq_results['max_ms']:.2f} ms")

    # 比较结果
    print("\n" + "=" * 60)
    print("比较结果")
    print("=" * 60)

    if "error" not in zeromq_results and "error" not in rabbitmq_results:
        zmq_avg = zeromq_results["avg_ms"]
        rmq_avg = rabbitmq_results["avg_ms"]

        if zmq_avg < rmq_avg:
            winner = "ZeroMQ"
            diff = rmq_avg - zmq_avg
            ratio = rmq_avg / zmq_avg if zmq_avg > 0 else float("inf")
        else:
            winner = "RabbitMQ"
            diff = zmq_avg - rmq_avg
            ratio = zmq_avg / rmq_avg if rmq_avg > 0 else float("inf")

        print(f"  🏆 推荐使用: {winner}")
        print(f"     差异: {diff:.2f} ms ({ratio:.1f}x)")

        if zmq_avg < 1.0:
            print("\n  💡 ZeroMQ 延迟 < 1ms，适合实时行情推送")
        elif zmq_avg < 5.0:
            print("\n  💡 ZeroMQ 延迟 < 5ms，可接受")
        else:
            print("\n  ⚠️ ZeroMQ 延迟较高，可能需要检查配置")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
