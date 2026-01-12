"""
日志管理 API 路由
"""

import asyncio
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, cast

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from loguru import logger

try:
    from core.observability.logger import logger_manager as _imported_logger_manager
except Exception:  # pragma: no cover - fallback when logging is unavailable
    _imported_logger_manager = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - typing only
    from core.observability.logger import LoggerManager


logger_manager: Optional["LoggerManager"] = cast(
    Optional["LoggerManager"], _imported_logger_manager
)


router = APIRouter()


def _resolve_log_directories() -> List[Path]:
    """Return candidate log directories in preferred order."""

    candidates: List[Path] = []

    if logger_manager is not None:
        try:
            manager_path = Path(logger_manager.log_path)
            candidates.append(manager_path)
        except Exception as exc:
            logger.opt(exception=exc).debug("无法解析 logger_manager 日志目录")

    candidates.extend([Path("data/logs"), Path("logs")])

    unique: List[Path] = []
    for directory in candidates:
        if directory not in unique:
            unique.append(directory)

    return unique


def _existing_log_directories() -> Iterable[Path]:
    """Yield log directories that currently exist."""

    for directory in _resolve_log_directories():
        if directory.exists():
            yield directory


def _find_log_file(filename: str) -> Optional[Path]:
    """Locate a log file within the known directories."""

    for directory in _existing_log_directories():
        candidate = directory / filename
        if candidate.exists() and candidate.is_file():
            return candidate

    return None


class LogTail:
    """日志文件尾部读取器"""

    def __init__(self, file_path: Path, lines: int = 100):
        self.file_path = file_path
        self.lines = lines
        self._file = None
        self._position = 0

    def __enter__(self):
        self._file = open(self.file_path, "r", encoding="utf-8")
        # 移动到文件末尾
        self._file.seek(0, 2)
        self._position = self._file.tell()

        # 读取最后N行
        self._file.seek(0)
        lines = deque(self._file, self.lines)
        self._file.seek(self._position)

        return lines

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()

    def get_new_lines(self) -> List[str]:
        """获取新增的日志行"""
        if not self._file:
            return []

        self._file.tell()
        new_lines = []

        line = self._file.readline()
        while line:
            new_lines.append(line.strip())
            line = self._file.readline()

        self._position = self._file.tell()
        return new_lines


def parse_log_line(line: str, line_id: int) -> Optional[Dict[str, Any]]:
    """解析日志行"""
    if not line.strip():
        return None

    # 解析Spring Boot风格的日志格式
    # 时间 | 级别 | 进程信息 | 文件位置 | 服务 | 消息
    parts = line.split(" | ")
    if len(parts) >= 6:
        try:
            return {
                "id": line_id,
                "timestamp": parts[0].strip(),
                "level": parts[1].strip(),
                "process_info": parts[2].strip(),
                "location": parts[3].strip(),
                "service": parts[4].strip(),
                "message": " | ".join(parts[5:]),
            }
        except Exception as exc:
            logger.opt(exception=exc).debug("解析结构化日志行失败")

    # 如果无法解析，返回原始行
    return {
        "id": line_id,
        "timestamp": datetime.now().isoformat(),
        "level": "INFO",
        "message": line,
    }


def get_latest_log_file() -> Optional[Path]:
    """��ȡ���µ���־�ļ�"""

    for log_dir in _existing_log_directories():
        log_files = [file for file in log_dir.glob("deepsearch_*.log") if file.is_file()]

        if not log_files:
            log_files = [file for file in log_dir.glob("*.log") if file.is_file()]

        if log_files:
            return max(log_files, key=lambda f: f.stat().st_mtime)

    return None


@router.get("/stream")
async def stream_logs(
    lines: int = 100, level: str = "INFO", follow: bool = True
) -> StreamingResponse:
    """
    流式传输日志。

    Args:
        lines: 初始返回的日志行数
        level: 日志级别过滤
        follow: 是否持续跟踪新日志

    Returns:
        SSE格式的日志流
    """
    log_file = get_latest_log_file()
    if not log_file:
        raise HTTPException(status_code=404, detail="未找到日志文件")

    async def generate():
        """生成SSE事件流"""
        try:
            # 首先发送历史日志
            with LogTail(log_file, lines) as initial_lines:
                line_id = 0
                for line in initial_lines:
                    log_entry = parse_log_line(line, line_id)
                    if log_entry:
                        yield f"data: {log_entry}\n\n"
                        line_id += 1

            # 如果需要跟踪新日志
            if follow:
                f = None
                try:
                    f = open(log_file, "r", encoding="utf-8")
                    # 移动到文件末尾
                    f.seek(0, 2)

                    while True:
                        line = f.readline()
                        if line:
                            log_entry = parse_log_line(line, line_id)
                            if log_entry:
                                yield f"data: {log_entry}\n\n"
                                line_id += 1
                        else:
                            # 没有新行，等待一下
                            await asyncio.sleep(0.5)
                finally:
                    if f:
                        f.close()

        except asyncio.CancelledError:
            # 客户端断开连接
            pass
        except Exception as e:
            logger.error(f"日志流错误: {e}")
            yield f"event: error\ndata: {{'error': '{str(e)}'}}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用nginx缓冲
        },
    )


@router.websocket("/ws")
async def websocket_logs(websocket: WebSocket):
    """
    WebSocket日志流。

    实时推送新的日志条目到客户端。
    """
    await websocket.accept()

    log_file = get_latest_log_file()
    if not log_file:
        await websocket.send_json({"type": "error", "message": "未找到日志文件"})
        await websocket.close()
        return

    try:
        line_id = 0

        # 发送初始日志
        with LogTail(log_file, 100) as initial_lines:
            logs = []
            for line in initial_lines:
                log_entry = parse_log_line(line, line_id)
                if log_entry:
                    logs.append(log_entry)
                    line_id += 1

            if logs:
                await websocket.send_json({"type": "initial", "logs": logs})

        # 持续监控新日志
        with open(log_file, "r", encoding="utf-8") as f:
            f.seek(0, 2)  # 移动到文件末尾

            while True:
                # 检查客户端消息（心跳等）
                try:
                    message = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                    if message == "ping":
                        await websocket.send_text("pong")
                except asyncio.TimeoutError:
                    pass

                # 读取新日志行
                line = f.readline()
                if line:
                    log_entry = parse_log_line(line, line_id)
                    if log_entry:
                        await websocket.send_json({"type": "update", "log": log_entry})
                        line_id += 1
                else:
                    await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        logger.debug("日志WebSocket连接已断开")
    except Exception as e:
        logger.error(f"日志WebSocket错误: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception as exc:
            logger.opt(exception=exc).debug("向日志 WebSocket 发送错误消息失败")


@router.get("/files")
async def list_log_files() -> Dict[str, Any]:
    """
    列举所有可用的日志文件

    Returns:
        日志文件列表
    """
    files: List[Dict[str, Any]] = []
    existing_dirs = list(_existing_log_directories())

    for log_dir in existing_dirs:
        for log_file in log_dir.glob("*.log"):
            if not log_file.is_file():
                continue

            try:
                stat_result = log_file.stat()
            except FileNotFoundError:
                continue

            files.append(
                {
                    "name": log_file.name,
                    "path": str(log_file),
                    "size": stat_result.st_size,
                    "modified": datetime.fromtimestamp(stat_result.st_mtime).isoformat(),
                    "created": datetime.fromtimestamp(stat_result.st_ctime).isoformat(),
                }
            )

    if not files:
        return {"status": "error", "message": "日志目录不存在", "files": []}

    files.sort(key=lambda item: item["modified"], reverse=True)

    return {
        "status": "success",
        "log_dir": str(existing_dirs[0]) if existing_dirs else "",
        "files": files,
        "total": len(files),
    }


@router.get("/download/{filename}")
async def download_log_file(filename: str) -> StreamingResponse:
    """
    下载指定的日志文件。

    Args:
        filename: 日志文件名

    Returns:
        文件流响应
    """
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="非法的日志文件名")

    log_file = _find_log_file(safe_name)

    if not log_file:
        raise HTTPException(status_code=404, detail="日志文件不存在")

    def iterfile():
        with open(log_file, "rb") as f:
            while chunk := f.read(65536):  # 64KB chunks
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={safe_name}"},
    )
