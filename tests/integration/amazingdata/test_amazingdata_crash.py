"""
AmazingData SDK 崩溃定位脚本。

此文件用于人工调试，默认不参与自动化回归。
"""

import os

import pytest


def _is_enabled(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def test_amazingdata_step_by_step() -> None:
    """逐步测试 AmazingData SDK 的关键调用。"""
    if not _is_enabled("RUN_AMAZINGDATA_CRASH_DEBUG"):
        pytest.skip("崩溃定位脚本默认关闭，设置 RUN_AMAZINGDATA_CRASH_DEBUG=1 后再执行。")

    print("=" * 60)
    print("AmazingData SDK 崩溃定位测试")
    print("=" * 60)

    print("\n[Step 1] 尝试导入 AmazingData...")
    try:
        import AmazingData as ad

        print("导入成功")
        print(f"版本信息: {dir(ad)[:5]}...")
    except ImportError as exc:
        print(f"导入失败: {exc}")
        return

    username = os.getenv("AMAZINGDATA_USERNAME", "").strip()
    password = os.getenv("AMAZINGDATA_PASSWORD", "").strip()
    host = os.getenv("AMAZINGDATA_HOST", "101.230.159.234").strip()
    port = int(os.getenv("AMAZINGDATA_PORT", "8600"))
    if not username or not password:
        pytest.skip("缺少 AMAZINGDATA_USERNAME/AMAZINGDATA_PASSWORD，跳过崩溃定位测试。")

    print("\n[Step 2] 尝试登录...")
    try:
        login_result = ad.login(username=username, password=password, host=host, port=port)
        print(f"登录返回: {login_result}")
        if login_result != 0 and login_result is not True:
            print(f"登录失败，错误码: {login_result}")
            return
        print("登录成功")
    except SystemExit as exc:
        print(f"登录触发 SystemExit: {exc}")
        return
    except Exception as exc:
        print(f"登录异常: {exc}")
        return

    print("\n[Step 3] 尝试创建 BaseData 对象...")
    print("即将执行: base_data = ad.BaseData()")
    if _is_enabled("RUN_AMAZINGDATA_INTERACTIVE"):
        input("按 Enter 继续（可在此处下断点）...")

    try:
        base_data = ad.BaseData()
        print("BaseData 对象创建成功")
        print(f"对象类型: {type(base_data)}")
        print(f"对象方法: {[m for m in dir(base_data) if not m.startswith('_')][:5]}...")
    except Exception as exc:
        print(f"创建 BaseData 失败: {exc}")
        print(f"异常类型: {type(exc).__name__}")
        try:
            ad.logout(username)
        except Exception:
            pass
        return

    print("\n[Step 4] 尝试获取股票代码信息...")
    print("即将执行: code_info = base_data.get_code_info('EXTRA_STOCK_A')")
    if _is_enabled("RUN_AMAZINGDATA_INTERACTIVE"):
        input("按 Enter 继续（可在此处下断点）...")

    try:
        code_info = base_data.get_code_info("EXTRA_STOCK_A")
        print("get_code_info 调用成功")
        print(f"返回类型: {type(code_info)}")
        if code_info is None:
            print("返回值为 None")
        else:
            try:
                print(f"数据长度: {len(code_info)}")
            except Exception:
                print("无法获取长度")
            try:
                print(f"数据形状: {code_info.shape}")
                print(f"列名: {list(code_info.columns)[:5]}...")
            except Exception:
                pass
    except Exception as exc:
        print(f"获取数据失败: {exc}")
        print(f"异常类型: {type(exc).__name__}")

    print("\n[Step 5] 清理资源...")
    try:
        ad.logout(username)
        print("登出成功")
    except Exception as exc:
        print(f"登出失败: {exc}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_amazingdata_step_by_step()
    if _is_enabled("RUN_AMAZINGDATA_INTERACTIVE"):
        input("\n按 Enter 退出...")
