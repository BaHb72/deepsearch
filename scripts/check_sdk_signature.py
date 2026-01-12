"""
SDK 函数签名检查
"""

import sys

sys.path.insert(0, r"D:\Stock\code\deepsearch")

print("=" * 60)
print("检查 SDK login 函数签名")
print("=" * 60)

# 尝试 AmazingData
try:
    import AmazingData as ad

    print(f"\n[1] import AmazingData 成功: {ad}")
    print(f"    ad.login = {ad.login}")

    import inspect

    sig = inspect.signature(ad.login)
    print(f"    签名: {sig}")
    print(f"    参数: {list(sig.parameters.keys())}")
except Exception as e:
    print(f"[1] import AmazingData 失败: {e}")

# 尝试 tgw
try:
    import tgw

    print(f"\n[2] import tgw 成功: {tgw}")
    if hasattr(tgw, "login"):
        print(f"    tgw.login = {tgw.login}")
    if hasattr(tgw, "Login"):
        print(f"    tgw.Login = {tgw.Login}")

    # 列出可用函数
    funcs = [
        attr for attr in dir(tgw) if not attr.startswith("_") and callable(getattr(tgw, attr, None))
    ]
    print(f"    可调用函数: {funcs[:15]}")
except Exception as e:
    print(f"[2] import tgw 失败: {e}")

# 检查 _sdk_loader
print("\n" + "=" * 60)
print("检查 _sdk_loader 加载的 SDK")
print("=" * 60)
try:
    from deepsearch.infrastructure.providers.implementations.amazingdata._sdk_loader import (
        HAS_AMAZINGDATA,
        ad,
    )

    print(f"ad = {ad}")
    print(f"HAS_AMAZINGDATA = {HAS_AMAZINGDATA}")
    if ad:
        print(f"ad.__name__ = {ad.__name__}")
        if hasattr(ad, "login"):
            print(f"ad.login = {ad.login}")
            import inspect

            try:
                sig = inspect.signature(ad.login)
                print(f"签名: {sig}")
            except Exception as e:
                print(f"无法获取签名: {e}")
except Exception as e:
    print(f"检查失败: {e}")
    import traceback

    traceback.print_exc()
