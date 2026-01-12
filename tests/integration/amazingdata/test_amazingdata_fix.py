"""
测试AmazingData数据源状态同步修复
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.observability.monitoring.data_source_monitor import get_monitor
from core.ports.data_sources import DataAccessType, DataSourceType

from apps.api.api.endpoints.datasources.datasource_manager import (
    update_datasource_status_after_test,
)


async def test_amazingdata_status():
    """测试AmazingData状态同步"""

    print("=" * 60)
    print("测试AmazingData数据源状态同步修复")
    print("=" * 60)

    monitor = get_monitor()

    # 1. 获取初始状态
    print("\n1. 获取AmazingData初始状态")
    initial_health = monitor.get_source_health(DataSourceType.AMAZINGDATA)
    print(f"   - 健康状态: {'健康' if initial_health['healthy'] else '不健康'}")
    print(f"   - 成功率: {initial_health['success_rate']:.2f}%")
    print(f"   - 错误率: {initial_health['recent_error_rate']:.2f}%")
    print(f"   - 总请求数: {initial_health['total_requests']}")

    # 2. 模拟几次失败的访问
    print("\n2. 模拟5次失败的访问（模拟历史错误）")
    for i in range(5):
        monitor.record_access(
            source=DataSourceType.AMAZINGDATA,
            access_type=DataAccessType.REALTIME_QUOTE,
            success=False,
            latency_ms=5000,
            symbol="000001",
            module="test",
            error_message="模拟连接失败",
        )

    # 3. 获取失败后的状态
    after_failure_health = monitor.get_source_health(DataSourceType.AMAZINGDATA)
    print(f"   - 健康状态: {'健康' if after_failure_health['healthy'] else '不健康'}")
    print(f"   - 成功率: {after_failure_health['success_rate']:.2f}%")
    print(f"   - 错误率: {after_failure_health['recent_error_rate']:.2f}%")
    print(f"   - 总请求数: {after_failure_health['total_requests']}")

    # 4. 调用测试成功后的状态更新函数
    print("\n3. 调用update_datasource_status_after_test模拟测试成功")
    # 调用更新函数
    update_datasource_status_after_test("amazingdata", True, 100)

    # 5. 获取更新后的状态
    print("\n4. 获取更新后的AmazingData状态")
    updated_health = monitor.get_source_health(DataSourceType.AMAZINGDATA)
    print(f"   - 健康状态: {'健康' if updated_health['healthy'] else '不健康'}")
    print(f"   - 成功率: {updated_health['success_rate']:.2f}%")
    print(f"   - 错误率: {updated_health['recent_error_rate']:.2f}%")
    print(f"   - 总请求数: {updated_health['total_requests']}")
    print(
        f"   - 平均延迟: {updated_health['avg_latency_ms']:.2f}ms"
        if updated_health["avg_latency_ms"] > 0
        else "   - 平均延迟: 暂无数据"
    )

    # 6. 验证修复效果
    print("\n5. 验证修复效果")
    if updated_health["healthy"]:
        print("   [OK] 修复成功！AmazingData现在显示为健康状态")
        print("   [OK] 测试成功后，监控系统状态已同步更新")
        return True
    else:
        print("   [ERROR] 修复失败！AmazingData仍然显示为不健康状态")
        print("   [ERROR] 可能需要进一步检查")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_amazingdata_status())

    print("\n" + "=" * 60)
    if success:
        print("测试通过！修复有效")
    else:
        print("测试失败！需要进一步调试")
    print("=" * 60)
