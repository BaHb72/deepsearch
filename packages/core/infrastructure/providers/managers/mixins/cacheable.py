"""
缓存混入模块

提供多级缓存能力，可选择性地混入到管理器中。
从 enhanced_manager.py 提取并优化。

设计原则：
- 混入专注于行为，不维护自己的状态
- 使用 Protocol 进行类型提示
- 提供清晰的初始化和使用接口

使用方法:
    class MyManager(BaseDataSourceManager, CacheableMixin):
        async def initialize(self):
            await super().initialize()
            self._init_cache()

        async def get_data(self, ...):
            # 尝试从缓存获取
            cached = await self.get_cached(cache_key)
            if cached is not None:
                return cached
            # 获取数据
            data = await self._fetch_data(...)
            # 存入缓存
            self.set_cached(cache_key, data)
            return data
"""

from typing import TYPE_CHECKING, Any, Dict, Optional, Protocol

from loguru import logger

if TYPE_CHECKING:
    # 避免循环导入
    pass


class _CacheManagerProtocol(Protocol):
    """缓存管理器协议

    定义缓存管理器需要实现的接口。
    """

    def get(self, key: str, max_age: Optional[int] = None) -> Optional[Any]:
        """获取缓存值"""
        ...

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """设置缓存值"""
        ...

    def clear(self) -> None:
        """清空缓存"""
        ...

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        ...


class CacheableMixin:
    """缓存混入

    为数据源管理器提供缓存能力。

    Attributes:
        _cache_enabled: 是否启用缓存
        _cache_manager: 缓存管理器实例
        _cache_default_ttl: 默认缓存过期时间（秒）

    Example:
        >>> class Manager(CacheableMixin):
        ...     pass
        >>> mgr = Manager()
        >>> mgr._init_cache(max_memory_size=1000)
        >>> mgr.set_cached("key", "value", ttl=60)
        >>> await mgr.get_cached("key")
        'value'
    """

    # 类属性声明（由混入使用者设置）
    _cache_enabled: bool = True
    _cache_manager: Optional[_CacheManagerProtocol] = None
    _cache_default_ttl: int = 300

    def _init_cache(
        self,
        max_memory_size: int = 2000,
        default_ttl: int = 300,
        enabled: bool = True,
    ) -> None:
        """初始化缓存管理器

        Args:
            max_memory_size: 最大内存缓存大小（条目数）
            default_ttl: 默认缓存过期时间（秒）
            enabled: 是否启用缓存

        Note:
            此方法应在管理器初始化时调用。
            如果 SmartCacheManager 不可用，缓存功能将被禁用。
        """
        self._cache_enabled = enabled
        self._cache_default_ttl = default_ttl

        if not self._cache_enabled:
            logger.debug("缓存功能已禁用")
            return

        try:
            from core.infrastructure.providers.implementations.qmt.unified_qmt_provider import (
                SmartCacheManager,
            )

            self._cache_manager = SmartCacheManager(max_memory_size=max_memory_size)  # type: ignore[assignment]
            logger.info(
                f"✅ 缓存管理器初始化成功，最大容量: {max_memory_size}，默认TTL: {default_ttl}秒"
            )
        except ImportError as e:
            logger.warning(f"SmartCacheManager 导入失败，缓存功能已禁用: {e}")
            self._cache_enabled = False
            self._cache_manager = None

    async def get_cached(
        self,
        key: str,
        max_age: Optional[int] = None,
    ) -> Optional[Any]:
        """从缓存获取数据

        Args:
            key: 缓存键
            max_age: 最大缓存年龄（秒）。
                     如果为 None，使用默认 TTL。
                     如果缓存项年龄超过此值，返回 None。

        Returns:
            缓存的数据，未命中或已过期返回 None

        Example:
            >>> data = await mgr.get_cached("stock:000001:quote")
            >>> if data is None:
            ...     data = await fetch_from_source()
        """
        if not self._cache_enabled or not self._cache_manager:
            return None

        try:
            if max_age is not None:
                return self._cache_manager.get(key, max_age=max_age)
            return self._cache_manager.get(key)
        except Exception as e:
            logger.debug(f"缓存读取失败 (key={key}): {e}")
            return None

    def set_cached(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """设置缓存

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）。如果为 None，使用默认 TTL。

        Note:
            如果缓存已禁用或管理器未初始化，此方法静默返回。

        Example:
            >>> mgr.set_cached("stock:000001:quote", quote_data, ttl=60)
        """
        if not self._cache_enabled or not self._cache_manager:
            return

        try:
            actual_ttl = ttl if ttl is not None else self._cache_default_ttl
            self._cache_manager.set(key, value, ttl=actual_ttl)
        except Exception as e:
            logger.debug(f"缓存写入失败 (key={key}): {e}")

    def invalidate_cache(self, key: str) -> bool:
        """使指定缓存失效

        Args:
            key: 要失效的缓存键

        Returns:
            是否成功失效（如果缓存存在）
        """
        if not self._cache_enabled or not self._cache_manager:
            return False

        try:
            # 通过设置过期的值来失效
            # 注意：SmartCacheManager 可能不支持 delete，
            # 这里使用 set 空值 + 0 TTL 作为替代
            self._cache_manager.set(key, None, ttl=0)
            return True
        except Exception:
            return False

    def clear_cache(self) -> None:
        """清空所有缓存

        Note:
            此操作不可逆，所有缓存数据将被删除。
        """
        if not self._cache_manager:
            return

        try:
            self._cache_manager.clear()
            logger.info("🗑️ 缓存已清空")
        except Exception as e:
            logger.warning(f"清空缓存失败: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            包含以下字段的字典:
            - enabled: 缓存是否启用
            - 其他由缓存管理器提供的统计信息

        Example:
            >>> stats = mgr.get_cache_stats()
            >>> print(f"命中率: {stats.get('hit_rate', 0):.2%}")
        """
        if not self._cache_manager:
            return {"enabled": False}

        try:
            stats = self._cache_manager.get_stats()
            return {
                "enabled": True,
                "default_ttl": self._cache_default_ttl,
                **stats,
            }
        except Exception as e:
            logger.debug(f"获取缓存统计失败: {e}")
            return {"enabled": True, "error": str(e)}

    @staticmethod
    def make_cache_key(*parts: Any, prefix: str = "ds") -> str:
        """生成标准化的缓存键

        Args:
            *parts: 缓存键的各个部分
            prefix: 键前缀，默认 "ds"（data source）

        Returns:
            格式化的缓存键

        Example:
            >>> CacheableMixin.make_cache_key("quote", "000001", "realtime")
            'ds:quote:000001:realtime'
        """
        parts_str = [str(p) for p in parts if p is not None]
        return f"{prefix}:{':'.join(parts_str)}"


__all__ = ["CacheableMixin"]
