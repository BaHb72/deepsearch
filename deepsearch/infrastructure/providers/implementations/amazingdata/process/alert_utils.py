"""Alert utilities for process-isolated AmazingData provider."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ..logging_utils import ProcessLoggerAdapter

logger = ProcessLoggerAdapter(action="process")

if TYPE_CHECKING:
    from ..amazingdata_process_adapter import AmazingDataProcessAdapter  # noqa: F401
    from .runtime import ProcessIsolatedAmazingDataProvider  # noqa: F401


async def trigger_alert(
    provider: "ProcessIsolatedAmazingDataProvider", alert_type: str, message: str
) -> None:
    """Emit alert via provider health monitor and record TGW snippet if available."""
    try:
        log_snippet = collect_tgw_log_snippet(provider, max_lines=10)
        final_message = (
            f"{message}\n--- TGW log snippet ---\n{log_snippet}" if log_snippet else message
        )
        logger.critical("[ALERT][{}] {}", alert_type, final_message)

        bucket = provider._alerts.setdefault(alert_type, [])
        bucket.append({"timestamp": datetime.now().isoformat(), "message": final_message})
        if len(bucket) > 10:
            provider._alerts[alert_type] = bucket[-10:]

        from deepsearch.infrastructure.monitoring.provider_health import get_monitor

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


def collect_tgw_log_snippet(
    provider: "ProcessIsolatedAmazingDataProvider", max_lines: int = 10
) -> Optional[str]:
    """Collect TGW log snippet based on provider configuration."""
    log_path = getattr(provider.config, "tgw_log_path", "") or ""
    if not log_path:
        return None

    path = Path(log_path).expanduser()
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
    """Read tail lines from TGW log file."""
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


__all__ = ["trigger_alert", "collect_tgw_log_snippet", "read_tgw_tail_lines"]
