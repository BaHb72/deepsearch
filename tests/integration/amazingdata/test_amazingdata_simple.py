#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单测试AmazingData连接
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from deepsearch.config import get_config

def test_simple():
    print("\n" + "=" * 60)
    print("AmazingData 简单连接测试")
    print("=" * 60)

    # 获取配置
    config = get_config()
    print(f"\n当前环境: {config.app.env}")

    # 获取AmazingData配置
    if hasattr(config, 'data_sources') and config.data_sources:
        providers = config.data_sources.get('providers', {})
        if 'amazingdata' in providers:
            print("\n使用新格式配置 (data_sources.providers.amazingdata)")
            ad_provider = providers['amazingdata']
            ad_config = ad_provider.get('config', {})
            conn_config = ad_config.get('connection', {})

            username = conn_config.get('username', '')
            password = conn_config.get('password', '')
            host = conn_config.get('host', '')
            port = conn_config.get('port', 8600)

            print(f"\n配置信息:")
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
                print(f"\n正在登录...")
                print(f"调用: ad.login('{username}', '{password}', '{host}', {port})")

                result = ad.login(username, password, host, port)

                print(f"登录结果: {result}")

                if result == 0 or result is True:
                    print("[OK] 登录成功!")

                    # 测试获取股票列表
                    print("\n测试获取股票列表...")
                    stock_list = ad.BaseData.get_stock_list()
                    if stock_list is not None:
                        print(f"[OK] 获取股票列表成功，共{len(stock_list)}只股票")

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
    if hasattr(config, 'amazingdata'):
        print("\n\n也找到旧格式配置 (amazingdata):")
        ad_config = config.amazingdata
        print(f"  用户名: {getattr(ad_config, 'username', '')}")
        print(f"  密码: {getattr(ad_config, 'password', '')}")
        print(f"  服务器: {getattr(ad_config, 'host', '')}:{getattr(ad_config, 'port', '')}")

if __name__ == "__main__":
    test_simple()