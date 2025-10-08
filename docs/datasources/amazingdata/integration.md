# AmazingData 数据源集成说明

> 更新时间：2025-10-10  
> 适用版本：Python 3.13 / DeepSearch 主干  
> 参考资料：`AmazingData_API.md`（2025-09-11，V1.0.8）  
> 维护人：DeepSearch 基础设施组

## 1. 当前定位
- AmazingData 是 **默认** 在生产环境启用的数据源，其它实现（如 AkShare、QMT）默认关闭，当 AmazingData 不可用或缺少所需数据时，可按流程启用 AkShare。
- 系统优先使用 `amazingdata_optimized.py` 的单进程实现；仅在兼容旧版 SDK 或隔离账号时启用进程池方案。
- 所有外部调用都必须经过 `AmazingDataSafeWrapper`，以统一处理登录重试、熔断与告警。
- WebUI、CLI 与 FastAPI 均通过 `DataSourceManager` 间接访问 provider，确保配置与运行状态一致。

## 2. 目录结构
```
deepsearch/
├── infrastructure/providers/
│   ├── implementations/amazingdata/
│   │   ├── amazingdata.py               # SDK 包装与核心实现
│   │   ├── amazingdata_optimized.py     # 默认单进程实现
│   │   ├── amazingdata_safe_wrapper.py  # 登录重试、熔断、降级控制
│   │   ├── amazingdata_process_pool.py  # 可选：多进程隔离
│   │   ├── amazingdata_process_proxy.py # 进程间通信代理
│   │   ├── _sdk_loader.py               # SDK 动态加载与版本探测
│   │   └── py39_worker.py               # 兼容旧版 SDK 的子进程入口
│   ├── managers/data_source_manager.py  # 统一数据源编排入口
│   ├── factory.py / registry.py         # Provider 构造与注册
│   └── interfaces/                      # 基础协议与能力枚举
├── webui/api/endpoints/datasource/      # 数据源管理 API（健康检测、保存配置）
├── webui/api/endpoints/amazingdata/     # 行情、历史、财务等业务接口
└── config/settings.<env>.yaml           # 环境配置（仅保留 amazingdata 段）
```

## 3. 配置要点
`settings.<env>.yaml` 中的关键字段：
```yaml
data_sources:
  providers:
    amazingdata:
      enabled: true
      priority: 1
      config:
        connection:
          username: your_username
          password: your_password
          host: 101.230.159.234
          port: 8600
          backup_hosts:
            - 140.206.44.234:8600
        retry:
          max_attempts: 3
          backoff: 5s
        cache:
          enabled: true
          ttl: 300
        isolation:
          process_pool:
            enabled: false
```
> 说明：示例文件仅提供占位符，真实凭据请放在本地安全存储中；提交代码前务必执行敏感词自检。

## 4. 调用链路
1. 入口（WebUI、CLI 或服务）通过 `DataSourceManager` 请求数据源能力。
2. `DataSourceManager` 根据配置解析 `amazingdata` 段并调用 `factory.create_data_provider()`。
3. 生成的 provider 由 `AmazingDataSafeWrapper` 包装，处理登录、重试与熔断逻辑。
4. 默认情况下直接调用 `amazingdata_optimized.py`；若配置启用进程池，则委派给 `AmazingDataProcessPool`。
5. 调用结果写入指标与日志：耗时、错误码、重试统计等都会通过 `observability` 输出。

## 5. WebUI & API
- 页面路径：`/system/config/data-source`
- 核心文件：
  - 前端：`webui/frontend/src/pages/SystemConfig/DataSourceConfig.tsx`
  - 后端：`webui/api/endpoints/datasource/datasource_management_api.py`
- 业务接口示例：
  - `GET /api/datasource/list`
  - `POST /api/datasource/test`
  - `GET /api/amazingdata/realtime/snapshot`
  - `GET /api/amazingdata/history/kline`

## 6. 稳定性措施
- **熔断**：连续失败达到阈值时自动阻断调用，并在 `logs/datasource/` 及通知渠道中记录事件。
- **降级**：当 SDK 加载失败时启用降级模式（只返回缓存或静态占位数据），相关逻辑集中在 `amazingdata_safe_wrapper.py`。
- **进程池（可选）**：在配置开启时，`AmazingDataProcessPool` 为不同账号或实验环境维护独立子进程，降低互相影响的风险。
- **监控**：`observability.metrics` 暴露登录成功率、重试次数、调用耗时；CLI `uv run python -m deepsearch.cli debug datasource status` 可查看实时状态。

## 7. 回归与诊断
- 单元测试：`tests/unit/infrastructure/providers/implementations/test_amazingdata_*.py`
- 集成测试：`tests/integration/amazingdata/`（覆盖登录、服务器可用性、降级流程）
- 快速脚本：`python tools/quick_datasource_test.py`
- 发布前建议执行：
  ```bash
  python scripts/run_all_tests.py --quick
  uv run pytest tests/integration/amazingdata -n auto
  ```

## 8. 维护指引
1. 新增或调整接口时，必须同步更新 `docs/api/` 系列文档并运行 `python tools/generate_api_documentation.py`。
2. 若启用进程池或其它实验特性，请在 PR 描述与 `docs/operations/runbooks/` 中备注原因及回滚方案。
3. AmazingData SDK 升级前先在隔离环境验证，确认 `_sdk_loader.py` 能正确识别版本再推广。
4. 所有改动需更新本目录的对应文档，并在 `docs/overview/document_index.md` 与 `docs/modules/README.md` 中保持索引一致。

## 9. 相关文档
- [setup.md](./setup.md)：账号、接入点、配置模板与验证流程。
- [api_guide.md](./api_guide.md)：缓存策略、错误处理与订阅模式说明。
- [resilience_strategy.md](./resilience_strategy.md) / [amazingdata_degraded_mode.md](./amazingdata_degraded_mode.md)：弹性、降级与恢复策略。
- [amazingdata_py39_bridge_plan.md](./amazingdata_py39_bridge_plan.md)：Python 3.9 Worker 隔离部署参考。

---
历史方案与淘汰实现请参考 `docs/archive/datasources/`。
