# 实时行情板块解析/代码表缺失排障指引

> 适用于：`RealTimeMarketDataService` 提示 `_ensure_boards 存在未解析板块`、`AmazingData 股票代码表为空`、
`DataProviderError: SDK returned None` 等场景。

## 现象确认

- 应用日志中出现 `实时行情 _ensure_boards 存在未解析板块`，同一周期内伴随 `Boards still unresolved after refresh`。
- `providers` 模块日志提示 `BaseData.get_code_list` 调用失败，或最终回退至 `BaseData.get_hist_code_list` 仍返回空。
- 新增 #67545（2025-10-30 起）之后，可额外关注以下日志：
    - `AmazingData execute attempt=... context=...` / `AmazingData execute 失败`：显示子进程调用出错的具体参数。
    - `AmazingData 股票列表获取完成 branch=... count=...`：确认成功命中的调用分支与返回条数。
    - `AmazingData 登录失败/成功 datasource=...`：识别登录环节是否异常、耗时是否异常。

## 快速止血

1. 若仅个别板块受影响，可在调用方配置 `fallback_codes`（固定代码集合）暂时代替板块订阅，待排障后回退。
2. 如果怀疑 SDK 离线缓存过期，可将 `amazingdata` 进程重启并执行 `get_stock_list` 手工验证；需确保业务空窗期执行。
3. 当 AmazingData 服务端维护时段导致长时间空返回，可切换至配置中的备用数据源或启用缓存快照回放（若已配置）。

## 排查步骤

1. **登录状态确认**
    - 查看最新的 `AmazingData 登录失败/成功` 日志，确保最近一次登录成功且耗时在秒级。
    - 调用 CLI：`uv run python tools/check_amazingdata.py --health`（示例命令，以实际工具为准），确认连接、心跳正常。
2. **代码表获取链路**
    - 搜索 `AmazingData 股票列表获取完成`，记录 `branch` 与 `count`。`branch` 指示使用的接口；`count=0` 表示返回为空。
    - 若 `branch` 为 `BaseData.get_hist_code_list[...]`，说明已进入回退逻辑，应关注日志中打印的
      `security_type/start/end/is_local`。
3. **子进程调用异常定位**
    - 查看 `AmazingData execute 失败/可恢复错误`，定位失败接口与参数，常见问题包括 `security_type` 不合法、`is_local` 不被支持。
    - 对于同一错误重复出现，可在配置文件中校正 `security_type` 或补充 SDK 版本差异说明。
4. **板块解析结果验证**
    - 执行一次 `refresh_board_universe()`（可通过运维 CLI 或在 Web 管理界面触发），随后检查
      `Boards still unresolved after refresh` 是否消失。
    - 如依旧存在缺失，确认 `stock_list_fetcher` 是否返回包含 `board` 字段的数据，必要时查看本地缓存目录是否存在最新文件。
5. **数据补充**
    - 若 `normalize_stock_records` 后仍缺少板块字段，可触发 `AmazingData get_stock_list 补全板块信息` 日志对应路径，确认
      InfoData/BaseData 元数据是否可用。

## 日志与监控建议

- 将 `AmazingData execute 失败` 配置为告警，携带 `method` 与 `context` 便于值班人员快速定位。
- 建议对 `AmazingData 股票列表获取完成 count` 设置阈值报警（例如返回数量低于 1000 触发告警）。
- 结合 `RealTimeMarketDataService.ensure_subscription` 的 warning，关联最近一次 `branch` 信息，方便跨模块排查。

## 成功标准

- `AmazingData 股票列表获取完成` 日志返回 `count > 0`，且 `Boards still unresolved after refresh` 不再出现。
- 终端服务可以成功针对出现问题的板块返回实时数据。
- 若为临时止血措施（固定代码集合），记得在故障解除后复位配置。
