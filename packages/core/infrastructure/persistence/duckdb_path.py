"""DuckDB 路径解析工具"

用于在不同环境（尤其是并行测试）下安全地解析 DuckDB 数据库文件路径，
避免多个 Python 进程同时访问同一个数据库文件导致的锁冲突。
"""

import atexit
import os
import shutil
import threading
from pathlib import Path
from typing import Dict, Optional

_TEST_PATH_CACHE: Dict[str, Path] = {}
_CLEANUP_REGISTERED: Dict[str, bool] = {}
_CACHE_LOCK = threading.Lock()


def is_test_context() -> bool:
    """判断当前是否处于测试或持续集成环境"""

    env = os.getenv("DEEPSEARCH_ENV", "").lower()
    if env in {"test", "testing", "ci"}:
        return True

    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("PYTEST_XDIST_WORKER"):
        return True

    if os.getenv("CI"):
        return True

    return False


def resolve_duckdb_path(original_path: Optional[str]) -> str:
    """根据环境解析 DuckDB 数据库路径"""

    if not original_path:
        return ":memory:"

    override_path = os.getenv("DEEPSEARCH_ANALYTICS_DB_PATH")
    if override_path:
        return _normalize_path(override_path)

    if original_path == ":memory:":
        return original_path

    normalized = _normalize_path(original_path)

    if not is_test_context():
        return normalized

    with _CACHE_LOCK:
        cached = _TEST_PATH_CACHE.get(normalized)
        if cached:
            return str(cached)

        base_path = Path(normalized)
        test_dir_env = os.getenv("DEEPSEARCH_ANALYTICS_TEST_DIR")
        if test_dir_env:
            test_dir = Path(test_dir_env).expanduser()
        else:
            test_dir = base_path.parent / "pytest_duckdb"

        test_dir.mkdir(parents=True, exist_ok=True)

        suffix = base_path.suffix or ".duckdb"
        stem = base_path.stem or "analytics"
        test_path = test_dir / f"{stem}_{os.getpid()}{suffix}"

        if (
            os.getenv("DEEPSEARCH_ANALYTICS_COPY_SEED", "0") == "1"
            and base_path.exists()
            and not test_path.exists()
        ):
            try:
                shutil.copy2(base_path, test_path)
            except OSError:
                pass

        _TEST_PATH_CACHE[normalized] = test_path
        _register_cleanup(test_path)
        return str(test_path)


def _normalize_path(path_str: str) -> str:
    path = Path(path_str).expanduser()
    try:
        return str(path.resolve(strict=False))
    except RuntimeError:
        return str(path.absolute())


def _register_cleanup(path: Path) -> None:
    key = str(path)
    if _CLEANUP_REGISTERED.get(key):
        return

    def _cleanup(target: Path = path) -> None:
        try:
            if target.exists():
                target.unlink()
        except OSError:
            pass

    atexit.register(_cleanup)
    _CLEANUP_REGISTERED[key] = True
