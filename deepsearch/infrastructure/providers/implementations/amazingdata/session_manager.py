"""Session and connection management helpers for AmazingData provider."""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .amazingdata_process_proxy import _InterProcessFileLock
from .logging_utils import log_debug

if TYPE_CHECKING:
    from .amazingdata import AmazingDataProvider


class AmazingDataSessionManager:
    """Encapsulates login/session level coordination for AmazingDataProvider."""

    def __init__(self, owner: "AmazingDataProvider") -> None:
        self._owner = owner
        self._login_file_lock: _InterProcessFileLock | None = None

    def _resolve_login_lock_path(self) -> Path:
        config = self._owner.config
        base_dir = Path(os.environ.get("DEEPSEARCH_AMAZINGDATA_LOCK_DIR") or tempfile.gettempdir())
        token = f"{config.username}@{config.host}:{config.port}"
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
        return base_dir / f"amazingdata_login_{digest}.lock"

    async def acquire_login_file_lock(self) -> _InterProcessFileLock | None:
        lock_path = self._resolve_login_lock_path()
        lock = _InterProcessFileLock(lock_path)
        loop = asyncio.get_running_loop()
        acquired = await loop.run_in_executor(None, lambda: lock.acquire(blocking=True))
        if not acquired:
            log_debug(
                "登录文件锁已被占用，等待释放",
                action="login_lock",
                metadata={"path": str(lock_path)},
            )
            return None
        log_debug("获取登录文件锁成功", action="login_lock", metadata={"path": str(lock_path)})
        self._login_file_lock = lock
        return lock

    async def release_login_file_lock(self) -> None:
        if not self._login_file_lock:
            return
        lock = self._login_file_lock
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lock.release)
        log_debug("登录文件锁已释放", action="login_lock", metadata={"path": str(lock.path)})
        self._login_file_lock = None
