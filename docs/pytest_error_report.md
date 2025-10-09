# Pytest 失败报告

## 执行命令

- `pytest`

## 报错信息摘要

- `pytest: error: unrecognized arguments: --cov=deepsearch --cov-report=term-missing --cov-report=html:htmlcov --cov-report=xml --cov-config=.coveragerc --benchmark-disable`
- `inifile: /workspace/deepsearch/pytest.ini`
- `rootdir: /workspace/deepsearch`

## 初步分析

当前环境缺少对 `pytest-cov` 与 `pytest-benchmark` 等附加插件的支持，导致 pytest 无法识别在 `pytest.ini` 中声明的相关命令行参数，应先安装这些插件或调整配置后再重试。
