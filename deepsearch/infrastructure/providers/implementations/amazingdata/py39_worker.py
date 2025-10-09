# encoding:utf-8
"""
AmazingData Python 3.9 Worker 模块
"""

import argparse
import base64
import os
import queue
import sys
import traceback
from multiprocessing.connection import Client, Connection
from typing import Optional, cast

from loguru import logger

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_proxy import (
    AmazingDataProcessProxy,
    WorkerQueue,
)


class _ConnectionQueue:
    """将 multiprocessing Connection 封装为队列接口"""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def get(self, timeout: Optional[float] = None) -> bytes:
        if timeout is None:
            return cast(bytes, self._conn.recv_bytes())
        if not self._conn.poll(timeout):
            raise queue.Empty
        return cast(bytes, self._conn.recv_bytes())

    def put(self, data: bytes) -> None:
        self._conn.send_bytes(data)


def _configure_logging(level: str) -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=level.upper(),
        format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] {message}",
    )


def _load_sdk_stub_if_needed() -> None:
    stub_module = os.environ.get("DEEPSEARCH_AMAZINGDATA_STUB")
    if not stub_module:
        return
    import importlib

    module = importlib.import_module(stub_module)
    sys.modules["AmazingData"] = module
    logger.info(f"Loaded AmazingData stub module: {stub_module}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AmazingData Python 3.9 worker")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--authkey", required=True)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    _configure_logging(args.log_level)
    _load_sdk_stub_if_needed()

    try:
        authkey = base64.b64decode(args.authkey.encode("ascii"))
    except Exception as exc:
        logger.error(f"Invalid authkey encoding: {exc}")
        sys.exit(2)

    logger.info(f"Connecting to controller {args.host}:{args.port}")
    conn = cast(Connection, Client((args.host, args.port), authkey=authkey))
    logger.info("Connected to controller, starting worker loop")

    request_queue: WorkerQueue = _ConnectionQueue(conn)
    response_queue: WorkerQueue = _ConnectionQueue(conn)

    try:
        AmazingDataProcessProxy._worker_loop(request_queue, response_queue)
    except KeyboardInterrupt:
        logger.info("Worker interrupted by keyboard")
    except Exception as exc:  # pragma: no cover - 异常时用于排查
        logger.error(f"Worker crashed: {exc}")
        logger.error(traceback.format_exc())
    finally:
        try:
            conn.close()
        except Exception:
            pass

    logger.info("Worker shutdown complete")


if __name__ == "__main__":
    main()
