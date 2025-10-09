"""日志管理器格式化逻辑单元测试"""

from datetime import datetime
from types import SimpleNamespace

from deepsearch.observability.logger import logger_manager


def test_normalize_module_with_alias():
    """带有前缀的模块名应匹配中文别名"""

    result = logger_manager._normalize_module_name("deepsearch.core.runtime.engine_adapter")
    assert result == "运行时调度"


def test_normalize_module_token_translation():
    """英文 token 组合应被翻译为中文"""

    result = logger_manager._normalize_module_name("engine_context")
    assert result == "引擎·上下文"


def test_normalize_module_preserve_chinese():
    """中文模块名保持不变"""

    assert logger_manager._normalize_module_name("数据采集") == "数据采集"


def test_resolve_file_location_escape_stdin():
    """特殊路径应被安全转义"""

    record = {"file": SimpleNamespace(path="<stdin>")}
    assert logger_manager._resolve_file_location(record) == "[stdin]"


def test_format_console_uses_translated_module(tmp_path):
    """控制台格式串应包含中文模块与文件信息"""

    fake_file = tmp_path / "demo.py"
    fake_file.write_text("print('demo')\n", encoding="utf-8")

    record = {
        "time": datetime(2025, 1, 1, 8, 0, 0, 123000),
        "level": SimpleNamespace(name="INFO"),
        "process": SimpleNamespace(id=4321),
        "thread": SimpleNamespace(name="MainThread"),
        "line": 42,
        "message": "AkShare 接口日志",
        "extra": {"module": "akshare_direct"},
        "name": "deepsearch.infrastructure.providers.akshare",
        "file": SimpleNamespace(path=str(fake_file)),
    }

    formatted = logger_manager._format_console(record)

    assert "| 模块=AkShare·直连" in formatted
    assert "d.i.p.akshare:42" in formatted
    assert "文件=" not in formatted
    assert "demo.py:42" not in formatted
