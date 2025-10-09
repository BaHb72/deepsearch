"""AI 操作日志记录模块的单元测试"""

import pytest

from deepsearch.observability.logging.ai_operation_logger import (
    AIOperationLogger,
    AIOperationStatus,
)


def test_ai_operation_logger_records_full_flow(tmp_path):
    """验证启动、进度与完成记录的完整流程"""

    logger = AIOperationLogger(log_dir=tmp_path, daily_rotation=False)
    operation_id = logger.start_operation(
        "测试 AI 任务",
        agent="planner",
        metadata={"priority": "high"},
    )

    logger.log_progress(
        operation_id,
        progress=0.45,
        step="fetch-data",
        message="拉取行情数据",
        metadata={"batch": 1},
    )
    logger.complete_operation(
        operation_id,
        message="任务执行完毕",
        metadata={"result": "ok"},
    )

    snapshots = logger.list_operations()
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot["operation_id"] == operation_id
    assert snapshot["status"] == AIOperationStatus.COMPLETED.value
    assert snapshot["progress"] == 100.0
    assert snapshot["current_step"] == "fetch-data"
    assert snapshot["metadata"]["priority"] == "high"
    assert snapshot["metadata"]["result"] == "ok"

    events = logger.get_recent_events()
    assert [event["event"] for event in events] == ["start", "progress", "complete"]
    assert events[1]["progress"] == pytest.approx(45.0)
    assert events[1]["metadata"]["batch"] == 1

    history = logger.load_history()
    assert len(history) == 3
    assert history[-1]["message"] == "任务执行完毕"


def test_progress_normalization_and_failure(tmp_path):
    """进度归一化与失败记录"""

    logger = AIOperationLogger(log_dir=tmp_path, daily_rotation=False)
    operation_id = logger.start_operation("测试归一化")

    logger.log_progress(operation_id, progress=0.2)
    logger.log_progress(operation_id, progress=120)
    logger.fail_operation(operation_id, error="timeout", message="执行超时")

    snapshot = logger.get_operation(operation_id)
    assert snapshot is not None
    assert snapshot["status"] == AIOperationStatus.FAILED.value
    assert snapshot["progress"] == pytest.approx(100.0)
    assert snapshot["metadata"]["error"] == "timeout"

    events = logger.get_recent_events()
    assert len(events) == 4
    assert events[-1]["event"] == "fail"
    assert events[1]["progress"] == pytest.approx(20.0)
    assert events[2]["progress"] == pytest.approx(100.0)

    limited = logger.load_history(limit=2)
    assert len(limited) == 2
    assert [record["event"] for record in limited] == ["progress", "fail"]


def test_duplicate_operation_id_not_allowed(tmp_path):
    """重复的操作编号应当被阻止"""

    logger = AIOperationLogger(log_dir=tmp_path, daily_rotation=False)
    operation_id = "fixed-id"
    logger.start_operation("任务一", operation_id=operation_id)

    with pytest.raises(ValueError):
        logger.start_operation("任务二", operation_id=operation_id)

    assert logger.get_operation(operation_id)["goal"] == "任务一"
