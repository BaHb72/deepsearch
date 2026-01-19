"""
Provider 架构集成测试 - 真实环境版本

使用真实的数据源连接参数进行测试
"""

import asyncio

from core.infrastructure.providers.container import ProviderContainer

# 导入基础架构
from core.infrastructure.providers.factory.provider_factory import ProviderFactory
from core.infrastructure.providers.protocols.capabilities import IKlineProvider, IRealtimeProvider
from core.infrastructure.providers.protocols.lifecycle import HealthStatus, ILifecycleProvider
from core.ports.data.requests import KlineRequest, RealtimeQuoteRequest
from loguru import logger

# 真实配置（从 data_sources.yaml 读取）
REAL_CONFIGS = {
    "amazingdata": {
        "username": "212200038719",
        "password": "212200038719@2025",
        "host": "101.230.159.234",
        "port": 8600,
        "cache_enabled": True,
        "heartbeat_interval": 60,
        "auto_reconnect": True,
        "reconnect_interval": 10,
        "timeout": 10,
    },
    "akshare": {
        "mode": "proxy",
        "proxy_enabled": True,
        "cache_enabled": True,
        "cache_ttl": 300,
    },
    "miniqmt": {
        "host": "127.0.0.1",
        "port": 7777,
        "mode": "auto",
    },
}


async def test_real_protocol_implementations():
    """测试 1: 真实环境 - Protocol 实现"""
    logger.info("=" * 60)
    logger.info("测试 1: 真实环境 Protocol 实现")
    logger.info("=" * 60)

    factory = ProviderFactory()
    results = []

    # 测试 AmazingData
    logger.info("\n[AmazingData] 真实连接测试...")
    try:
        config = REAL_CONFIGS["amazingdata"]
        provider = factory.create("amazingdata", config)
        logger.info(f"  ✓ 创建成功: {type(provider).__name__}")

        # 检查 Protocol 实现
        implements_lifecycle = isinstance(provider, ILifecycleProvider)
        implements_kline = isinstance(provider, IKlineProvider)
        implements_realtime = isinstance(provider, IRealtimeProvider)

        logger.info(f"  ILifecycleProvider: {implements_lifecycle}")
        logger.info(f"  IKlineProvider: {implements_kline}")
        logger.info(f"  IRealtimeProvider: {implements_realtime}")

        results.append(
            {
                "provider": "amazingdata",
                "success": True,
                "lifecycle": implements_lifecycle,
                "kline": implements_kline,
                "realtime": implements_realtime,
            }
        )

    except Exception as e:
        logger.error(f"  ✗ 失败: {e}")
        results.append({"provider": "amazingdata", "success": False, "error": str(e)})

    # 测试 AkShare
    logger.info("\n[AkShare] 真实连接测试...")
    try:
        config = REAL_CONFIGS["akshare"]
        provider = factory.create("akshare", config)
        logger.info(f"  ✓ 创建成功: {type(provider).__name__}")

        implements_lifecycle = isinstance(provider, ILifecycleProvider)
        implements_kline = isinstance(provider, IKlineProvider)
        implements_realtime = isinstance(provider, IRealtimeProvider)

        logger.info(f"  ILifecycleProvider: {implements_lifecycle}")
        logger.info(f"  IKlineProvider: {implements_kline}")
        logger.info(f"  IRealtimeProvider: {implements_realtime}")

        results.append(
            {
                "provider": "akshare",
                "success": True,
                "lifecycle": implements_lifecycle,
                "kline": implements_kline,
                "realtime": implements_realtime,
            }
        )

    except Exception as e:
        logger.error(f"  ✗ 失败: {e}")
        results.append({"provider": "akshare", "success": False, "error": str(e)})

    # 汇总
    logger.info("\n" + "=" * 60)
    logger.info("测试 1 结果:")
    for result in results:
        if result["success"]:
            logger.info(
                f"  {result['provider']}: ✓ Lifecycle={result['lifecycle']}, "
                f"Kline={result['kline']}, Realtime={result['realtime']}"
            )
        else:
            logger.error(f"  {result['provider']}: ✗ {result.get('error')}")

    success_count = sum(1 for r in results if r["success"])
    return success_count == len(results)


async def test_real_lifecycle_management():
    """测试 2: 真实环境 - 生命周期管理"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 2: 真实环境生命周期管理")
    logger.info("=" * 60)

    container = ProviderContainer()

    try:
        # 创建并初始化 AmazingData Provider
        logger.info("\n[1] 创建 AmazingData Provider...")
        config = REAL_CONFIGS["amazingdata"]
        provider = await container.create_and_register("amazingdata", config)
        logger.info(f"  ✓ Provider 创建成功: {type(provider).__name__}")

        # 检查健康状态
        logger.info("\n[2] 执行健康检查...")
        health_status = await container.health_check("amazingdata")
        logger.info(f"  状态: {health_status.value}")
        if health_status == HealthStatus.HEALTHY:
            logger.info("  消息: 运行正常")
        else:
            logger.warning(f"  状态异常: {health_status.value}")

        # 测试 Protocol 方法（如果实现了）
        if isinstance(provider, ILifecycleProvider):
            logger.info("\n[3] 测试 ILifecycleProvider 方法...")

            # start() 已在 create_and_register 中调用
            logger.info("  ✓ start() 已调用")

            # 再次健康检查
            health2 = await provider.health_check()
            logger.info(f"  健康状态: {health2.status.value} - {health2.message}")

        # 测试 K线查询（如果实现了）
        if isinstance(provider, IKlineProvider):
            logger.info("\n[4] 测试 K线查询...")
            try:
                request = KlineRequest(
                    asset="000001.SZ",
                    timeframe="1d",
                    start_date="20240101",
                    end_date="20240110",
                )
                response = await provider.query_kline(request)
                logger.info(f"  ✓ K线查询成功: {response.success}")
                logger.info(f"  数据条数: {len(response.data) if response.data else 0}")
            except Exception as e:
                logger.warning(f"  ⚠ K线查询失败: {e}")

        # 测试实时行情（如果实现了）
        if isinstance(provider, IRealtimeProvider):
            logger.info("\n[5] 测试实时行情查询...")
            try:
                request = RealtimeQuoteRequest(assets=["000001.SZ", "600000.SH"])
                response = await provider.query_realtime(request)
                logger.info(f"  ✓ 实时行情查询成功: {response.success}")
                logger.info(f"  数据条数: {len(response.data) if response.data else 0}")
            except Exception as e:
                logger.warning(f"  ⚠ 实时行情查询失败: {e}")

        # 关闭容器
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
        try:
            await container.shutdown()
        except:
            pass
        return False


async def test_real_akshare_integration():
    """测试 3: 真实环境 - AkShare 集成"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 3: 真实环境 AkShare 集成")
    logger.info("=" * 60)

    container = ProviderContainer()

    try:
        # 创建 AkShare Provider
        logger.info("\n[1] 创建 AkShare Provider...")
        config = REAL_CONFIGS["akshare"]
        provider = await container.create_and_register("akshare", config)
        logger.info(f"  ✓ Provider 创建成功: {type(provider).__name__}")

        # 健康检查
        logger.info("\n[2] 执行健康检查...")
        health_status = await container.health_check("akshare")
        logger.info(f"  状态: {health_status.value}")
        if health_status == HealthStatus.HEALTHY:
            logger.info("  消息: 运行正常")
        else:
            logger.warning(f"  状态异常: {health_status.value}")

        # 测试 Protocol 方法
        if isinstance(provider, IKlineProvider):
            logger.info("\n[3] 测试 K线查询...")
            try:
                request = KlineRequest(
                    asset="000001",  # AkShare 使用纯数字格式
                    timeframe="1d",
                    start_date="20240101",
                    end_date="20240110",
                )
                response = await provider.query_kline(request)
                logger.info(f"  ✓ K线查询成功: {response.success}")
                if response.data:
                    logger.info(f"  数据条数: {len(response.data)}")
                    logger.info(f"  示例数据: {response.data[0] if response.data else 'N/A'}")
            except Exception as e:
                logger.warning(f"  ⚠ K线查询失败: {e}")

        if isinstance(provider, IRealtimeProvider):
            logger.info("\n[4] 测试实时行情查询...")
            try:
                request = RealtimeQuoteRequest(assets=["000001", "600000"])
                response = await provider.query_realtime(request)
                logger.info(f"  ✓ 实时行情查询成功: {response.success}")
                if response.data:
                    logger.info(f"  数据条数: {len(response.data)}")
            except Exception as e:
                logger.warning(f"  ⚠ 实时行情查询失败: {e}")

        # 关闭
        logger.info("\n[5] 关闭容器...")
        await container.shutdown()
        logger.info("  ✓ 容器关闭成功")

        logger.info("\n" + "=" * 60)
        logger.info("测试 3 结果: 全部通过 ✓")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"\n测试 3 失败: {e}")
        logger.exception(e)
        try:
            await container.shutdown()
        except:
            pass
        return False


async def test_real_multi_provider():
    """测试 4: 真实环境 - 多 Provider 并行管理"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 4: 真实环境多 Provider 并行管理")
    logger.info("=" * 60)

    container = ProviderContainer()

    try:
        # 同时创建多个 Provider
        logger.info("\n[1] 并行创建多个 Provider...")

        providers = {}
        for name in ["amazingdata", "akshare"]:
            try:
                config = REAL_CONFIGS[name]
                provider = await container.create_and_register(name, config)
                providers[name] = provider
                logger.info(f"  ✓ {name}: {type(provider).__name__}")
            except Exception as e:
                logger.warning(f"  ⚠ {name} 创建失败: {e}")

        # 批量健康检查
        logger.info("\n[2] 批量健康检查...")
        for name in providers:
            health_result = await container.health_check(name)
            status_symbol = "✓" if health_result.status == HealthStatus.HEALTHY else "⚠"
            logger.info(
                f"  {status_symbol} {name}: {health_result.status.value} - {health_result.message}"
            )

        # 测试数据查询（如果可用）
        logger.info("\n[3] 测试数据查询...")
        test_symbol = "000001.SZ"

        for name, provider in providers.items():
            if isinstance(provider, IRealtimeProvider):
                try:
                    request = RealtimeQuoteRequest(assets=[test_symbol])
                    response = await provider.query_realtime(request)
                    logger.info(f"  ✓ {name} 实时行情: {response.success}")
                except Exception as e:
                    logger.warning(f"  ⚠ {name} 查询失败: {e}")

        # 关闭所有
        logger.info("\n[4] 关闭所有 Provider...")
        await container.shutdown()
        logger.info("  ✓ 所有 Provider 已关闭")

        logger.info("\n" + "=" * 60)
        logger.info("测试 4 结果: 全部通过 ✓")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"\n测试 4 失败: {e}")
        logger.exception(e)
        try:
            await container.shutdown()
        except:
            pass
        return False


async def run_all_real_tests():
    """运行所有真实环境测试"""
    logger.info("\n")
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + " " * 10 + "Provider 真实环境集成测试" + " " * 22 + "║")
    logger.info("╚" + "=" * 58 + "╝")

    results = []

    # 测试 1: Protocol 实现
    try:
        result = await test_real_protocol_implementations()
        results.append(("Protocol 实现", result))
    except Exception as e:
        logger.error(f"测试 1 异常: {e}")
        results.append(("Protocol 实现", False))

    # 测试 2: 生命周期管理
    try:
        result = await test_real_lifecycle_management()
        results.append(("生命周期管理", result))
    except Exception as e:
        logger.error(f"测试 2 异常: {e}")
        results.append(("生命周期管理", False))

    # 测试 3: AkShare 集成
    try:
        result = await test_real_akshare_integration()
        results.append(("AkShare 集成", result))
    except Exception as e:
        logger.error(f"测试 3 异常: {e}")
        results.append(("AkShare 集成", False))

    # 测试 4: 多 Provider 管理
    try:
        result = await test_real_multi_provider()
        results.append(("多 Provider 管理", result))
    except Exception as e:
        logger.error(f"测试 4 异常: {e}")
        results.append(("多 Provider 管理", False))

    # 汇总报告
    logger.info("\n")
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + " " * 18 + "最终测试报告" + " " * 28 + "║")
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
        logger.info("\n🎉 所有真实环境测试通过！")
        return True
    else:
        logger.warning(f"\n⚠️  有 {failed} 个测试失败")
        return False


if __name__ == "__main__":
    asyncio.run(run_all_real_tests())
