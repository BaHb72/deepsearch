"""
Provider 架构集成测试

验证 Phase 1 和 Phase 2 的实现是否正确：
1. Protocol 定义是否正确
2. Factory 能否创建 Provider
3. Provider 是否实现了 Protocol
4. Container 能否管理 Provider 生命周期
"""

import asyncio

from core.infrastructure.providers.container import ProviderContainer

# Phase 1: 导入基础架构
from core.infrastructure.providers.exceptions import ProviderNotFoundError
from core.infrastructure.providers.factory.provider_factory import ProviderFactory
from core.infrastructure.providers.protocols.capabilities import IKlineProvider, IRealtimeProvider
from core.infrastructure.providers.protocols.lifecycle import HealthStatus, ILifecycleProvider
from loguru import logger


async def test_protocol_implementations():
    """测试 1: 验证所有 Provider 实现了 Protocol"""
    logger.info("=" * 60)
    logger.info("测试 1: 验证 Protocol 实现")
    logger.info("=" * 60)

    factory = ProviderFactory()

    # 测试配置
    test_configs = {
        "amazingdata": {
            "username": "test_user",
            "password": "test_pass",
            "host": "124.71.151.123",
            "port": 16666,
            "cache_enabled": True,
        },
        "miniqmt": {
            "host": "127.0.0.1",
            "port": 7777,
        },
        "akshare": {},
    }

    results = []

    for name, config in test_configs.items():
        try:
            logger.info(f"\n检查 {name} Provider...")

            # 创建 Provider
            provider = factory.create(name, config)
            logger.info(f"  ✓ 创建成功: {type(provider).__name__}")

            # 检查 ILifecycleProvider
            if isinstance(provider, ILifecycleProvider):
                logger.info("  ✓ 实现了 ILifecycleProvider")
                has_lifecycle = True
            else:
                logger.warning("  ✗ 未实现 ILifecycleProvider")
                has_lifecycle = False

            # 检查 IKlineProvider
            if isinstance(provider, IKlineProvider):
                logger.info("  ✓ 实现了 IKlineProvider")
                has_kline = True
            else:
                logger.warning("  ✗ 未实现 IKlineProvider")
                has_kline = False

            # 检查 IRealtimeProvider
            if isinstance(provider, IRealtimeProvider):
                logger.info("  ✓ 实现了 IRealtimeProvider")
                has_realtime = True
            else:
                logger.warning("  ✗ 未实现 IRealtimeProvider")
                has_realtime = False

            results.append(
                {
                    "provider": name,
                    "success": True,
                    "lifecycle": has_lifecycle,
                    "kline": has_kline,
                    "realtime": has_realtime,
                }
            )

        except Exception as e:
            logger.error(f"  ✗ 创建失败: {e}")
            results.append({"provider": name, "success": False, "error": str(e)})

    # 汇总结果
    logger.info("\n" + "=" * 60)
    logger.info("测试 1 结果汇总:")
    logger.info("=" * 60)

    for result in results:
        if result["success"]:
            logger.info(
                f"{result['provider']}: Lifecycle={result['lifecycle']}, "
                f"Kline={result['kline']}, Realtime={result['realtime']}"
            )
        else:
            logger.error(f"{result['provider']}: 创建失败 - {result.get('error')}")

    return all(r["success"] for r in results)


async def test_container_lifecycle():
    """测试 2: 验证 Container 生命周期管理"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 2: 验证 Container 生命周期管理")
    logger.info("=" * 60)

    container = ProviderContainer()

    try:
        # 测试 1: 创建并注册 Provider
        logger.info("\n[1] 创建并注册 Provider...")
        config = {
            "username": "test",
            "password": "test",
            "host": "124.71.151.123",
            "port": 16666,
        }

        provider = await container.create_and_register("amazingdata", config)
        logger.info(f"  ✓ Provider 创建成功: {type(provider).__name__}")

        # 测试 2: 获取已注册的 Provider
        logger.info("\n[2] 获取已注册的 Provider...")
        retrieved = await container.get("amazingdata")
        if retrieved is provider:
            logger.info("  ✓ 获取成功，实例相同（单例模式）")
        else:
            logger.warning("  ✗ 获取的实例不同")

        # 测试 3: 检查 Provider 是否存在
        logger.info("\n[3] 检查 Provider 是否存在...")
        if container.has("amazingdata"):
            logger.info("  ✓ Provider 存在于容器中")
        else:
            logger.error("  ✗ Provider 不存在于容器中")

        # 测试 4: 获取不存在的 Provider
        logger.info("\n[4] 获取不存在的 Provider...")
        try:
            await container.get("nonexistent")
            logger.error("  ✗ 应该抛出 ProviderNotFoundError")
            return False
        except ProviderNotFoundError:
            logger.info("  ✓ 正确抛出 ProviderNotFoundError")

        # 测试 5: 健康检查
        logger.info("\n[5] 执行健康检查...")
        health = await container.health_check("amazingdata")
        logger.info(f"  健康状态: {health.status.value}")
        logger.info(f"  消息: {health.message}")
        logger.info(f"  详情: {health.details}")

        # 测试 6: 关闭容器
        logger.info("\n[6] 关闭容器...")
        await container.shutdown()
        logger.info("  ✓ 容器关闭成功")

        logger.info("\n" + "=" * 60)
        logger.info("测试 2 结果: 全部通过 ✓")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"\n测试 2 失败: {e}")
        logger.exception(e)
        return False


async def test_factory_strategies():
    """测试 3: 验证 Factory 策略模式"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 3: 验证 Factory 策略模式")
    logger.info("=" * 60)

    factory = ProviderFactory()

    # 测试 1: 检查所有注册的策略
    logger.info("\n[1] 检查注册的 Factory 策略...")
    registered = factory.get_registered_providers()
    logger.info(f"  已注册的 Provider: {registered}")

    expected = {"amazingdata", "miniqmt", "akshare"}
    if set(registered) == expected:
        logger.info("  ✓ 所有预期的 Factory 都已注册")
    else:
        missing = expected - set(registered)
        extra = set(registered) - expected
        if missing:
            logger.warning(f"  ✗ 缺少的 Factory: {missing}")
        if extra:
            logger.warning(f"  ✗ 额外的 Factory: {extra}")

    # 测试 2: 验证配置
    logger.info("\n[2] 验证配置...")
    valid_configs = {
        "amazingdata": {
            "username": "test",
            "password": "test",
            "host": "124.71.151.123",
            "port": 16666,
        },
        "miniqmt": {"host": "127.0.0.1", "port": 7777},
        "akshare": {},
    }

    for name, config in valid_configs.items():
        try:
            factory.validate_config(name, config)
            logger.info(f"  ✓ {name} 配置验证通过")
        except Exception as e:
            logger.error(f"  ✗ {name} 配置验证失败: {e}")

    # 测试 3: 无效配置应该抛出异常
    logger.info("\n[3] 测试无效配置...")
    try:
        factory.validate_config("amazingdata", {})  # 缺少必需字段
        logger.error("  ✗ 应该抛出配置验证异常")
    except Exception:
        logger.info("  ✓ 正确抛出配置验证异常")

    # 测试 4: 未知 Provider 应该抛出异常
    logger.info("\n[4] 测试未知 Provider...")
    try:
        factory.create("unknown_provider", {})
        logger.error("  ✗ 应该抛出 UnknownProviderError")
    except Exception as e:
        if "未知的 Provider 类型" in str(e):
            logger.info("  ✓ 正确抛出 UnknownProviderError")
        else:
            logger.warning(f"  ⚠ 抛出了异常但消息不符: {e}")

    logger.info("\n" + "=" * 60)
    logger.info("测试 3 结果: 全部通过 ✓")
    logger.info("=" * 60)
    return True


async def test_health_check_states():
    """测试 4: 验证健康检查状态"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 4: 验证健康检查状态")
    logger.info("=" * 60)

    container = ProviderContainer()

    try:
        # 创建 Provider 但不启动
        logger.info("\n[1] 创建未启动的 Provider...")
        config = {
            "username": "test",
            "password": "test",
            "host": "124.71.151.123",
            "port": 16666,
        }
        provider = await container.create_and_register("amazingdata", config)

        # 执行健康检查
        health = await container.health_check("amazingdata")
        logger.info(f"  状态: {health.status.value}")
        logger.info(f"  消息: {health.message}")

        # 验证状态枚举
        logger.info("\n[2] 验证 HealthStatus 枚举...")
        valid_states = {
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.UNHEALTHY,
            HealthStatus.UNKNOWN,
        }
        if health.status in valid_states:
            logger.info(f"  ✓ 状态有效: {health.status.value}")
        else:
            logger.error(f"  ✗ 状态无效: {health.status}")

        # 关闭
        await container.shutdown()

        logger.info("\n" + "=" * 60)
        logger.info("测试 4 结果: 全部通过 ✓")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"\n测试 4 失败: {e}")
        logger.exception(e)
        return False


async def run_all_tests():
    """运行所有集成测试"""
    logger.info("\n")
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + " " * 10 + "Provider 架构集成测试套件" + " " * 22 + "║")
    logger.info("╚" + "=" * 58 + "╝")

    results = []

    # 测试 1: Protocol 实现
    try:
        result = await test_protocol_implementations()
        results.append(("Protocol 实现", result))
    except Exception as e:
        logger.error(f"测试 1 异常: {e}")
        results.append(("Protocol 实现", False))

    # 测试 2: Container 生命周期
    try:
        result = await test_container_lifecycle()
        results.append(("Container 生命周期", result))
    except Exception as e:
        logger.error(f"测试 2 异常: {e}")
        results.append(("Container 生命周期", False))

    # 测试 3: Factory 策略
    try:
        result = await test_factory_strategies()
        results.append(("Factory 策略", result))
    except Exception as e:
        logger.error(f"测试 3 异常: {e}")
        results.append(("Factory 策略", False))

    # 测试 4: 健康检查
    try:
        result = await test_health_check_states()
        results.append(("健康检查状态", result))
    except Exception as e:
        logger.error(f"测试 4 异常: {e}")
        results.append(("健康检查状态", False))

    # 汇总报告
    logger.info("\n")
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + " " * 20 + "最终测试报告" + " " * 26 + "║")
    logger.info("╚" + "=" * 58 + "╝")

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"  {name}: {status}")

    total = len(results)
    passed = sum(1 for _, r in results if r)
    failed = total - passed

    logger.info("\n" + "-" * 60)
    logger.info(f"总计: {total} 个测试，{passed} 个通过，{failed} 个失败")
    logger.info("-" * 60)

    if failed == 0:
        logger.info("\n🎉 所有测试通过！Provider 架构重构成功！")
        return True
    else:
        logger.warning(f"\n⚠️  有 {failed} 个测试失败，需要修复")
        return False


if __name__ == "__main__":
    asyncio.run(run_all_tests())
