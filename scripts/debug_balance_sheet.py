"""
调试 get_balance_sheet 接口失败原因

通过 Monkey Patch 拦截 BalanceSheetSpi.OnResponse 回调，
捕获 tgw 层返回的具体错误码和数据。
"""

import asyncio
import sys

sys.path.insert(0, "packages")


async def test():
    import AmazingData as sdk
    import tgw
    from core.config import get_config

    settings = get_config()
    providers = getattr(settings.data_sources, "providers", {})
    ad_provider = (
        providers.get("amazingdata")
        if isinstance(providers, dict)
        else getattr(providers, "amazingdata", None)
    )
    ad_cfg = (
        getattr(ad_provider, "config", None)
        if not isinstance(ad_provider, dict)
        else ad_provider.get("config")
    )
    conn = (
        ad_cfg.get("connection")
        if isinstance(ad_cfg, dict)
        else getattr(ad_cfg, "connection", None)
    )
    username = (conn.get("username") if isinstance(conn, dict) else conn.username) if conn else ""
    password = (conn.get("password") if isinstance(conn, dict) else conn.password) if conn else ""

    sdk.login(username=username, password=password, host="101.230.159.234", port=8600)
    print("✅ Logged in")

    # Patch BalanceSheetSpi.OnResponse
    from AmazingData.download_data import info_spi

    original_on_response = info_spi.BalanceSheetSpi.OnResponse

    def debug_on_response(self, data, status):
        print("\n>>> BalanceSheetSpi.OnResponse called:")
        print(f"    code: {self._code}")
        print(f"    status: {status}")

        # 映射错误码名称
        error_name = "UNKNOWN"
        for name in dir(tgw.ErrorCode):
            if not name.startswith("_"):
                if getattr(tgw.ErrorCode, name) == status:
                    error_name = name
                    break
        print(f"    error_name: {error_name}")

        print(f"    data type: {type(data).__name__}")
        if isinstance(data, str):
            # 可能是错误消息
            print(f"    data (str): {data[:500]}")
        elif hasattr(data, "__len__"):
            print(f"    data len: {len(data)}")
            if len(data) > 0 and hasattr(data, "__getitem__"):
                print(f"    first item: {data[0]}")

        return original_on_response(self, data, status)

    info_spi.BalanceSheetSpi.OnResponse = debug_on_response
    print("🔧 Patched BalanceSheetSpi.OnResponse")

    # 调用接口
    info = sdk.InfoData()
    print("\n🔍 Calling get_balance_sheet(['000001'], begin_date=20230101, end_date=20231231)...")
    try:
        result = info.get_balance_sheet(["000001"], begin_date=20230101, end_date=20231231)
        print(f"✅ Result: {type(result).__name__}, len={len(result) if result is not None else 0}")
        if result is not None and len(result) > 0:
            print(f"   Columns: {list(result.columns)[:10]}...")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")

        # 检查 EnvBalanceSheet 状态
        try:
            from AmazingData.download_data.download_info_data import EnvBalanceSheet

            print(f"\n📊 EnvBalanceSheet state after error:")
            print(f"    error_list: {EnvBalanceSheet.error_list}")
            print(f"    req_list_len: {EnvBalanceSheet.req_list_len}")
        except Exception as e2:
            print(f"    Cannot access EnvBalanceSheet: {e2}")


if __name__ == "__main__":
    asyncio.run(test())
