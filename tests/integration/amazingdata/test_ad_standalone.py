"""
独立的AmazingData测试脚本
不依赖项目环境
"""


def test():
    print("\n" + "=" * 60)
    print("AmazingData 独立测试")
    print("=" * 60)

    from helpers import fetch_code_list

    # 直接导入测试
    try:
        import AmazingData as ad

        print("\n[OK] SDK导入成功")
    except Exception:
        print("[FAIL] SDK导入失败")
        return

    # 测试登录（使用关键字参数）
    print("\n正在登录...")
    result = ad.login(
        username="212200038719", password="212200038719@2025", host="101.230.159.234", port=8600
    )

    print(f"登录结果: {result}")
    if result or result == 0:
        print("[SUCCESS] ✅ 登录成功！")

        # 获取股票列表
        print("\n获取股票列表...")
        try:
            stocks = fetch_code_list(ad)
            if not stocks.empty:
                print(f"[SUCCESS] 获取{len(stocks)}只股票")
            else:
                print("[WARNING] 股票列表为空")
        except Exception as e:
            print(f"[ERROR] {e}")

        # 登出
        ad.logout()
        print("\n[OK] 已登出")
    else:
        print("[FAIL] 登录失败")


if __name__ == "__main__":
    test()
