# Pytest 失败报告

## 执行命令

1. `pip install pytest-cov pytest-benchmark`
2. `pytest`

## 报错信息摘要

### 依赖安装前

- `pytest: error: unrecognized arguments: --cov=deepsearch --cov-report=term-missing --cov-report=html:htmlcov --cov-report=xml --cov-config=.coveragerc --benchmark-disable`
- `inifile: /workspace/deepsearch/pytest.ini`
- `rootdir: /workspace/deepsearch`

### 依赖安装后

- `ModuleNotFoundError: No module named 'fastapi'`
- `ModuleNotFoundError: No module named 'pandas'`
- `ModuleNotFoundError: No module named 'loguru'`
- `ModuleNotFoundError: No module named 'pydantic'`
- `ModuleNotFoundError: No module named 'redis'`
- `ModuleNotFoundError: No module named 'psutil'`
- `ModuleNotFoundError: No module named 'yaml'`
- `PytestConfigWarning: Unknown config option: asyncio_mode`

## 初步分析

### 2024-XX-XX 更新

在当前容器中补充安装 `pytest-cov` 与 `pytest-benchmark` 后，pytest 已能正确识别 `pytest.ini` 中配置的覆盖率与基准测试参数。
随后执行 `pytest`，收集阶段仍因大量运行时依赖缺失而失败，典型报错包括：

- `ModuleNotFoundError: No module named 'fastapi'`
- `ModuleNotFoundError: No module named 'pandas'`
- `ModuleNotFoundError: No module named 'loguru'`
- `ModuleNotFoundError: No module named 'pydantic'`
- `ModuleNotFoundError: No module named 'redis'`
- `ModuleNotFoundError: No module named 'psutil'`
- `ModuleNotFoundError: No module named 'yaml'`

上述错误覆盖了 Web API、数据源适配器、监控与基础设施等多个测试模块，说明当前环境尚未安装项目运行所需的核心第三方库。

### 处理建议

1. 按照 `requirements.txt`、`requirements-amazingdata.txt` 及相关文档补齐依赖（如 `fastapi`、`pandas`、`loguru`、`pydantic`、`redis`、`psutil`、`PyYAML` 等）。
2. 重新执行 `pytest`，确认收集阶段能够顺利完成，再逐步分析后续可能出现的断言或运行时失败。
