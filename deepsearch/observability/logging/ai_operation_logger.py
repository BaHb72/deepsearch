"""
AI 操作日志模块

提供结构化记录，以追踪 AI 行为的目标、进度和结果，便于后续复盘。
"""

from __future__ import annotations

import json
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

_DEFAULT_HISTORY_LIMIT = 500


def _utcnow() -> datetime:
    """返回当前 UTC 时间"""
    return datetime.now(timezone.utc)


class AIOperationEventType(str, Enum):
    """AI 操作事件类型"""

    START = "start"
    PROGRESS = "progress"
    COMPLETE = "complete"
    FAIL = "fail"
    NOTE = "note"


class AIOperationStatus(str, Enum):
    """AI 操作状态枚举"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AIOperationLogEntry:
    """AI 操作日志条目"""

    operation_id: str
    event: AIOperationEventType
    goal: Optional[str] = None
    progress: Optional[float] = None
    status: Optional[str] = None
    message: Optional[str] = None
    step: Optional[str] = None
    agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        metadata = dict(self.metadata) if self.metadata else {}
        return {
            "operation_id": self.operation_id,
            "event": self.event.value,
            "goal": self.goal,
            "progress": self.progress,
            "status": self.status,
            "message": self.message,
            "step": self.step,
            "agent": self.agent,
            "metadata": metadata,
            "timestamp": self.created_at.timestamp(),
            "datetime": self.created_at.isoformat(),
        }


@dataclass
class OperationSnapshot:
    """AI 操作快照，便于快速查看当前状态"""

    operation_id: str
    goal: str
    status: AIOperationStatus = AIOperationStatus.RUNNING
    progress: float = 0.0
    agent: Optional[str] = None
    current_step: Optional[str] = None
    message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "goal": self.goal,
            "status": self.status.value,
            "progress": self.progress,
            "agent": self.agent,
            "current_step": self.current_step,
            "message": self.message,
            "metadata": dict(self.metadata),
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def touch(self) -> None:
        self.updated_at = _utcnow()


class AIOperationLogger:
    """AI 操作日志记录器"""

    def __init__(
        self,
        log_dir: Optional[Path | str] = None,
        *,
        history_size: int = _DEFAULT_HISTORY_LIMIT,
        file_prefix: str = "ai_operations",
        daily_rotation: bool = True,
    ) -> None:
        self.log_dir = Path(log_dir) if log_dir else Path("logs") / "ai_operations"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.history_size = max(1, history_size)
        self.file_prefix = file_prefix
        self.daily_rotation = daily_rotation

        self._lock = threading.RLock()
        self._history: Deque[AIOperationLogEntry] = deque(maxlen=self.history_size)
        self._snapshots: Dict[str, OperationSnapshot] = {}
        self._current_file_key: Optional[str] = None
        self._current_file_path: Optional[Path] = None

    # --- 内部工具 ---
    def _build_file_key(self) -> str:
        if self.daily_rotation:
            return _utcnow().strftime("%Y%m%d")
        return "static"

    def _resolve_file_path(self, key: str) -> Path:
        if self.daily_rotation:
            filename = f"{self.file_prefix}_{key}.jsonl"
        else:
            filename = f"{self.file_prefix}.jsonl"
        return self.log_dir / filename

    def _get_log_file_path(self) -> Path:
        key = self._build_file_key()
        if self._current_file_key != key or self._current_file_path is None:
            self._current_file_key = key
            self._current_file_path = self._resolve_file_path(key)
        return self._current_file_path

    @staticmethod
    def _normalize_progress(progress: Optional[float]) -> Optional[float]:
        if progress is None:
            return None
        try:
            value = float(progress)
        except (TypeError, ValueError) as exc:
            raise ValueError("progress 必须为数值类型") from exc

        if value <= 1.0:
            value *= 100.0
        value = max(0.0, min(value, 100.0))
        return round(value, 2)

    def _write_entry(self, entry: AIOperationLogEntry) -> None:
        with self._lock:
            log_file = self._get_log_file_path()
            payload = json.dumps(entry.to_dict(), ensure_ascii=False)
            with log_file.open("a", encoding="utf-8") as stream:
                stream.write(payload + "\n")
            self._history.append(entry)

    def _update_snapshot(
        self,
        operation_id: str,
        *,
        status: Optional[AIOperationStatus] = None,
        progress: Optional[float] = None,
        step: Optional[str] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        agent: Optional[str] = None,
    ) -> OperationSnapshot:
        with self._lock:
            snapshot = self._snapshots.get(operation_id)
            if snapshot is None:
                raise KeyError(f"操作 {operation_id} 不存在")

            if status is not None:
                snapshot.status = status
            if progress is not None:
                snapshot.progress = progress
            if step is not None:
                snapshot.current_step = step
            if message is not None:
                snapshot.message = message
            if metadata:
                snapshot.metadata.update(metadata)
            if agent is not None:
                snapshot.agent = agent
            snapshot.touch()
            return snapshot

    # --- 对外 API ---
    def start_operation(
        self,
        goal: str,
        *,
        operation_id: Optional[str] = None,
        agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not goal:
            raise ValueError("goal 不能为空")

        metadata = dict(metadata or {})
        operation_id = operation_id or str(uuid.uuid4())

        with self._lock:
            if operation_id in self._snapshots:
                raise ValueError(f"操作 {operation_id} 已存在")

            snapshot = OperationSnapshot(
                operation_id=operation_id,
                goal=goal,
                status=AIOperationStatus.RUNNING,
                progress=0.0,
                agent=agent,
                message="操作启动",
                metadata=metadata.copy(),
            )
            self._snapshots[operation_id] = snapshot

        entry = AIOperationLogEntry(
            operation_id=operation_id,
            event=AIOperationEventType.START,
            goal=goal,
            progress=0.0,
            status=AIOperationStatus.RUNNING.value,
            message="AI 操作启动",
            agent=agent,
            metadata=metadata,
        )
        self._write_entry(entry)
        return operation_id

    def log_progress(
        self,
        operation_id: str,
        *,
        progress: Optional[float] = None,
        step: Optional[str] = None,
        message: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        agent: Optional[str] = None,
    ) -> None:
        normalized = self._normalize_progress(progress)
        metadata = dict(metadata or {})

        snapshot = self._update_snapshot(
            operation_id,
            status=AIOperationStatus.RUNNING,
            progress=normalized if normalized is not None else None,
            step=step,
            message=message,
            metadata=metadata,
            agent=agent,
        )

        entry = AIOperationLogEntry(
            operation_id=operation_id,
            event=AIOperationEventType.PROGRESS,
            progress=normalized if normalized is not None else snapshot.progress,
            status=status or snapshot.status.value,
            message=message,
            step=step,
            agent=agent or snapshot.agent,
            metadata=metadata,
        )
        self._write_entry(entry)

    def complete_operation(
        self,
        operation_id: str,
        *,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        metadata = dict(metadata or {})

        snapshot = self._update_snapshot(
            operation_id,
            status=AIOperationStatus.COMPLETED,
            progress=100.0,
            message=message or "操作完成",
            metadata=metadata,
        )

        entry = AIOperationLogEntry(
            operation_id=operation_id,
            event=AIOperationEventType.COMPLETE,
            progress=100.0,
            status=AIOperationStatus.COMPLETED.value,
            message=message or snapshot.message,
            agent=snapshot.agent,
            metadata=metadata,
        )
        self._write_entry(entry)

    def fail_operation(
        self,
        operation_id: str,
        *,
        error: Optional[str] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        metadata = dict(metadata or {})
        if error:
            metadata.setdefault("error", error)

        snapshot = self._update_snapshot(
            operation_id,
            status=AIOperationStatus.FAILED,
            message=message or "操作失败",
            metadata=metadata,
        )

        entry = AIOperationLogEntry(
            operation_id=operation_id,
            event=AIOperationEventType.FAIL,
            progress=snapshot.progress,
            status=AIOperationStatus.FAILED.value,
            message=message or snapshot.message,
            agent=snapshot.agent,
            metadata=metadata,
        )
        self._write_entry(entry)

    def log_note(
        self,
        operation_id: str,
        note: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not note:
            raise ValueError("note 不能为空")

        metadata = dict(metadata or {})
        snapshot = self._update_snapshot(
            operation_id,
            metadata=metadata,
            message=note,
        )

        entry = AIOperationLogEntry(
            operation_id=operation_id,
            event=AIOperationEventType.NOTE,
            progress=snapshot.progress,
            status=snapshot.status.value,
            message=note,
            agent=snapshot.agent,
            metadata=metadata,
        )
        self._write_entry(entry)

    # --- 查询能力 ---
    def get_operation(self, operation_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            snapshot = self._snapshots.get(operation_id)
            if snapshot is None:
                return None
            return snapshot.to_dict()

    def list_operations(self) -> List[Dict[str, Any]]:
        with self._lock:
            snapshots = list(self._snapshots.values())
        snapshots.sort(key=lambda item: item.started_at)
        return [snapshot.to_dict() for snapshot in snapshots]

    def get_recent_events(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            events = list(self._history)
        if limit is not None and limit > 0:
            events = events[-limit:]
        return [entry.to_dict() for entry in events]

    def load_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if limit is not None and limit <= 0:
            return []

        files = sorted(self.log_dir.glob(f"{self.file_prefix}*.jsonl"))
        records: List[Dict[str, Any]] = []
        for path in files:
            with path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    records.append(record)
        if limit is not None:
            records = records[-limit:]
        return records

    def reset(self) -> None:
        """重置内存态，仅供测试或调试使用"""
        with self._lock:
            self._history.clear()
            self._snapshots.clear()


# 默认实例，供系统各处直接引用
ai_operation_logger = AIOperationLogger()


def get_ai_operation_logger() -> AIOperationLogger:
    """获取全局 AI 操作日志记录器"""
    return ai_operation_logger
