"""
回归测试脚本 - 验证新架构组件
"""

import sys


def test_docker_services():
    """测试 1: Docker 服务"""
    print("=" * 60)
    print("测试 1: Docker 服务健康检查")
    print("=" * 60)

    import subprocess

    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}: {{.Status}}"], capture_output=True, text=True
    )

    services = {"rabbitmq": False, "redis": False, "dask-scheduler": False, "dask-worker": False}

    for line in result.stdout.strip().split("\n"):
        for svc in services:
            if svc in line.lower() and "up" in line.lower():
                services[svc] = True
                print(f"  ✅ {line}")

    all_ok = all(services.values())
    if not all_ok:
        for svc, ok in services.items():
            if not ok:
                print(f"  ❌ {svc} 未运行")

    return all_ok


def test_rabbitmq():
    """测试 2: RabbitMQ 消息总线"""
    print("\n" + "=" * 60)
    print("测试 2: RabbitMQ 消息总线")
    print("=" * 60)

    import time

    from deepsearch.messaging import RabbitMQMessageBus

    bus = RabbitMQMessageBus()
    received = []

    def handler(topic, message):
        received.append((topic, message))

    try:
        bus.start()
        print("  ✅ 连接成功")

        bus.subscribe("test.*", handler)
        time.sleep(0.3)

        bus.publish("test.hello", {"msg": "回归测试"})
        bus.publish("test.world", {"msg": "通配符测试"})
        time.sleep(0.5)

        bus.stop()

        if len(received) >= 2:
            print(f"  ✅ 发布/订阅正常 (收到 {len(received)} 条消息)")
            return True
        else:
            print(f"  ❌ 消息丢失 (收到 {len(received)} 条)")
            return False

    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False


def test_dask():
    """测试 3: Dask 集群"""
    print("\n" + "=" * 60)
    print("测试 3: Dask 集群")
    print("=" * 60)

    from deepsearch.compute import DaskTaskClient

    try:
        client = DaskTaskClient()
        info = client.get_cluster_info()
        print(f"  ✅ 连接成功: {info['n_workers']} workers, {info['total_threads']} threads")

        # 简单任务测试
        def add(x, y):
            return x + y

        future = client.submit_task(add, 10, 20)
        result = client.get_result(future, timeout=10)

        if result == 30:
            print(f"  ✅ 任务执行正常: 10 + 20 = {result}")
            client.close()
            return True
        else:
            print(f"  ❌ 任务结果错误: {result}")
            client.close()
            return False

    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False


def test_aggregation():
    """测试 4: 聚合框架"""
    print("\n" + "=" * 60)
    print("测试 4: 聚合框架")
    print("=" * 60)

    import asyncio

    import deepsearch.application.services.aggregation.impl  # noqa
    from deepsearch.application.services.aggregation import (
        AggregationEngine,
        ExecutionMode,
        get_cache,
        get_registry,
    )

    registry = get_registry()
    print(f"  已注册聚合: {list(registry.keys())}")

    async def run_test():
        # 重置单例
        AggregationEngine._instance = None
        engine = AggregationEngine()

        # 测试 DASK 模式
        engine.start(mode=ExecutionMode.DASK)
        await asyncio.sleep(3)

        cache = get_cache()
        await engine.refresh("top_gainers")

        result = cache.get("top_gainers")
        engine.stop()

        return result is not None and len(result) > 0

    try:
        success = asyncio.run(run_test())
        if success:
            print("  ✅ DASK 模式聚合正常")
            return True
        else:
            print("  ❌ 聚合结果为空")
            return False
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False


def main():
    print("\n🔍 DeepSearch 新架构回归测试\n")

    results = {
        "Docker 服务": test_docker_services(),
        "RabbitMQ": test_rabbitmq(),
        "Dask 集群": test_dask(),
        "聚合框架": test_aggregation(),
    }

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    all_passed = True
    for name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("\n" + ("🎉 所有测试通过！" if all_passed else "⚠️ 部分测试失败"))
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
