# encoding:utf-8
"""
AmazingData 实时数据订阅辅助模块
用于测试和获取实时数据的辅助函数

Author: DeepSearch Team
Version: 1.0.0
Date: 2025-09-18
"""

import threading
import time
from typing import Any, Dict

from loguru import logger


def test_realtime_subscription(ad_module, symbol: str, timeout: int = 3) -> Dict[str, Any]:
    """
    使用订阅模式测试实时数据获取

    Args:
        ad_module: AmazingData SDK模块
        symbol: 股票代码（如SH.600000）
        timeout: 超时时间（秒）

    Returns:
        测试结果字典
    """
    result = {"success": False, "message": "", "data": None, "error": None}

    try:
        # 创建订阅对象
        sub_data = ad_module.SubscribeData()
        received_data = []

        # 注册回调函数
        @sub_data.register(code_list=[symbol], period=ad_module.constant.Period.snapshot.value)
        def onSnapshot(data, period):
            """实时快照回调函数"""
            received_data.append({"data": data, "period": period, "timestamp": time.time()})
            logger.info(f"收到实时数据: {symbol} - {period}")

        # 在后台线程运行订阅
        def run_subscription():
            try:
                sub_data.run()
            except Exception as e:
                logger.error(f"订阅运行错误: {e}")

        thread = threading.Thread(target=run_subscription)
        thread.daemon = True
        thread.start()

        # 等待数据
        start_time = time.time()
        while time.time() - start_time < timeout:
            if received_data:
                result["success"] = True
                result["message"] = f"成功接收到{len(received_data)}条实时数据"
                result["data"] = received_data
                break
            time.sleep(0.1)

        if not received_data:
            result["message"] = "未接收到实时数据（可能不在交易时间）"
            result["error"] = "No realtime data received"

        # 停止订阅
        if hasattr(sub_data, "stop"):
            sub_data.stop()

    except Exception as e:
        result["message"] = "订阅测试失败"
        result["error"] = str(e)
        logger.error(f"订阅测试异常: {e}")

    return result


async def test_realtime_with_fallback(ad_module, symbol: str) -> Dict[str, Any]:
    """
    测试实时数据，如果订阅失败则降级到基础数据

    Args:
        ad_module: AmazingData SDK模块
        symbol: 股票代码

    Returns:
        测试结果
    """
    # 首先尝试订阅模式
    subscription_result = test_realtime_subscription(ad_module, symbol, timeout=2)

    if subscription_result["success"]:
        return subscription_result

    # 降级到基础数据测试
    logger.info("订阅模式未返回数据，降级到基础数据测试")

    try:
        base_data = ad_module.BaseData()

        # 获取证券信息
        code_info = base_data.get_code_info("EXTRA_STOCK_A")

        if code_info is not None and len(code_info) > 0:
            # 查找特定股票信息
            if symbol in code_info.index:
                stock_info = code_info.loc[symbol]
                return {
                    "success": True,
                    "message": "获取到股票基础信息",
                    "data": {
                        "symbol": symbol,
                        "pre_close": stock_info.get("pre_close", None),
                        "high_limited": stock_info.get("high_limited", None),
                        "low_limited": stock_info.get("low_limited", None),
                    },
                    "error": None,
                    "note": "实时行情需在交易时间通过订阅获取",
                }
            else:
                # 获取交易日历验证连接
                calendar = base_data.get_calendar()
                return {
                    "success": True,
                    "message": "连接成功，获取到交易日历",
                    "data": {
                        "trading_days": len(calendar) if calendar else 0,
                        "total_stocks": len(code_info),
                    },
                    "error": None,
                    "note": "股票代码不在列表中",
                }
        else:
            return {
                "success": False,
                "message": "无法获取基础数据",
                "data": None,
                "error": "Failed to get basic data",
            }
    except Exception as e:
        return {"success": False, "message": "基础数据测试失败", "data": None, "error": str(e)}


def format_symbol_for_amazingdata(symbol: str) -> str:
    """
    格式化股票代码为AmazingData格式

    Args:
        symbol: 原始股票代码（如000001或SZ.000001）

    Returns:
        格式化后的代码（如SZ.000001）
    """
    # 如果已经是正确格式，直接返回
    if "." in symbol:
        return symbol

    # 6位数字代码，需要添加市场前缀
    if len(symbol) == 6 and symbol.isdigit():
        # 上海市场
        if symbol.startswith(("60", "68", "50", "51")):
            return f"SH.{symbol}"
        # 深圳市场
        elif symbol.startswith(("00", "30", "12")):
            return f"SZ.{symbol}"
        # 北交所
        elif symbol.startswith(("83", "43", "87", "88")):
            return f"BJ.{symbol}"

    # 默认返回原始代码
    return symbol
