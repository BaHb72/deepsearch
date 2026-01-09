"""Alert utilities for AmazingData providers (both thread/process modes).

统一封装告警与监控逻辑，避免在 Provider 内部重复实现。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional

from .logging_utils import ProcessLoggerAdapter

logger = ProcessLoggerAdapter(action="alert")


def _append_alert_bucket(container: Any, alert_type: str, message: str) -> None:
    """将告警消息追加到 Provider 的本地告警缓存中。

    - 优先写入 `provider._alerts[alert_type]`
    - 若不存在 `_alerts`，退化为 `provider._stats[alert_type]`
    - 仅保留最近 10 条
    """

    payload = {"timestamp": datetime.now().isoformat(), "message": message}

    # 进程隔离 Provider 使用 _alerts
    bucket = None
    if hasattr(container, "_alerts") and isinstance(getattr(container, "_alerts"), dict):
        alerts = getattr(container, "_alerts")
        bucket = alerts.setdefault(alert_type, [])
        bucket.append(payload)
        if len(bucket) > 10:
            alerts[alert_type] = bucket[-10:]
        return

    # 线程版 Provider 使用 _stats
    if hasattr(container, "_stats") and isinstance(getattr(container, "_stats"), dict):
        stats = getattr(container, "_stats")
        bucket = stats.setdefault(alert_type, [])
        try:
            # list[dict[str, str]]
            bucket.append(payload)
        except Exception:
            # 如果历史结构不兼容，尽力写入
            stats[alert_type] = [payload]
        if len(stats.get(alert_type, [])) > 10:
            stats[alert_type] = stats[alert_type][-10:]


def collect_tgw_log_snippet(container: Any, max_lines: int = 10) -> Optional[str]:
    """根据 Provider 配置收集 TGW 日志片段。

    兼容两种 Provider：线程版与进程隔离版（均应包含 config.tgw_log_path）。
    """

    log_path = getattr(getattr(container, "config", None), "tgw_log_path", "") or ""
    if not log_path:
        return None

    path = Path(str(log_path)).expanduser()
    try:
        if not path.exists():
            return f"未找到 TGW 日志路径: {path}"

        if path.is_dir():
            candidates = [p for p in path.glob("*.log") if p.is_file()]
            if not candidates:
                return f"TGW 日志目录 {path} 未检测到 *.log 文件"
            target = max(candidates, key=lambda p: p.stat().st_mtime)
        else:
            target = path

        snippet_lines = read_tgw_tail_lines(target, max_lines=max_lines)
        snippet_text = "\n".join(snippet_lines) if snippet_lines else "(日志为空)"
        return f"{target}:\n{snippet_text}"
    except Exception as exc:  # noqa: BLE001
        logger.debug("读取 TGW 日志失败: {}", exc)
        return f"读取 TGW 日志失败: {exc}"


def read_tgw_tail_lines(file_path: Path, max_bytes: int = 4096, max_lines: int = 10) -> list[str]:
    """读取 TGW 日志文件尾部若干行，自动处理编码。"""
    try:
        size = file_path.stat().st_size
        with file_path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(size - max_bytes)
            data = handle.read()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("gbk", errors="ignore")
        lines = text.splitlines()
        return lines[-max_lines:]
    except Exception as exc:  # noqa: BLE001
        return [f"(读取失败: {exc})"]


async def trigger_alert(
    container: Any, alert_type: str, message: str, *, extras: Mapping[str, Any] | None = None
) -> None:
    """触发告警：
    - 拼接 TGW 日志片段
    - 记录日志与本地告警缓存
    - 通知 ProviderHealthMonitor
    """

    try:
        snippet = collect_tgw_log_snippet(container, max_lines=10)
        final_message = f"{message}\n--- TGW log snippet ---\n{snippet}" if snippet else message
        logger.critical("[ALERT][{}] {}", alert_type, final_message, metadata=dict(extras or {}))

        _append_alert_bucket(container, alert_type, final_message)

        # 统一接入健康监控
        from core.infrastructure.monitoring.provider_health import get_monitor

        monitor = get_monitor()
        if alert_type in {"error", "SDK_EXIT", "PROCESS_CRASH"}:
            monitor.record_error("amazingdata", alert_type, final_message)

        severity = "high" if alert_type in {"SDK_EXIT", "PROCESS_CRASH", "error"} else "medium"
        monitor._trigger_alert(
            "ERROR" if severity == "high" else "WARNING",
            "amazingdata",
            final_message,
            alert_type,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to trigger alert: {}", exc)


__all__ = [
    "trigger_alert",
    "collect_tgw_log_snippet",
    "read_tgw_tail_lines",
]
