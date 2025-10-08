"""
Provider Health Monitoring System

监控数据提供者的健康状态，记录故障，触发告警，
支持自动恢复和降级决策。
"""

import asyncio
import importlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from loguru import logger

from deepsearch.observability.logger import logger_manager


class ProviderStatus(Enum):
    """提供者状态枚举"""

    HEALTHY = "healthy"  # 健康
    DEGRADED = "degraded"  # 降级
    RECOVERING = "recovering"  # 恢复中
    FAILED = "failed"  # 失败
    UNKNOWN = "unknown"  # 未知


@dataclass
class ProviderHealth:
    """提供者健康状态数据类"""

    name: str
    status: ProviderStatus
    last_check: datetime
    consecutive_errors: int = 0
    total_errors: int = 0
    total_requests: int = 0
    success_rate: float = 0.0
    average_latency_ms: float = 0.0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    sdk_exit_count: int = 0  # SDK退出次数
    recovery_attempts: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data["status"] = self.status.value
        data["last_check"] = self.last_check.isoformat()
        if self.last_error_time:
            data["last_error_time"] = self.last_error_time.isoformat()
        return data


class ProviderHealthMonitor:
    """
    提供者健康监控器

    负责监控所有数据提供者的健康状态，
    记录故障信息，触发告警，支持自动恢复。
    """

    def __init__(
        self,
        check_interval: int = 60,  # 健康检查间隔（秒）
        max_consecutive_errors: int = 3,  # 最大连续错误次数
        recovery_cooldown: int = 300,  # 恢复冷却时间（秒）
        persist_dir: Optional[Path] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化监控器

        Args:
            check_interval: 健康检查间隔
            max_consecutive_errors: 触发降级的最大连续错误次数
            recovery_cooldown: 恢复尝试的冷却时间
            persist_dir: 持久化目录
        """
        self.check_interval = check_interval
        self.max_consecutive_errors = max_consecutive_errors
        self.recovery_cooldown = recovery_cooldown
        self.persist_dir = persist_dir or Path("./monitoring_data")
        self._config: Dict[str, Any] = config or {}

        # 健康状态存储
        self._health_status: Dict[str, ProviderHealth] = {}

        # 告警记录
        self._alerts: List[Dict[str, Any]] = []

        # 监控任务
        self._monitoring_task: Optional[asyncio.Task] = None

        # 确保持久化目录存在
        if self.persist_dir:
            self.persist_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ProviderHealthMonitor initialized | interval={check_interval}s")

    def update_config(self, config: Optional[Dict[str, Any]]) -> None:
        self._config = config or {}

    async def start_monitoring(self):
        """启动监控"""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("Monitoring already running")
            return

        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Health monitoring started")

    async def stop_monitoring(self):
        """停止监控"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Health monitoring stopped")

    async def _monitoring_loop(self):
        """监控循环"""
        while True:
            try:
                await self._check_all_providers()
                await self._evaluate_recovery()
                await self._persist_status()
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(5)  # 错误后短暂等待

    async def _check_all_providers(self):
        """检查所有提供者的健康状态"""
        # 这里应该调用实际的提供者健康检查
        # 现在使用模拟实现
        pass

    def record_request(self, provider_name: str, success: bool, latency_ms: float = 0):
        """
        记录请求结果

        Args:
            provider_name: 提供者名称
            success: 是否成功
            latency_ms: 延迟（毫秒）
        """
        if provider_name not in self._health_status:
            self._health_status[provider_name] = ProviderHealth(
                name=provider_name, status=ProviderStatus.UNKNOWN, last_check=datetime.now()
            )

        health = self._health_status[provider_name]
        health.total_requests += 1
        health.last_check = datetime.now()

        if success:
            health.consecutive_errors = 0
            health.average_latency_ms = (
                health.average_latency_ms * (health.total_requests - 1) + latency_ms
            ) / health.total_requests
        else:
            health.consecutive_errors += 1
            health.total_errors += 1

        # 更新成功率
        health.success_rate = (health.total_requests - health.total_errors) / health.total_requests

        # 评估状态
        self._evaluate_status(provider_name)

    def record_error(self, provider_name: str, error_type: str, error_msg: str):
        """
        记录错误

        Args:
            provider_name: 提供者名称
            error_type: 错误类型
            error_msg: 错误消息
        """
        if provider_name not in self._health_status:
            self._health_status[provider_name] = ProviderHealth(
                name=provider_name, status=ProviderStatus.UNKNOWN, last_check=datetime.now()
            )

        health = self._health_status[provider_name]
        health.last_error = error_msg
        health.last_error_time = datetime.now()
        health.total_errors += 1
        health.consecutive_errors += 1

        # 特殊处理SDK退出
        if error_type == "SDK_EXIT":
            health.sdk_exit_count += 1
            self._trigger_alert(
                level="CRITICAL",
                provider=provider_name,
                message=f"SDK attempted to exit! Count: {health.sdk_exit_count}",
                alert_type="SDK_EXIT",
            )

        # 评估状态
        self._evaluate_status(provider_name)

    def _evaluate_status(self, provider_name: str):
        """
        评估提供者状态

        Args:
            provider_name: 提供者名称
        """
        health = self._health_status.get(provider_name)
        if not health:
            return

        old_status = health.status

        # 根据连续错误次数判断状态
        if health.consecutive_errors == 0:
            health.status = ProviderStatus.HEALTHY

        elif health.consecutive_errors < self.max_consecutive_errors:
            health.status = ProviderStatus.DEGRADED

        else:
            health.status = ProviderStatus.FAILED

        # SDK退出立即标记为失败
        if health.sdk_exit_count > 0:
            health.status = ProviderStatus.FAILED

        # 状态变化时触发告警
        if old_status != health.status:
            self._on_status_change(provider_name, old_status, health.status)

    def _on_status_change(
        self, provider_name: str, old_status: ProviderStatus, new_status: ProviderStatus
    ):
        """
        状态变化处理

        Args:
            provider_name: 提供者名称
            old_status: 旧状态
            new_status: 新状态
        """
        logger.warning(
            f"Provider {provider_name} status changed: {old_status.value} -> {new_status.value}"
        )

        # 触发告警
        if new_status == ProviderStatus.FAILED:
            self._trigger_alert(
                level="ERROR",
                provider=provider_name,
                message=f"Provider failed after {self._health_status[provider_name].consecutive_errors} errors",
                alert_type="PROVIDER_FAILED",
            )

        elif new_status == ProviderStatus.DEGRADED:
            self._trigger_alert(
                level="WARNING",
                provider=provider_name,
                message=f"Provider degraded, errors: {self._health_status[provider_name].consecutive_errors}",
                alert_type="PROVIDER_DEGRADED",
            )

        elif new_status == ProviderStatus.HEALTHY and old_status == ProviderStatus.FAILED:
            self._trigger_alert(
                level="INFO",
                provider=provider_name,
                message="Provider recovered",
                alert_type="PROVIDER_RECOVERED",
            )

    def _trigger_alert(self, level: str, provider: str, message: str, alert_type: str):
        """
        触发告警

        Args:
            level: 告警级别（CRITICAL, ERROR, WARNING, INFO）
            provider: 提供者名称
            message: 告警消息
            alert_type: 告警类型
        """
        alert = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "provider": provider,
            "message": message,
            "type": alert_type,
        }

        self._alerts.append(alert)

        # 保留最近的100条告警
        if len(self._alerts) > 100:
            self._alerts = self._alerts[-100:]

        # 记录到日志
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(f"[ALERT][{alert_type}] {provider}: {message}")

        # 集成告警系统
        self._send_alert_notification_sync(alert)

    def _send_alert_notification_sync(self, alert: Dict[str, Any]):
        """
        同步发送告警通知到各种渠道

        Args:
            alert: 告警信息字典
        """
        try:
            # 1. WebSocket推送（如果有连接的客户端）
            # 这里需要WebSocket管理器的集成
            # 示例: websocket_manager.broadcast_alert(alert)

            # 2. 写入告警日志文件（可被外部系统监控）
            alert_log_file = logger_manager.ensure_subdirectory("alerts") / "alerts.jsonl"

            import json

            with open(alert_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert, ensure_ascii=False) + "\n")

            # 3. 发送到监控队列（如果配置了）
            # 可以使用Redis Pub/Sub或其他消息队列
            # 示例: redis_client.publish("alerts", json.dumps(alert))

            # 4. 调用Webhook（如果配置了）
            webhook_urls = self._config.get("alert_webhooks", [])
            if webhook_urls:
                requests_module = importlib.import_module("requests")

                for url in webhook_urls:
                    try:
                        cast(Any, requests_module).post(url, json=alert, timeout=5)
                    except Exception as e:
                        logger.warning(f"Failed to send alert to webhook {url}: {e}")

            # 5. 未来扩展点：
            # - 邮件通知（通过SMTP或API）
            # - 微信企业号/钉钉机器人
            # - Telegram Bot
            # - PagerDuty/Opsgenie等专业告警平台

            logger.debug(f"Alert notification sent: {alert['type']}")

        except Exception as e:
            logger.error(f"Failed to send alert notification: {e}")
            # 告警发送失败不应影响主流程

    async def _send_alert_notification(self, alert: Dict[str, Any]):
        """
        发送告警通知到各种渠道

        Args:
            alert: 告警信息字典
        """
        try:
            # 1. WebSocket推送（如果有连接的客户端）
            # 这里需要WebSocket管理器的集成
            # 示例: await websocket_manager.broadcast_alert(alert)

            # 2. 写入告警日志文件（可被外部系统监控）
            alert_log_file = logger_manager.ensure_subdirectory("alerts") / "alerts.jsonl"

            import json

            with open(alert_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert, ensure_ascii=False) + "\n")

            # 3. 发送到监控队列（如果配置了）
            # 可以使用Redis Pub/Sub或其他消息队列
            # 示例: await redis_client.publish("alerts", json.dumps(alert))

            # 4. 调用Webhook（如果配置了）
            webhook_urls = self._config.get("alert_webhooks", [])
            if webhook_urls:
                import aiohttp

                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    for url in webhook_urls:
                        try:
                            await session.post(url, json=alert)
                        except Exception as e:
                            logger.warning(f"Failed to send alert to webhook {url}: {e}")

            # 5. 未来扩展点：
            # - 邮件通知（通过SMTP或API）
            # - 微信企业号/钉钉机器人
            # - Telegram Bot
            # - PagerDuty/Opsgenie等专业告警平台

            logger.debug(f"Alert notification sent: {alert['type']}")

        except Exception as e:
            logger.error(f"Failed to send alert notification: {e}")
            # 告警发送失败不应影响主流程

    async def _evaluate_recovery(self):
        """评估是否可以尝试恢复失败的提供者"""
        now = datetime.now()

        for provider_name, health in self._health_status.items():
            if health.status != ProviderStatus.FAILED:
                continue

            # 检查冷却时间
            if health.last_error_time:
                time_since_error = (now - health.last_error_time).total_seconds()
                if time_since_error > self.recovery_cooldown:
                    health.status = ProviderStatus.RECOVERING
                    health.recovery_attempts += 1
                    logger.info(
                        f"Attempting recovery for {provider_name}, attempt #{health.recovery_attempts}"
                    )

    async def _persist_status(self):
        """持久化健康状态"""
        if not self.persist_dir:
            return

        try:
            # 保存健康状态
            health_file = self.persist_dir / "provider_health.json"
            health_data = {name: health.to_dict() for name, health in self._health_status.items()}

            with open(health_file, "w", encoding="utf-8") as f:
                json.dump(health_data, f, indent=2, ensure_ascii=False)

            # 保存告警记录
            alerts_file = self.persist_dir / "alerts.json"
            with open(alerts_file, "w", encoding="utf-8") as f:
                json.dump(self._alerts, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to persist monitoring data: {e}")

    def get_health_summary(self) -> Dict[str, Any]:
        """
        获取健康状态摘要

        Returns:
            健康状态摘要
        """
        total_providers = len(self._health_status)
        healthy_count = sum(
            1 for h in self._health_status.values() if h.status == ProviderStatus.HEALTHY
        )
        degraded_count = sum(
            1 for h in self._health_status.values() if h.status == ProviderStatus.DEGRADED
        )
        failed_count = sum(
            1 for h in self._health_status.values() if h.status == ProviderStatus.FAILED
        )

        return {
            "timestamp": datetime.now().isoformat(),
            "total_providers": total_providers,
            "healthy": healthy_count,
            "degraded": degraded_count,
            "failed": failed_count,
            "providers": {
                name: {
                    "status": health.status.value,
                    "success_rate": f"{health.success_rate:.2%}",
                    "consecutive_errors": health.consecutive_errors,
                    "sdk_exits": health.sdk_exit_count,
                }
                for name, health in self._health_status.items()
            },
            "recent_alerts": self._alerts[-10:] if self._alerts else [],
        }

    def get_provider_health(self, provider_name: str) -> Optional[ProviderHealth]:
        """获取特定提供者的健康状态"""
        return self._health_status.get(provider_name)

    def reset_provider(self, provider_name: str):
        """重置提供者状态"""
        if provider_name in self._health_status:
            health = self._health_status[provider_name]
            health.consecutive_errors = 0
            health.status = ProviderStatus.UNKNOWN
            health.recovery_attempts = 0
            logger.info(f"Provider {provider_name} status reset")


# 全局监控器实例
_monitor: Optional[ProviderHealthMonitor] = None


def get_monitor() -> ProviderHealthMonitor:
    """获取全局监控器实例"""
    global _monitor
    if _monitor is None:
        _monitor = ProviderHealthMonitor()
    return _monitor


async def start_monitoring():
    """启动全局监控"""
    monitor = get_monitor()
    await monitor.start_monitoring()


async def stop_monitoring():
    """停止全局监控"""
    monitor = get_monitor()
    await monitor.stop_monitoring()
