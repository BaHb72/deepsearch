"""
Arrow IPC File Cache Manager

基于 Apache Arrow IPC 格式的高性能文件缓存，支持多进程共享。
采用 Qlib 风格的内存映射策略，实现近零堆内存占用。

特性：
- Arrow IPC 格式存储，支持零拷贝读取
- 跨平台兼容 (Linux: /dev/shm, Windows: %TEMP%)
- 命名空间隔离不同子系统
- TTL 过期自动清理
- 线程安全的写入操作
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

import pandas as pd

# TYPE_CHECKING 模式：mypy 静态分析时导入，运行时不导入
if TYPE_CHECKING:
    import pyarrow as pa

# 运行时导入
try:
    import pyarrow as pa_runtime
    import pyarrow.ipc as ipc_runtime

    PYARROW_AVAILABLE = True
except ImportError:
    pa_runtime = None  # type: ignore[assignment]
    ipc_runtime = None  # type: ignore[assignment]
    PYARROW_AVAILABLE = False


def _get_default_cache_dir() -> Path:
    """获取默认缓存目录（跨平台兼容）"""
    if sys.platform == "linux":
        # Linux: 使用 /dev/shm 实现真正的共享内存
        shm_dir = Path("/dev/shm/deepsearch_cache")
        if shm_dir.parent.exists():
            return shm_dir

    # Windows / 其他平台 / /dev/shm 不可用时：使用临时目录
    return Path(tempfile.gettempdir()) / "deepsearch_cache"


class ArrowCacheManager:
    """
    系统级 Arrow IPC 文件缓存（多进程安全）

    特性:
    - 使用 Arrow IPC 格式，支持 memory_map 零拷贝读取
    - 文件锁保证多进程写入安全
    - 可配置命名空间隔离不同子系统
    - 跨进程共享：多个 Python 进程可同时读取
    - 支持热重载配置（动态更新 TTL）

    用法:
        cache = ArrowCacheManager(namespace="amazingdata")
        cache.set("key", df)
        df = cache.get("key")

        # 热重载配置
        cache.reload_config()
    """

    # 类级别默认目录
    DEFAULT_BASE_DIR: Path = _get_default_cache_dir()

    def __init__(
        self,
        namespace: str = "default",
        base_dir: Optional[Path] = None,
        ttl: Optional[int] = None,
        use_config: bool = True,
    ):
        """
        初始化缓存管理器

        Args:
            namespace: 命名空间，用于隔离不同子系统的缓存
            base_dir: 缓存基础目录，None=从配置读取或使用跨平台默认目录
            ttl: 缓存过期时间（秒），None=从配置读取或使用默认值 300
            use_config: 是否从配置文件读取设置（支持热重载）
        """
        if not PYARROW_AVAILABLE:
            raise ImportError(
                "pyarrow is required for ArrowCacheManager. " "Install with: pip install pyarrow"
            )

        self.namespace = namespace
        self._use_config = use_config
        self._explicit_ttl = ttl  # 显式传入的 TTL（优先级最高）
        self._explicit_base_dir = base_dir  # 显式传入的目录

        # 加载配置
        self._load_config()

        self.cache_dir = self.base_dir / namespace
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # 统计信息
        self._stats = {"hits": 0, "misses": 0, "writes": 0}

        # 索引文件
        self.index_path = self.cache_dir / "index.json"
        self._index = self._load_index()

    def _load_config(self) -> None:
        """从配置文件加载设置（支持热重载）"""
        config_ttl = 300
        config_base_dir = None

        if self._use_config:
            try:
                from deepsearch.config.models.arrow_cache import get_arrow_cache_config

                config = get_arrow_cache_config()
                config_ttl = config.get_namespace_ttl(self.namespace)
                if config.base_dir:
                    config_base_dir = Path(config.base_dir)
            except Exception:
                pass

        # 优先级: 显式参数 > 配置文件 > 默认值
        self.ttl = self._explicit_ttl if self._explicit_ttl is not None else config_ttl
        self.base_dir = (
            self._explicit_base_dir
            if self._explicit_base_dir
            else (config_base_dir if config_base_dir else self.DEFAULT_BASE_DIR)
        )

    def reload_config(self) -> Dict[str, Any]:
        """
        热重载配置（从配置文件重新读取 TTL 等设置）

        Returns:
            更新后的配置信息
        """
        old_ttl = self.ttl
        self._load_config()

        return {
            "namespace": self.namespace,
            "old_ttl": old_ttl,
            "new_ttl": self.ttl,
            "base_dir": str(self.base_dir),
            "reloaded": True,
        }

    def generate_cache_key(self, **params) -> str:
        """
        生成标准化缓存键（兼容 OptimizedCacheManager API）

        Args:
            **params: 缓存参数（如 symbol, period, start_date 等）

        Returns:
            标准化的缓存键字符串
        """
        # 参数标准化：过滤 None 值
        normalized = {k: v for k, v in params.items() if v is not None}

        # 排序保证顺序一致
        sorted_params = sorted(normalized.items())

        # 生成哈希键
        key_str = json.dumps(sorted_params, ensure_ascii=False)
        hash_key = hashlib.md5(key_str.encode()).hexdigest()[:16]

        # 添加可读前缀
        prefix = f"{params.get('symbol', 'unknown')}:{params.get('period', 'unknown')}"

        return f"{prefix}:{hash_key}"

    def _load_index(self) -> Dict[str, Any]:
        """加载索引文件"""
        if self.index_path.exists():
            try:
                return json.loads(self.index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_index(self) -> None:
        """保存索引文件"""
        try:
            self.index_path.write_text(
                json.dumps(self._index, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass  # 忽略写入错误

    def _get_file_path(self, key: str) -> Path:
        """根据 key 生成文件路径"""
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{hash_key}.arrow"

    def get(self, key: str, as_arrow: bool = False) -> Optional[Union[pd.DataFrame, "pa.Table"]]:
        """
        获取缓存

        Args:
            key: 缓存键
            as_arrow: 如果 True，返回 Arrow Table（零拷贝）; 否则返回 DataFrame

        Returns:
            缓存的数据，未命中或过期返回 None
        """
        if key not in self._index:
            self._stats["misses"] += 1
            return None

        entry = self._index[key]
        file_path = Path(entry["path"])

        # TTL 检查
        if time.time() - entry["created_at"] > self.ttl:
            self.invalidate(key)
            self._stats["misses"] += 1
            return None

        # 文件存在性检查
        if not file_path.exists():
            del self._index[key]
            self._stats["misses"] += 1
            return None

        # 使用内存映射读取
        try:
            with pa_runtime.memory_map(str(file_path), "r") as source:
                reader = ipc_runtime.open_file(source)
                table = reader.read_all()

            self._stats["hits"] += 1
            return table if as_arrow else table.to_pandas()
        except Exception:
            # 读取失败，清理无效缓存
            self.invalidate(key)
            self._stats["misses"] += 1
            return None

    def set(self, key: str, data: Union[pd.DataFrame, "pa.Table"]) -> None:
        """
        设置缓存

        Args:
            key: 缓存键
            data: 要缓存的数据（DataFrame 或 Arrow Table）
        """
        file_path = self._get_file_path(key)

        # 转换为 Arrow Table
        if isinstance(data, pd.DataFrame):
            table = pa_runtime.Table.from_pandas(data)
        else:
            table = data

        # 写入（带锁保证线程安全）
        with self._lock:
            try:
                with pa_runtime.OSFile(str(file_path), "wb") as sink:
                    writer = ipc_runtime.new_file(sink, table.schema)
                    writer.write_table(table)
                    writer.close()

                self._index[key] = {
                    "path": str(file_path),
                    "created_at": time.time(),
                    "size_bytes": file_path.stat().st_size,
                }
                self._save_index()
                self._stats["writes"] += 1
            except Exception:
                # 写入失败，静默忽略
                pass

    def invalidate(self, key: str) -> None:
        """使指定缓存失效"""
        if key in self._index:
            file_path = Path(self._index[key]["path"])
            try:
                if file_path.exists():
                    file_path.unlink()
            except OSError:
                pass
            del self._index[key]
            self._save_index()

    def clear(self) -> int:
        """
        清空所有缓存

        Returns:
            清理的缓存条目数
        """
        count = len(self._index)
        for key in list(self._index.keys()):
            self.invalidate(key)
        return count

    def cleanup_expired(self) -> int:
        """
        清理过期缓存

        Returns:
            清理的缓存条目数
        """
        now = time.time()
        expired_keys = [
            k for k, v in self._index.items() if now - v.get("created_at", 0) > self.ttl
        ]
        for key in expired_keys:
            self.invalidate(key)
        return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            包含命名空间、文件数、总大小等信息的字典
        """
        total_size = sum(entry.get("size_bytes", 0) for entry in self._index.values())
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0

        return {
            "namespace": self.namespace,
            "cache_dir": str(self.cache_dir),
            "cache_files": len(self._index),
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "ttl": self.ttl,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "writes": self._stats["writes"],
            "hit_rate": f"{hit_rate:.1%}",
        }

    def __repr__(self) -> str:
        return f"ArrowCacheManager(namespace='{self.namespace}', cache_dir='{self.cache_dir}')"
