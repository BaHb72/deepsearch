"""
MockErrorProvider - 错误处理兜底提供者

当所有数据源都失败时，使用此提供者返回明确的错误信息，
避免系统崩溃，同时记录访问日志用于监控。
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
import pandas as pd
from loguru import logger


class MockErrorProvider:
    """
    错误提供者 - 作为最后的兜底方案

    当所有数据源（AmazingData、AkShare等）都失败时使用，
    返回明确的错误信息而不是让系统崩溃。
    """

    def __init__(self, failure_reason: str = "All data providers failed"):
        """
        初始化错误提供者

        Args:
            failure_reason: 创建此提供者的原因（上游失败信息）
        """
        self.failure_reason = failure_reason
        self.created_at = datetime.now()
        self.access_log = []
        self.access_count = 0
        logger.warning(f"MockErrorProvider created due to: {failure_reason}")

    async def initialize(self) -> bool:
        """
        初始化（始终成功）

        Returns:
            True - 错误提供者始终可用
        """
        logger.info("MockErrorProvider initialized as fallback")
        return True

    async def get_kline(self, symbol: str, **kwargs) -> pd.DataFrame:
        """
        返回空的K线数据框架和错误信息

        Args:
            symbol: 股票代码
            **kwargs: 其他参数

        Returns:
            空的DataFrame
        """
        self._log_access("get_kline", {"symbol": symbol, **kwargs})

        logger.error(f"MockErrorProvider: get_kline called for {symbol}")

        # 返回空的DataFrame，但包含正确的列结构
        return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])

    async def get_realtime_quote(self, symbols: List[str]) -> Dict[str, Any]:
        """
        返回实时行情错误信息

        Args:
            symbols: 股票代码列表

        Returns:
            包含错误信息的字典
        """
        self._log_access("get_realtime_quote", {"symbols": symbols})

        logger.error(f"MockErrorProvider: get_realtime_quote called for {symbols}")

        return {
            "error": "Data provider unavailable",
            "reason": self.failure_reason,
            "provider": "MockErrorProvider",
            "symbols": symbols,
            "timestamp": datetime.now().isoformat()
        }

    async def get_financial_data(self, symbol: str, **kwargs) -> Dict[str, Any]:
        """
        返回财务数据错误信息

        Args:
            symbol: 股票代码
            **kwargs: 其他参数

        Returns:
            包含错误信息的字典
        """
        self._log_access("get_financial_data", {"symbol": symbol, **kwargs})

        logger.error(f"MockErrorProvider: get_financial_data called for {symbol}")

        return {
            "error": "Financial data unavailable",
            "reason": self.failure_reason,
            "provider": "MockErrorProvider",
            "symbol": symbol,
            "timestamp": datetime.now().isoformat()
        }

    async def get_data(self, request_type: str, **kwargs) -> Any:
        """
        通用数据获取接口

        Args:
            request_type: 请求类型
            **kwargs: 请求参数

        Returns:
            错误信息
        """
        self._log_access("get_data", {"request_type": request_type, **kwargs})

        logger.error(f"MockErrorProvider: get_data called for {request_type}")

        return {
            "error": "Data unavailable",
            "reason": self.failure_reason,
            "provider": "MockErrorProvider",
            "request_type": request_type,
            "parameters": kwargs,
            "timestamp": datetime.now().isoformat(),
            "suggestion": "Please check data provider configuration and network connectivity"
        }

    def _log_access(self, method: str, params: Dict[str, Any]):
        """
        记录访问日志

        Args:
            method: 调用的方法名
            params: 调用参数
        """
        self.access_count += 1

        access_record = {
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "params": params,
            "count": self.access_count
        }

        self.access_log.append(access_record)

        # 保留最近的100条访问记录
        if len(self.access_log) > 100:
            self.access_log = self.access_log[-100:]

        # 每10次访问输出一次警告
        if self.access_count % 10 == 0:
            logger.warning(
                f"MockErrorProvider has been accessed {self.access_count} times. "
                f"Original failure: {self.failure_reason}"
            )

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        method_counts = {}
        for record in self.access_log:
            method = record["method"]
            method_counts[method] = method_counts.get(method, 0) + 1

        return {
            "provider_type": "MockErrorProvider",
            "failure_reason": self.failure_reason,
            "created_at": self.created_at.isoformat(),
            "total_access_count": self.access_count,
            "method_counts": method_counts,
            "recent_accesses": self.access_log[-10:] if self.access_log else [],
            "uptime_seconds": (datetime.now() - self.created_at).total_seconds()
        }

    def __repr__(self) -> str:
        """字符串表示"""
        return f"MockErrorProvider(reason='{self.failure_reason[:50]}...', accesses={self.access_count})"

    async def close(self):
        """
        关闭提供者（记录最终统计）
        """
        stats = self.get_statistics()
        logger.info(f"MockErrorProvider closing. Final stats: {stats}")

    # 实现IDataProvider接口的其他方法
    async def get_stock_list(self, market: str = "all") -> List[Dict[str, Any]]:
        """获取股票列表"""
        self._log_access("get_stock_list", {"market": market})
        return []

    async def get_index_components(self, index_code: str) -> List[str]:
        """获取指数成分股"""
        self._log_access("get_index_components", {"index_code": index_code})
        return []

    async def get_trading_calendar(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日历"""
        self._log_access("get_trading_calendar", {"start_date": start_date, "end_date": end_date})
        return []