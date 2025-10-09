"""
AmazingData SDK崩溃测试脚本
用于定位具体哪个API调用导致崩溃
"""


def test_amazingdata_step_by_step():
    """逐步测试AmazingData SDK的各个功能"""

    print("=" * 60)
    print("AmazingData SDK崩溃定位测试")
    print("=" * 60)

    # Step 1: 导入测试
    print("\n[Step 1] 尝试导入AmazingData...")
    try:
        import AmazingData as ad

        print("✓ 导入成功")
        print(f"  版本信息: {dir(ad)[:5]}...")  # 打印部分属性
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return

    # Step 2: 登录测试
    print("\n[Step 2] 尝试登录...")
    try:
        login_result = ad.login(
            username="212200038719", password="212200038719@2025", host="101.230.159.234", port=8600
        )
        print(f"✓ 登录返回: {login_result}")
        if login_result != 0 and login_result is not True:
            print(f"  登录失败，错误码: {login_result}")
            return
        print("  登录成功！")
    except Exception as e:
        print(f"✗ 登录异常: {e}")
        return

    # Step 3: BaseData对象创建测试
    print("\n[Step 3] 尝试创建BaseData对象...")
    print("  [调试] 即将执行: base_data = ad.BaseData()")
    input("  按Enter继续（可在此处下断点）...")

    try:
        base_data = ad.BaseData()
        print("✓ BaseData对象创建成功")
        print(f"  对象类型: {type(base_data)}")
        print(f"  对象方法: {[m for m in dir(base_data) if not m.startswith('_')][:5]}...")
    except Exception as e:
        print(f"✗ 创建BaseData失败: {e}")
        print(f"  异常类型: {type(e).__name__}")

        # 尝试登出
        try:
            ad.logout("212200038719")
            print("  已登出")
        except Exception:
            pass
        return

    # Step 4: 获取数据测试
    print("\n[Step 4] 尝试获取股票代码信息...")
    print("  [调试] 即将执行: code_info = base_data.get_code_info('EXTRA_STOCK_A')")
    input("  按Enter继续（可在此处下断点）...")

    try:
        code_info = base_data.get_code_info("EXTRA_STOCK_A")
        print("✓ get_code_info调用成功")
        print(f"  返回类型: {type(code_info)}")

        # 安全地检查返回值
        if code_info is None:
            print("  返回值为None")
        else:
            try:
                # 尝试获取长度
                length = len(code_info)
                print(f"  数据长度: {length}")
            except Exception:
                print("  无法获取长度")

            # 如果是DataFrame，打印一些信息
            try:
                print(f"  数据形状: {code_info.shape}")
                print(f"  列名: {list(code_info.columns)[:5]}...")
            except Exception:
                pass

    except Exception as e:
        print(f"✗ 获取数据失败: {e}")
        print(f"  异常类型: {type(e).__name__}")

    # Step 5: 清理
    print("\n[Step 5] 清理资源...")
    try:
        ad.logout("212200038719")
        print("✓ 登出成功")
    except Exception as e:
        print(f"✗ 登出失败: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_amazingdata_step_by_step()
    except Exception as e:
        print(f"\n严重错误: {e}")
        import traceback

        traceback.print_exc()

    input("\n按Enter退出...")
