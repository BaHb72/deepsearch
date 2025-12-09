from __future__ import annotations

import asyncio
from typing import Sequence

from deepsearch.config.models.amazingdata import AmazingDataConnectionConfig as Conn
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process import (
    ProcessIsolatedAmazingDataProvider,
)


async def diagnose(symbols: Sequence[str]) -> None:
    # 从 dev 配置复制的账号参数（仅用于本地快速诊断；生产请改为加载 settings.dev.yaml）
    cfg = Conn(
        username="212200038719",
        password="212200038719@2025",
        host="101.230.159.234",
        port=8600,
        timeout=5000,
        heartbeat_interval=60,
        auto_reconnect=True,
    )

    provider = ProcessIsolatedAmazingDataProvider(cfg)
    await provider.initialize()
    try:
        res = await provider._fetch_board_metadata(symbols)
        print("symbols=", symbols)
        print("records_count=", len(res))
        if res:
            print("sample=", res[:2])
    finally:
        await provider.shutdown()


if __name__ == "__main__":
    # 可选：若现场没有 AmazingData SDK，可先用 stub 进行代码路径验证
    # os.environ.setdefault("DEEPSEARCH_AMAZINGDATA_STUB", "tests.stubs.amazingdata_stub")
    symbols = ["600519.SH", "300750.SZ", "510050.SH", "588000.SH"]
    asyncio.run(diagnose(symbols))
