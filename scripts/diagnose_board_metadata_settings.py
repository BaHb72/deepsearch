from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any, Mapping, Sequence

from deepsearch.config import get_config
from deepsearch.config.models.amazingdata import AmazingDataConnectionConfig as Conn
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process import (
    ProcessIsolatedAmazingDataProvider,
)
from deepsearch.ports.amazingdata_process import ProcessCommand


def _resolve_conn_from_settings() -> Conn:
    """从 Settings 解析 AmazingData 连接参数，优先 data_sources.providers，再回退 amazingdata.connection。"""
    settings = get_config()

    # 优先 data_sources.providers.amazingdata.config.connection
    ds = getattr(settings, "data_sources", None)
    if ds and getattr(ds, "providers", None):
        provider = ds.providers.get("amazingdata")
        if provider and isinstance(provider.config, Mapping):
            cfg = provider.config  # type: ignore[assignment]
            conn = cfg.get("connection") if isinstance(cfg.get("connection"), Mapping) else cfg
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

    # 回退 settings.amazingdata.connection
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

    raise RuntimeError("未在 Settings 中找到有效的 AmazingData 连接配置")


async def diagnose(symbols: Sequence[str]) -> None:
    # 若未显式设置，默认读取 dev 环境配置
    os.environ.setdefault("APP__ENV", "dev")

    # 解析连接参数
    cfg = _resolve_conn_from_settings()

    provider = ProcessIsolatedAmazingDataProvider(cfg)
    await provider.initialize()
    try:
        # 1) 打印 normalized symbols 样例与总数
        normalized = sorted({s.upper() for s in symbols if isinstance(s, str) and s.strip()})
        print("normalized_symbols_sample=", normalized[:5])
        print("normalized_symbols_total=", len(normalized))

        # 2) 直接调用 InfoData.get_stock_basic（最小化验证）
        info_cmd = ProcessCommand[Any](
            method="InfoData.get_stock_basic",
            kwargs={"code_list": normalized[:20] or normalized},
        )
        info_res = await provider._execute(info_cmd)
        info_ok = (
            isinstance(info_res, (dict, list))
            or getattr(getattr(info_res, "__class__", object), "__name__", "") == "DataFrame"
        )
        print("info.get_stock_basic_type=", type(info_res).__name__)
        if hasattr(info_res, "head"):
            try:
                head = info_res.head(2)  # type: ignore[attr-defined]
                print("info.get_stock_basic_sample=", head.to_dict("records"))
            except Exception:
                pass

        # 3) 调用 _fetch_board_metadata（内置分支：InfoData DataFrame -> BaseData 映射）
        merged = await provider._fetch_board_metadata(normalized)
        print("fetch_board_metadata_count=", len(merged))
        if merged:
            print("fetch_board_metadata_sample=", merged[:2])

        # 输出用于快速判断的提示
        if info_ok and merged:
            print("branch_used≈InfoData.get_stock_basic (优先使用 DataFrame)")
        elif not info_ok and merged:
            print("branch_used≈BaseData.get_code_info (InfoData 为空或失败)")
        elif not merged:
            print("board_metadata_empty: 可能为权限/限流/品种混入/security_type 不匹配")
    finally:
        await provider.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="诊断 AmazingData 板块元数据为空的原因")
    parser.add_argument(
        "symbols",
        nargs="*",
        help="待检查的代码列表，默认示例：600519.SH 300750.SZ 510050.SH 588000.SH",
    )
    args = parser.parse_args()
    symbols = args.symbols or ["600519.SH", "300750.SZ", "510050.SH", "588000.SH"]
    asyncio.run(diagnose(symbols))


if __name__ == "__main__":
    main()
