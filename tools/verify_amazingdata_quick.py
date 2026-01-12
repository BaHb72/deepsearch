#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速验证 AmazingData SDK 登录和基础数据获取
"""
import sys

sys.path.insert(0, ".")


def main():
    print("=" * 60)
    print("AmazingData SDK 快速验证")
    print("=" * 60)

    # 1. 加载配置
    print("\n[1] 加载配置...")
    try:
        from deepsearch.config import get_config

        config = get_config()

        # 获取 AmazingData 配置
        data_sources = config.data_sources if hasattr(config, "data_sources") else None
        if data_sources is None:
            print("[ERROR] 未找到 data_sources 配置")
            return False

        # 从 Pydantic model 中提取配置
        if hasattr(data_sources, "model_dump"):
            ds_dict = data_sources.model_dump()
        else:
            ds_dict = dict(data_sources)

        providers = ds_dict.get("providers", {})
        ad_config = providers.get("amazingdata", {})

        if not ad_config:
            print("[ERROR] 未找到 amazingdata 配置")
            return False

        conn = ad_config.get("config", {}).get("connection", {})
        username = conn.get("username", "")
        password = conn.get("password", "")
        host = conn.get("host", "")
        port = conn.get("port", 8600)

        print(f"  用户名: {username}")
        print(f"  服务器: {host}:{port}")
        print(f"  密码长度: {len(password)}")
        print("[OK] 配置加载成功")
    except Exception as e:
        print(f"[ERROR] 加载配置失败: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 2. 导入 SDK
    print("\n[2] 导入 AmazingData SDK...")
    try:
        import AmazingData as ad

        print(f"[OK] SDK 版本: {getattr(ad, '__version__', 'unknown')}")
    except Exception as e:
        print(f"[ERROR] SDK 导入失败: {e}")
        return False

    # 3. 登录测试
    print("\n[3] 测试登录...")
    try:
        result = ad.login(username, password, host, port)
        if result == 0 or result is True:
            print("[OK] 登录成功!")
        else:
            print(f"[FAIL] 登录失败，返回值: {result}")
            return False
    except Exception as e:
        print(f"[ERROR] 登录异常: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 4. 获取基础数据
    print("\n[4] 测试获取股票列表...")
    try:
        base = ad.BaseData()
        code_list = base.get_code_list(security_type="EXTRA_STOCK_A_SH_SZ")
        if code_list is not None and not code_list.empty:
            print(f"[OK] 获取股票列表成功，共 {len(code_list)} 只股票")
            print(f"  示例: {code_list.head(3).to_dict('records')}")
        else:
            print("[WARNING] 股票列表为空")
    except Exception as e:
        print(f"[WARNING] 获取股票列表失败: {e}")

    # 5. 登出
    print("\n[5] 登出...")
    try:
        ad.logout()
        print("[OK] 已登出")
    except Exception as e:
        print(f"[WARNING] 登出异常: {e}")

    print("\n" + "=" * 60)
    print("[SUCCESS] AmazingData 验证完成")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
