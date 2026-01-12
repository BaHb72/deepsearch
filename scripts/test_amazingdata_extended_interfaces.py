# encoding:utf-8
"""
AmazingData 扩展接口测试脚本
测试 ETF 和指数相关接口

Author: DeepSearch Team
Date: 2025-12-16
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from deepsearch.config.models.amazingdata import AmazingDataConfig
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_extended import (
    AmazingDataExtended,
)


def print_section(title: str):
    """打印分隔线"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


async def test_etf_interfaces():
    """测试 ETF 相关接口"""
    print_section("测试 ETF 相关接口")

    # 从环境变量获取配置
    username = os.getenv("AMAZINGDATA_USERNAME")
    password = os.getenv("AMAZINGDATA_PASSWORD")
    port = int(os.getenv("AMAZINGDATA_PORT", "16320"))

    if not username or not password:
        print("错误: 请设置环境变量 AMAZINGDATA_USERNAME 和 AMAZINGDATA_PASSWORD")
        return

    # 创建配置
    config = AmazingDataConfig(
        username=username,
        password=password,
        port=port,
        enabled=True,
    )

    # 创建提供者
    provider = AmazingDataExtended(config)

    try:
        # 连接
        print("正在连接到 AmazingData...")
        connected = await provider.connect()
        if not connected:
            print("连接失败")
            return

        print("连接成功!\n")

        # 测试 ETF 列表 - 仅测试几个标的
        etf_codes = ["510300.SH", "510500.SH"]  # 沪深300ETF, 中证500ETF
        print(f"测试 ETF 代码: {etf_codes}\n")

        # 计算日期范围 - 最近30天
        end_date = datetime.now()
        begin_date = end_date - timedelta(days=30)
        begin_date_int = int(begin_date.strftime("%Y%m%d"))
        end_date_int = int(end_date.strftime("%Y%m%d"))

        # 1. 测试 get_fund_share - ETF基金份额
        print_section("1. 测试 get_fund_share (ETF基金份额)")
        try:
            fund_share = await provider.get_fund_share(
                code_list=etf_codes,
                begin_date=begin_date_int,
                end_date=end_date_int,
            )
            print(f"获取到 {len(fund_share)} 条 ETF 份额数据")
            if not fund_share.empty:
                print("\n前5条数据:")
                print(fund_share.head())
                print(f"\n列名: {fund_share.columns.tolist()}")
        except Exception as e:
            print(f"测试失败: {e}")

        # 2. 测试 get_fund_iopv - ETF每日收益
        print_section("2. 测试 get_fund_iopv (ETF每日收益)")
        try:
            fund_iopv = await provider.get_fund_iopv(
                code_list=etf_codes,
                begin_date=begin_date_int,
                end_date=end_date_int,
            )
            print(f"获取到 {len(fund_iopv)} 条 ETF IOPV 数据")
            if not fund_iopv.empty:
                print("\n前5条数据:")
                print(fund_iopv.head())
                print(f"\n列名: {fund_iopv.columns.tolist()}")
        except Exception as e:
            print(f"测试失败: {e}")

    finally:
        # 断开连接
        await provider.disconnect()
        print("\n已断开连接")


async def test_index_interfaces():
    """测试指数相关接口"""
    print_section("测试指数相关接口")

    # 从环境变量获取配置
    username = os.getenv("AMAZINGDATA_USERNAME")
    password = os.getenv("AMAZINGDATA_PASSWORD")
    port = int(os.getenv("AMAZINGDATA_PORT", "16320"))

    if not username or not password:
        print("错误: 请设置环境变量 AMAZINGDATA_USERNAME 和 AMAZINGDATA_PASSWORD")
        return

    # 创建配置
    config = AmazingDataConfig(
        username=username,
        password=password,
        port=port,
        enabled=True,
    )

    # 创建提供者
    provider = AmazingDataExtended(config)

    try:
        # 连接
        print("正在连接到 AmazingData...")
        connected = await provider.connect()
        if not connected:
            print("连接失败")
            return

        print("连接成功!\n")

        # 测试指数代码 - 仅测试一个指数
        index_code = "000300.SH"  # 沪深300
        index_codes = ["000300.SH"]  # 用于批量接口
        print(f"测试指数代码: {index_code}\n")

        # 计算日期
        begin_date_int = int((datetime.now() - timedelta(days=30)).strftime("%Y%m%d"))

        # 3. 测试 get_index_constituent - 指数成分股
        print_section("3. 测试 get_index_constituent (指数成分股)")
        try:
            index_constituent = await provider.get_index_constituent(
                index_code=index_code,
            )
            print(f"获取到 {len(index_constituent)} 条成分股数据")
            if not index_constituent.empty:
                print("\n前5条数据:")
                print(index_constituent.head())
                print(f"\n列名: {index_constituent.columns.tolist()}")
        except Exception as e:
            print(f"测试失败: {e}")

        # 4. 测试 get_index_weight - 指数成分股权重
        print_section("4. 测试 get_index_weight (指数成分股权重)")
        try:
            index_weight = await provider.get_index_weight(
                code_list=index_codes,
                begin_date=begin_date_int,
            )
            print(f"获取到 {len(index_weight)} 条权重数据")
            if not index_weight.empty:
                print("\n前5条数据:")
                print(index_weight.head())
                print(f"\n列名: {index_weight.columns.tolist()}")
        except Exception as e:
            print(f"测试失败: {e}")

        # 5. 测试 get_industry_base_info - 行业指数基本信息
        print_section("5. 测试 get_industry_base_info (行业指数基本信息)")
        try:
            industry_info = await provider.get_industry_base_info()
            print(f"获取到 {len(industry_info)} 条行业指数信息")
            if not industry_info.empty:
                print("\n前5条数据:")
                print(industry_info.head())
                print(f"\n列名: {industry_info.columns.tolist()}")
        except Exception as e:
            print(f"测试失败: {e}")

    finally:
        # 断开连接
        await provider.disconnect()
        print("\n已断开连接")


async def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("  AmazingData 扩展接口测试")
    print("=" * 80)

    # 测试 ETF 接口
    await test_etf_interfaces()

    # 等待一下，避免请求过快
    await asyncio.sleep(2)

    # 测试指数接口
    await test_index_interfaces()

    print_section("测试完成")


if __name__ == "__main__":
    asyncio.run(main())
