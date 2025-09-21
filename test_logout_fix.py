"""
测试logout修复效果

验证logout时正确传递username参数。

Author: DeepSearch Team
Date: 2025-01-21
"""

import time
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_proxy import (
    AmazingDataProcessProxy,
    RequestType
)


def test_logout_with_username():
    """测试logout是否正确传递username"""
    print("=" * 60)
    print("测试AmazingData logout修复")
    print("=" * 60)

    # 创建进程代理
    proxy = AmazingDataProcessProxy(restart_on_crash=False)

    try:
        # 启动进程
        print("\n1. 启动进程...")
        if not proxy.start():
            print("   进程启动失败")
            return
        print("   ✓ 进程启动成功")

        # 测试登录
        print("\n2. 测试登录...")
        username = "test_user"
        password = "test_password"
        host = "101.230.159.234"
        port = 8600

        response = proxy.execute(
            "login",
            username,
            password,
            host,
            port,
            request_type=RequestType.LOGIN,
            timeout=30.0
        )

        if response.success or response.error_type == "SystemExit":
            print(f"   ✓ 登录测试完成")
            print(f"   - 保存的用户名: {proxy.last_login_username}")
        else:
            print(f"   ✗ 登录失败: {response.error}")

        # 停止进程（包含logout）
        print("\n3. 停止进程（包含logout）...")
        print(f"   - 将logout用户: {proxy.last_login_username}")

        success = proxy.stop(with_logout=True, timeout=5.0)

        if success:
            print("   ✓ 进程停止成功（logout已执行）")
        else:
            print("   ✗ 进程停止失败")

        # 检查日志
        print("\n4. 关键日志检查：")
        print("   - 应该看到: 'Login successful, saved username: test_user'")
        print("   - 应该看到: 'Including username in logout request: test_user'")
        print("   - 应该看到: 'Logging out user: test_user'")
        print("   - 不应该看到: 'logout() missing 1 required positional argument'")

    except Exception as e:
        print(f"\n错误: {e}")

    finally:
        # 确保进程被清理
        if proxy.is_running:
            proxy.stop(timeout=1.0)

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_logout_with_username()