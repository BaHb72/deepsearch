#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData 扩展接口测试
专门测试龙虎榜、大宗交易和期权相关接口

使用方法:
    python test_amazingdata_extended_apis.py
"""

import sys

sys.path.insert(0, "d:/Stock/code/deepsearch")

from datetime import datetime, timedelta

import pandas as pd

# ========== 配置 ==========
CONFIG = {
    "username": "212200038719",
    "password": "212200038719@2025",
    "host": "101.230.159.234",
    "port": 8600,
}
LOCAL_PATH = "D://AmazingData_local_data//"

# 全局缓存
_ad = None
_logged_in = False


def get_sdk():
    global _ad
    if _ad is None:
        import AmazingData as ad

        _ad = ad
    return _ad


def login():
    global _logged_in
    if _logged_in:
        return True
    ad = get_sdk()
    result = ad.login(**CONFIG)
    if result == 0 or result is True:
        print("[OK] 登录成功")
        _logged_in = True
        return True
    print(f"[FAIL] 登录失败: {result}")
    return False


def logout():
    global _logged_in
    if _logged_in:
        try:
            get_sdk().logout(CONFIG["username"])
        except:
            pass
        _logged_in = False


def test_get_long_hu_bang():
    """
    测试 InfoData.get_long_hu_bang
    龙虎榜数据
    """
    print("\n" + "=" * 60)
    print("测试 get_long_hu_bang (龙虎榜)")
    print("=" * 60)

    login()
    info = get_sdk().InfoData()

    # 测试最近30天
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date = int((datetime.now() - timedelta(days=30)).strftime("%Y%m%d"))

    print("测试参数:")
    print("  股票代码: ['000001.SZ', '600519.SH']")
    print(f"  时间范围: {begin_date} ~ {end_date}")

    try:
        data = info.get_long_hu_bang(
            ["000001.SZ", "600519.SH"],
            local_path=LOCAL_PATH,
            begin_date=begin_date,
            end_date=end_date,
        )

        if isinstance(data, pd.DataFrame) and not data.empty:
            print(f"\n[成功] 获取到 {len(data)} 条龙虎榜数据")
            print("\n字段列表:")
            for col in data.columns:
                print(f"  - {col}")

            print("\n数据预览:")
            print(data.head())

            # 检查关键字段
            expected_cols = [
                "MARKET_CODE",
                "TRADE_DATE",
                "SECURITY_NAME",
                "REASON_TYPE_NAME",
                "CHANGE_RANGE",
                "TRADER_NAME",
                "BUY_AMOUNT",
                "SELL_AMOUNT",
            ]
            missing_cols = [col for col in expected_cols if col not in data.columns]
            if missing_cols:
                print(f"\n[警告] 缺少字段: {missing_cols}")

            return True
        else:
            print("[信息] 无上榜记录(正常)")
            return True

    except Exception as e:
        print(f"[错误] 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_get_block_trading():
    """
    测试 InfoData.block_trading
    大宗交易数据
    """
    print("\n" + "=" * 60)
    print("测试 block_trading (大宗交易)")
    print("=" * 60)

    login()
    info = get_sdk().InfoData()

    # 测试最近30天
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date = int((datetime.now() - timedelta(days=30)).strftime("%Y%m%d"))

    print("测试参数:")
    print("  股票代码: ['000001.SZ', '600519.SH']")
    print(f"  时间范围: {begin_date} ~ {end_date}")

    try:
        # 注意：SDK中方法名是 block_trading
        block_method = getattr(info, "block_trading", None)
        if block_method is None:
            print("[错误] AmazingData SDK 未提供 block_trading 接口")
            return False

        data = block_method(
            ["000001.SZ", "600519.SH"],
            local_path=LOCAL_PATH,
            is_local=False,
            begin_date=begin_date,
            end_date=end_date,
        )

        if isinstance(data, pd.DataFrame) and not data.empty:
            print(f"\n[成功] 获取到 {len(data)} 条大宗交易数据")
            print("\n字段列表:")
            for col in data.columns:
                print(f"  - {col}")

            print("\n数据预览:")
            print(data.head())

            # 检查关键字段
            expected_cols = [
                "MARKET_CODE",
                "TRADE_DATE",
                "B_SHARE_PRICE",
                "B_SHARE_VOLUME",
                "B_FREQUENCY",
                "BLOCK_AVG_VOLUME",
                "B_SHARE_AMOUNT",
                "B_BUYER_NAME",
                "B_SELLER_NAME",
            ]
            missing_cols = [col for col in expected_cols if col not in data.columns]
            if missing_cols:
                print(f"\n[警告] 缺少字段: {missing_cols}")

            return True
        else:
            print("[信息] 无大宗交易数据")
            return True

    except Exception as e:
        print(f"[错误] 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_get_option_basic_info():
    """
    测试 InfoData.get_option_basic_info
    期权基本资料
    """
    print("\n" + "=" * 60)
    print("测试 get_option_basic_info (期权基本资料)")
    print("=" * 60)

    login()
    base = get_sdk().BaseData()
    info = get_sdk().InfoData()

    # 先获取期权代码列表
    print("获取期权代码列表...")
    options = base.get_option_code_list()

    if not options or len(options) == 0:
        print("[错误] 无期权代码")
        return False

    # 只测试前3个期权代码
    test_options = options[:3]
    print("测试参数:")
    print(f"  期权代码: {test_options}")

    try:
        data = info.get_option_basic_info(test_options, local_path=LOCAL_PATH, is_local=False)

        if isinstance(data, pd.DataFrame) and not data.empty:
            print(f"\n[成功] 获取到 {len(data)} 条期权基本资料")
            print("\n字段列表:")
            for col in data.columns:
                print(f"  - {col}")

            print("\n数据预览:")
            print(data.head())

            # 检查关键字段
            expected_cols = [
                "CONTRACT_FULL_NAME",
                "CONTRACT_TYPE",
                "DELIVERY_MONTH",
                "EXPIRY_DATE",
                "EXERCISE_PRICE",
                "EXERCISE_END_DATE",
                "START_TRADE_DATE",
                "LISTING_REF_PRICE",
                "LAST_TRADE_DATE",
                "EXCHANGE_CODE",
                "CONTRACT_UNIT",
                "MARKET_CODE",
            ]
            missing_cols = [col for col in expected_cols if col not in data.columns]
            if missing_cols:
                print(f"\n[警告] 缺少字段: {missing_cols}")
            else:
                print("\n[验证] 所有期望字段都存在")

            return True
        else:
            print("[错误] 无数据")
            return False

    except Exception as e:
        print(f"[错误] 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_get_option_std_ctr_specs():
    """
    测试 InfoData.get_option_std_ctr_specs
    期权标准合约属性
    """
    print("\n" + "=" * 60)
    print("测试 get_option_std_ctr_specs (期权标准合约属性)")
    print("=" * 60)

    login()
    info = get_sdk().InfoData()

    # 测试深沪ETF期权代码
    test_codes = ["159919.SZ", "159915.SZ", "510300.SH", "510050.SH"]
    print("测试参数:")
    print(f"  ETF代码: {test_codes}")

    try:
        data = info.get_option_std_ctr_specs(test_codes, local_path=LOCAL_PATH, is_local=False)

        if isinstance(data, pd.DataFrame) and not data.empty:
            print(f"\n[成功] 获取到 {len(data)} 条期权合约属性")
            print("\n字段列表:")
            for col in data.columns:
                print(f"  - {col}")

            print("\n数据预览:")
            print(data.head())

            # 检查关键字段
            expected_cols = [
                "EXERCISE_DATE",
                "CONTRACT_UNIT",
                "POSITION_DECLARE_MIN",
                "QUOTE_CURRENCY_UNIT",
                "LAST_TRADING_DATE",
                "POSITION_LIMIT",
                "DELIST_DATE",
                "NOTIONAL_VALUE",
                "EXERCISE_METHOD",
                "DELIVERY_METHOD",
                "SETTLEMENT_MONTH",
                "TRADING_FEE",
                "EXCHANGE_NAME",
                "OPTION_EN_NAME",
                "CONTRACT_VALUE",
                "OPTION_STRIKE_PRICE",
                "LISTED_DATE",
                "OPTION_NAME",
                "PREMIUM",
                "OPTION_TYPE",
                "TRADING_HOURS_DESC",
            ]
            missing_cols = [col for col in expected_cols if col not in data.columns]
            if missing_cols:
                print(f"\n[警告] 缺少字段: {missing_cols}")
            else:
                print("\n[验证] 所有期望字段都存在")

            return True
        else:
            print("[错误] 无数据")
            return False

    except Exception as e:
        print(f"[错误] 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("AmazingData 扩展接口测试")
    print("=" * 60)

    tests = [
        ("龙虎榜", test_get_long_hu_bang),
        ("大宗交易", test_get_block_trading),
        ("期权基本资料", test_get_option_basic_info),
        ("期权标准合约属性", test_get_option_std_ctr_specs),
    ]

    results = []

    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n[严重错误] 测试 '{name}' 时发生异常: {e}")
            import traceback

            traceback.print_exc()
            results.append((name, False))

    # 打印汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    for name, result in results:
        status = "[通过]" if result else "[失败]"
        print(f"{status} {name}")

    # 登出
    logout()
    print("\n测试完成！")


if __name__ == "__main__":
    main()
