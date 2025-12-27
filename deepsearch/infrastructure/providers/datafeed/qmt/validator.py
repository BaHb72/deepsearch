"""
QMT数据验证和容错机制

实现数据质量检查、异常检测和自动修复
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger


class DataValidator:
    """数据验证器"""

    def __init__(self):
        """初始化验证器"""
        # 价格限制
        self.price_limits: Dict[str, float] = {
            "daily_limit": 0.1,  # 涨跌停限制10%
            "st_limit": 0.05,  # ST股票5%
            "kcb_limit": 0.2,  # 科创板20%
            "cyb_limit": 0.2,  # 创业板20%
        }

        # 异常检测阈值
        self.thresholds: Dict[str, float] = {
            "volume_spike": 10.0,  # 成交量异常倍数
            "price_gap": 0.15,  # 价格跳空阈值
            "zero_volume_days": 30.0,  # 零成交天数阈值
        }

    def validate_tick_data(self, tick_data: Dict) -> Tuple[bool, str]:
        """
        验证Tick数据

        Args:
            tick_data: Tick数据字典

        Returns:
            (是否有效, 错误信息)
        """
        try:
            # 必需字段检查
            required_fields = ["symbol", "last_price", "volume", "timestamp"]
            for field in required_fields:
                if field not in tick_data:
                    return False, f"缺少必需字段: {field}"

            # 价格合理性检查
            last_price = tick_data.get("last_price", 0)
            if last_price <= 0:
                return False, "价格必须大于0"

            # 时间戳检查
            timestamp = tick_data.get("timestamp")
            if timestamp:
                # 检查时间是否在合理范围内（不能是未来时间）
                current_time = datetime.now()
                tick_time = datetime.fromtimestamp(timestamp)
                if tick_time > current_time:
                    return False, "时间戳不能是未来时间"

                # 检查是否在交易时间内
                if not self._is_trading_time(tick_time):
                    logger.warning(f"Tick data not in trading hours: {tick_time}")

            # 成交量检查
            volume = tick_data.get("volume", 0)
            if volume < 0:
                return False, "成交量不能为负"

            # 盘口数据检查
            bid_prices = tick_data.get("bid_price", [])
            ask_prices = tick_data.get("ask_price", [])

            if bid_prices and ask_prices:
                # 买一价应该小于卖一价
                if bid_prices[0] >= ask_prices[0]:
                    return False, "买一价不能大于等于卖一价"

                # 盘口价格应该递减/递增
                for i in range(1, len(bid_prices)):
                    if bid_prices[i] >= bid_prices[i - 1]:
                        return False, "买盘价格应该递减"

                for i in range(1, len(ask_prices)):
                    if ask_prices[i] <= ask_prices[i - 1]:
                        return False, "卖盘价格应该递增"

            return True, ""

        except Exception as e:
            return False, f"验证异常: {str(e)}"

    def validate_kline_data(
        self, kline_data: pd.DataFrame, symbol: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """
        验证K线数据

        Args:
            kline_data: K线数据DataFrame
            symbol: 股票代码

        Returns:
            (是否有效, 错误列表)
        """
        errors = []

        if kline_data.empty:
            return False, ["K线数据为空"]

        try:
            # 必需列检查
            required_columns = ["open", "high", "low", "close", "volume"]
            missing_columns = set(required_columns) - set(kline_data.columns)
            if missing_columns:
                errors.append(f"缺少必需列: {missing_columns}")

            # OHLC关系检查
            if "high" in kline_data.columns and "low" in kline_data.columns:
                invalid_hl = kline_data[kline_data["high"] < kline_data["low"]]
                if not invalid_hl.empty:
                    errors.append(f"发现{len(invalid_hl)}条高价小于低价的记录")

            if all(col in kline_data.columns for col in ["open", "high", "low", "close"]):
                # 最高价应该是OHLC中最大的
                invalid_high = kline_data[
                    (kline_data["high"] < kline_data["open"])
                    | (kline_data["high"] < kline_data["close"])
                ]
                if not invalid_high.empty:
                    errors.append(f"发现{len(invalid_high)}条最高价异常的记录")

                # 最低价应该是OHLC中最小的
                invalid_low = kline_data[
                    (kline_data["low"] > kline_data["open"])
                    | (kline_data["low"] > kline_data["close"])
                ]
                if not invalid_low.empty:
                    errors.append(f"发现{len(invalid_low)}条最低价异常的记录")

            # 价格连续性检查（检测异常跳空）
            if "close" in kline_data.columns:
                price_changes = kline_data["close"].pct_change()

                # 获取股票类型对应的涨跌停限制
                limit = self._get_price_limit(symbol)

                # 检查是否超过涨跌停
                extreme_changes = price_changes[price_changes.abs() > limit * 1.1]  # 允许10%误差
                if not extreme_changes.empty:
                    errors.append(f"发现{len(extreme_changes)}条超过涨跌停限制的记录")

            # 成交量检查
            if "volume" in kline_data.columns:
                negative_volume = kline_data[kline_data["volume"] < 0]
                if not negative_volume.empty:
                    errors.append(f"发现{len(negative_volume)}条成交量为负的记录")

                # 检查长期零成交
                zero_volume = kline_data[kline_data["volume"] == 0]
                zero_volume_limit = int(self.thresholds["zero_volume_days"])
                if len(zero_volume) > zero_volume_limit:
                    errors.append(f"发现超过{zero_volume_limit}天零成交")

            # 时间连续性检查
            if kline_data.index.name == "date" or "date" in kline_data.columns:
                # 检查是否有重复日期
                if kline_data.index.duplicated().any():
                    errors.append("发现重复的日期索引")

            return len(errors) == 0, errors

        except Exception as e:
            errors.append(f"验证异常: {str(e)}")
            return False, errors

    def fix_kline_data(self, kline_data: pd.DataFrame) -> pd.DataFrame:
        """
        修复K线数据中的常见问题

        Args:
            kline_data: K线数据DataFrame

        Returns:
            修复后的K线数据
        """
        df = kline_data.copy()

        try:
            # 修复OHLC关系
            if all(col in df.columns for col in ["open", "high", "low", "close"]):
                # 确保high是最高的
                df["high"] = df[["open", "high", "low", "close"]].max(axis=1)

                # 确保low是最低的
                df["low"] = df[["open", "high", "low", "close"]].min(axis=1)

            # 修复负成交量
            if "volume" in df.columns:
                df.loc[df["volume"] < 0, "volume"] = 0

            if "amount" in df.columns:
                df.loc[df["amount"] < 0, "amount"] = 0

            # 删除全为NaN的行
            df = df.dropna(how="all")

            # 前向填充缺失值（针对停牌等情况）
            df = df.fillna(method="ffill")

            # 删除重复索引
            if df.index.duplicated().any():
                df = df[~df.index.duplicated(keep="first")]

            logger.info(
                f"K-line data fixed, original {len(kline_data)} records, fixed {len(df)} records"
            )

        except Exception as e:
            logger.error(f"Failed to fix K-line data: {e}")
            return kline_data

        return df

    def validate_financial_data(self, financial_data: Dict) -> Tuple[bool, str]:
        """
        验证财务数据

        Args:
            financial_data: 财务数据字典

        Returns:
            (是否有效, 错误信息)
        """
        try:
            # 检查必需字段
            if not financial_data:
                return False, "财务数据为空"

            # 检查数据合理性
            # 例如：净利润率不应该超过100%
            if "net_profit_margin" in financial_data:
                npm = financial_data["net_profit_margin"]
                if npm > 100 or npm < -100:
                    return False, f"净利润率异常: {npm}%"

            # ROE不应该超过100%
            if "roe" in financial_data:
                roe = financial_data["roe"]
                if roe > 100 or roe < -100:
                    return False, f"ROE异常: {roe}%"

            return True, ""

        except Exception as e:
            return False, f"验证异常: {str(e)}"

    def _is_trading_time(self, dt: datetime) -> bool:
        """
        检查是否在交易时间内

        Args:
            dt: 时间

        Returns:
            是否在交易时间内
        """
        # 周末不交易
        if dt.weekday() >= 5:
            return False

        # 交易时间段
        time = dt.time()
        morning_open = datetime.strptime("09:30", "%H:%M").time()
        morning_close = datetime.strptime("11:30", "%H:%M").time()
        afternoon_open = datetime.strptime("13:00", "%H:%M").time()
        afternoon_close = datetime.strptime("15:00", "%H:%M").time()

        return (morning_open <= time <= morning_close) or (
            afternoon_open <= time <= afternoon_close
        )

    def _get_price_limit(self, symbol: Optional[str]) -> float:
        """
        获取股票的涨跌停限制

        Args:
            symbol: 股票代码

        Returns:
            涨跌停限制比例
        """
        if not symbol:
            return self.price_limits["daily_limit"]

        # 科创板
        if symbol.startswith("688"):
            return self.price_limits["kcb_limit"]

        # 创业板
        if symbol.startswith("300"):
            return self.price_limits["cyb_limit"]

        # ST股票（需要从股票名称判断，这里简化处理）
        # 实际应该从股票信息中获取

        return self.price_limits["daily_limit"]

    def detect_anomalies(self, df: pd.DataFrame) -> List[Dict]:
        """
        检测数据中的异常

        Args:
            df: 数据DataFrame

        Returns:
            异常列表
        """
        anomalies = []

        try:
            # 成交量异常检测
            if "volume" in df.columns:
                volume_mean = df["volume"].rolling(window=20).mean()
                volume_std = df["volume"].rolling(window=20).std()

                # Z-score方法检测异常
                z_scores = (df["volume"] - volume_mean) / volume_std
                volume_anomalies = df[z_scores.abs() > 3]

                for idx, row in volume_anomalies.iterrows():
                    anomalies.append(
                        {
                            "date": idx,
                            "type": "volume_spike",
                            "value": row["volume"],
                            "description": "成交量异常",
                        }
                    )

            # 价格跳空检测
            if "close" in df.columns and "open" in df.columns:
                gap = (df["open"] - df["close"].shift(1)) / df["close"].shift(1)
                large_gaps = df[gap.abs() > self.thresholds["price_gap"]]

                for idx, row in large_gaps.iterrows():
                    anomalies.append(
                        {
                            "date": idx,
                            "type": "price_gap",
                            "value": gap[idx],
                            "description": f"价格跳空{gap[idx]:.2%}",
                        }
                    )

        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")

        return anomalies


# 全局验证器实例
_validator_instance = None


def get_validator() -> DataValidator:
    """获取全局验证器实例"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = DataValidator()
    return _validator_instance
