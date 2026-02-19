#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单测试AmazingData连接
"""

import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import get_config
from helpers import fetch_code_list


def _as_dict(value):
    """将配置对象转换为 dict。"""
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump()
            if isinstance(dumped, dict):
                return dict(dumped)
        except Exception:
            return {}
    raw = getattr(value, "__dict__", None)
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def _read_field(value, key, default=None):
    """兼容 dict / pydantic 对象读取字段。"""
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def test_simple():
    print("\n" + "=" * 60)
    print("AmazingData 简单连接测试")
    print("=" * 60)

    # 获取配置
    config = get_config()
    print(f"\n当前环境: {config.app.env}")

    # 获取AmazingData配置
    if hasattr(config, "data_sources") and config.data_sources:
        providers = _as_dict(_read_field(config.data_sources, "providers", {}))
        if "amazingdata" in providers:
            print("\n使用新格式配置 (data_sources.providers.amazingdata)")
            ad_provider = providers["amazingdata"]
            ad_config = _as_dict(_read_field(ad_provider, "config", {}))
            conn_config = _as_dict(ad_config.get("connection", {}))

            username = conn_config.get("username", "")
            password = conn_config.get("password", "")
            host = conn_config.get("host", "")
            port = conn_config.get("port", 8600)

            print("\n配置信息:")
            print(f"  服务器: {host}:{port}")
            print(f"  用户名: {username}")
            print(f"  密码: {password}")
            print(f"  密码长度: {len(password)}")

            # 尝试导入和登录
            try:
                import AmazingData as ad

                print("\n[OK] AmazingData SDK已导入")
                print(f"SDK版本: {getattr(ad, '__version__', '未知')}")

                # 尝试登录
                print("\n正在登录...")
                print(f"调用: ad.login('{username}', '{password}', '{host}', {port})")

                result = ad.login(username, password, host, port)

                print(f"登录结果: {result}")

                if result == 0 or result is True:
                    print("[OK] 登录成功!")

                    # 测试获取股票列表
                    print("\n测试获取股票列表...")
                    stock_list = fetch_code_list(ad)
                    if not stock_list.empty:
                        print(f"[OK] 获取股票列表成功，共{len(stock_list)}只股票")
                    else:
                        print("[WARNING] 股票列表为空")

                    # 登出
                    ad.logout()
                    print("[OK] 已登出")
                else:
                    print(f"[FAIL] 登录失败，返回值: {result}")

            except Exception as e:
                print(f"[ERROR] {e}")
                import traceback

                traceback.print_exc()

    # 也检查旧格式配置
    if hasattr(config, "amazingdata"):
        print("\n\n也找到旧格式配置 (amazingdata):")
        ad_config = config.amazingdata
        print(f"  用户名: {getattr(ad_config, 'username', '')}")
        print(f"  密码: {getattr(ad_config, 'password', '')}")
        print(f"  服务器: {getattr(ad_config, 'host', '')}:{getattr(ad_config, 'port', '')}")


if __name__ == "__main__":
    test_simple()
