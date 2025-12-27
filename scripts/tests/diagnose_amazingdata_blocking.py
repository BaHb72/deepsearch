#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData 阻塞问题诊断脚本

用于诊断AmazingData API阻塞的根本原因：
1. SDK是否正确加载
2. Provider是否正确初始化
3. 登录是否执行/成功
4. 数据对象是否初始化
"""

import asyncio
import sys
import time
from pathlib import Path

# 确保项目根目录在path中
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def print_section(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_check(name: str, result: bool, detail: str = ""):
    status = "[OK]" if result else "[FAIL]"
    print(f"  {status} {name}")
    if detail:
        print(f"       -> {detail}")


async def diagnose():
    """执行完整的诊断流程"""

    print_section("Step 1: 检查SDK加载状态")

    try:
        from deepsearch.infrastructure.providers.implementations.amazingdata._sdk_loader import (
            HAS_AMAZINGDATA,
            IMPORT_ERROR,
            ad,
        )

        print_check("SDK模块导入", True, f"HAS_AMAZINGDATA = {HAS_AMAZINGDATA}")

        if not HAS_AMAZINGDATA:
            print_check("SDK可用性", False, f"导入错误: {IMPORT_ERROR}")
            print("\n结论: SDK未安装或导入失败，将进入降级模式")
            return

        print_check("SDK可用性", True, f"ad模块类型: {type(ad)}")

        # 检查SDK的关键组件
        if ad:
            has_login = hasattr(ad, "login")
            has_basedata = hasattr(ad, "BaseData")
            has_infodata = hasattr(ad, "InfoData")
            print_check("SDK.login方法", has_login)
            print_check("SDK.BaseData类", has_basedata)
            print_check("SDK.InfoData类", has_infodata)

    except Exception as e:
        print_check("SDK模块导入", False, str(e))
        return

    print_section("Step 2: 检查配置")

    try:
        from deepsearch.config import get_config

        config = get_config()

        data_sources_cfg = getattr(config, "data_sources", None)
        if data_sources_cfg:
            print_check("data_sources配置", True)

            providers_cfg = getattr(data_sources_cfg, "providers", None)
            if providers_cfg:
                print_check("providers配置", True)

                # 尝试获取amazingdata配置
                ad_cfg = None
                if hasattr(providers_cfg, "amazingdata"):
                    ad_cfg = getattr(providers_cfg, "amazingdata")
                elif hasattr(providers_cfg, "get"):
                    ad_cfg = providers_cfg.get("amazingdata")
                elif hasattr(providers_cfg, "model_dump"):
                    ad_cfg = providers_cfg.model_dump().get("amazingdata")

                if ad_cfg:
                    print_check("amazingdata配置", True)

                    # 检查连接配置
                    if hasattr(ad_cfg, "config"):
                        cfg_inner = ad_cfg.config
                        if hasattr(cfg_inner, "connection"):
                            conn = cfg_inner.connection
                            username = getattr(conn, "username", None)
                            host = getattr(conn, "host", None)
                            port = getattr(conn, "port", None)
                            print(f"       -> username: {username}")
                            print(f"       -> host: {host}")
                            print(f"       -> port: {port}")
                            if username:
                                print_check("用户名配置", True)
                            else:
                                print_check("用户名配置", False, "未配置用户名！")
                        else:
                            print_check("connection配置", False, "缺少connection节点")
                    else:
                        print_check("config节点", False, "缺少config节点")
                else:
                    print_check("amazingdata配置", False, "未找到amazingdata配置")
            else:
                print_check("providers配置", False)
        else:
            print_check("data_sources配置", False)

    except Exception as e:
        print_check("配置检查", False, str(e))

    print_section("Step 3: 测试Provider创建和初始化")

    try:
        from deepsearch.config import get_config
        from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_extended import (
            AmazingDataExtended,
        )
        from deepsearch.infrastructure.providers.implementations.amazingdata.config import (
            ensure_amazingdata_provider_config,
        )

        config = get_config()
        data_sources = config.data_sources
        providers = data_sources.providers

        # 获取amazingdata配置
        if hasattr(providers, "amazingdata"):
            ad_provider_cfg = providers.amazingdata
        elif hasattr(providers, "model_dump"):
            ad_provider_cfg = providers.model_dump().get("amazingdata", {})
        else:
            ad_provider_cfg = {}

        if hasattr(ad_provider_cfg, "config"):
            raw_config = ad_provider_cfg.config
        elif isinstance(ad_provider_cfg, dict):
            raw_config = ad_provider_cfg.get("config", {})
        else:
            raw_config = {}

        # 构建配置
        connection_cfg = (
            getattr(raw_config, "connection", {})
            if hasattr(raw_config, "connection")
            else raw_config.get("connection", {})
        )

        if hasattr(connection_cfg, "username"):
            username = connection_cfg.username
            password = connection_cfg.password
            host = connection_cfg.host
            port = connection_cfg.port
        elif isinstance(connection_cfg, dict):
            username = connection_cfg.get("username", "")
            password = connection_cfg.get("password", "")
            host = connection_cfg.get("host", "101.230.159.234")
            port = connection_cfg.get("port", 8600)
        else:
            username = ""
            password = ""
            host = "101.230.159.234"
            port = 8600

        print(f"  使用配置: username={username}, host={host}, port={port}")

        config_payload = {
            "username": username,
            "password": password,
            "host": host,
            "port": port,
            "timeout": 10.0,
        }

        provider_config = ensure_amazingdata_provider_config(config_payload)
        print_check("配置创建", True)

        # 创建Provider
        print("\n  创建 AmazingDataExtended...")
        provider = AmazingDataExtended(provider_config)
        print_check("Provider创建", True)

        # 检查初始状态
        print("\n  初始状态:")
        print(f"    _connected = {provider._connected}")
        print(f"    _degraded_mode = {provider._degraded_mode}")
        print(f"    _sdk_available = {provider._sdk_available}")
        print(f"    _initialized_objects = {provider._initialized_objects}")
        print(f"    _base_data = {provider._base_data}")
        print(f"    _info_data = {provider._info_data}")

        if provider._degraded_mode:
            print_check("降级模式检查", False, "Provider处于降级模式！将无法登录")
            return

        # 尝试初始化
        print("\n  执行 provider.initialize()...")
        start_time = time.time()

        try:
            result = await asyncio.wait_for(provider.initialize(), timeout=15.0)
            elapsed = time.time() - start_time
            print_check(f"初始化完成 ({elapsed:.2f}s)", result)
        except asyncio.TimeoutError:
            print_check("初始化", False, "超时！(15秒)")
            print("\n  这就是阻塞问题！初始化过程卡住了。")
            return
        except Exception as e:
            elapsed = time.time() - start_time
            print_check(f"初始化 ({elapsed:.2f}s)", False, str(e))
            return

        # 检查初始化后的状态
        print("\n  初始化后状态:")
        print(f"    _connected = {provider._connected}")
        print(f"    _initialized_objects = {provider._initialized_objects}")
        print(f"    _base_data = {provider._base_data}")
        print(f"    _info_data = {provider._info_data}")

        if not provider._connected:
            print_check("连接状态", False, "初始化后仍未连接！登录失败")
        else:
            print_check("连接状态", True, "已连接")

    except Exception as e:
        import traceback

        print_check("Provider测试", False, str(e))
        print(f"\n  详细错误:\n{traceback.format_exc()}")

    print_section("Step 4: 测试API调用")

    if "provider" in dir() and provider._connected:
        try:
            print("  调用 get_balance_sheet(['SH.600519'])...")
            start_time = time.time()
            result = await asyncio.wait_for(provider.get_balance_sheet(["SH.600519"]), timeout=30.0)
            elapsed = time.time() - start_time
            print_check(f"get_balance_sheet ({elapsed:.2f}s)", True, f"返回{len(result)}条数据")
        except asyncio.TimeoutError:
            print_check("get_balance_sheet", False, "超时！(30秒)")
        except Exception as e:
            print_check("get_balance_sheet", False, str(e))
    else:
        print("  跳过API测试（Provider未连接）")

    print_section("诊断完成")


if __name__ == "__main__":
    print("AmazingData 阻塞问题诊断工具")
    print("=" * 60)
    asyncio.run(diagnose())
