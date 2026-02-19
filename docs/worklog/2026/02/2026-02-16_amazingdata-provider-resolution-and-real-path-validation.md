# AmazingData: Provider 解析收口与真实链路可用性校验

> 日期: 2026-02-16
> 模块: amazingdata-api, provider, integration-test
> 类型: bugfix / validation

---

## 为什么要改

### 遇到的问题

`/api/amazingdata` 路由的 provider 获取逻辑存在“请求阶段二次构造”分支：

- 先从 `DataProviderFactory` 取 provider
- 若不是 `AmazingDataExtended`，就在请求中创建新的 `AmazingDataExtended` 并初始化

这与“统一主路径”目标冲突，并且在 AmazingData 单连接约束下会放大连接竞争风险。

### 现有方案的问题

原方案（A）的问题在于把“运行时 provider 类型差异”当作“需要重建本地直连实例”的触发条件，导致：

1. 绕过既有 Actor/代理路径
2. 引入重复登录和额外初始化成本
3. 增加行为不确定性（同一路由不同 provider 类型走不同主链）

---

## 尝试过的方案

### 方案 A：保留原逻辑，遇到非 Extended 就重建

**思路**: 强制把 provider 统一成 `AmazingDataExtended`，避免 endpoint 适配。

**问题**: 会在请求路径频繁触发初始化，破坏主路径收敛，并与单连接约束相冲突。

### 方案 B：复用工厂返回实例（最终采用）

**思路**: `get_amazingdata_provider()` 只做“获取与兜底错误”，不在请求期重建 provider。

**收益**: 主路径一致、连接状态可控、与后续容器化收敛方向一致。

---

## 最终方案

### 选择: 方案 B（复用实例，不在请求期重建）

**原因**:

1. 与 Provider 收敛路线一致（减少隐式分叉）
2. 减少重复初始化副作用
3. 便于后续把 AmazingData 路由整体迁到 `provider_deps + container`

### 关键改动

- `apps/api/api/endpoints/amazingdata/amazingdata_api.py`
  - `get_amazingdata_provider()` 改为直接复用工厂实例
  - 空实例返回 `503`
  - 保留 `HTTPException` 原状态码，不再误包 500
  - `login()` 回写缓存键统一为 `DataSourceType.AMAZINGDATA.value`
  - 修复 `BlockTradingRequest` 字段说明乱码
- `tests/unit/api/test_amazingdata_provider_resolution.py`
  - 验证已有 provider 不会被请求阶段重建
  - 验证空 provider 返回 503
- `packages/core/cli/main.py`
  - `check-amazingdata` 新增 distributed 模式下的 Dask Worker 可用性检查
- `tests/unit/cli/test_check_amazingdata_command.py`
  - 新增 distributed 模式无 Worker 时返回 failed 的单测
- `tests/integration/amazingdata/test_amazingdata_working.py`
  - 移除明文凭证，改为环境变量注入
- `packages/core/infrastructure/providers/implementations/amazingdata/config.py`
  - 修复配置合并优先级：`connection` 非空字段优先于顶层历史字段
- `scripts/start_windows_dask.ps1`
  - 重写为 ASCII-only，修复 powershell.exe (5.1) 解析失败
- `Dockerfile.dask`
  - 补齐 `packages/core/utils`
  - 配置目录改为完整复制 `packages/core/config/`

---

## 验证结果

1. `uv run --python ./.venv/Scripts/python.exe pytest tests/unit/api/test_amazingdata_provider_resolution.py tests/unit/cli/test_check_amazingdata_command.py -q`
   - 6 passed
2. `uv run --python ./.venv/Scripts/python.exe python -m core.cli.main check-amazingdata dev --timeout 2`
   - 配置加载、连接校验、TCP 连通性为 `ok`
   - 在无 Worker 时：`Dask Worker 可用性 = failed`，顶层状态为 `failed`
   - 启动本机 Scheduler+Worker 后：`Dask Worker 可用性 = ok`，顶层状态为 `warning`（仅 TGW 日志未配置）
3. 真实 smoke（非 mock）：
   - `get_amazingdata_provider()` 返回 `ActorWrapper`
   - `provider.get_calendar()` 成功返回 8585 条交易日历
4. Docker 路径现状：
   - 初始复现：`ModuleNotFoundError: core.utils` / `core.config.manager`
   - 已完成重建并验证闭环：
     - `docker compose build dask-scheduler`
     - `docker compose up -d dask-scheduler`
     - Windows Worker 重新连接后，真实 smoke 成功

## 补充进展（2026-02-16 夜间）

1. **巡检可观测性补齐（日志路径）**
   - 在 `packages/core/config/data_sources.yaml` 增加：
     - `amazingdata.connection.tgw_log_path: ./data/logs/datasource`
   - 结果：`uv run deepsearch check-amazingdata dev --timeout 2` 顶层状态由 `warning` 变为 `ok`。

2. **新增可选真实 API 探测入口（非 mock）**
   - `packages/core/cli/main.py` 的 `check-amazingdata` 新增参数：
     - `--probe-calendar/--no-probe-calendar`
     - `--probe-timeout`
     - `--probe-market`
     - `--probe-data-type`
   - 目的：将“端口可达”扩展为“业务方法可调用”的标准化探测能力。

3. **单测覆盖扩展**
   - `tests/unit/cli/test_check_amazingdata_command.py`
     - `test_check_amazingdata_probe_calendar_success`
     - `test_check_amazingdata_probe_calendar_failed_when_provider_unavailable`
   - 验证：相关 CLI 单测全部通过。

4. **新暴露问题（已回填 backlog）**
   - 在独立 CLI 进程触发 `--probe-calendar` 时，出现 Actor 链路偶发失败：
     - `Unable to contact Actor's worker`
     - `get_calendar` 超时（`TimeoutError`）
   - 说明：当前“真实探测能力”已具备，但“独立进程下稳定性”仍待治理。

---

## 非代码层面的实际意义

1. **运行一致性提升**：同一 API 不再因 provider 具体类型不同而走不同“隐式主链路”。
2. **风险可控**：减少重复登录和连接竞争，降低“偶现但难复现”故障概率。
3. **排障效率提升**：责任边界更清晰，遇到问题时能更快定位在配置、连接、还是调用层。
4. **协作成本下降**：把“临时兜底分支”收敛掉，团队后续不需要维护多套心智模型。

---

## 关键结论

> 在数据源场景里，真正稳定的不是“每次都新建一个能跑的实例”，而是“保证所有请求走同一条可观测、可治理、可回归验证的主路径”。
