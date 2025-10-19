"""
金融计算Decimal工具类

使用Python的decimal模块实现精确的金融计算
避免浮点数精度问题，确保金融计算的准确性

Author: DeepSearch Team
Version: 1.0.0
"""

from decimal import ROUND_HALF_UP, Decimal, getcontext
from collections.abc import Sequence
from typing import Optional, Union

# 设置全局精度（小数位数）
# 金融计算通常需要4-10位精度
getcontext().prec = 10
getcontext().rounding = ROUND_HALF_UP  # 四舍五入


class FinanceDecimal:
    """
    金融计算专用Decimal包装类

    提供常用的金融计算方法，自动处理类型转换和精度控制
    """

    def __init__(self, value: Union[str, float, int, Decimal], precision: int = 4):
        """
        初始化金融数值

        Args:
            value: 数值（建议使用字符串以避免精度损失）
            precision: 小数位数精度（默认4位）
        """
        self.precision = precision

        # 转换为Decimal
        if isinstance(value, Decimal):
            self._value = value
        elif isinstance(value, str):
            self._value = Decimal(value)
        elif isinstance(value, (int, float)):
            # 浮点数先转字符串再转Decimal，避免精度损失
            self._value = Decimal(str(value))
        else:
            raise TypeError(f"Unsupported type: {type(value)}")

    @property
    def value(self) -> Decimal:
        """获取Decimal值"""
        return self._value

    def to_float(self) -> float:
        """转换为浮点数（可能损失精度）"""
        return float(self._value)

    def to_str(self, precision: Optional[int] = None) -> str:
        """
        转换为字符串

        Args:
            precision: 小数位数，None则使用初始化时的精度
        """
        prec = precision or self.precision
        quantize_str = "0." + "0" * prec
        return str(self._value.quantize(Decimal(quantize_str)))

    def __str__(self) -> str:
        return self.to_str()

    def __repr__(self) -> str:
        return f"FinanceDecimal('{self._value}')"

    # 算术运算符重载
    def __add__(self, other):
        other_decimal = self._to_decimal(other)
        return FinanceDecimal(self._value + other_decimal, self.precision)

    def __sub__(self, other):
        other_decimal = self._to_decimal(other)
        return FinanceDecimal(self._value - other_decimal, self.precision)

    def __mul__(self, other):
        other_decimal = self._to_decimal(other)
        return FinanceDecimal(self._value * other_decimal, self.precision)

    def __truediv__(self, other):
        other_decimal = self._to_decimal(other)
        if other_decimal == 0:
            raise ZeroDivisionError("Division by zero")
        return FinanceDecimal(self._value / other_decimal, self.precision)

    # 比较运算符重载
    def __eq__(self, other):
        other_decimal = self._to_decimal(other)
        return self._value == other_decimal

    def __lt__(self, other):
        other_decimal = self._to_decimal(other)
        return self._value < other_decimal

    def __le__(self, other):
        other_decimal = self._to_decimal(other)
        return self._value <= other_decimal

    def __gt__(self, other):
        other_decimal = self._to_decimal(other)
        return self._value > other_decimal

    def __ge__(self, other):
        other_decimal = self._to_decimal(other)
        return self._value >= other_decimal

    @staticmethod
    def _to_decimal(value) -> Decimal:
        """转换为Decimal类型"""
        if isinstance(value, FinanceDecimal):
            return value._value
        elif isinstance(value, Decimal):
            return value
        elif isinstance(value, str):
            return Decimal(value)
        elif isinstance(value, (int, float)):
            return Decimal(str(value))
        else:
            raise TypeError(f"Cannot convert {type(value)} to Decimal")


# ==================== 常用金融计算函数 ====================


def calculate_spread(
    bid_price: Union[float, str, Decimal], ask_price: Union[float, str, Decimal], precision: int = 4
) -> Decimal:
    """
    计算买卖价差

    Args:
        bid_price: 买入价
        ask_price: 卖出价
        precision: 精度（小数位数）

    Returns:
        价差（Decimal类型）
    """
    bid = Decimal(str(bid_price))
    ask = Decimal(str(ask_price))
    spread = ask - bid

    # 设置精度
    quantize_str = "0." + "0" * precision
    return spread.quantize(Decimal(quantize_str))


def calculate_change_rate(
    current_price: Union[float, str, Decimal],
    previous_price: Union[float, str, Decimal],
    precision: int = 4,
) -> Decimal:
    """
    计算涨跌幅

    Args:
        current_price: 当前价格
        previous_price: 前一价格（如昨收价）
        precision: 精度（小数位数）

    Returns:
        涨跌幅（百分比形式，如0.0523表示5.23%）
    """
    current = Decimal(str(current_price))
    previous = Decimal(str(previous_price))

    if previous == 0:
        return Decimal("0")

    change_rate = (current - previous) / previous

    # 设置精度
    quantize_str = "0." + "0" * precision
    return change_rate.quantize(Decimal(quantize_str))


def calculate_return(
    initial_value: Union[float, str, Decimal],
    final_value: Union[float, str, Decimal],
    precision: int = 6,
) -> Decimal:
    """
    计算收益率

    Args:
        initial_value: 初始价值
        final_value: 最终价值
        precision: 精度（小数位数）

    Returns:
        收益率（Decimal类型）
    """
    initial = Decimal(str(initial_value))
    final = Decimal(str(final_value))

    if initial == 0:
        return Decimal("0")

    return_rate = (final - initial) / initial

    # 设置精度
    quantize_str = "0." + "0" * precision
    return return_rate.quantize(Decimal(quantize_str))


def format_price(price: Union[float, str, Decimal], precision: int = 2) -> str:
    """
    格式化价格显示

    Args:
        price: 价格
        precision: 小数位数（默认2位）

    Returns:
        格式化后的价格字符串
    """
    price_decimal = Decimal(str(price))
    quantize_str = "0." + "0" * precision
    formatted = price_decimal.quantize(Decimal(quantize_str))
    return str(formatted)


def format_volume(volume: Union[int, float, str], unit: str = "hand") -> str:
    """
    格式化成交量显示

    Args:
        volume: 成交量（股）
        unit: 单位（'hand'表示手，'k'表示千，'m'表示百万）

    Returns:
        格式化后的成交量字符串
    """
    vol = Decimal(str(volume))

    if unit == "hand":
        # A股1手=100股
        hands = vol / 100
        return f"{hands:.0f}手"
    elif unit == "k":
        thousands = vol / 1000
        return f"{thousands:.2f}K"
    elif unit == "m":
        millions = vol / 1000000
        return f"{millions:.2f}M"
    else:
        return str(int(vol))


def round_price(
    price: Union[float, str, Decimal], tick_size: Union[float, str, Decimal] = "0.01"
) -> Decimal:
    """
    按最小变动单位取整价格

    Args:
        price: 原始价格
        tick_size: 最小变动单位（如0.01元）

    Returns:
        取整后的价格
    """
    price_decimal = Decimal(str(price))
    tick = Decimal(str(tick_size))

    # 向下取整到最近的tick
    return (price_decimal // tick) * tick


def compare_prices(
    price1: Union[float, str, Decimal],
    price2: Union[float, str, Decimal],
    tolerance: Union[float, str, Decimal] = "0.0001",
) -> int:
    """
    比较两个价格（带容差）

    Args:
        price1: 第一个价格
        price2: 第二个价格
        tolerance: 容差值

    Returns:
        0: 相等（在容差范围内）
        1: price1 > price2
        -1: price1 < price2
    """
    p1 = Decimal(str(price1))
    p2 = Decimal(str(price2))
    tol = Decimal(str(tolerance))

    diff = abs(p1 - p2)

    if diff <= tol:
        return 0
    elif p1 > p2:
        return 1
    else:
        return -1


def sum_prices(prices: Sequence[Union[float, str, Decimal]]) -> Decimal:
    """
    求和价格列表

    Args:
        prices: 价格列表

    Returns:
        总和（Decimal类型）
    """
    total = Decimal("0")
    for price in prices:
        total += Decimal(str(price))
    return total


def average_price(prices: Sequence[Union[float, str, Decimal]], precision: int = 4) -> Decimal:
    """
    计算平均价格

    Args:
        prices: 价格列表
        precision: 精度（小数位数）

    Returns:
        平均价格（Decimal类型）
    """
    if not prices:
        return Decimal("0")

    total = sum_prices(prices)
    count = Decimal(str(len(prices)))
    avg = total / count

    # 设置精度
    quantize_str = "0." + "0" * precision
    return avg.quantize(Decimal(quantize_str))


# ==================== 特殊金融计算 ====================


def calculate_vwap(
    prices: Sequence[Union[float, str, Decimal]],
    volumes: Sequence[Union[int, float, str]],
    precision: int = 4,
) -> Decimal:
    """
    计算成交量加权平均价格（VWAP）

    Args:
        prices: 价格列表
        volumes: 对应的成交量列表
        precision: 精度（小数位数）

    Returns:
        VWAP（Decimal类型）
    """
    if len(prices) != len(volumes):
        raise ValueError("Prices and volumes must have same length")

    if not prices:
        return Decimal("0")

    total_value = Decimal("0")
    total_volume = Decimal("0")

    for price, volume in zip(prices, volumes):
        p = Decimal(str(price))
        v = Decimal(str(volume))
        total_value += p * v
        total_volume += v

    if total_volume == 0:
        return Decimal("0")

    vwap = total_value / total_volume

    # 设置精度
    quantize_str = "0." + "0" * precision
    return vwap.quantize(Decimal(quantize_str))


def calculate_commission(
    trade_value: Union[float, str, Decimal],
    commission_rate: Union[float, str, Decimal] = "0.0003",
    min_commission: Union[float, str, Decimal] = "5",
) -> Decimal:
    """
    计算交易佣金

    Args:
        trade_value: 交易金额
        commission_rate: 佣金率（默认万三）
        min_commission: 最低佣金（默认5元）

    Returns:
        佣金金额（Decimal类型）
    """
    value = Decimal(str(trade_value))
    rate = Decimal(str(commission_rate))
    min_comm = Decimal(str(min_commission))

    commission = value * rate

    # 应用最低佣金
    if commission < min_comm:
        commission = min_comm

    # 佣金一般保留2位小数
    return commission.quantize(Decimal("0.01"))


def calculate_stamp_duty(
    trade_value: Union[float, str, Decimal], rate: Union[float, str, Decimal] = "0.001"
) -> Decimal:
    """
    计算印花税（仅卖出收取）

    Args:
        trade_value: 交易金额
        rate: 印花税率（默认千一）

    Returns:
        印花税金额（Decimal类型）
    """
    value = Decimal(str(trade_value))
    tax_rate = Decimal(str(rate))

    stamp_duty = value * tax_rate

    # 印花税保留2位小数
    return stamp_duty.quantize(Decimal("0.01"))


if __name__ == "__main__":
    # 测试示例
    print("=== 金融计算Decimal工具测试 ===")

    # 1. 价差计算
    bid = 10.00
    ask = 10.02
    spread = calculate_spread(bid, ask)
    print(f"买卖价差: {spread}")  # 0.0200

    # 2. 涨跌幅计算
    current = 11.5
    previous = 10.0
    change = calculate_change_rate(current, previous)
    print(f"涨跌幅: {change:.4%}")  # 15.00%

    # 3. VWAP计算
    prices = [10.01, 10.02, 10.03, 10.02, 10.01]
    volumes = [1000, 2000, 1500, 1000, 500]
    vwap = calculate_vwap(prices, volumes)
    print(f"VWAP: {vwap}")  # 10.0183

    # 4. 佣金计算
    trade_value = 10000
    commission = calculate_commission(trade_value)
    print(f"佣金: {commission}")  # 5.00（最低佣金）

    # 5. 使用FinanceDecimal类
    price1 = FinanceDecimal("10.02")
    price2 = FinanceDecimal("10.00")
    diff = price1 - price2
    print(f"价格差: {diff}")  # 0.0200


