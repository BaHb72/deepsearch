#!/usr/bin/env python
# encoding:utf-8
"""
测试 AmazingData 字段映射

验证所有数据结构的字段映射定义
"""

import sys
from pathlib import Path

# 获取项目根目录
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# 导入字段映射模块
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_field_maps import (
    SNAPSHOT_FIELDS,
    SNAPSHOT_OPTION_FIELDS,
    SNAPSHOT_FUTURE_FIELDS,
    SNAPSHOT_INDEX_FIELDS,
    SNAPSHOT_HKT_FIELDS,
    KLINE_FIELDS,
    FIVE_LEVEL_FIELDS,
    OHLCV_FIELDS,
    get_field_description,
    get_all_fields,
    is_five_level_field,
    is_ohlcv_field,
)


def test_snapshot_fields():
    """测试快照字段映射"""
    print("=" * 80)
    print("测试1: Snapshot（股票快照）字段映射")
    print("=" * 80)
    
    print(f"\n总字段数: {len(SNAPSHOT_FIELDS)}")
    print("\n基础字段:")
    basic_fields = ["code", "datetime", "last", "open", "high", "low", "close", "volume", "amount"]
    for field in basic_fields:
        desc = SNAPSHOT_FIELDS.get(field, "未知")
        print(f"  {field:20s} -> {desc}")
    
    print("\n特殊字段:")
    special_fields = ["iopv", "trading_phase_code", "high_limited", "low_limited"]
    for field in special_fields:
        desc = SNAPSHOT_FIELDS.get(field, "未知")
        print(f"  {field:20s} -> {desc}")
    
    print()


def test_option_fields():
    """测试期权快照字段映射"""
    print("=" * 80)
    print("测试2: SnapshotOption（ETF期权快照）字段映射")
    print("=" * 80)
    
    print(f"\n总字段数: {len(SNAPSHOT_OPTION_FIELDS)}")
    print("\n期权特有字段:")
    option_specific = ["total_long_position", "auction_price", "auction_volume", 
                      "contract_type", "expire_date", "underlying_security_cod", "exercise_price"]
    for field in option_specific:
        desc = SNAPSHOT_OPTION_FIELDS.get(field, "未知")
        print(f"  {field:25s} -> {desc}")
    
    print()


def test_future_fields():
    """测试期货快照字段映射"""
    print("=" * 80)
    print("测试3: SnapshotFuture（期货快照）字段映射")
    print("=" * 80)
    
    print(f"\n总字段数: {len(SNAPSHOT_FUTURE_FIELDS)}")
    print("\n期货特有字段:")
    future_specific = ["action_day", "trading_day", "pre_settle", "pre_open_interest", "open_interest"]
    for field in future_specific:
        desc = SNAPSHOT_FUTURE_FIELDS.get(field, "未知")
        print(f"  {field:20s} -> {desc}")
    
    print()


def test_index_fields():
    """测试指数快照字段映射"""
    print("=" * 80)
    print("测试4: SnapshotIndex（指数快照）字段映射")
    print("=" * 80)
    
    print(f"\n总字段数: {len(SNAPSHOT_INDEX_FIELDS)}")
    print("\n所有字段:")
    for field, desc in SNAPSHOT_INDEX_FIELDS.items():
        print(f"  {field:20s} -> {desc}")
    
    print()


def test_hkt_fields():
    """测试港股通快照字段映射"""
    print("=" * 80)
    print("测试5: SnapshotHKT（港股通快照）字段映射")
    print("=" * 80)
    
    print(f"\n总字段数: {len(SNAPSHOT_HKT_FIELDS)}")
    print("\n港股通特有字段:")
    hkt_specific = ["nominal_price", "ref_price", "bid_price_limit_up", "bid_price_limit_down",
                   "offer_price_limit_up", "offer_price_limit_down"]
    for field in hkt_specific:
        desc = SNAPSHOT_HKT_FIELDS.get(field, "未知")
        print(f"  {field:25s} -> {desc}")
    
    print()


def test_kline_fields():
    """测试K线字段映射"""
    print("=" * 80)
    print("测试6: Kline（K线）字段映射")
    print("=" * 80)
    
    print(f"\n总字段数: {len(KLINE_FIELDS)}")
    print("\n所有字段:")
    for field, desc in KLINE_FIELDS.items():
        print(f"  {field:20s} -> {desc}")
    
    print()


def test_helper_functions():
    """测试辅助函数"""
    print("=" * 80)
    print("测试7: 辅助函数")
    print("=" * 80)
    
    # 测试get_field_description
    print("\n1. get_field_description():")
    test_cases = [
        ("snapshot", "last"),
        ("snapshot_option", "exercise_price"),
        ("snapshot_future", "open_interest"),
        ("snapshot_index", "volume"),
        ("kline", "close"),
    ]
    for data_type, field in test_cases:
        desc = get_field_description(data_type, field)
        print(f"  {data_type:20s}.{field:20s} -> {desc}")
    
    # 测试get_all_fields
    print("\n2. get_all_fields():")
    for data_type in ["snapshot", "snapshot_index", "kline"]:
        fields = get_all_fields(data_type)
        print(f"  {data_type:20s}: {len(fields)}个字段")
    
    # 测试is_five_level_field
    print("\n3. is_five_level_field():")
    test_fields = ["ask_price1", "bid_volume3", "last", "open", "high"]
    for field in test_fields:
        is_five = is_five_level_field(field)
        print(f"  {field:20s}: {'是' if is_five else '否'}五档字段")
    
    # 测试is_ohlcv_field
    print("\n4. is_ohlcv_field():")
    test_fields = ["open", "high", "low", "close", "volume", "amount", "last"]
    for field in test_fields:
        is_ohlcv = is_ohlcv_field(field)
        print(f"  {field:20s}: {'是' if is_ohlcv else '否'}OHLCV字段")
    
    print()


def test_five_level_and_ohlcv():
    """测试五档和OHLCV字段"""
    print("=" * 80)
    print("测试8: 五档盘口和OHLCV基础字段")
    print("=" * 80)
    
    print(f"\n五档盘口字段总数: {len(FIVE_LEVEL_FIELDS)}")
    print("五档字段列表:")
    for i, field in enumerate(FIVE_LEVEL_FIELDS, 1):
        print(f"  {i:2d}. {field}")
        if i % 5 == 0:
            print()
    
    print(f"\nOHLCV基础字段总数: {len(OHLCV_FIELDS)}")
    print("OHLCV字段列表:")
    for i, field in enumerate(OHLCV_FIELDS, 1):
        print(f"  {i}. {field}")
    
    print()


def test_field_coverage():
    """测试字段覆盖率"""
    print("=" * 80)
    print("测试9: 字段覆盖率统计")
    print("=" * 80)
    
    data_types = {
        "Snapshot": SNAPSHOT_FIELDS,
        "SnapshotOption": SNAPSHOT_OPTION_FIELDS,
        "SnapshotFuture": SNAPSHOT_FUTURE_FIELDS,
        "SnapshotIndex": SNAPSHOT_INDEX_FIELDS,
        "SnapshotHKT": SNAPSHOT_HKT_FIELDS,
        "Kline": KLINE_FIELDS,
    }
    
    print("\n各数据类型字段统计:")
    total_unique_fields = set()
    for name, fields in data_types.items():
        total_unique_fields.update(fields.keys())
        # 统计五档字段
        five_level_count = sum(1 for f in fields.keys() if is_five_level_field(f))
        # 统计OHLCV字段
        ohlcv_count = sum(1 for f in fields.keys() if is_ohlcv_field(f))
        
        print(f"\n  {name}:")
        print(f"    总字段数: {len(fields)}")
        print(f"    五档字段: {five_level_count}")
        print(f"    OHLCV字段: {ohlcv_count}")
        print(f"    特殊字段: {len(fields) - five_level_count - ohlcv_count}")
    
    print(f"\n所有数据类型去重后的唯一字段数: {len(total_unique_fields)}")
    print()


def test_practical_usage():
    """测试实际使用场景"""
    print("=" * 80)
    print("测试10: 实际使用场景")
    print("=" * 80)
    
    # 场景1: 处理快照数据时查询字段含义
    print("\n场景1: 查询快照数据字段含义")
    snapshot_data = {
        "code": "000001.SZ",
        "last": 10.5,
        "volume": 1000000,
        "ask_price1": 10.51,
        "bid_price1": 10.50,
    }
    
    print("  快照数据字段解析:")
    for field, value in snapshot_data.items():
        desc = get_field_description("snapshot", field)
        print(f"    {field} = {value} ({desc})")
    
    # 场景2: 验证数据完整性
    print("\n场景2: 验证K线数据完整性")
    kline_data = {
        "code": "600000.SH",
        "datetime": "2024-06-15 09:30:00",
        "open": 8.50,
        "high": 8.70,
        "low": 8.45,
        "close": 8.65,
        "volume": 500000,
        "amount": 4300000,
    }
    
    required_fields = get_all_fields("kline")
    missing_fields = [f for f in required_fields if f not in kline_data]
    
    print(f"  需要字段: {len(required_fields)}个")
    print(f"  实际字段: {len(kline_data)}个")
    if missing_fields:
        print(f"  缺失字段: {missing_fields}")
    else:
        print(f"  ✓ 数据完整")
    
    # 场景3: 提取五档盘口数据
    print("\n场景3: 提取五档盘口数据")
    market_data = {
        "code": "000001.SZ",
        "last": 10.5,
        "ask_price1": 10.51, "ask_volume1": 1000,
        "ask_price2": 10.52, "ask_volume2": 2000,
        "bid_price1": 10.50, "bid_volume1": 1500,
        "bid_price2": 10.49, "bid_volume2": 2500,
    }
    
    five_level_data = {k: v for k, v in market_data.items() if is_five_level_field(k)}
    print(f"  提取的五档数据: {len(five_level_data)}个字段")
    for field, value in five_level_data.items():
        print(f"    {field}: {value}")
    
    print()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("AmazingData 字段映射测试")
    print("=" * 80 + "\n")
    
    try:
        test_snapshot_fields()
        test_option_fields()
        test_future_fields()
        test_index_fields()
        test_hkt_fields()
        test_kline_fields()
        test_helper_functions()
        test_five_level_and_ohlcv()
        test_field_coverage()
        test_practical_usage()
        
        print("=" * 80)
        print("所有测试完成!")
        print("=" * 80)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
