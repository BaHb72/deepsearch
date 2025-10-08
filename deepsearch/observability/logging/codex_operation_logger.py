"""
Codex 操作日志模块

用于记录 Codex 代理在仓库中的实际操作过程，便于回溯和分析。
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

_DEFAULT_HISTORY_LIMIT = 1000


def _utcnow() -> datetime:
    """返回当前 UTC 时间"""
    return datetime.now(timezone.utc)


class CodexOperationEventType(str, Enum):
    """Codex 操作事件类型"""

    SESSION_START = "session_start"
    SESSION_END = "session_end"
    COMMAND = "command"
    FILE_CHANGE = "file_change"
    TEST = "test"
    NOTE = "note"


class CodexSessionStatus(str, Enum):
    """Codex 会话状态"""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CodexOperationLogEntry:
    """Codex 操作日志条目"""

    session_id: str
    event: CodexOperationEventType
    goal: Optional[str] = None
    command: Optional[str] = None
    cwd: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: Optional[float] = None
    status: Optional[str] = None
    message: Optional[str] = None
    files: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    agent: Optional[str] = None
    created_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "event": self.event.value,
            "goal": self.goal,
            "command": self.command,
            "cwd": self.cwd,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "message": self.message,
            "files": list(self.files),
            "metadata": dict(self.metadata),
            "agent": self.agent,
            "timestamp": self.created_at.timestamp(),
            "datetime": self.created_at.isoformat(),
        }


@dataclass
class CodexSessionSnapshot:
    """Codex 会话快照"""

    session_id: str
    goal: str
    status: CodexSessionStatus = CodexSessionStatus.ACTIVE
    agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    operations_count: int = 0
    last_event: Optional[str] = None
    last_message: Optional[str] = None
    started_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "goal": self.goal,
            "status": self.status.value,
            "agent": self.agent,
            "metadata": dict(self.metadata),
            "operations_count": self.operations_count,
            "last_event": self.last_event,
            "last_message": self.last_message,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def touch(self) -> None:
        self.updated_at = _utcnow()


class CodexOperationLogger:
    """Codex 操作日志记录器"""

    def __init__(
        self,
        log_dir: Optional[Path | str] = None,
        *,
        history_size: int = _DEFAULT_HISTORY_LIMIT,
        file_prefix: str = "codex_operations",
        daily_rotation: bool = True,
    ) -> None:
        self.log_dir = Path(log_dir) if log_dir else Path("logs") / "codex_operations"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.history_size = max(1, history_size)
        self.file_prefix = file_prefix
        self.daily_rotation = daily_rotation

        self._lock = threading.RLock()
        self._history: Deque[CodexOperationLogEntry] = deque(maxlen=self.history_size)
        self._sessions: Dict[str, CodexSessionSnapshot] = {}
        self._current_file_key: Optional[str] = None
        self._current_file_path: Optional[Path] = None

    # --- 基础工具 ---
    def _build_file_key(self) -> str:
        if self.daily_rotation:
            return _utcnow().strftime("%Y%m%d")
        return "static"

    def _resolve_file_path(self, key: str) -> Path:
        filename = f"{self.file_prefix}_{key}.jsonl" if self.daily_rotation else f"{self.file_prefix}.jsonl"
        return self.log_dir / filename

    def _get_log_file_path(self) -> Path:
        key = self._build_file_key()
        if self._current_file_key != key or self._current_file_path is None:
            self._current_file_key = key
            self._current_file_path = self._resolve_file_path(key)
        return self._current_file_path

    def _persist_entry(
        self,
        entry: CodexOperationLogEntry,
        *,
        update_metadata: Optional[Dict[str, Any]] = None,
        update_status: Optional[CodexSessionStatus] = None,
        update_message: Optional[str] = None,
        increment_counter: bool = False,
    ) -> CodexSessionSnapshot:
        with self._lock:
            snapshot = self._sessions.get(entry.session_id)
            if snapshot is None:
                raise KeyError(f"会话 {entry.session_id} 不存在")

            if update_status is not None:
                snapshot.status = update_status
            if update_metadata:
                snapshot.metadata.update(update_metadata)
            if update_message is not None:
                snapshot.last_message = update_message
            if increment_counter:
                snapshot.operations_count += 1
            snapshot.last_event = entry.event.value
            snapshot.touch()

            log_file = self._get_log_file_path()
            payload = json.dumps(entry.to_dict(), ensure_ascii=False)
            with log_file.open("a", encoding="utf-8") as stream:
                stream.write(payload + "\n")
            self._history.append(entry)
            return snapshot

    @staticmethod
    def _normalize_duration(duration: Optional[float]) -> Optional[float]:
        if duration is None:
            return None
        try:
            value = float(duration)
        except (TypeError, ValueError) as exc:
            raise ValueError("duration 必须为数值") from exc
        if value < 0:
            return 0.0
        if value > 0 and value < 1:
            return round(value * 1000, 2)
        return round(value * 1000, 2)

    # --- 公共 API ---
    def start_session(
        self,
        goal: str,
        *,
        session_id: Optional[str] = None,
        agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not goal:
            raise ValueError("goal 不能为空")

        session_id = session_id or str(uuid.uuid4())
        metadata = dict(metadata or {})

        with self._lock:
            if session_id in self._sessions:
                raise ValueError(f"会话 {session_id} 已存在")
            snapshot = CodexSessionSnapshot(
                session_id=session_id,
                goal=goal,
                agent=agent,
                metadata=metadata.copy(),
                last_event=CodexOperationEventType.SESSION_START.value,
                last_message="会话启动",
            )
            self._sessions[session_id] = snapshot

        entry = CodexOperationLogEntry(
            session_id=session_id,
            event=CodexOperationEventType.SESSION_START,
            goal=goal,
            message="Codex 会话启动",
            metadata=metadata,
            agent=agent,
        )
        self._persist_entry(entry, update_metadata=metadata, update_message=entry.message)
        return session_id

    def log_command(
        self,
        session_id: str,
        command: str,
        *,
        exit_code: Optional[int] = None,
        duration: Optional[float] = None,
        cwd: Optional[str] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not command:
            raise ValueError("command 不能为空")

        metadata = dict(metadata or {})
        entry = CodexOperationLogEntry(
            session_id=session_id,
            event=CodexOperationEventType.COMMAND,
            command=command,
            cwd=cwd,
            exit_code=exit_code,
            duration_ms=self._normalize_duration(duration),
            status="success" if exit_code == 0 else "failed" if exit_code is not None else None,
            message=message,
            metadata=metadata,
        )
        self._persist_entry(
            entry,
            update_metadata=metadata,
            update_message=message,
            increment_counter=True,
        )

    def log_file_change(
        self,
        session_id: str,
        file_path: str,
        *,
        action: str = "modified",
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not file_path:
            raise ValueError("file_path 不能为空")

        change = {"path": file_path, "action": action}
        metadata = dict(metadata or {})
        entry = CodexOperationLogEntry(
            session_id=session_id,
            event=CodexOperationEventType.FILE_CHANGE,
            files=[change],
            message=message,
            metadata=metadata,
            status=action,
        )
        self._persist_entry(
            entry,
            update_metadata=metadata,
            update_message=message,
            increment_counter=True,
        )

    def log_test(
        self,
        session_id: str,
        command: str,
        *,
        status: str,
        duration: Optional[float] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not command:
            raise ValueError("command 不能为空")
        if not status:
            raise ValueError("status 不能为空")

        metadata = dict(metadata or {})
        entry = CodexOperationLogEntry(
            session_id=session_id,
            event=CodexOperationEventType.TEST,
            command=command,
            duration_ms=self._normalize_duration(duration),
            status=status,
            message=message,
            metadata=metadata,
        )
        self._persist_entry(
            entry,
            update_metadata=metadata,
            update_message=message,
            increment_counter=True,
        )

    def log_note(
        self,
        session_id: str,
        note: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not note:
            raise ValueError("note 不能为空")

        metadata = dict(metadata or {})
        entry = CodexOperationLogEntry(
            session_id=session_id,
            event=CodexOperationEventType.NOTE,
            message=note,
            metadata=metadata,
        )
        self._persist_entry(
            entry,
            update_metadata=metadata,
            update_message=note,
            increment_counter=True,
        )

    def end_session(
        self,
        session_id: str,
        *,
        status: CodexSessionStatus = CodexSessionStatus.COMPLETED,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        metadata = dict(metadata or {})
        entry = CodexOperationLogEntry(
            session_id=session_id,
            event=CodexOperationEventType.SESSION_END,
            status=status.value,
            message=message or "会话结束",
            metadata=metadata,
        )
        self._persist_entry(
            entry,
            update_status=status,
            update_metadata=metadata,
            update_message=entry.message,
        )

    def fail_session(
        self,
        session_id: str,
        *,
        error: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        metadata = dict(metadata or {})
        metadata.setdefault("error", error)
        self.end_session(
            session_id,
            status=CodexSessionStatus.FAILED,
            message=error,
            metadata=metadata,
        )

    # --- 查询能力 ---
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            snapshot = self._sessions.get(session_id)
            if snapshot is None:
                return None
            return snapshot.to_dict()

    def list_sessions(self) -> List[Dict[str, Any]]:
        with self._lock:
            sessions = list(self._sessions.values())
        sessions.sort(key=lambda item: item.started_at)
        return [session.to_dict() for session in sessions]

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
        """清空内存态，用于测试或调试"""
        with self._lock:
            self._history.clear()
            self._sessions.clear()
            self._current_file_key = None
            self._current_file_path = None


# 默认实例
codex_operation_logger = CodexOperationLogger()


def get_codex_operation_logger() -> CodexOperationLogger:
    """获取全局 Codex 操作日志记录器"""
    return codex_operation_logger
