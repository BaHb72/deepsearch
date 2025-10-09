# mypy整改计划

## 并行子任务进展

### 3. WebUI API 与运行配置

- **进度回顾（2025-10-08）**：完成 `ServerManager.create_server_config` 显式传参与 `WebServerConfig` 覆盖项梳理，新增 AmazingData 订阅接口统一响应构造工具并增强 `dataframe_to_dict` 的 None 处理，成功通过 `mypy --follow-imports=skip deepsearch/webui` 自检。
- **建议命令**：`.\.venv\Scripts\python.exe -m mypy --follow-imports=skip deepsearch/webui`
