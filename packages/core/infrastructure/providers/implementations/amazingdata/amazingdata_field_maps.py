# encoding:utf-8
"""
AmazingData 数据结构字段映射

本文件定义了AmazingData各种数据结构的字段映射常量
基于官方文档 4.2 数据结构说明
"""

from typing import Dict, List

# ==================== 4.2.1 Level-1 快照 Snapshot ====================

SNAPSHOT_FIELDS: Dict[str, str] = {
    "code": "证券代码+市场",
    "datetime": "交易所行情数据时间",
    "trade_time": "交易所行情数据时间",
    "pre_close": "昨收价",
    "last": "最新价",
    "open": "开盘价",
    "high": "最高价",
    "low": "最低价",
    "close": "收盘价",
    "volume": "成交总额",
    "amount": "成交总金额",
    "num_trades": "成交笔数",
    "high_limited": "涨停价",
    "low_limited": "跌停价",
    # 五档买卖盘
    "ask_price1": "卖1档价格",
    "ask_price2": "卖2档价格",
    "ask_price3": "卖3档价格",
    "ask_price4": "卖4档价格",
    "ask_price5": "卖5档价格",
    "ask_volume1": "卖1档量",
    "ask_volume2": "卖2档量",
    "ask_volume3": "卖3档量",
    "ask_volume4": "卖4档量",
    "ask_volume5": "卖5档量",
    "bid_price1": "买1档价格",
    "bid_price2": "买2档价格",
    "bid_price3": "买3档价格",
    "bid_price4": "买4档价格",
    "bid_price5": "买5档价格",
    "bid_volume1": "买1档量",
    "bid_volume2": "买2档量",
    "bid_volume3": "买3档量",
    "bid_volume4": "买4档量",
    "bid_volume5": "买5档量",
    "iopv": "净估值价（仅适合基金快照）",
    "trading_phase_code": "交易阶段代码",
}


# ==================== 4.2.2 ETF 期权快照 SnapshotOption ====================

SNAPSHOT_OPTION_FIELDS: Dict[str, str] = {
    "code": "证券代码+市场",
    "trade_time": "交易所行情数据时间",
    "trading_phase_code": "交易阶段代码",
    "total_long_position": "总持仓量",
    "volume": "成交总额",
    "amount": "成交总金额",
    "pre_close": "昨收价",
    "pre_settle": "上次结算价",
    "auction_price": "动态参考价（盘前竞价时段真实价格，发上时有效）",
    "auction_volume": "集中成交数量（（盘上保货数）",
    "last": "最新价",
    "open": "开盘价",
    "high": "最高价",
    "low": "最低价",
    "close": "收盘价",
    "settle": "本次结算价",
    "high_limited": "涨停价",
    "low_limited": "跌停价",
    # 五档买卖盘（同Snapshot）
    "ask_price1": "卖1档价格",
    "ask_price2": "卖2档价格",
    "ask_price3": "卖3档价格",
    "ask_price4": "卖4档价格",
    "ask_price5": "卖5档价格",
    "ask_volume1": "卖1档量",
    "ask_volume2": "卖2档量",
    "ask_volume3": "卖3档量",
    "ask_volume4": "卖4档量",
    "ask_volume5": "卖5档量",
    "bid_price1": "买1档价格",
    "bid_price2": "买2档价格",
    "bid_price3": "买3档价格",
    "bid_price4": "买4档价格",
    "bid_price5": "买5档价格",
    "bid_volume1": "买1档量",
    "bid_volume2": "买2档量",
    "bid_volume3": "买3档量",
    "bid_volume4": "买4档量",
    "bid_volume5": "买5档量",
    "contract_type": "合约类型",
    "expire_date": "到期日",
    "underlying_security_cod": "标的代码",
    "exercise_price": "行权价",
}


# ==================== 4.2.3 期货快照 SnapshotFuture ====================

SNAPSHOT_FUTURE_FIELDS: Dict[str, str] = {
    "code": "证券代码+市场",
    "trade_time": "交易所行情数据时间",
    "action_day": "业务日期",
    "trading_day": "交易日期",
    "pre_close": "昨收价",
    "pre_settle": "上次结算价",
    "pre_open_interest": "昨持仓量",
    "open_interest": "持仓量",
    "last": "最新价",
    "open": "开盘价",
    "high": "最高价",
    "low": "最低价",
    "close": "收盘价",
    "volume": "成交总额",
    "amount": "成交总金额",
    "high_limited": "涨停价",
    "low_limited": "跌停价",
    # 五档买卖盘
    "ask_price1": "卖1档价格",
    "ask_price2": "卖2档价格",
    "ask_price3": "卖3档价格",
    "ask_price4": "卖4档价格",
    "ask_price5": "卖5档价格",
    "ask_volume1": "卖1档量",
    "ask_volume2": "卖2档量",
    "ask_volume3": "卖3档量",
    "ask_volume4": "卖4档量",
    "ask_volume5": "卖5档量",
    "bid_price1": "买1档价格",
    "bid_price2": "买2档价格",
    "bid_price3": "买3档价格",
    "bid_price4": "买4档价格",
    "bid_price5": "买5档价格",
    "bid_volume1": "买1档量",
    "bid_volume2": "买2档量",
    "bid_volume3": "买3档量",
    "bid_volume4": "买4档量",
    "bid_volume5": "买5档量",
}


# ==================== 4.2.4 指数快照 SnapshotIndex ====================

SNAPSHOT_INDEX_FIELDS: Dict[str, str] = {
    "code": "证券代码+市场",
    "trade_time": "交易所行情数据时间",
    "last": "最新价",
    "pre_close": "昨收价",
    "open": "开盘价",
    "high": "最高价",
    "low": "最低价",
    "close": "收盘价（交易所盘后数）",
    "volume": "成交总额（1亿张沪深/、深交所1张）",
    "amount": "成交总金额",
}


# ==================== 4.2.5 港股通快照 SnapshotHKT ====================

SNAPSHOT_HKT_FIELDS: Dict[str, str] = {
    "code": "证券代码+市场",
    "trade_time": "交易所行情数据时间",
    "pre_close": "昨收价",
    "last": "最新价",
    "high": "最高价",
    "low": "最低价",
    "volume": "成交总额",
    "amount": "成交总金额",
    "nominal_price": "叫盘价",
    "ref_price": "参考价",
    "bid_price_limit_up": "买盘上限价",
    "bid_price_limit_down": "买盘下限价",
    "offer_price_limit_up": "卖盘上限价",
    "offer_price_limit_down": "卖盘下限价",
    "high_limited": "涨停价格价格上限",
    "low_limited": "跌停价格价格下限",
    # 五档买卖盘
    "ask_price1": "卖1档价格",
    "ask_price2": "卖2档价格",
    "ask_price3": "卖3档价格",
    "ask_price4": "卖4档价格",
    "ask_price5": "卖5档价格",
    "ask_volume1": "卖1档量",
    "ask_volume2": "卖2档量",
    "ask_volume3": "卖3档量",
    "ask_volume4": "卖4档量",
    "ask_volume5": "卖5档量",
    "bid_price1": "买1档价格",
    "bid_price2": "买2档价格",
    "bid_price3": "买3档价格",
    "bid_price4": "买4档价格",
    "bid_price5": "买5档价格",
    "bid_volume1": "买1档量",
    "bid_volume2": "买2档量",
    "bid_volume3": "买3档量",
    "bid_volume4": "买4档量",
    "bid_volume5": "买5档量",
    "trading_phase_code": "交易阶段代码",
}


# ==================== 4.2.6 K线 Kline ====================

KLINE_FIELDS: Dict[str, str] = {
    "code": "证券代码+市场",
    "datetime": "交易所行情数据时间",
    "trade_time": "交易所行情数据时间",
    "open": "开盘价",
    "high": "最高价",
    "low": "最低价",
    "close": "收盘价",
    "volume": "成交总额",
    "amount": "成交总金额",
}


# ==================== 通用五档盘口字段 ====================

FIVE_LEVEL_FIELDS: List[str] = [
    "ask_price1",
    "ask_price2",
    "ask_price3",
    "ask_price4",
    "ask_price5",
    "ask_volume1",
    "ask_volume2",
    "ask_volume3",
    "ask_volume4",
    "ask_volume5",
    "bid_price1",
    "bid_price2",
    "bid_price3",
    "bid_price4",
    "bid_price5",
    "bid_volume1",
    "bid_volume2",
    "bid_volume3",
    "bid_volume4",
    "bid_volume5",
]


# ==================== 基础OHLCV字段 ====================

OHLCV_FIELDS: List[str] = [
    "open",  # 开盘价
    "high",  # 最高价
    "low",  # 最低价
    "close",  # 收盘价
    "volume",  # 成交量
]


# ==================== 辅助函数 ====================


def get_field_description(data_type: str, field_name: str) -> str:
    """获取字段描述

    Args:
        data_type: 数据类型（snapshot, snapshot_option, snapshot_future等）
        field_name: 字段名

    Returns:
        字段描述，未找到返回字段名本身
    """
    field_maps = {
        "snapshot": SNAPSHOT_FIELDS,
        "snapshot_option": SNAPSHOT_OPTION_FIELDS,
        "snapshot_future": SNAPSHOT_FUTURE_FIELDS,
        "snapshot_index": SNAPSHOT_INDEX_FIELDS,
        "snapshot_hkt": SNAPSHOT_HKT_FIELDS,
        "kline": KLINE_FIELDS,
    }

    field_map = field_maps.get(data_type.lower())
    if field_map:
        return field_map.get(field_name, field_name)
    return field_name


def get_all_fields(data_type: str) -> List[str]:
    """获取数据类型的所有字段列表

    Args:
        data_type: 数据类型

    Returns:
        字段名列表
    """
    field_maps = {
        "snapshot": SNAPSHOT_FIELDS,
        "snapshot_option": SNAPSHOT_OPTION_FIELDS,
        "snapshot_future": SNAPSHOT_FUTURE_FIELDS,
        "snapshot_index": SNAPSHOT_INDEX_FIELDS,
        "snapshot_hkt": SNAPSHOT_HKT_FIELDS,
        "kline": KLINE_FIELDS,
    }

    field_map = field_maps.get(data_type.lower())
    if field_map:
        return list(field_map.keys())
    return []


def is_five_level_field(field_name: str) -> bool:
    """判断是否是五档盘口字段

    Args:
        field_name: 字段名

    Returns:
        是否是五档字段
    """
    return field_name in FIVE_LEVEL_FIELDS


def is_ohlcv_field(field_name: str) -> bool:
    """判断是否是OHLCV基础字段

    Args:
        field_name: 字段名

    Returns:
        是否是OHLCV字段
    """
    return field_name in OHLCV_FIELDS
