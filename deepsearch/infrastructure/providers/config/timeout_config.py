"""
数据源超时配置管理
提供统一的超时配置和动态调整机制
"""
from typing import Dict, Optional
from enum import Enum
from loguru import logger


class DataSourceType(Enum):
    """数据源类型"""
    AMAZINGDATA = "amazingdata"
    CLOUDFLARE = "cloudflare"
    AKSHARE = "akshare"
    QMT = "qmt"
    DEFAULT = "default"


class RequestType(Enum):
    """请求类型"""
    REALTIME = "realtime"  # 实时数据
    HISTORICAL = "historical"  # 历史数据
    STOCK_LIST = "stock_list"  # 股票列表
    STOCK_INFO = "stock_info"  # 股票信息
    HEALTH_CHECK = "health_check"  # 健康检查


class TimeoutManager:
    """超时管理器"""

    def __init__(self):
        # 默认超时配置（单位：秒）
        self._default_timeouts = {
            RequestType.REALTIME: 5,  # 实时数据需要快速响应
            RequestType.HISTORICAL: 30,  # 历史数据可以慢一些
            RequestType.STOCK_LIST: 60,  # 股票列表数据量大，需要更长时间
            RequestType.STOCK_INFO: 10,  # 股票信息中等
            RequestType.HEALTH_CHECK: 3,  # 健康检查要快
        }

        # 数据源特定的超时配置
        self._source_timeouts: Dict[DataSourceType, Dict[RequestType, float]] = {
            DataSourceType.AMAZINGDATA: {
                RequestType.REALTIME: 3,  # AmazingData很快
                RequestType.HISTORICAL: 20,
                RequestType.STOCK_LIST: 30,
            },
            DataSourceType.CLOUDFLARE: {
                RequestType.REALTIME: 10,  # 代理稍慢
                RequestType.HISTORICAL: 40,
                RequestType.STOCK_LIST: 45,
            },
            DataSourceType.AKSHARE: {
                RequestType.REALTIME: 15,  # AKShare东方财富接口很慢
                RequestType.HISTORICAL: 60,
                RequestType.STOCK_LIST: 120,  # 东方财富全市场查询特别慢
            },
            DataSourceType.QMT: {
                RequestType.REALTIME: 2,  # QMT本地很快
                RequestType.HISTORICAL: 15,
                RequestType.STOCK_LIST: 20,
            }
        }

        # 动态调整记录
        self._adjustment_history: Dict[str, list] = {}

    def get_timeout(
        self,
        source: DataSourceType = DataSourceType.DEFAULT,
        request_type: RequestType = RequestType.REALTIME,
        custom_timeout: Optional[float] = None
    ) -> float:
        """
        获取超时时间

        Args:
            source: 数据源类型
            request_type: 请求类型
            custom_timeout: 自定义超时（优先级最高）

        Returns:
            超时时间（秒）
        """
        # 优先使用自定义超时
        if custom_timeout is not None and custom_timeout > 0:
            return custom_timeout

        # 查找数据源特定配置
        if source in self._source_timeouts:
            source_config = self._source_timeouts[source]
            if request_type in source_config:
                return source_config[request_type]

        # 使用默认配置
        return self._default_timeouts.get(request_type, 30)

    def adjust_timeout(
        self,
        source: DataSourceType,
        request_type: RequestType,
        success: bool,
        actual_time: float
    ):
        """
        根据实际执行情况动态调整超时

        Args:
            source: 数据源类型
            request_type: 请求类型
            success: 是否成功
            actual_time: 实际耗时
        """
        key = f"{source.value}_{request_type.value}"

        # 记录历史
        if key not in self._adjustment_history:
            self._adjustment_history[key] = []
        self._adjustment_history[key].append({
            'success': success,
            'time': actual_time
        })

        # 只保留最近100条记录
        if len(self._adjustment_history[key]) > 100:
            self._adjustment_history[key] = self._adjustment_history[key][-100:]

        # 计算调整
        if len(self._adjustment_history[key]) >= 10:
            recent = self._adjustment_history[key][-10:]
            success_times = [r['time'] for r in recent if r['success']]

            if success_times:
                # 计算P95时间
                success_times.sort()
                p95_index = int(len(success_times) * 0.95)
                p95_time = success_times[p95_index] if p95_index < len(success_times) else success_times[-1]

                # 新超时 = P95时间 * 1.5（留出余量）
                new_timeout = p95_time * 1.5

                # 更新配置
                if source not in self._source_timeouts:
                    self._source_timeouts[source] = {}

                old_timeout = self.get_timeout(source, request_type)

                # 限制调整幅度（每次最多调整50%）
                if new_timeout > old_timeout * 1.5:
                    new_timeout = old_timeout * 1.5
                elif new_timeout < old_timeout * 0.5:
                    new_timeout = old_timeout * 0.5

                self._source_timeouts[source][request_type] = new_timeout

                logger.debug(
                    f"调整超时: {source.value}.{request_type.value} "
                    f"从 {old_timeout:.1f}s 到 {new_timeout:.1f}s"
                )

    def get_statistics(self) -> Dict:
        """获取超时统计信息"""
        stats = {}

        for key, history in self._adjustment_history.items():
            if history:
                success_count = sum(1 for r in history if r['success'])
                total_count = len(history)
                avg_time = sum(r['time'] for r in history) / total_count

                stats[key] = {
                    'success_rate': success_count / total_count,
                    'avg_time': avg_time,
                    'total_requests': total_count
                }

        return stats


# 全局超时管理器实例
_timeout_manager = TimeoutManager()


def get_timeout(
    source: str = "default",
    request_type: str = "realtime",
    custom_timeout: Optional[float] = None
) -> float:
    """
    获取超时配置（便捷函数）

    Args:
        source: 数据源名称
        request_type: 请求类型
        custom_timeout: 自定义超时

    Returns:
        超时时间（秒）
    """
    try:
        source_enum = DataSourceType[source.upper()]
    except KeyError:
        source_enum = DataSourceType.DEFAULT

    try:
        request_enum = RequestType[request_type.upper()]
    except KeyError:
        request_enum = RequestType.REALTIME

    return _timeout_manager.get_timeout(source_enum, request_enum, custom_timeout)


def adjust_timeout(
    source: str,
    request_type: str,
    success: bool,
    actual_time: float
):
    """
    动态调整超时（便捷函数）

    Args:
        source: 数据源名称
        request_type: 请求类型
        success: 是否成功
        actual_time: 实际耗时
    """
    try:
        source_enum = DataSourceType[source.upper()]
        request_enum = RequestType[request_type.upper()]
        _timeout_manager.adjust_timeout(source_enum, request_enum, success, actual_time)
    except KeyError:
        pass  # 忽略未知类型


def get_timeout_stats() -> Dict:
    """获取超时统计信息"""
    return _timeout_manager.get_statistics()