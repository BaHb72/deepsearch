# pytest 测试状态

- 执行命令：`uv run pytest tests/test_data_sources.py tests/test_database.py tests/test_market_data.py tests/test_system.py tests/webui/test_api_endpoints.py -q`
- 结果：78 项通过，3 项跳过，0 失败（包含 webui 与系统相关回归场景）。
- 报告时间：2025-10-12

后续如需覆盖其余模块，请在运行前清理 `data_source_test_report.txt` 等测试产物。
