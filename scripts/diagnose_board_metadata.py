from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Sequence

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import get_config
from core.config.models.amazingdata import AmazingDataConnectionConfig as Conn
from core.infrastructure.providers.implementations.amazingdata.amazingdata_process import (
    ProcessIsolatedAmazingDataProvider,
)


async def diagnose(symbols: Sequence[str]) -> None:
    # 从配置文件读取凭据
    config = get_config()
    ad_conn = config.amazingdata.connection

    cfg = Conn(
        username=ad_conn.username,
        password=ad_conn.password,
        host=ad_conn.host,
        port=ad_conn.port,
        timeout=getattr(ad_conn, "timeout", 5000),
        heartbeat_interval=getattr(ad_conn, "heartbeat_interval", 60),
        auto_reconnect=getattr(ad_conn, "auto_reconnect", True),
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
    symbols = ["600519.SH", "300750.SZ", "510050.SH", "588000.SH"]
    asyncio.run(diagnose(symbols))
