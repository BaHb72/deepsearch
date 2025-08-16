"""
数据源验证服务
对比和验证不同数据源的数据质量
"""
import time
from enum import Enum
from typing import Dict, Any, List, Tuple

import numpy as np


class DataSource(Enum):
    """数据源枚举"""
    AKSHARE = "akshare"
    QMT = "qmt"
    EASTMONEY = "eastmoney"
    SINA = "sina"


class ValidationResult:
    """验证结果"""

    def __init__(self):
        self.timestamp = time.time()
        self.symbol = ""
        self.field = ""
        self.source1 = None
        self.source2 = None
        self.value1 = None
        self.value2 = None
        self.diff_value = None
        self.diff_percent = None
        self.is_valid = True
        self.message = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "field": self.field,
            "source1": self.source1.value if self.source1 else None,
            "source2": self.source2.value if self.source2 else None,
            "value1": self.value1,
            "value2": self.value2,
            "diff_value": self.diff_value,
            "diff_percent": self.diff_percent,
            "is_valid": self.is_valid,
            "message": self.message
        }


class DataSourceValidator:
    """数据源验证器"""

    # 允许的价格偏差百分比
    PRICE_TOLERANCE = 0.1  # 0.1%
    # 允许的成交量偏差百分比
    VOLUME_TOLERANCE = 1.0  # 1%
    # 允许的时间偏差（秒）
    TIME_TOLERANCE = 5

    def __init__(self):
        """初始化验证器"""
        self.validation_history: List[ValidationResult] = []
        self.max_history = 1000

        # 数据源状态
        self.source_status = {
            DataSource.AKSHARE: {"available": True, "last_check": 0, "error_count": 0},
            DataSource.QMT: {"available": True, "last_check": 0, "error_count": 0},
        }

        # 统计信息
        self.stats = {
            "total_validations": 0,
            "valid_count": 0,
            "invalid_count": 0,
            "source_errors": {},
            "field_errors": {}
        }

    def validate_price(self, price1: float, price2: float,
                       tolerance: float = None) -> Tuple[bool, float]:
        """
        验证价格数据
        
        Args:
            price1: 第一个价格
            price2: 第二个价格
            tolerance: 容差百分比
            
        Returns:
            (是否有效, 偏差百分比)
        """
        if tolerance is None:
            tolerance = self.PRICE_TOLERANCE

        if price1 == 0 or price2 == 0:
            return price1 == price2, 0

        diff_percent = abs(price1 - price2) / price1 * 100
        return diff_percent <= tolerance, diff_percent

    def validate_volume(self, volume1: int, volume2: int,
                        tolerance: float = None) -> Tuple[bool, float]:
        """
        验证成交量数据
        
        Args:
            volume1: 第一个成交量
            volume2: 第二个成交量
            tolerance: 容差百分比
            
        Returns:
            (是否有效, 偏差百分比)
        """
        if tolerance is None:
            tolerance = self.VOLUME_TOLERANCE

        if volume1 == 0 or volume2 == 0:
            return volume1 == volume2, 0

        diff_percent = abs(volume1 - volume2) / volume1 * 100
        return diff_percent <= tolerance, diff_percent

    def validate_tick_data(self, data1: Dict[str, Any], data2: Dict[str, Any],
                           source1: DataSource, source2: DataSource) -> List[ValidationResult]:
        """
        验证Tick数据
        
        Args:
            data1: 第一个数据源的数据
            data2: 第二个数据源的数据
            source1: 第一个数据源
            source2: 第二个数据源
            
        Returns:
            验证结果列表
        """
        results = []
        symbol = data1.get("symbol", data2.get("symbol", ""))

        # 验证价格字段
        price_fields = [
            ("price", "当前价"),
            ("open", "开盘价"),
            ("high", "最高价"),
            ("low", "最低价"),
            ("prev_close", "昨收价")
        ]

        for field, name in price_fields:
            if field in data1 and field in data2:
                result = ValidationResult()
                result.symbol = symbol
                result.field = name
                result.source1 = source1
                result.source2 = source2
                result.value1 = data1[field]
                result.value2 = data2[field]

                is_valid, diff_percent = self.validate_price(
                    data1[field], data2[field]
                )

                result.is_valid = is_valid
                result.diff_percent = diff_percent
                result.diff_value = abs(data1[field] - data2[field])

                if not is_valid:
                    result.message = f"{name}偏差过大: {diff_percent:.2f}%"

                results.append(result)

        # 验证成交量
        if "volume" in data1 and "volume" in data2:
            result = ValidationResult()
            result.symbol = symbol
            result.field = "成交量"
            result.source1 = source1
            result.source2 = source2
            result.value1 = data1["volume"]
            result.value2 = data2["volume"]

            is_valid, diff_percent = self.validate_volume(
                data1["volume"], data2["volume"]
            )

            result.is_valid = is_valid
            result.diff_percent = diff_percent
            result.diff_value = abs(data1["volume"] - data2["volume"])

            if not is_valid:
                result.message = f"成交量偏差过大: {diff_percent:.2f}%"

            results.append(result)

        # 更新统计
        self.stats["total_validations"] += len(results)
        for result in results:
            if result.is_valid:
                self.stats["valid_count"] += 1
            else:
                self.stats["invalid_count"] += 1

                # 记录错误字段
                field_key = f"{symbol}_{result.field}"
                if field_key not in self.stats["field_errors"]:
                    self.stats["field_errors"][field_key] = 0
                self.stats["field_errors"][field_key] += 1

        # 保存历史
        self.validation_history.extend(results)
        if len(self.validation_history) > self.max_history:
            self.validation_history = self.validation_history[-self.max_history:]

        return results

    def compare_kline_data(self, bars1: List[Dict], bars2: List[Dict],
                           source1: DataSource, source2: DataSource) -> Dict[str, Any]:
        """
        比较K线数据
        
        Args:
            bars1: 第一个数据源的K线数据
            bars2: 第二个数据源的K线数据
            source1: 第一个数据源
            source2: 第二个数据源
            
        Returns:
            比较结果
        """
        if not bars1 or not bars2:
            return {
                "status": "error",
                "message": "数据为空"
            }

        # 按时间对齐数据
        time_map1 = {bar.get("time"): bar for bar in bars1}
        time_map2 = {bar.get("time"): bar for bar in bars2}

        common_times = set(time_map1.keys()) & set(time_map2.keys())

        if not common_times:
            return {
                "status": "error",
                "message": "没有共同的时间点"
            }

        # 比较每个时间点的数据
        total_points = len(common_times)
        price_diffs = []
        volume_diffs = []

        for time_key in common_times:
            bar1 = time_map1[time_key]
            bar2 = time_map2[time_key]

            # 计算价格偏差
            for field in ["open", "high", "low", "close"]:
                if field in bar1 and field in bar2:
                    if bar1[field] > 0:
                        diff = abs(bar1[field] - bar2[field]) / bar1[field] * 100
                        price_diffs.append(diff)

            # 计算成交量偏差
            if "volume" in bar1 and "volume" in bar2:
                if bar1["volume"] > 0:
                    diff = abs(bar1["volume"] - bar2["volume"]) / bar1["volume"] * 100
                    volume_diffs.append(diff)

        # 统计结果
        result = {
            "status": "success",
            "total_points": total_points,
            "common_points": len(common_times),
            "coverage": len(common_times) / total_points * 100,
            "price_stats": {
                "mean_diff": np.mean(price_diffs) if price_diffs else 0,
                "max_diff": np.max(price_diffs) if price_diffs else 0,
                "min_diff": np.min(price_diffs) if price_diffs else 0,
                "std_diff": np.std(price_diffs) if price_diffs else 0
            },
            "volume_stats": {
                "mean_diff": np.mean(volume_diffs) if volume_diffs else 0,
                "max_diff": np.max(volume_diffs) if volume_diffs else 0,
                "min_diff": np.min(volume_diffs) if volume_diffs else 0,
                "std_diff": np.std(volume_diffs) if volume_diffs else 0
            }
        }

        # 判断数据质量
        if result["price_stats"]["mean_diff"] < 0.1:
            result["quality"] = "excellent"
        elif result["price_stats"]["mean_diff"] < 0.5:
            result["quality"] = "good"
        elif result["price_stats"]["mean_diff"] < 1.0:
            result["quality"] = "fair"
        else:
            result["quality"] = "poor"

        return result

    def get_validation_report(self) -> Dict[str, Any]:
        """
        获取验证报告
        
        Returns:
            验证报告
        """
        recent_validations = self.validation_history[-100:]

        # 计算成功率
        success_rate = (
            self.stats["valid_count"] / self.stats["total_validations"] * 100
            if self.stats["total_validations"] > 0 else 0
        )

        # 找出问题最多的字段
        top_errors = sorted(
            self.stats["field_errors"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        return {
            "timestamp": time.time(),
            "total_validations": self.stats["total_validations"],
            "success_rate": success_rate,
            "valid_count": self.stats["valid_count"],
            "invalid_count": self.stats["invalid_count"],
            "recent_validations": [v.to_dict() for v in recent_validations],
            "top_error_fields": top_errors,
            "source_status": {
                k.value: v for k, v in self.source_status.items()
            }
        }

    def check_source_availability(self, source: DataSource) -> bool:
        """
        检查数据源可用性
        
        Args:
            source: 数据源
            
        Returns:
            是否可用
        """
        status = self.source_status.get(source, {})
        return status.get("available", False)

    def update_source_status(self, source: DataSource, available: bool, error: str = None):
        """
        更新数据源状态
        
        Args:
            source: 数据源
            available: 是否可用
            error: 错误信息
        """
        if source in self.source_status:
            self.source_status[source]["available"] = available
            self.source_status[source]["last_check"] = time.time()

            if not available:
                self.source_status[source]["error_count"] += 1
                if error:
                    self.source_status[source]["last_error"] = error
            else:
                self.source_status[source]["error_count"] = 0
