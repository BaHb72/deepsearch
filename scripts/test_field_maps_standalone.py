#!/usr/bin/env python
# encoding:utf-8
"""
测试 AmazingData 字段映射（独立版本）

直接加载模块文件，不依赖整个框架
"""

from pathlib import Path

# 获取项目根目录
script_dir = Path(__file__).parent
project_root = script_dir.parent

# 直接加载字段映射模块
field_maps_file = (
    project_root
    / "deepsearch"
    / "infrastructure"
    / "providers"
    / "implementations"
    / "amazingdata"
    / "amazingdata_field_maps.py"
)

import importlib.util

spec = importlib.util.spec_from_file_location("amazingdata_field_maps", field_maps_file)
field_maps_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(field_maps_mod)

# 获取需要的对象
SNAPSHOT_FIELDS = field_maps_mod.SNAPSHOT_FIELDS
SNAPSHOT_OPTION_FIELDS = field_maps_mod.SNAPSHOT_OPTION_FIELDS
SNAPSHOT_FUTURE_FIELDS = field_maps_mod.SNAPSHOT_FUTURE_FIELDS
SNAPSHOT_INDEX_FIELDS = field_maps_mod.SNAPSHOT_INDEX_FIELDS
SNAPSHOT_HKT_FIELDS = field_maps_mod.SNAPSHOT_HKT_FIELDS
KLINE_FIELDS = field_maps_mod.KLINE_FIELDS
FIVE_LEVEL_FIELDS = field_maps_mod.FIVE_LEVEL_FIELDS
OHLCV_FIELDS = field_maps_mod.OHLCV_FIELDS
get_field_description = field_maps_mod.get_field_description
get_all_fields = field_maps_mod.get_all_fields
is_five_level_field = field_maps_mod.is_five_level_field
is_ohlcv_field = field_maps_mod.is_ohlcv_field


def main():
    print("\n" + "=" * 80)
    print("AmazingData 字段映射测试（独立版）")
    print("=" * 80 + "\n")

    # 测试1: 字段数量统计
    print("=" * 80)
    print("测试1: 各数据类型字段数量")
    print("=" * 80)
    print(f"  Snapshot (股票快照):        {len(SNAPSHOT_FIELDS)}个字段")
    print(f"  SnapshotOption (ETF期权):   {len(SNAPSHOT_OPTION_FIELDS)}个字段")
    print(f"  SnapshotFuture (期货):      {len(SNAPSHOT_FUTURE_FIELDS)}个字段")
    print(f"  SnapshotIndex (指数):       {len(SNAPSHOT_INDEX_FIELDS)}个字段")
    print(f"  SnapshotHKT (港股通):       {len(SNAPSHOT_HKT_FIELDS)}个字段")
    print(f"  Kline (K线):                {len(KLINE_FIELDS)}个字段")
    print()

    # 测试2: 基础字段展示
    print("=" * 80)
    print("测试2: Snapshot 基础字段")
    print("=" * 80)
    basic_fields = ["code", "last", "open", "high", "low", "close", "volume"]
    for field in basic_fields:
        desc = SNAPSHOT_FIELDS.get(field, "未知")
        print(f"  {field:15s} -> {desc}")
    print()

    # 测试3: 辅助函数
    print("=" * 80)
    print("测试3: 辅助函数 - get_field_description()")
    print("=" * 80)
    test_cases = [
        ("snapshot", "last", "最新价"),
        ("snapshot_option", "exercise_price", "行权价"),
        ("snapshot_future", "open_interest", "持仓量"),
        ("kline", "close", "收盘价"),
    ]
    for data_type, field, expected in test_cases:
        desc = get_field_description(data_type, field)
        status = "✓" if expected in desc else "✗"
        print(f"  {status} {data_type:18s}.{field:20s} -> {desc}")
    print()

    # 测试4: 五档字段
    print("=" * 80)
    print("测试4: 五档盘口字段识别")
    print("=" * 80)
    print(f"  五档字段总数: {len(FIVE_LEVEL_FIELDS)}")
    test_fields = ["ask_price1", "bid_volume3", "last", "open"]
    for field in test_fields:
        is_five = is_five_level_field(field)
        result = "是五档字段" if is_five else "非五档字段"
        print(f"  {field:15s} -> {result}")
    print()

    # 测试5: OHLCV字段
    print("=" * 80)
    print("测试5: OHLCV基础字段识别")
    print("=" * 80)
    print(f"  OHLCV字段: {', '.join(OHLCV_FIELDS)}")
    test_fields = ["open", "high", "volume", "amount", "last"]
    for field in test_fields:
        is_ohlcv = is_ohlcv_field(field)
        result = "是OHLCV字段" if is_ohlcv else "非OHLCV字段"
        print(f"  {field:15s} -> {result}")
    print()

    # 测试6: 实际应用 - 数据完整性检查
    print("=" * 80)
    print("测试6: 实际应用 - K线数据完整性检查")
    print("=" * 80)
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
    print(f"  需要的字段数: {len(required_fields)}")
    print(f"  实际字段数: {len(kline_data)}")

    missing_fields = [f for f in required_fields if f not in kline_data]
    extra_fields = [f for f in kline_data if f not in required_fields]

    if missing_fields:
        print(f"  缺失字段: {missing_fields}")
    if extra_fields:
        print(f"  额外字段: {extra_fields}")
    if not missing_fields and not extra_fields:
        print("  ✓ 数据完整，字段匹配")
    print()

    # 测试7: 实际应用 - 五档数据提取
    print("=" * 80)
    print("测试7: 实际应用 - 提取五档盘口数据")
    print("=" * 80)
    market_data = {
        "code": "000001.SZ",
        "last": 10.5,
        "volume": 1000000,
        "ask_price1": 10.51,
        "ask_volume1": 1000,
        "ask_price2": 10.52,
        "ask_volume2": 2000,
        "bid_price1": 10.50,
        "bid_volume1": 1500,
        "bid_price2": 10.49,
        "bid_volume2": 2500,
    }

    five_level_data = {k: v for k, v in market_data.items() if is_five_level_field(k)}
    print(f"  原始数据字段: {len(market_data)}个")
    print(f"  提取五档字段: {len(five_level_data)}个")
    print("  五档数据内容:")
    for field, value in sorted(five_level_data.items()):
        print(f"    {field:15s} = {value}")
    print()

    # 统计所有唯一字段
    print("=" * 80)
    print("测试8: 唯一字段统计")
    print("=" * 80)
    all_unique_fields = set()
    all_unique_fields.update(SNAPSHOT_FIELDS.keys())
    all_unique_fields.update(SNAPSHOT_OPTION_FIELDS.keys())
    all_unique_fields.update(SNAPSHOT_FUTURE_FIELDS.keys())
    all_unique_fields.update(SNAPSHOT_INDEX_FIELDS.keys())
    all_unique_fields.update(SNAPSHOT_HKT_FIELDS.keys())
    all_unique_fields.update(KLINE_FIELDS.keys())

    print(f"  所有数据类型去重后的唯一字段数: {len(all_unique_fields)}")
    print()

    print("=" * 80)
    print("所有测试完成! ✓")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback

        traceback.print_exc()
