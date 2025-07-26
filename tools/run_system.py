#!/usr/bin/env python3
"""
启动完整的 DeepSearch 系统（包括 WebUI）
"""
import time

from deepsearch.constants import EVENT_TICK, EVENT_ORDER
from deepsearch.core import MainEngine


def main():
    print("=== DeepSearch 系统启动 ===")

    # 创建并初始化引擎
    print("1. 初始化系统...")
    engine = MainEngine()
    engine.initialize()

    # 启动系统（包括 WebUI）
    print("2. 启动系统组件...")
    engine.start()

    print("\n系统已启动！")
    print("- WebUI 地址: http://localhost:8000")
    print("- 前端开发服务器: http://localhost:3000")
    print("\n按 Ctrl+C 停止系统")

    # 等待一下让服务完全启动
    time.sleep(2)

    # 可选：自动打开浏览器
    # webbrowser.open('http://localhost:3000')

    try:
        # 模拟一些事件
        print("\n开始生成模拟事件...")
        count = 0
        while True:
            # 生成 TICK 事件
            if count % 5 == 0:
                event = engine._event_engine.create_event(
                    EVENT_TICK,
                    {
                        "symbol": "AAPL",
                        "price": 150 + (count % 10) * 0.1,
                        "volume": 1000 + (count % 100) * 10,
                        "timestamp": time.time()
                    }
                )
                engine._event_engine.put(event)

            # 生成 ORDER 事件
            if count % 10 == 0:
                event = engine._event_engine.create_event(
                    EVENT_ORDER,
                    {
                        "order_id": f"ORD_{count}",
                        "symbol": "AAPL",
                        "side": "BUY" if count % 20 == 0 else "SELL",
                        "price": 150 + (count % 10) * 0.1,
                        "quantity": 100,
                        "status": "FILLED",
                        "timestamp": time.time()
                    }
                )
                engine._event_engine.put(event)

            count += 1
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n正在停止系统...")
        engine.stop()
        print("系统已停止")


if __name__ == "__main__":
    main()
