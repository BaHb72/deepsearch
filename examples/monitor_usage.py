"""
监控系统使用示例。

展示如何在 DeepSearch 中使用监控功能。
"""
import time

from deepsearch.event.engine import EventEngine, Event
from deepsearch.monitoring import EventSystemMonitor, MonitorAPI, setup_simple_monitoring


def example_with_api():
    """使用 MonitorAPI 的示例（为 Web UI 做准备）。"""
    print("=== 监控 API 示例 ===")

    # 创建事件引擎
    engine = EventEngine()

    # 创建监控器
    monitor = EventSystemMonitor(engine)
    monitor.start()

    # 创建监控 API
    monitor_api = MonitorAPI(monitor)
    monitor_api.start()

    # 注册一些测试处理器
    def handle_tick(event: Event):
        """处理行情事件"""
        time.sleep(0.01)  # 模拟处理时间

    def handle_order(event: Event):
        """处理订单事件"""
        time.sleep(0.02)
        # 模拟偶尔失败
        if event.data.get("order_id", 0) % 10 == 0:
            raise Exception("模拟订单处理失败")

    engine.register("TICK", handle_tick)
    engine.register("ORDER_STATUS", handle_order)

    # 启动引擎
    engine.start()

    print("监控系统已启动，开始生成测试事件...")

    # 生成一些测试事件
    for i in range(100):
        # 发送行情事件
        engine.put(Event("TICK", {"price": 100 + i * 0.1}))

        # 每5个行情发送一个订单事件
        if i % 5 == 0:
            engine.put(Event("ORDER_STATUS", {"order_id": i}))

        time.sleep(0.1)

    print("\n获取监控数据：")

    # 获取仪表板数据
    dashboard = monitor_api.get_dashboard_data()
    print(f"\n仪表板数据：")
    print(f"  健康状态: {dashboard['current']['health_status']}")
    print(f"  总事件数: {dashboard['current']['total_events']}")
    print(f"  队列大小: {dashboard['current']['queue_size']}")
    print(f"  慢事件数: {dashboard['current']['slow_events']}")
    print(f"  活跃告警: {dashboard['current']['active_alerts']}")

    # 获取实时指标
    metrics = monitor_api.get_realtime_metrics()
    print(f"\n实时指标：")
    for event_type, data in metrics['series'].items():
        if data['count']:
            print(f"  {event_type}:")
            print(f"    最新处理数: {data['count'][-1]}")
            print(f"    成功率: {data['success_rate'][-1]}%")
            print(f"    平均耗时: {data['avg_time_ms'][-1]}ms")

    # 获取告警
    if dashboard['alerts']:
        print(f"\n告警信息：")
        for alert in dashboard['alerts']:
            print(f"  [{alert['level']}] {alert['message']}")

    # 停止系统
    engine.stop()
    monitor.stop()
    monitor_api.stop()

    print("\n监控数据已保存到 data/monitoring/ 目录")


def example_simple_monitor():
    """使用简化监控的示例（适合单机使用）。"""
    print("\n=== 简化监控示例 ===")

    # 创建事件引擎
    engine = EventEngine()

    # 一行启动监控
    monitor = setup_simple_monitoring(engine, config={
        "interval": 10,  # 10秒记录一次
        "enable_json_log": True
    })

    print("简化监控已启动，日志将写入 logs/monitoring/ 目录")

    # 注册处理器并生成事件...
    # （与上面示例相同的代码）

    # 获取最新指标
    latest = monitor.get_latest_metrics()
    if latest:
        print(f"\n最新监控指标：")
        print(f"  时间: {latest['timestamp']}")
        print(f"  健康: {latest['health_status']}")
        print(f"  总事件: {latest['performance']['total_events']}")

        if latest['warnings']:
            print(f"\n警告：")
            for warning in latest['warnings']:
                print(f"  - {warning}")


def example_custom_health_check():
    """添加自定义健康检查的示例。"""
    from deepsearch.monitoring.event_monitor import HealthCheck

    print("\n=== 自定义健康检查示例 ===")

    engine = EventEngine()
    monitor = EventSystemMonitor(engine)

    # 添加自定义健康检查
    def check_database():
        """检查数据库连接"""
        # 这里应该是实际的数据库检查逻辑
        try:
            # 模拟数据库检查
            import random
            if random.random() > 0.9:
                return False, "数据库连接失败"
            return True, None
        except Exception as e:
            return False, str(e)

    def check_disk_space():
        """检查磁盘空间"""
        # 实际应该检查磁盘使用率
        import random
        usage = random.randint(60, 95)
        if usage > 90:
            return False, f"磁盘使用率过高：{usage}%"
        return True, None

    # 添加到健康监控
    monitor._health_monitor.add_check(HealthCheck(
        name="database",
        check_func=check_database,
        critical=True,
        timeout=5.0
    ))

    monitor._health_monitor.add_check(HealthCheck(
        name="disk_space",
        check_func=check_disk_space,
        critical=False,
        timeout=3.0
    ))

    monitor.start()
    engine.start()

    print("已添加自定义健康检查，等待检查结果...")
    time.sleep(5)

    # 获取健康状态
    status, details = monitor._health_monitor.get_status()
    print(f"\n健康状态: {status.value}")
    print("检查详情:")
    for check_name, info in details.items():
        status_str = "✓" if info['success'] else "✗"
        print(f"  {status_str} {check_name}: {info.get('message', 'OK')}")


if __name__ == "__main__":
    # 运行示例
    print("DeepSearch 监控系统示例\n")

    # 1. API 方式（为 Web UI 准备）
    example_with_api()

    # 2. 简化方式（适合单机）
    # example_simple_monitor()

    # 3. 自定义健康检查
    # example_custom_health_check()
