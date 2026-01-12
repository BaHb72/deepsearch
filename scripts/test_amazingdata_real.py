"""
AmazingData 真实连接测试脚本
测试 SDK 登录和财务数据获取
"""

import asyncio
import sys
import time

# 添加项目路径
sys.path.insert(0, r"D:\Stock\code\deepsearch")


async def test_sdk_connection():
    """测试SDK直接连接"""
    print("=" * 60)
    print("测试1: SDK 直接连接")
    print("=" * 60)

    try:
        # 尝试导入SDK
        import AmazingData as ad

        print(f"[OK] SDK导入成功: {ad}")

        # 登录参数
        username = "212200038719"
        password = "212200038719@2025"
        host = "101.230.159.234"
        port = 8600

        print(f"[INFO] 尝试登录...")
        print(f"  - 用户名: {username}")
        print(f"  - 主机: {host}:{port}")

        start = time.time()
        # 按文档使用关键字参数
        result = ad.login(username=username, password=password, host=host, port=port)
        elapsed = time.time() - start
        print(f"[INFO] 登录结果: {result}, 耗时: {elapsed:.2f}秒")

        if result:  # 成功返回True
            print("[OK] 登录成功!")

            # 测试获取财务数据
            print("\n[INFO] 测试获取资产负债表...")
            try:
                info_data = ad.InfoData()
                balance = info_data.get_balance_sheet(
                    code_list=["600519.SH"],
                    local_path="D://AmazingData_local_data//",
                    is_local=True,
                )
                print(f"[OK] 资产负债表获取成功!")
                if balance is not None:
                    print(f"  - 类型: {type(balance)}")
                    if hasattr(balance, "shape"):
                        print(f"  - 数据形状: {balance.shape}")
                    if hasattr(balance, "columns"):
                        print(f"  - 列名: {list(balance.columns)[:5]}...")
            except Exception as e:
                print(f"[ERROR] 获取资产负债表失败: {e}")

            # 登出
            ad.logout(username)
            print("[OK] 已登出")
        else:
            print(f"[ERROR] 登录失败, 返回码: {result}")

    except ImportError as e:
        print(f"[ERROR] SDK导入失败: {e}")
        print("[INFO] 尝试导入 tgw...")
        try:
            import tgw as ad

            print(f"[OK] tgw导入成功: {ad}")
            print(f"[INFO] 可用属性: {[a for a in dir(ad) if not a.startswith('_')][:20]}")
        except ImportError as e2:
            print(f"[ERROR] tgw也导入失败: {e2}")
    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback

        traceback.print_exc()


async def test_provider_connection():
    """测试通过Provider连接"""
    print("\n" + "=" * 60)
    print("测试2: AmazingDataExtended Provider 连接")
    print("=" * 60)

    try:
        from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_extended import (
            AmazingDataExtended,
        )

        config = {
            "username": "212200038719",
            "password": "212200038719@2025",
            "host": "101.230.159.234",
            "port": 8600,
            "timeout": 30,
        }

        print("[INFO] 创建 AmazingDataExtended...")
        provider = AmazingDataExtended(config)

        print("[INFO] 初始化中...")
        start = time.time()
        result = await provider.initialize()
        elapsed = time.time() - start
        print(f"[INFO] 初始化结果: {result}, 耗时: {elapsed:.2f}秒")

        print(f"[INFO] Provider状态:")
        print(f"  - _connected: {getattr(provider, '_connected', 'N/A')}")
        print(f"  - _degraded_mode: {getattr(provider, '_degraded_mode', 'N/A')}")
        print(f"  - _sdk_available: {getattr(provider, '_sdk_available', 'N/A')}")

        if getattr(provider, "_connected", False):
            print("\n[INFO] 测试获取资产负债表...")
            start = time.time()
            balance = await provider.get_balance_sheet(
                code_list=["600519.SH"], local_path="D://AmazingData_local_data//", is_local=True
            )
            elapsed = time.time() - start
            print(f"[OK] 获取成功, 耗时: {elapsed:.2f}秒")
            if balance is not None:
                print(f"  - 类型: {type(balance)}")
                if hasattr(balance, "shape"):
                    print(f"  - 数据形状: {balance.shape}")

        await provider.stop_async()
        print("[OK] Provider已停止")

    except Exception as e:
        print(f"[ERROR] Provider测试失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("AmazingData 真实连接测试")
    print("账号: 212200038719")
    print("时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print()

    # asyncio.run(test_sdk_connection())
    asyncio.run(test_provider_connection())  # 测试Provider
