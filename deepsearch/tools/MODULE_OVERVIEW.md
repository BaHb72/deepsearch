# 工具模块概览

## 模块定位

`deepsearch/tools` 收录运维、诊断类脚本，辅助分析日志和检测数据源连通性。工具通常以 CLI 形式提供，也可作为库函数复用在自动化流程中。

## 主要脚本

- `log_analyzer.py`：
    - `LogAnalyzer` 支持解析日志目录（默认 `./logs`），统计错误类型、性能瓶颈、组件活跃度。
    - 提供 CLI 子命令：`errors`、`performance`、`components`、`report`、`summary`，可输出 JSON 或控制台摘要。
    - 功能包括：汇总最近 N 小时的错误趋势、计算耗时分位数、识别慢操作、统计模块日志数量等。
- `datasource_diagnostics/connectivity_tester.py`：
    - `ConnectivityTester` 根据配置自动测试 AmazingData、QMT、Cloudflare、AkShare、数据库等数据源的网络连通性和认证状态。
    - 记录 TCP 连接耗时、认证结果、额外健康信息（如 Redis 可用性），并将结果导出到
      `data/monitoring/diagnostics/connectivity_test.json`。
    - 提供 `NetworkDiagnostics` 工具计算 DNS、TCP、Ping 等指标，可在调试时定位延迟瓶颈。
    - 可直接运行脚本获得终端报告，也可作为异步库在其他模块中调用 (`await tester.test_all_sources()`).

## 使用建议

- 在发现日志暴增或性能下降时运行 `python -m deepsearch.tools.log_analyzer report --log-dir data/logs` 生成报告。
- 部署或网络调整后执行 `python -m deepsearch.tools.datasource_diagnostics.connectivity_tester` 复核数据源可用性，并保留导出的
  JSON 供审计。

## 扩展方向

- 可在 `datasource_diagnostics` 下新增针对特定 provider 的压力测试或 API 响应校验脚本。
- `log_analyzer` 可继续扩展为支持 JSONL 格式或 Prometheus 指标输出，便于集成到流水线中。
