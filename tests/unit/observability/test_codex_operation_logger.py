"""Codex 操作日志模块的单元测试"""

import pytest

from deepsearch.observability.logging.codex_operation_logger import (
    CodexOperationEventType,
    CodexOperationLogger,
    CodexSessionStatus,
)


def test_codex_operation_logger_full_flow(tmp_path):
    """验证 Codex 操作会话从启动到结束的完整记录"""

    logger = CodexOperationLogger(log_dir=tmp_path, daily_rotation=False)
    session_id = logger.start_session(
        "修复单测",
        agent="codex",
        metadata={"task": "unit"},
    )

    logger.log_command(
        session_id,
        command="git status",
        exit_code=0,
        duration=0.2,
        cwd="D:/repo",
        message="查看工作区状态",
    )
    logger.log_file_change(
        session_id,
        file_path="deepsearch/module.py",
        action="modified",
        message="更新逻辑",
    )
    logger.log_test(
        session_id,
        command="pytest tests/unit",
        status="passed",
        duration=1.5,
        message="测试通过",
    )
    logger.log_note(session_id, "准备提交补丁")
    logger.end_session(
        session_id,
        status=CodexSessionStatus.COMPLETED,
        message="全部完成",
    )

    snapshot = logger.get_session(session_id)
    assert snapshot is not None
    assert snapshot["status"] == CodexSessionStatus.COMPLETED.value
    assert snapshot["operations_count"] == 4
    assert snapshot["last_event"] == CodexOperationEventType.SESSION_END.value
    assert snapshot["last_message"] == "全部完成"

    events = logger.get_recent_events()
    assert [event["event"] for event in events] == [
        "session_start",
        "command",
        "file_change",
        "test",
        "note",
        "session_end",
    ]
    assert events[1]["duration_ms"] == pytest.approx(200.0)
    assert events[2]["files"][0]["path"] == "deepsearch/module.py"
    assert events[3]["status"] == "passed"

    history = logger.load_history()
    assert len(history) == 6
    assert history[-1]["message"] == "全部完成"


def test_codex_operation_logger_failure(tmp_path):
    """失败会话应记录失败状态与错误信息"""

    logger = CodexOperationLogger(log_dir=tmp_path, daily_rotation=False)
    session_id = logger.start_session("尝试执行命令")
    logger.log_command(session_id, command="uv run lint", exit_code=1, duration=0.05)

    logger.fail_session(session_id, error="命令执行失败", metadata={"step": "lint"})

    snapshot = logger.get_session(session_id)
    assert snapshot is not None
    assert snapshot["status"] == CodexSessionStatus.FAILED.value
    assert snapshot["metadata"]["error"] == "命令执行失败"

    events = logger.get_recent_events()
    assert len(events) == 3
    assert events[-1]["event"] == "session_end"
    assert events[-1]["status"] == CodexSessionStatus.FAILED.value
    assert events[-1]["metadata"]["error"] == "命令执行失败"

    limited = logger.load_history(limit=2)
    assert len(limited) == 2
    assert limited[-1]["event"] == "session_end"


def test_codex_duplicate_session_not_allowed(tmp_path):
    """重复会话编号应触发异常"""

    logger = CodexOperationLogger(log_dir=tmp_path, daily_rotation=False)
    session_id = "fixed-session"
    logger.start_session("任务一", session_id=session_id)

    with pytest.raises(ValueError):
        logger.start_session("任务二", session_id=session_id)

    assert logger.get_session(session_id)["goal"] == "任务一"
