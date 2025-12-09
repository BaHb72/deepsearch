from __future__ import annotations

import asyncio
import os
from typing import Sequence

from deepsearch.config import get_config
from deepsearch.config.models.amazingdata import AmazingDataConnectionConfig as Conn
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process import (
    ProcessIsolatedAmazingDataProvider,
)


def _resolve_conn_from_settings() -> Conn:
    settings = get_config()
    ds = getattr(settings, "data_sources", None)
    if ds and getattr(ds, "providers", None):
        provider = ds.providers.get("amazingdata")
        if provider and isinstance(provider.config, dict):
            cfg = provider.config
            conn = cfg.get("connection") if isinstance(cfg.get("connection"), dict) else cfg
            username = str(conn.get("username") or "").strip()
            password = str(conn.get("password") or "").strip()
            host = str(conn.get("host") or "").strip()
            port = int(conn.get("port") or 0)
            timeout = int(conn.get("timeout") or 5000)
            heartbeat_interval = int(conn.get("heartbeat_interval") or 60)
            auto_reconnect = bool(conn.get("auto_reconnect", True))
            if username and password and host and port:
                return Conn(
                    username=username,
                    password=password,
                    host=host,
                    port=port,
                    timeout=timeout,
                    heartbeat_interval=heartbeat_interval,
                    auto_reconnect=auto_reconnect,
                )
    ad = getattr(settings, "amazingdata", None)
    if ad and getattr(ad, "connection", None):
        c = ad.connection
        return Conn(
            username=c.username,
            password=c.password,
            host=c.host,
            port=c.port,
            timeout=int(getattr(c, "timeout", 5000)),
            heartbeat_interval=int(getattr(c, "heartbeat_interval", 60)),
            auto_reconnect=bool(getattr(c, "auto_reconnect", True)),
        )
    raise RuntimeError("Settings 中未找到有效 AmazingData 连接")


async def test(markets: Sequence[str]) -> None:
    os.environ.setdefault("APP__ENV", "dev")
    cfg = _resolve_conn_from_settings()

    provider = ProcessIsolatedAmazingDataProvider(cfg)
    await provider.initialize()
    try:
        for m in markets:
            try:
                days = await provider.get_calendar(market=m, data_type="int")
                print(f"market={m} days_count={(len(days) if days else 0)}")
            except Exception as exc:
                print(f"market={m} error={exc}")
    finally:
        await provider.close()


if __name__ == "__main__":
    asyncio.run(test(["BJ", "BSE", "INDEX", "ETF", "SH", "SZ"]))
