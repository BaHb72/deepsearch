from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

import redis
import redistimeseries.client as ts

from deepsearch.event.engine import Event

logger = logging.getLogger(__name__)


class RedisTimeSeriesStorage:
    """
    RedisTimeSeries 存储类，用于持久化 ZeroMQ 消息序列
    该类提供了将消息事件按时间序列存储到 Redis 的功能，
    支持按时间范围查询历史消息数据。
    """

    # 类常量
    MESSAGES_SUFFIX = ":messages"
    DEFAULT_RETENTION_MS = 86400000  # 24小时
    HASH_MASK = 0x7FFFFFFF
    TTL_KEY_NOT_EXISTS = -2

    def __init__(
            self,
            host: str = "localhost",
            port: int = 6379,
            db: int = 0,
            password: Optional[str] = None,
            key_prefix: str = "deepsearch:ts:",
            retention_ms: int = DEFAULT_RETENTION_MS,
            duplicate_policy: str = "LAST",
    ) -> None:
        """
        初始化 RedisTimeSeries 存储实例
        
        :param host: Redis 服务器地址
        :param port: Redis 服务器端口
        :param db: Redis 数据库编号
        :param password: Redis 服务器密码
        :param key_prefix: 时间序列键前缀
        :param retention_ms: 数据保留时间（毫秒）
        :param duplicate_policy: 重复数据处理策略
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.key_prefix = key_prefix
        self.retention_ms = retention_ms
        self.duplicate_policy = duplicate_policy

        # 创建 Redis 客户端
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,
        )

        # 创建 RedisTimeSeries 客户端
        self.ts_client = ts.Client(self.redis_client)

        logger.info(f"RedisTimeSeries 存储初始化完成: {host}:{port}/{db}")

    def _get_series_key(self, topic: str, event_type: str) -> str:
        """获取时间序列键名"""
        return f"{self.key_prefix}{topic}:{event_type}"

    def _get_hash_key(self, ts_key: str) -> str:
        """获取Hash键名"""
        return f"{ts_key}{self.MESSAGES_SUFFIX}"

    def _current_timestamp_ms(self) -> int:
        """获取当前时间戳（毫秒）"""
        return int(time.time() * 1000)

    def _serialize_event(self, event: Event, source: Optional[str] = None) -> str:
        """将事件序列化为JSON字符串"""
        event_data = {
            "type": event.type,
            "data": event.data,
            "source": source,
            "timestamp": time.time(),
        }
        return json.dumps(event_data, ensure_ascii=False)

    def _extract_topics_from_keys(self, keys: List[str]) -> List[str]:
        """从键列表中提取主题"""
        topics = set()
        for key in keys:
            if not key.endswith(self.MESSAGES_SUFFIX):
                key_without_prefix = key[len(self.key_prefix):]
                parts = key_without_prefix.split(":", 1)
                if len(parts) >= 1:
                    topics.add(parts[0])
        return list(topics)

    def _extract_event_types_from_keys(self, keys: List[str]) -> List[str]:
        """从键列表中提取事件类型"""
        event_types = set()
        for key in keys:
            if not key.endswith(self.MESSAGES_SUFFIX):
                key_without_prefix = key[len(self.key_prefix):]
                parts = key_without_prefix.split(":", 1)
                if len(parts) > 1:
                    event_types.add(parts[1])
        return list(event_types)

    def _ensure_timeseries(self, key: str, labels: Dict[str, str] = None) -> None:
        """确保时间序列存在"""
        try:
            # 检查时间序列是否存在
            self.ts_client.info(key)
        except redis.exceptions.ResponseError:
            # 时间序列不存在，创建新的
            try:
                self.ts_client.create(
                    key,
                    retention_msecs=self.retention_ms,
                    duplicate_policy=self.duplicate_policy,
                    labels=labels or {},
                )
                logger.debug(f"创建时间序列: {key}")
            except Exception as e:
                logger.error(f"创建时间序列失败 {key}: {e}")
                raise

    def store_event(self, event: Event, topic: str = None, source: str = None) -> bool:
        """
        存储事件到时间序列
        
        :param event: 要存储的事件
        :param topic: 自定义主题，默认使用事件类型
        :param source: 事件来源
        :return: 存储是否成功
        """
        try:
            topic = topic or event.type
            ts_key = self._get_series_key(topic, event.type)

            # 准备标签
            labels = {"topic": topic, "event_type": event.type}
            if source:
                labels["source"] = source

            # 确保时间序列存在
            self._ensure_timeseries(ts_key, labels)

            # 序列化事件数据
            event_json = self._serialize_event(event, source)
            timestamp_ms = self._current_timestamp_ms()

            # 使用消息数据的哈希作为值（确保为正数）
            value = hash(event_json) & self.HASH_MASK

            self.ts_client.add(ts_key, timestamp_ms, value)

            # 将完整消息存储到 Hash 结构中
            hash_key = self._get_hash_key(ts_key)
            self.redis_client.hset(hash_key, timestamp_ms, event_json)

            # 设置 Hash 的过期时间
            self.redis_client.expire(hash_key, self.retention_ms // 1000)

            logger.debug(f"事件已存储: {ts_key} @ {timestamp_ms}")
            return True

        except Exception as e:
            logger.error(f"存储事件失败: {e}")
            return False

    def query_events(
            self,
            topic: str,
            event_type: str,
            start_time: Optional[float] = None,
            end_time: Optional[float] = None,
            limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        查询时间范围内的事件
        
        :param topic: 主题
        :param event_type: 事件类型
        :param start_time: 开始时间（秒级时间戳）
        :param end_time: 结束时间（秒级时间戳）
        :param limit: 限制返回数量
        :return: 事件列表
        """
        try:
            ts_key = self._get_series_key(topic, event_type)
            hash_key = self._get_hash_key(ts_key)

            # 构建查询参数
            from_time = int(start_time * 1000) if start_time else "-"
            to_time = int(end_time * 1000) if end_time else "+"

            # 查询时间序列获取时间戳
            ts_data = self.ts_client.range(
                ts_key,
                from_time=from_time,
                to_time=to_time,
                count=limit,
            )

            events = []
            for timestamp_ms, _ in ts_data:
                # 从 Hash 中获取完整消息
                event_json = self.redis_client.hget(hash_key, timestamp_ms)
                if event_json:
                    try:
                        event_data = json.loads(event_json)
                        events.append(event_data)
                    except json.JSONDecodeError as e:
                        logger.warning(f"解析事件JSON失败: {e}")

            logger.debug(f"查询到 {len(events)} 条事件: {ts_key}")
            return events

        except Exception as e:
            logger.error(f"查询事件失败: {e}")
            return []

    def get_topics(self) -> List[str]:
        """获取所有主题列表"""
        try:
            pattern = f"{self.key_prefix}*"
            keys = self.redis_client.keys(pattern)
            return self._extract_topics_from_keys(keys)
        except Exception as e:
            logger.error(f"获取主题列表失败: {e}")
            return []

    def get_event_types(self, topic: str) -> List[str]:
        """获取指定主题下的事件类型列表"""
        try:
            pattern = f"{self.key_prefix}{topic}:*"
            keys = self.redis_client.keys(pattern)
            return self._extract_event_types_from_keys(keys)
        except Exception as e:
            logger.error(f"获取事件类型列表失败: {e}")
            return []

    def cleanup_expired_data(self) -> None:
        """清理过期数据"""
        try:
            # RedisTimeSeries 会自动清理过期的时间序列数据
            # 这里只需清理相关的 Hash 数据
            pattern = f"{self.key_prefix}*{self.MESSAGES_SUFFIX}"
            keys = self.redis_client.keys(pattern)

            for key in keys:
                # 检查 TTL，如果已过期则删除
                ttl = self.redis_client.ttl(key)
                if ttl == self.TTL_KEY_NOT_EXISTS:
                    self.redis_client.delete(key)
                    logger.debug(f"清理过期数据: {key}")
        except Exception as e:
            logger.error(f"清理过期数据失败: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        try:
            pattern = f"{self.key_prefix}*"
            keys = self.redis_client.keys(pattern)

            ts_keys = [k for k in keys if not k.endswith(self.MESSAGES_SUFFIX)]
            hash_keys = [k for k in keys if k.endswith(self.MESSAGES_SUFFIX)]

            return {
                "total_timeseries": len(ts_keys),
                "total_hash_keys": len(hash_keys),
                "topics": len(self.get_topics()),
                "redis_memory_usage": self.redis_client.info("memory").get("used_memory_human", "N/A"),
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

    def close(self) -> None:
        """关闭连接"""
        try:
            self.redis_client.close()
            logger.info("RedisTimeSeries 存储连接已关闭")
        except Exception as e:
            logger.error(f"关闭 RedisTimeSeries 连接失败: {e}")
