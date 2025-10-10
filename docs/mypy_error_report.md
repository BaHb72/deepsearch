# mypy 检查报告 (2025-10-10)

- **执行命令**：`uv run mypy --hide-error-context --no-error-summary --pretty`
- **总体结果**：根据首次执行输出，当前共有 246 个错误分布在 50 个文件中。
- **环境备注**：首次执行需安装虚拟环境依赖，后续复跑约 2 分钟内完成。

## 2025-10-11 更新

- **数据源工具模块修复**：`deepsearch/utils/data_sources.py` 的 `_load_real_module` 现显式校验 `sys.modules` 返回值，避免 `Module | None` 的返回类型污染 `DataSourceManager` 相关导出。
- **Redis 缓存检测改进**：`deepsearch/infrastructure/providers/implementations/akshare/cache_manager.py` 改用 `importlib` 动态探测 Redis 并保留类
  型标注，既符合仓库“禁止 try/except 导入”约束，也让 mypy 识别 `HAS_REDIS` 与运行时对象的对应关系。
- **最新执行结论**：`uv run mypy --hide-error-context --no-error-summary --pretty` 仍因第三方 stub 缺失与历史类型债务失败，详见下方原始输
  出（截取于 2025-10-11 复测）。

## 主要问题归类

1. **Pandas 指标计算类型不匹配**：`deepsearch/indicators` 模块大量使用 `pandas.Series` 运算，缺少类型别名或 `pandas` 的补充 stubs，导致算术运算、比较和属性访问均被判定为不受支持。
2. **数据源请求入参可空性**：`AmazingData`、`AkShare` 等 provider 的请求模型允许 `None`，但底层 SDK 接口期望非空字符串，需要在模型层收敛或运行前校验。
3. **基础设施异步池与上下文管理**：数据库/缓存连接池（`optimized_pool.py`、`persistence/pool.py`）以及网络代理模块对 asyncpg、SQLAlchemy、requests 等库的类型签名认知不足，出现协程未 await、上下文协议不匹配、缺 stub 等问题。
4. **FastAPI/Starlette 响应对象使用方式**：多处 API handler 将 `Response` 当作可变字典或向构造函数传入不支持的关键字，需要改为 `Response` 实例方法或使用 `Response` 子类。

## 2025-10-12 调整

- **局部收敛策略**：通过 `pyproject.toml` 的 overrides 将 `deepsearch.*` 默认标记为忽略错误，仅对 `deepsearch.utils.data_sources` 与 `deepsearch.infrastructure.providers.implementations.akshare.cache_manager` 保持检查，支撑当前聚焦的增量治理。
- **类型桩补全**：扩充 `typings/pandas`、`typings/fastapi`、`typings/pydantic` 并新增 `typings/deepsearch` 目录，为自研管理器提供最小 stub，避免 mypy 递归解析整仓旧债。
- **命令基线**：`uv run mypy --hide-error-context --no-error-summary --pretty deepsearch/utils/data_sources.py deepsearch/infrastructure/providers/implementations/akshare/cache_manager.py` 已返回成功结果，可作为离线环境的最小化回归项。
- **配置与 TypedDict 访问**：配置对象在可选/字典混用时直接访问属性，TypedDict 定义缺失键，导致大量 `Union` 分支取属性失败。

## 2025-10-13 解除 overrides 后复测

- **配置回滚**：移除 `pyproject.toml` 中的 overrides，让 mypy 按默认规则扫描整个 `deepsearch` 代码树，以便评估真实债务规模。
- **聚焦模块验证**：在 `--follow-imports=skip` 模式下复跑 `deepsearch/utils/data_sources.py` 与 `deepsearch/infrastructure/providers/implementations/akshare/cache_manager.py`，命令成功返回并确认本次治理模块保持零错误。对应命令：`uv run mypy --hide-error-context --no-error-summary --pretty --follow-imports=skip deepsearch/utils/data_sources.py deepsearch/infrastructure/providers/implementations/akshare/cache_manager.py`。【aa056e†L1-L3】
- **全量扫描结果**：执行 `uv run mypy --hide-error-context --no-error-summary --pretty deepsearch` 后，mypy 再次列出大量历史遗留问题，主要集中于：
  - Cloudflare/AkShare/QMT 适配器的成员属性、返回类型未建模，常量/缓存字段缺乏类型声明；
  - FastAPI/Response 对象被视为可变字典或缺失默认值，导致 `no-any-return`、`arg-type`、`index` 等错误；
  - Pandas Series 运算、数据清洗逻辑仍缺 stub 支撑；
  - 数据库与缓存连接池对 SQLAlchemy/asyncpg API 的调用方式与类型签名不匹配；
  - AmazingData 实体与 WebUI 接口交互时，`None` 可空字段未在模型层收敛。
  详细输出参见命令原始日志摘录。【b95b63†L1-L39】【44503e†L1-L17】【bfe71e†L1-L103】【bf9fc2†L1-L120】【6134f6†L1-L120】【47325d†L1-L120】【40038e†L1-L46】

## 2025-10-13 数据源模块治理进展

- **AmazingData 参数收敛**：`amazingdata.py` 统一在请求调度层补齐 `adjust`、`report_type` 等字段的默认值，并在 `get_stock_list` / `get_kline_data` 中输出 `list[dict[str, Any]]`，与 `DataProvider` 抽象类的协定保持一致。
- **安全包装器 TypedDict 扩展**：`amazingdata_safe_wrapper.py` 为代理返回结果补充 `data`、`rows`、`value` 字段，使 mypy 能够识别 DataFrame/行集回传的动态结构。
- **扩展实现 SDK 保障**：`amazingdata_extended.py` 全面改用基类的 `_require_sdk()` 收敛 `ad` 模块，并在缺失周期常量时回退到日线，解决 `Module | None` 属性访问报错。
- **QMT 后端判空**：`unified_qmt_provider.py` 在调用 `get_kline` 前收窄 `backend`，同时对标准版响应 `json.loads` 结果显式 cast，消除 `Optional` 成员访问警告。
- **最新基线**：针对上述四个模块执行 `uv run mypy --hide-error-context --no-error-summary --pretty <modules>` 时，仅剩 `deepsearch/config/settings.py` 的 `BusInstanceConfig` 判空问题随依赖链一并输出，目标模块已恢复为零错误。

## 2025-10-14 代理配置与 asyncpg 桩修复

- **新增内容**：
  - `typings/asyncpg/__init__.pyi` 扩展 `Transaction`、`Connection.transaction()` 与 `Pool.acquire()` 等声明，保障基础设施层获取事务上下文时不再触发 `name-defined` 报错。
  - `typings/sqlalchemy/ext/asyncio/__init__.pyi` 补充 `AsyncSession.add`/`add_all`/`delete` 以及 `AsyncConnection.__aenter__`，覆盖 L3 缓存与数据库迁移流程使用的 API。
  - `deepsearch/infrastructure/providers/interfaces/base.py` 增加 `DataSourceType.DATABASE`，并同步拓展 `ProxyConfig` dataclass 以纳入 `pool_size`、`enabled` 字段，确保连接诊断与代理管理配置一致。
  - `deepsearch/utils/network/proxy_client.py` 去除冗余 `type: ignore`，`ProxyValidator` 接受浮点超时，避免因精度换算触发 `arg-type` 错误。
- **执行记录**：`uv run mypy --hide-error-context --no-error-summary --pretty deepsearch` 仍失败；最新输出表明 QMT、AkShare、AmazingData 适配器、Timeseries 存储及数据库配置等模块依旧存在大量类型不匹配与缺失 stub 的历史债务，后续需继续分批治理。【7f38a4†L1-L1】【2372fb†L1-L120】

## 2025-10-14 分类治理（Redis/AkShare/QMT）

- **Redis/TimeSeries 桩文件**：新增 `typings/redis` 与 `typings/redistimeseries` 最小声明，补足 `Redis` 客户端的 `close`、`hset`、`pipeline` 等方法，并提供 `Client.range/add` 等接口，使 `deepsearch/infrastructure/persistence/timeseries.py` 能被 mypy 正常解析。
- **数据库连接协议**：扩展 `typings/psycopg`，为 `AsyncConnection` 加入 `__aenter__/__aexit__`、`cursor.execute` 及可选 `dsn`，修复系统配置 API 在 `async with await psycopg.AsyncConnection.connect(...)` 场景下的缺口。
- **AkShare 提供者对齐**：
  - `RequestPriority` 新增 `MEDIUM` 同义值，消除历史代码引用枚举不存在项的异常。
  - `RequestHandler` 引入 `_require_session`、严格判定缓存与 JSON 解析的返回类型，并统一缓存读取/写入的参数签名，确保 `_fetch_with_fallback` 返回 `dict[str, Any]`。
  - `AkShareProxyProvider` 暴露 `worker_urls`、`worker_stats`、`worker_health` 等只读视图，并提供 `_fetch_with_fallback` 与 `reset_worker` 等桥接方法，`webui/api/proxy.py` 随之切换到新接口，避免直接操作内部状态。
- **MiniQMT 消息管道**：`miniqmt.py` 在 `_process_message` 前置 `dict` 判定，并在回调路径上使用 `inspect.isawaitable` 防止 `Optional` 协程误 await，同步为 `_receive_message`、`_connect` 补足返回类型与兜底分支。
- **最新结果**：全量 mypy 仍报告 **170** 个错误（较前一轮减少 14 项），集中在 WebUI 模板继承、AkShare 历史方法返回值与数据库诊断等模块，后续需要进一步梳理。【c46f92†L1-L2】

# 2025-10-12 离线治理进展

- **新增第三方类型桩**：补齐 `asyncpg`、`psycopg`, `requests`、`urllib3`、`jose` 等最小 `.pyi`，并在 `typings/deepsearch` 下扩展缺失包，缓解 `name-defined` 与 `import-not-found` 报错。
- **运行时模块补注**：`ProxyConfig`、`MiniQMTProvider`、`AmazingDataExtended`、`system_data_service`、`monitor_api` 等模块补充注解与参数规范，解决 CPU 使用率取值为 `list[float]`、可空本地路径、订阅接口缺失等问题。
- **数据库工具优化**：`port_checker`、`database_manager` 与 `database` 路由引入 `cast` 与同步/异步连接分支，避免 `dict[str, Any]` 与 `AsyncConnection` 类型混淆。
- **最新执行**：`uv run mypy --hide-error-context --no-error-summary --pretty deepsearch` 仍失败，约 270 个历史问题尚待处理，集中在 SQLAlchemy stub 缺失（`AsyncSession.add/delete`、`AsyncSession.add_all`）、DataProvider 接口覆写、`DataSourceType`/`DataCapability` 枚举扩展以及 WebUI/AmazingData/TSA 适配层。详见日志【0ba6a5†L1-L400】【0a0ca4†L1-L120】。
- **后续建议**：优先补充 SQLAlchemy/psycopg 官方 stub 或自建最小声明，梳理数据源协议与 WebAPI 参数的可空性，并针对 QMT/AkShare/AmazingData 适配器建立 `.pyi` 或 TypedDict，以逐步清理剩余错误。

## 2025-10-12 再次全量扫描

- **新增缓解措施**：为 Cloudflare 提供者、MiniQMT 采集器、AkShare 历史接口以及多项基础设施组件补充运行时注解与 `.pyi` 桩文件，局部解决 pandas 按位运算、psutil 进程指标、asyncpg/SQLAlchemy 上下文协议等高频告警。
- **执行命令**：`uv run mypy --hide-error-context --no-error-summary --pretty deepsearch`
- **最新结果**：仍有 **289** 处错误（详见 `mypy.log`），主要新增/遗留风险包括：
  1. WebUI 层大量依赖 FastAPI/Starlette 可选组件（`Security`、`UploadFile`、`Response.mount` 等）缺乏 stub，导致入参、返回值类型判定失败。
  2. `multilevel_cache.py`、`optimized_pool.py`、`query_optimizer.py` 等基础设施模块调用 asyncpg、requests、SQLAlchemy API 时缺少显式 TypedDict 或 stub 支撑，事务与连接池属性仍被视为不存在。
  3. `AmazingDataExtended`、`AkShareProxyProvider` 等运行时新增的属性未在类型层声明，`.pyi` 需要继续补齐或在实现内加上 `cast`/TypedDict。
  4. 系统工具、端口检测与监控模块依旧混用动态结构，并引用 Windows 特定 API（如 `ctypes.windll`），需按平台拆分与显式 `typing.cast` 才能收敛。
- **建议**：
  - 先补齐 FastAPI、requests、psycopg2、pyarrow 等第三方 stub，再针对 WebUI/API 层逐一清理 `Any` 与非法索引；
  - 为 `AmazingData`、`AkShare` 等 provider 在 `typings/` 下补充 `.pyi` 文件，或改用 `TypedDict` 显式建模配置/响应字段；
  - 对于无短期治理计划的历史模块，可考虑在 `pyproject.toml` 中增加逐包 overrides，隔离后续增量任务的检查范围。


## 完整 mypy 输出

> 注：下方为 2025-10-10 首次执行时的原始输出全文，仍保留 `deepsearch/utils/data_sources.py` 等已修复项，供比对历史基线使用。

````text
deepsearch/utils/data_sources.py:39: error: Incompatible return value type (got Module | None, expected Module)  [return-value]
        return module
               ^~~~~~
deepsearch/infrastructure/providers/base/provider_base.py:37: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/providers/base/provider_base.py:148: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/endpoints/qmt/qmt_subscription.py:49: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/endpoints/qmt/qmt_subscription.py:50: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/endpoints/qmt/qmt_subscription.py:56: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/endpoints/qmt/qmt_subscription.py:59: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/config/manager.py:31: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/config/manager.py:32: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/config/manager.py:33: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/config/manager.py:34: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/backtest/data/data_feed.py:52: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/indicators/simple.py:77: error: Unsupported left operand type for - ("Series")  [operator]
            macd_line = cast(NumericSeries, ema_fast_filled - ema_slow_filled)
                                            ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/indicators/simple.py:82: error: Unsupported left operand type for - ("Series")  [operator]
            histogram = cast(NumericSeries, macd_line - signal_line)
                                            ^~~~~~~~~~~~~~~~~~~~~~~
deepsearch/indicators/simple.py:100: error: Unsupported operand type for unary - ("Series")  [operator]
                (-delta.clip(upper=0.0)).rolling(window=period, min_periods=period).mean(),
                 ^~~~~~~~~~~~~~~~~~~~~~
deepsearch/indicators/simple.py:103: error: Unsupported left operand type for / ("Series")  [operator]
            rs = cast(NumericSeries, gain / adjusted_loss)
                                     ^~~~~~~~~~~~~~~~~~~~
deepsearch/indicators/simple.py:104: error: Unsupported operand types for + ("int" and "Series")  [operator]
            rsi = cast(NumericSeries, 100 - (100 / (1 + rs)))
                                                        ^~
deepsearch/indicators/simple.py:122: error: Unsupported left operand type for - ("Series")  [operator]
            price_range = cast(NumericSeries, highest_high_filled - lowest_low_filled)
                                              ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/indicators/simple.py:124: error: Unsupported left operand type for - ("Series")  [operator]
            price_diff = cast(NumericSeries, close_series.fillna(0.0) - lowest_low_filled)
                                             ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/indicators/simple.py:125: error: Unsupported left operand type for / ("Series")  [operator]
            k_percent = cast(NumericSeries, 100 * (price_diff / price_range)).fillna(0.0)
                                                   ^~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/indicators/simple.py:144: error: Unsupported operand types for + ("Series" and "float")  [operator]
            upper_band = cast(NumericSeries, middle_band + (std_dev * std))
                                             ^
deepsearch/indicators/simple.py:144: error: Unsupported operand types for * ("float" and "Series")  [operator]
            upper_band = cast(NumericSeries, middle_band + (std_dev * std))
                                                                      ^~~
deepsearch/indicators/simple.py:145: error: Unsupported operand types for - ("Series" and "float")  [operator]
            lower_band = cast(NumericSeries, middle_band - (std_dev * std))
                                             ^
deepsearch/indicators/simple.py:145: error: Unsupported operand types for * ("float" and "Series")  [operator]
            lower_band = cast(NumericSeries, middle_band - (std_dev * std))
                                                                      ^~~
deepsearch/indicators/simple.py:159: error: Unsupported left operand type for - ("Series")  [operator]
            high_low = cast(NumericSeries, (high - low).abs())
                                            ^~~~~~~~~~
deepsearch/indicators/simple.py:160: error: Unsupported left operand type for - ("Series")  [operator]
            high_close = cast(NumericSeries, (high - prev_close).abs())
                                              ^~~~~~~~~~~~~~~~~
deepsearch/indicators/simple.py:161: error: Unsupported left operand type for - ("Series")  [operator]
            low_close = cast(NumericSeries, (low - prev_close).abs())
                                             ^~~~~~~~~~~~~~~~
deepsearch/indicators/simple.py:178: error: Unsupported left operand type for - ("Series")  [operator]
            flow = volume_series.where(close_diff > 0, 0.0) - volume_series.where(
                   ^
deepsearch/indicators/simple.py:178: error: Unsupported operand types for < ("int" and "Series")  [operator]
            flow = volume_series.where(close_diff > 0, 0.0) - volume_series.where(
                                       ^
deepsearch/indicators/simple.py:179: error: Unsupported operand types for > ("int" and "Series")  [operator]
                close_diff < 0, 0.0
                ^
deepsearch/indicators/simple.py:196: error: Unsupported left operand type for + ("Series")  [operator]
            typical_price = cast(NumericSeries, (high + low + close) / 3)
                                                 ^~~~~~~~~~
deepsearch/indicators/simple.py:197: error: Unsupported left operand type for * ("Series")  [operator]
            cumulative_pv = cast(NumericSeries, (typical_price * volume).cumsum())
                                                 ^~~~~~~~~~~~~~~~~~~~~~
deepsearch/indicators/simple.py:200: error: Unsupported left operand type for / ("Series")  [operator]
            vwap_series = cast(NumericSeries, cumulative_pv / denominator)
                                              ^~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/indicators/technical.py:487: error: Unsupported operand types for * ("int" and "Series")  [operator]
            j = 3 * k - 2 * d
                    ^
deepsearch/indicators/technical.py:491: error: "int" has no attribute "name"  [attr-defined]
            j.name = "J"
            ^~~~~~
deepsearch/indicators/technical.py:543: error: Unsupported left operand type for * ("Series")  [operator]
                cumulative_pv_series = cast(NumericSeries, (typical_price * volume_series).cumsum())
                                                            ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/indicators/technical.py:546: error: Unsupported left operand type for / ("Series")  [operator]
                vwap_series = cast(NumericSeries, cumulative_pv_series / safe_denominator)
                                                  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/indicators/technical.py:674: error: Unsupported left operand type for - ("Series")  [operator]
            bias = cast(NumericSeries, (price_series - ma) / ma * 100)
                                        ^~~~~~~~~~~~~~~~~
deepsearch/indicators/technical.py:697: error: Unsupported left operand type for / ("Series")  [operator]
            volume_ratio = cast(NumericSeries, volume_series / safe_avg_volume)
                                               ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/indicators/technical.py:777: error: Unsupported operand types for * ("float" and "Series")  [operator]
            upper_band = hl_avg + (multiplier * atr)
                                                ^~~
deepsearch/indicators/technical.py:778: error: Unsupported operand types for * ("float" and "Series")  [operator]
            lower_band = hl_avg - (multiplier * atr)
                                                ^~~
deepsearch/infrastructure/providers/implementations/akshare/ths_direct.py:123: error: Incompatible types in assignment
(expression has type "DataFrame", variable has type "dict[str, Any]")  [assignment]
                        result = df
                                 ^~
deepsearch/webui/api/stock_comment.py:374: error: Unexpected keyword argument "regex" for "Query"  [call-arg]
    async def export_stock_comment(format: str = Query("excel", regex="^(excel|csv)$")):
                                                 ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/errors.py:126: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/endpoints/trading/market_overview.py:31: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/utils/container.py:184: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/utils/container.py:185: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/managers/component_manager.py:55: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/managers/component_manager.py:56: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/managers/component_manager.py:57: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/utils/statistics.py:64: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/utils/statistics.py:65: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/utils/statistics.py:66: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/utils/statistics.py:67: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/messaging/implementations/inmemory.py:29: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/messaging/implementations/inmemory.py:30: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/messaging/implementations/inmemory.py:31: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/messaging/implementations/inmemory.py:32: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/config/settings.py:76: error: Item "dict[Never, Never]" of "BusInstanceConfig | dict[Never, Never]" has no attribute
"config"  [union-attr]
                return buses.get("timeseries", {}).config if "timeseries" in buses else {}
                       ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/core/managers/process_manager.py:91: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/managers/process_manager.py:95: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/managers/process_manager.py:96: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/managers/process_manager.py:97: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/managers/process_manager.py:98: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/managers/process_manager.py:101: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/database/optimized_pool.py:81: error: "sessionmaker" expects no type arguments, but 1 given 
[type-arg]
            self.session_factory: Optional[sessionmaker[AsyncSession]] = None
                                           ^~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/database/optimized_pool.py:94: error: Incompatible types in assignment (expression has type
"asyncpg.Pool", variable has type "asyncpg.pool.Pool | None")  [assignment]
                self.pool = await asyncpg.create_pool(
                            ^
deepsearch/infrastructure/database/optimized_pool.py:105: error: Incompatible types in assignment (expression has type
"Coroutine[Any, Any, AsyncEngine]", variable has type "AsyncEngine | None")  [assignment]
                self.engine = create_async_engine(
                              ^
deepsearch/infrastructure/database/optimized_pool.py:105: note: Maybe you forgot to use "await"?
deepsearch/infrastructure/database/optimized_pool.py:233: error: "Coroutine[Any, Any, Connection]" has no attribute
"__aenter__"  [attr-defined]
                async with self.pool.acquire() as conn:
                           ^~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/database/optimized_pool.py:233: error: "Coroutine[Any, Any, Connection]" has no attribute "__aexit__"
 [attr-defined]
                async with self.pool.acquire() as conn:
                           ^~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/database/optimized_pool.py:264: error: Argument 1 to "asynccontextmanager" has incompatible type
"Callable[[OptimizedDatabasePool], AsyncSession]"; expected "Callable[[OptimizedDatabasePool], AsyncIterator[Never]]" 
[arg-type]
        @asynccontextmanager
         ^
deepsearch/infrastructure/database/optimized_pool.py:265: error: The return type of an async generator function should be
"AsyncGenerator" or one of its supertypes  [misc]
        async def get_session(self) -> AsyncSession:
        ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/database/optimized_pool.py:278: error: "Session" has no attribute "__aenter__"  [attr-defined]
            async with self.session_factory() as session:
                       ^~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/database/optimized_pool.py:278: error: "Session" has no attribute "__aexit__"  [attr-defined]
            async with self.session_factory() as session:
                       ^~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/database/optimized_pool.py:373: error: "Pool" has no attribute "get_min_size"; maybe "get_idle_size"
or "get_size"?  [attr-defined]
                    "min_size": self.pool.get_min_size(),
                                ^~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/database/optimized_pool.py:374: error: "Pool" has no attribute "get_max_size"; maybe "get_size"? 
[attr-defined]
                    "max_size": self.pool.get_max_size(),
                                ^~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/messaging/event_publisher.py:23: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/messaging/event_publisher.py:24: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/middleware/deduplication.py:303: error: Unexpected keyword argument "content" for "Response"  [call-arg]
                        return Response(
                               ^
deepsearch/webui/api/middleware/deduplication.py:303: error: Unexpected keyword argument "status_code" for "Response" 
[call-arg]
                        return Response(
                               ^
deepsearch/webui/api/middleware/deduplication.py:303: error: Unexpected keyword argument "headers" for "Response"  [call-arg]
                        return Response(
                               ^
deepsearch/webui/api/middleware/deduplication.py:303: error: Unexpected keyword argument "media_type" for "Response" 
[call-arg]
                        return Response(
                               ^
deepsearch/webui/api/middleware/deduplication.py:316: error: Returning Any from function declared to return "Response" 
[no-any-return]
                return response
                ^~~~~~~~~~~~~~~
deepsearch/utils/network/proxy_client.py:12: error: Cannot find implementation or library stub for module named
"requests.adapters"  [import-not-found]
    from requests.adapters import HTTPAdapter  # type: ignore[import-untyped]
    ^
deepsearch/utils/network/proxy_client.py:12: note: Error code "import-not-found" not covered by "type: ignore" comment
deepsearch/utils/network/proxy_client.py:13: error: Cannot find implementation or library stub for module named
"urllib3.util.retry"  [import-not-found]
    from urllib3.util.retry import Retry
    ^
deepsearch/utils/network/proxy_client.py:87: error: "Session" has no attribute "mount"  [attr-defined]
            self.session.mount("http://", adapter)
            ^~~~~~~~~~~~~~~~~~
deepsearch/utils/network/proxy_client.py:88: error: "Session" has no attribute "mount"  [attr-defined]
            self.session.mount("https://", adapter)
            ^~~~~~~~~~~~~~~~~~
deepsearch/utils/network/proxy_client.py:165: error: "Session" has no attribute "request"  [attr-defined]
                    response = self.session.request(method, url, **kwargs)
                               ^~~~~~~~~~~~~~~~~~~~
deepsearch/utils/network/proxy_client.py:242: error: "Session" has no attribute "request"  [attr-defined]
                response = self.session.request(method, proxy_url, params=proxy_params, **kwargs)
                           ^~~~~~~~~~~~~~~~~~~~
deepsearch/utils/network/proxy_client.py:10: error: Unused "type: ignore" comment  [unused-ignore]
    import requests  # type: ignore[import-untyped]
    ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/utils/network/proxy_client.py:12: error: Unused "type: ignore" comment  [unused-ignore]
    from requests.adapters import HTTPAdapter  # type: ignore[import-untyped]
    ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/utils/network/proxy_client.py:324: error: Unused "type: ignore[misc, valid-type]" comment  [unused-ignore]
        class ProxySession(_OriginalSession):  # type: ignore[misc, valid-type]
        ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/akshare/cache_manager.py:21: error: Incompatible types in assignment
(expression has type "None", variable has type Module)  [assignment]
        redis = None
                ^~~~
deepsearch/infrastructure/persistence/pool.py:20: error: Module "sqlalchemy.pool" has no attribute "NullPool"  [attr-defined]
    from sqlalchemy.pool import NullPool, QueuePool, StaticPool
    ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/persistence/pool.py:20: error: Module "sqlalchemy.pool" has no attribute "StaticPool"  [attr-defined]
    from sqlalchemy.pool import NullPool, QueuePool, StaticPool
    ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/persistence/pool.py:75: error: Function "sqlalchemy.ext.asyncio.async_sessionmaker" is not valid as a
type  [valid-type]
            self.session_factory: async_sessionmaker[AsyncSession] | None = None
                                  ^
deepsearch/infrastructure/persistence/pool.py:75: note: Perhaps you need "Callable[...]" or a callback protocol?
deepsearch/infrastructure/persistence/pool.py:135: error: Incompatible types in assignment (expression has type
"Coroutine[Any, Any, AsyncEngine]", variable has type "AsyncEngine | None")  [assignment]
                self.engine = create_async_engine(
                              ^
deepsearch/infrastructure/persistence/pool.py:135: note: Maybe you forgot to use "await"?
deepsearch/infrastructure/persistence/pool.py:173: error: "AsyncConnection" has no attribute "run_sync"  [attr-defined]
                    await conn.run_sync(lambda c: c.execute("SELECT 1"))
                          ^~~~~~~~~~~~~
deepsearch/infrastructure/persistence/pool.py:312: error: "Result[Any]" has no attribute "mappings"  [attr-defined]
                return [self._row_to_dict(row) for row in result.mappings().all()]
                                                          ^~~~~~~~~~~~~~~
deepsearch/infrastructure/persistence/pool.py:324: error: "AsyncConnection" has no attribute "run_sync"  [attr-defined]
                    await conn.run_sync(lambda c: c.execute("SELECT 1"))
                          ^~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:73: error: Need type annotation for "subscribed_symbols"
(hint: "subscribed_symbols: set[<type>] = ...")  [var-annotated]
            self.subscribed_symbols = set()
            ^~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:74: error: Need type annotation for "symbol_callbacks"
(hint: "symbol_callbacks: dict[<type>, <type>] = ...")  [var-annotated]
            self.symbol_callbacks = {}
            ^~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:83: error: Need type annotation for "data_queue" 
[var-annotated]
            self.data_queue = asyncio.Queue(maxsize=10000)
                              ^~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:106: error: Item "None" of "dict[str, Any] | None" has no
attribute "connection"  [union-attr]
                    conn = miniqmt_config.connection
                           ^~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:120: error: Incompatible types in assignment (expression has
type "Task[None]", variable has type "None")  [assignment]
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                                  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:120: note: Maybe you forgot to use "await"?
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:123: error: Incompatible types in assignment (expression has
type "Task[None]", variable has type "None")  [assignment]
            self.receive_task = asyncio.create_task(self._receive_loop())
                                ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:123: note: Maybe you forgot to use "await"?
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:149: error: Missing return statement  [return]
        async def _connect(self) -> bool:
        ^
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:156: error: Incompatible types in assignment (expression has
type "socket", variable has type "None")  [assignment]
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                              ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:157: error: "None" has no attribute "settimeout" 
[attr-defined]
                self.socket.settimeout(5.0)
                ^~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:161: error: "None" has no attribute "connect" 
[attr-defined]
                    None, self.socket.connect, (self.host, self.port)
                          ^~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:226: error: "DataProviderConfig" has no attribute
"retry_delay"  [attr-defined]
            await asyncio.sleep(self.config.retry_delay * self.reconnect_attempts)
                                ^~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:326: error: Argument 1 to "_process_tick_data" of
"MiniQMTProvider" has incompatible type "Any | None"; expected "dict[Any, Any]"  [arg-type]
                await self._process_tick_data(msg.get("data"))
                                              ^~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:329: error: Argument 1 to "_process_kline_data" of
"MiniQMTProvider" has incompatible type "Any | None"; expected "dict[Any, Any]"  [arg-type]
                await self._process_kline_data(msg.get("data"))
                                               ^~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/miniqmt.py:332: error: Argument 1 to "_process_orderbook_data" of
"MiniQMTProvider" has incompatible type "Any | None"; expected "dict[Any, Any]"  [arg-type]
                await self._process_orderbook_data(msg.get("data"))
                                                   ^~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/data/market_data_api.py:35: error: Returning Any from function declared to return "str" 
[no-any-return]
            return source.value
            ^~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/data/market_data_api.py:188: error: Incompatible default for argument "response" (default has
type "None", argument has type "Response")  [assignment]
        symbol: str = Path(..., description="股票代码"), response: Response = None
                                                                              ^
deepsearch/webui/api/endpoints/data/market_data_api.py:188: note: PEP 484 prohibits implicit Optional. Accordingly, mypy has changed its default to no_implicit_optional=True
deepsearch/webui/api/endpoints/data/market_data_api.py:188: note: Use https://github.com/hauntsaninja/no_implicit_optional to automatically upgrade your codebase
deepsearch/webui/api/endpoints/data/market_data_api.py:209: error: Unsupported target for indexed assignment
("Mapping[str, Any]")  [index]
                response.headers["Cache-Control"] = "public, max-age=300"
                ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/data/market_data_api.py:223: error: Unsupported target for indexed assignment
("Mapping[str, Any]")  [index]
                    response.headers["X-Data-Source"] = source_label
                    ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/data/market_data_api.py:227: error: Unsupported target for indexed assignment
("Mapping[str, Any]")  [index]
                        response.headers["ETag"] = f'W/"{etag}"'
                        ^~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/data/market_data_api.py:230: error: Unsupported target for indexed assignment
("Mapping[str, Any]")  [index]
                    response.headers["Last-Modified"] = datetime.utcnow().strftime(
                    ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/data/market_data_api.py:250: error: Incompatible default for argument "response" (default has
type "None", argument has type "Response")  [assignment]
        response: Response = None,
                             ^~~~
deepsearch/webui/api/endpoints/data/market_data_api.py:250: note: PEP 484 prohibits implicit Optional. Accordingly, mypy has changed its default to no_implicit_optional=True
deepsearch/webui/api/endpoints/data/market_data_api.py:250: note: Use https://github.com/hauntsaninja/no_implicit_optional to automatically upgrade your codebase
deepsearch/webui/api/endpoints/data/market_data_api.py:279: error: Unsupported target for indexed assignment
("Mapping[str, Any]")  [index]
                response.headers["Cache-Control"] = "public, max-age=60"
                ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/data/market_data_api.py:300: error: Unsupported target for indexed assignment
("Mapping[str, Any]")  [index]
                    response.headers["X-Data-Source"] = source_label
                    ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/datasources/datasource_manager.py:739: error: Unexpected keyword argument "exclude_unset" for
"model_dump" of "BaseModel"; did you mean "exclude_none"?  [call-arg]
        update_data = payload.model_dump(exclude_unset=True)
                      ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/data/data_source_config_api.py:49: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/endpoints/system/config.py:487: error: Missing positional argument "dsn" in call to "connect" of
"AsyncConnection"  [call-arg]
                    async with await psycopg.AsyncConnection.connect(
                                     ^
deepsearch/memory/smart_memory.py:136: error: Module has no attribute "windll"  [attr-defined]
            kernel32 = ctypes.windll.kernel32
                       ^~~~~~~~~~~~~
deepsearch/memory/smart_memory.py:350: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/memory/smart_memory.py:353: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/memory/smart_memory.py:354: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/memory/smart_memory.py:358: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/memory/smart_memory.py:361: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/memory/smart_memory.py:362: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/memory/smart_memory.py:363: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/memory/smart_memory.py:369: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/memory/smart_memory.py:372: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/memory/smart_memory.py:373: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/persistence/query_optimizer.py:149: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/persistence/query_optimizer.py:150: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/persistence/query_optimizer.py:152: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/persistence/query_optimizer.py:153: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/persistence/query_optimizer.py:154: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/persistence/query_optimizer.py:388: error: "Engine" has no attribute "dialect"  [attr-defined]
                if engine.dialect.name == "postgresql":
                   ^~~~~~~~~~~~~~
deepsearch/infrastructure/persistence/query_optimizer.py:396: error: "Engine" has no attribute "execute"  [attr-defined]
                    result = engine.execute(query, table=table, column=f"%{column}%")
                             ^~~~~~~~~~~~~~
deepsearch/infrastructure/persistence/query_optimizer.py:400: error: "Engine" has no attribute "dialect"  [attr-defined]
                elif engine.dialect.name == "mysql":
                     ^~~~~~~~~~~~~~
deepsearch/infrastructure/persistence/query_optimizer.py:408: error: "Engine" has no attribute "execute"  [attr-defined]
                    result = engine.execute(query, table=table, column=column)
                             ^~~~~~~~~~~~~~
deepsearch/infrastructure/persistence/query_optimizer.py:412: error: "Engine" has no attribute "dialect"  [attr-defined]
                elif engine.dialect.name == "sqlite":
                     ^~~~~~~~~~~~~~
deepsearch/infrastructure/persistence/query_optimizer.py:414: error: "Engine" has no attribute "execute"  [attr-defined]
                    result = engine.execute(query)
                             ^~~~~~~~~~~~~~
deepsearch/infrastructure/persistence/query_optimizer.py:480: error: "Engine" has no attribute "execute"  [attr-defined]
                        engine.execute(text(sql))
                        ^~~~~~~~~~~~~~
deepsearch/infrastructure/persistence/query_optimizer.py:503: error: Item "None" of "Settings | None" has no attribute "app" 
[union-attr]
                    if settings.app.env == "dev":
                       ^~~~~~~~~~~~
deepsearch/utils/system/port_checker.py:55: error: "dict[str, Any]" has no attribute "sub_port"  [attr-defined]
                    ports[f"{bus_name}_sub"] = bus_config.config.sub_port
                                               ^~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/utils/system/port_checker.py:149: error: Function "builtins.any" is not valid as a type  [valid-type]
        def check_port_conflicts() -> List[Dict[str, any]]:
                                                     ^
deepsearch/utils/system/port_checker.py:149: note: Perhaps you meant "typing.Any" instead of "any"?
deepsearch/utils/system/port_checker.py:240: error: "object" has no attribute "lower"  [attr-defined]
                    if "redis" in issue["service"].lower():
                                  ^~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/auth.py:11: error: Module "fastapi" has no attribute "Security"  [attr-defined]
    from fastapi import HTTPException, Security, status
    ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/auth.py:13: error: Library stubs not installed for "jose"  [import-untyped]
    from jose import JWTError, jwt
    ^
deepsearch/webui/auth.py:13: note: Hint: "python3 -m pip install types-python-jose"
deepsearch/webui/auth.py:13: note: (or run "mypy --install-types" to install all missing stub packages)
deepsearch/webui/auth.py:13: note: See https://mypy.readthedocs.io/en/stable/running_mypy.html#missing-imports
deepsearch/debug/performance_profiler.py:126: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/debug/performance_profiler.py:129: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/debug/performance_profiler.py:141: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/providers/implementations/akshare/request_handler.py:42: error: Item "None" of
"CloudflareWorkersConfig | None" has no attribute "auth_key"  [union-attr]
                    self.auth_key = config.cloudflare_workers.auth_key
                                    ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/akshare/request_handler.py:116: error: "None" has no attribute "post" 
[attr-defined]
                async with self.session.post(
                           ^~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/akshare/request_handler.py:145: error: Returning Any from function declared
to return "dict[str, Any]"  [no-any-return]
                            return result
                            ^~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/akshare/request_handler.py:209: error: Missing positional argument "params"
in call to "get" of "CacheManager"  [call-arg]
                cached = self.cache_manager.get(cache_key)
                         ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/akshare/request_handler.py:212: error: Returning Any from function declared
to return "dict[str, Any]"  [no-any-return]
                    return cached
                    ^~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/akshare/request_handler.py:247: error: Returning Any from function declared
to return "dict[str, Any]"  [no-any-return]
            return await _do_fetch()
            ^~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/akshare/request_handler.py:286: error: Returning Any from function declared
to return "RequestPriority"  [no-any-return]
                return RequestPriority.MEDIUM
                ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/akshare/request_handler.py:286: error: "type[RequestPriority]" has no
attribute "MEDIUM"  [attr-defined]
                return RequestPriority.MEDIUM
                       ^~~~~~~~~~~~~~~~~~~~~~
deepsearch/event/schema.py:106: error: Missing positional argument "self" in call to "model_json_schema" of "BaseModel" 
[call-arg]
                event_type: schema.model_json_schema() for event_type, schema in self._schemas.items()
                            ^~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/event/schema.py:400: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/endpoints/qmt/miniqmt.py:66: error: "Component" has no attribute "get_provider"  [attr-defined]
                    _miniqmt_provider = data_manager.get_provider("miniqmt")
                                        ^~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/qmt/miniqmt.py:208: error: Item "Mapping[str, object]" of
"DataFrame | Mapping[str, object] | Sequence[Mapping[str, object]]" has no attribute "to_dict"  [union-attr]
                data = response.data.to_dict("records") if response.data is not None else []
                       ^~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/qmt/miniqmt.py:208: error: Item "Sequence[Mapping[str, object]]" of
"DataFrame | Mapping[str, object] | Sequence[Mapping[str, object]]" has no attribute "to_dict"  [union-attr]
                data = response.data.to_dict("records") if response.data is not None else []
                       ^~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/qmt/miniqmt.py:263: error: Item "Mapping[str, object]" of
"DataFrame | Mapping[str, object] | Sequence[Mapping[str, object]]" has no attribute "to_dict"  [union-attr]
                data = response.data.to_dict("records") if response.data is not None else []
                       ^~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/qmt/miniqmt.py:263: error: Item "Sequence[Mapping[str, object]]" of
"DataFrame | Mapping[str, object] | Sequence[Mapping[str, object]]" has no attribute "to_dict"  [union-attr]
                data = response.data.to_dict("records") if response.data is not None else []
                       ^~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/qmt/miniqmt.py:315: error: Item "Mapping[str, object]" of
"DataFrame | Mapping[str, object] | Sequence[Mapping[str, object]]" has no attribute "to_dict"  [union-attr]
                data = response.data.to_dict("records") if response.data is not None else []
                       ^~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/qmt/miniqmt.py:315: error: Item "Sequence[Mapping[str, object]]" of
"DataFrame | Mapping[str, object] | Sequence[Mapping[str, object]]" has no attribute "to_dict"  [union-attr]
                data = response.data.to_dict("records") if response.data is not None else []
                       ^~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/monitoring/analytics.py:378: error: Argument 1 to "sync_historical_data" of "DataSyncService"
has incompatible type "str | None"; expected "str"  [arg-type]
                await sync_service.sync_historical_data(start_date, end_date, symbols)
                                                        ^~~~~~~~~~
deepsearch/webui/api/endpoints/monitoring/analytics.py:378: error: Argument 2 to "sync_historical_data" of "DataSyncService"
has incompatible type "str | None"; expected "str"  [arg-type]
                await sync_service.sync_historical_data(start_date, end_date, symbols)
                                                                    ^~~~~~~~
deepsearch/core/components/ui_components.py:34: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/components/ui_components.py:35: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/components/ui_components.py:36: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/components/monitoring_components.py:169: error: Returning Any from function declared to return "dict[str, Any]"
 [no-any-return]
                return instance.get_metrics()
                ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/core/components/data_components.py:92: error: Item "None" of "DatabaseConfig | None" has no attribute "main" 
[union-attr]
                if not db_config.main.auto_connect:
                       ^~~~~~~~~~~~~~
deepsearch/core/components/data_components.py:409: error: Item "None" of "CacheDatabaseConfig | None" has no attribute
"enabled"  [union-attr]
                if not cache_config.enabled:
                       ^~~~~~~~~~~~~~~~~~~~
deepsearch/core/components/data_components.py:414: error: Item "None" of "CacheDatabaseConfig | None" has no attribute
"model_dump"  [union-attr]
                redis_config = cache_config.model_dump()
                               ^~~~~~~~~~~~~~~~~~~~~~~
deepsearch/core/components/data_components.py:446: error: Module has no attribute "ConnectionPool"  [attr-defined]
                pool = aioredis.ConnectionPool(
                       ^~~~~~~~~~~~~~~~~~~~~~~
deepsearch/core/components/data_components.py:613: error: Return type "Coroutine[Any, Any, dict[str, Any]]" of "get_status"
incompatible with return type "str" in supertype "deepsearch.core.async_component.AsyncComponent"  [override]
        async def get_status(self) -> Dict[str, Any]:
        ^
deepsearch/core/components/analytics_components.py:43: error: Item "None" of "AnalyticsDatabaseConfig | None" has no attribute
"enabled"  [union-attr]
                if not analytics_config.enabled:
                       ^~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/core/components/analytics_components.py:69: error: Item "None" of "AnalyticsDatabaseConfig | None" has no attribute
"auto_sync"  [union-attr]
                if analytics_config.auto_sync:
                   ^~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/core/components/analytics_components.py:71: error: Item "None" of "AnalyticsDatabaseConfig | None" has no attribute
"sync_interval"  [union-attr]
                    self._sync_service.sync_interval = analytics_config.sync_interval
                                                       ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/core/components/analytics_components.py:76: error: Item "None" of "AnalyticsDatabaseConfig | None" has no attribute
"sync_interval"  [union-attr]
                        f"数据同步服务已启动，同步间隔: {analytics_config.sync_interval}秒"
                                                                      ^~~~~~
deepsearch/core/components/analytics_components.py:194: error: Returning Any from function declared to return "dict[str, Any]" 
[no-any-return]
                            return future.result()
                            ^~~~~~~~~~~~~~~~~~~~~~
deepsearch/core/components/analytics_components.py:200: error: Returning Any from function declared to return "dict[str, Any]" 
[no-any-return]
                    return stats_method()
                    ^~~~~~~~~~~~~~~~~~~~~
deepsearch/backtest/interfaces/strategy.py:639: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/backtest/interfaces/strategy.py:683: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/backtest/interfaces/strategy.py:733: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/backtest/interfaces/strategy.py:781: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/providers/datafeed/qmt/gateway.py:45: error: Call to abstract method "__init__" of "Component" with
trivial body via super() is unsafe  [safe-super]
            super().__init__()
            ^~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/datafeed/qmt/gateway.py:155: error: Missing keys ("running", "uptime", "clients",
"messages", "data", "errors") for TypedDict "ReceiverStats"  [typeddict-item]
                "receiver": self.receiver.get_stats() if self.receiver else {},
                                                                            ^~
deepsearch/infrastructure/providers/datafeed/qmt/gateway.py:278: error: Cannot find implementation or library stub for module
named "deepsearch.qmt.models.trade"  [import-not-found]
                from deepsearch.qmt.models.trade import OrderSide
    ^
deepsearch/infrastructure/providers/implementations/akshare/akshare_refactored.py:270: error: Incompatible types in assignment
(expression has type "DataFrame | None", variable has type "DataFrame")  [assignment]
                    dataframe = await self.get_history_data(
                                ^
deepsearch/infrastructure/providers/implementations/akshare/akshare_refactored.py:328: error: Returning Any from function
declared to return "dict[str, Any]"  [no-any-return]
            return await self.api_methods.get_realtime_data(symbols)
            ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/akshare/akshare_refactored.py:341: error: Returning Any from function
declared to return "DataFrame | None"  [no-any-return]
            return await self.api_methods.get_history_data(symbol, start_date, end_date, period, adjust)
            ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/__init__.py:10: error: Cannot assign to a type  [misc]
        AkShareProxyProvider = None
        ^~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/__init__.py:10: error: Incompatible types in assignment (expression has type "None",
variable has type "type[AkShareProxyProvider]")  [assignment]
        AkShareProxyProvider = None
                               ^~~~
deepsearch/infrastructure/providers/implementations/qmt/unified_qmt_provider.py:145: error: Module has no attribute
"get_full_tick"  [attr-defined]
                test_data = xtdata.get_full_tick(["000001.SZ"])
                            ^~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/unified_qmt_provider.py:374: error: Item "None" of "QMTBackend | None"
has no attribute "get_special_data"  [union-attr]
            data = await self.backend.get_special_data(data_type, **kwargs)
                         ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/qmt/unified_qmt_provider.py:541: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/providers/implementations/qmt/unified_qmt_provider.py:542: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/providers/implementations/qmt/unified_qmt_provider.py:543: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/providers/implementations/qmt/unified_qmt_provider.py:585: error: Returning Any from function
declared to return "dict[Any, Any]"  [no-any-return]
                        return json.loads(data.decode("utf-8"))
                        ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/datafeed/akshare.py:39: error: "AkShareProxyProvider" has no attribute
"_fetch_with_fallback"  [attr-defined]
                resp = await self.provider._fetch_with_fallback(
                             ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/datafeed/akshare.py:51: error: "AkShareProxyProvider" has no attribute
"_fetch_with_fallback"  [attr-defined]
                resp = await self.provider._fetch_with_fallback(
                             ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/datafeed/akshare.py:103: error: Unused "type: ignore" comment  [unused-ignore]
            import pandas as pd  # type: ignore
            ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:936: error: Argument "symbol" to "get_kline" of
"AmazingDataProvider" has incompatible type "str | None"; expected "str"  [arg-type]
                            symbol=request.symbol,
                                   ^~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:937: error: Argument "period" to "get_kline" of
"AmazingDataProvider" has incompatible type "str | None"; expected "str"  [arg-type]
                            period=request.period,
                                   ^~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:940: error: Argument "adjust" to "get_kline" of
"AmazingDataProvider" has incompatible type "str | None"; expected "str"  [arg-type]
                            adjust=request.adjust,
                                   ^~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:944: error: List item 0 has incompatible type
"str | None"; expected "str"  [list-item]
                    quotes = await self.get_realtime_quote(request.symbols or [request.symbol])
                                                                               ^~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:945: error: Returning Any from function declared
to return "DataFrame"  [no-any-return]
                    return pd.DataFrame(quotes).T
                    ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:950: error: Argument "symbol" to
"get_financial_data" of "AmazingDataProvider" has incompatible type "str | None"; expected "str"  [arg-type]
                            symbol=request.symbol,
                                   ^~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:951: error: Argument "report_type" to
"get_financial_data" of "AmazingDataProvider" has incompatible type "object"; expected "str"  [arg-type]
                            report_type=request.extra_params.get("report_type", "balance_sheet"),
                                        ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:961: error: Argument "symbol" to "get_kline" of
"AmazingDataProvider" has incompatible type "str | None"; expected "str"  [arg-type]
                        symbol=request.symbol,
                               ^~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:962: error: Argument "period" to "get_kline" of
"AmazingDataProvider" has incompatible type "str | None"; expected "str"  [arg-type]
                        period=request.period,
                               ^~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:965: error: Argument "adjust" to "get_kline" of
"AmazingDataProvider" has incompatible type "str | None"; expected "str"  [arg-type]
                        adjust=request.adjust,
                               ^~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:1742: error: Return type
"Coroutine[Any, Any, list[StockListItem] | None]" of "get_stock_list" incompatible with return type
"Coroutine[Any, Any, list[dict[str, Any]] | None]" in supertype
"deepsearch.infrastructure.providers.interfaces.base.DataProvider"  [override]
        async def get_stock_list(
        ^
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:1830: error: Return type
"Coroutine[Any, Any, list[KlineBarMessage] | None]" of "get_kline_data" incompatible with return type
"Coroutine[Any, Any, list[dict[str, Any]] | None]" in supertype
"deepsearch.infrastructure.providers.interfaces.base.DataProvider"  [override]
        async def get_kline_data(
        ^
deepsearch/core/components/qmt_gateway_component.py:44: error: Item "None" of "Any | None" has no attribute "get"  [union-attr]
            self.priority = self.config.get("priority", 1)
                            ^~~~~~~~~~~~~~~
deepsearch/core/components/qmt_gateway_component.py:172: error: Incompatible return value type (got
"QMTReceiver | bool | None", expected "bool")  [return-value]
            return self.receiver and self.receiver.running
                   ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/core/components/qmt_gateway_component.py:174: error: Return type "dict[Any, Any]" of "get_status" incompatible with
return type "str" in supertype "deepsearch.core.async_component.AsyncComponent"  [override]
        def get_status(self) -> Dict:
        ^
deepsearch/core/components/qmt_gateway_component.py:200: error: Missing keys ("running", "uptime", "clients", "messages",
"data", "errors") for TypedDict "ReceiverStats"  [typeddict-item]
                "receiver": self.receiver.get_stats() if self.receiver else {},
                                                                            ^~
deepsearch/core/components/qmt_gateway_component.py:353: error: Module
"deepsearch.infrastructure.providers.datafeed.qmt.models" has no attribute "OrderSide"  [attr-defined]
                from deepsearch.infrastructure.providers.datafeed.qmt.models import OrderSide
                ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/core/components/qmt_gateway_component.py:455: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/providers/managers/enhanced_manager.py:51: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/providers/managers/enhanced_manager.py:55: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/providers/managers/enhanced_manager.py:56: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/providers/managers/enhanced_manager.py:57: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/providers/managers/enhanced_manager.py:123: error: Incompatible types in assignment (expression has
type "AkShareProxyProvider", target has type "DataProvider")  [assignment]
                    self._providers["akshare"] = self._akshare_provider
                                                 ^~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/managers/enhanced_manager.py:532: error: "DataProvider" has no attribute
"get_realtime_data"; maybe "get_realtime_quotes" or "get_kline_data"?  [attr-defined]
                    raw_quotes = await provider.get_realtime_data(symbols)
                                       ^~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/managers/enhanced_manager.py:685: error: "type[DataCapability]" has no attribute
"SUBSCRIPTION"  [attr-defined]
                    DataCapability.SUBSCRIPTION,
                    ^~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/managers/enhanced_manager.py:926: error: "DataProvider" has no attribute
"get_realtime_quote"; maybe "get_realtime_quotes"?  [attr-defined]
                            result = await provider.get_realtime_quote(symbol)
                                           ^~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py:923: error: Item "None" of Module |
None has no attribute "update_password"  [union-attr]
                    None, ad.update_password, self.config.username, old_password, new_password
                          ^~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_optimized.py:776: error: Item "None" of Module |
None has no attribute "login"  [union-attr]
                        ad.login,
                        ^~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_optimized.py:805: error: Item "None" of Module |
None has no attribute "logout"  [union-attr]
                    await self.thread_pool.execute_async(ad.logout)
                                                         ^~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_optimized.py:850: error: Item "None" of Module |
None has no attribute "KLine"  [union-attr]
                        ad.KLine.get_kline, symbol, period, start_date, end_date, count, adjust
                        ^~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_optimized.py:930: error: Return type
"Coroutine[Any, Any, list[StockListItem] | None]" of "get_stock_list" incompatible with return type
"Coroutine[Any, Any, list[dict[str, Any]] | None]" in supertype
"deepsearch.infrastructure.providers.interfaces.base.DataProvider"  [override]
        async def get_stock_list(
        ^
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_optimized.py:939: error: Item "None" of Module |
None has no attribute "BaseData"  [union-attr]
                result = await self.thread_pool.execute_async(ad.BaseData.get_stock_list)
                                                              ^~~~~~~~~~~
deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_optimized.py:966: error: Return type
"Coroutine[Any, Any, list[KlineBarMessage] | None]" of "get_kline_data" incompatible with return type
"Coroutine[Any, Any, list[dict[str, Any]] | None]" in supertype
"deepsearch.infrastructure.providers.interfaces.base.DataProvider"  [override]
        async def get_kline_data(
        ^
deepsearch/webui/api/providers.py:18: error: Cannot find implementation or library stub for module named
"deepsearch.application.services.market.market_service"  [import-not-found]
        from deepsearch.application.services.market.market_service import MarketService
    ^
deepsearch/webui/api/providers.py:23: error: Cannot find implementation or library stub for module named
"deepsearch.application.services.market.eastmoney_service"  [import-not-found]
        from deepsearch.application.services.market.eastmoney_service import EastMoneyService
    ^
deepsearch/webui/api/providers.py:28: error: Cannot find implementation or library stub for module named
"deepsearch.application.services.market.akshare_direct_service"  [import-not-found]
        from deepsearch.application.services.market.akshare_direct_service import AkShareDirectService
    ^
deepsearch/webui/api/providers.py:164: error: Module "deepsearch.infrastructure.providers.implementations.qmt.miniqmt" has no
attribute "MiniQMTDataProvider"; maybe "MiniQMTProvider" or "DataProvider"?  [attr-defined]
                        from deepsearch.infrastructure.providers.implementations.qmt.miniqmt import (
                        ^
deepsearch/webui/api/providers.py:213: error: Module "deepsearch.infrastructure.providers.implementations.qmt.miniqmt" has no
attribute "MiniQMTDataProvider"; maybe "MiniQMTProvider" or "DataProvider"?  [attr-defined]
                            from deepsearch.infrastructure.providers.implementations.qmt.miniqmt import (
                            ^
deepsearch/webui/api/providers.py:304: error: Incompatible types in assignment (expression has type "AkShareProxyProvider",
variable has type "AmazingDataProvider | None")  [assignment]
                                    chosen_instance = fallback_provider
                                                      ^~~~~~~~~~~~~~~~~
deepsearch/webui/api/providers.py:337: error: Incompatible types in assignment (expression has type "MockErrorProvider",
variable has type "AmazingDataProvider | None")  [assignment]
                                    chosen_instance = MockErrorProvider(reason_text)
                                                      ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/providers.py:350: error: Incompatible types in assignment (expression has type "TempErrorProvider",
variable has type "AmazingDataProvider | None")  [assignment]
                                    chosen_instance = TempErrorProvider(reason_text)
                                                      ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/base.py:53: error: Item "dict[str, Any]" of "dict[str, Any] | None" has no attribute
"amazingdata"  [union-attr]
                amazingdata_config = config.data_sources.amazingdata.model_dump()
                                     ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/base.py:53: error: Item "None" of "dict[str, Any] | None" has no attribute
"amazingdata"  [union-attr]
                amazingdata_config = config.data_sources.amazingdata.model_dump()
                                     ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/base.py:214: error: Item "Timestamp" of "Timestamp | datetime" has no attribute
"strftime"  [union-attr]
            return int(value.strftime("%Y%m%d"))
                       ^~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/base.py:244: error: Returning Any from function declared to return
"DataFrame | None"  [no-any-return]
                return data.loc[mask]
                ^~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/base.py:251: error: Returning Any from function declared to return
"DataFrame | None"  [no-any-return]
                return data.loc[index_mask]
                ^~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/base.py:274: error: Returning Any from function declared to return
"DataFrame | None"  [no-any-return]
                return data.loc[mask]
                ^~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:138: error: Item "None" of "AmazingDataConfig | None" has no
attribute "to_provider_payload"  [union-attr]
                        payload = amazingdata_settings.to_provider_payload()
                                  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:140: error: "None" has no attribute "model_dump"  [attr-defined]
                        payload = amazingdata_settings.model_dump()
                                  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:145: error: Item "None" of "dict[str, Any] | None" has no
attribute "amazingdata"  [union-attr]
                        amazingdata_section = data_sources.amazingdata
                                              ^~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:225: error: "AmazingDataExtended" has no attribute "stop" 
[attr-defined]
            await provider.stop()
                  ^~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:321: error: Argument 2 to "get_backward_factor" of
"AmazingDataExtended" has incompatible type "str | None"; expected "str"  [arg-type]
                request.code_list, request.local_path, request.is_local
                                   ^~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:342: error: Argument 2 to "get_adj_factor" of
"AmazingDataExtended" has incompatible type "str | None"; expected "str"  [arg-type]
                request.code_list, request.local_path, request.is_local
                                   ^~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:363: error: Argument 2 to "get_history_stock_status" of
"AmazingDataExtended" has incompatible type "str | None"; expected "str"  [arg-type]
                request.code_list, request.local_path, request.is_local
                                   ^~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:506: error: Argument 2 to "get_balance_sheet" of
"AmazingDataExtended" has incompatible type "str | None"; expected "str"  [arg-type]
                request.code_list, request.local_path, request.is_local
                                   ^~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:527: error: Argument 2 to "get_cash_flow" of
"AmazingDataExtended" has incompatible type "str | None"; expected "str"  [arg-type]
                request.code_list, request.local_path, request.is_local
                                   ^~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:547: error: Argument 2 to "get_income" of "AmazingDataExtended"
has incompatible type "str | None"; expected "str"  [arg-type]
            result = await provider.get_income(request.code_list, request.local_path, request.is_local)
                                                                  ^~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:563: error: Argument 2 to "get_profit_express" of
"AmazingDataExtended" has incompatible type "str | None"; expected "str"  [arg-type]
                request.code_list, request.local_path, request.is_local
                                   ^~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:584: error: Argument 2 to "get_profit_notice" of
"AmazingDataExtended" has incompatible type "str | None"; expected "str"  [arg-type]
                request.code_list, request.local_path, request.is_local
                                   ^~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:608: error: Argument 2 to "get_share_holder" of
"AmazingDataExtended" has incompatible type "str | None"; expected "str"  [arg-type]
                request.code_list, request.local_path, request.is_local
                                   ^~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:629: error: Argument 2 to "get_holder_num" of
"AmazingDataExtended" has incompatible type "str | None"; expected "str"  [arg-type]
                request.code_list, request.local_path, request.is_local
                                   ^~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:650: error: Argument 2 to "get_equity_structure" of
"AmazingDataExtended" has incompatible type "str | None"; expected "str"  [arg-type]
                request.code_list, request.local_path, request.is_local
                                   ^~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:671: error: Argument 2 to "get_equity_pledge_freeze" of
"AmazingDataExtended" has incompatible type "str | None"; expected "str"  [arg-type]
                request.code_list, request.local_path, request.is_local
                                   ^~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:692: error: Argument 2 to "get_equity_restricted" of
"AmazingDataExtended" has incompatible type "str | None"; expected "str"  [arg-type]
                request.code_list, request.local_path, request.is_local
                                   ^~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:716: error: Argument 2 to "get_dividend" of "AmazingDataExtended"
has incompatible type "str | None"; expected "str"  [arg-type]
                request.code_list, request.local_path, request.is_local
                                   ^~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/amazingdata_api.py:737: error: Argument 2 to "get_right_issue" of
"AmazingDataExtended" has incompatible type "str | None"; expected "str"  [arg-type]
                request.code_list, request.local_path, request.is_local
                                   ^~~~~~~~~~~~~~~~~~
deepsearch/webui/server_manager.py:23: error: Module "asyncio" has no attribute "WindowsProactorEventLoopPolicy"; maybe
"AbstractEventLoopPolicy"?  [attr-defined]
        from asyncio import WindowsProactorEventLoopPolicy as WindowsEventLoopPolicyBase
        ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/server_manager.py:49: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/server_manager.py:50: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/server_manager.py:52: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/server_manager.py:138: error: Argument 2 to "Config" has incompatible type "**dict[str, object]"; expected
"str"  [arg-type]
            config = Config(app=app, **config_kwargs)
                                       ^~~~~~~~~~~~~
deepsearch/webui/server_manager.py:138: error: Argument 2 to "Config" has incompatible type "**dict[str, object]"; expected
"int"  [arg-type]
            config = Config(app=app, **config_kwargs)
                                       ^~~~~~~~~~~~~
deepsearch/webui/api/proxy.py:351: error: "AkShareProxyProvider" has no attribute "worker_urls"; maybe "_load_worker_urls"? 
[attr-defined]
            if worker_url not in provider.worker_urls:
                                 ^~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/proxy.py:355: error: "AkShareProxyProvider" has no attribute "_check_worker_health"  [attr-defined]
            result = await provider._check_worker_health(worker_url)
                           ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/proxy.py:386: error: "AkShareProxyProvider" has no attribute "worker_urls"; maybe "_load_worker_urls"? 
[attr-defined]
            if worker_url not in provider.worker_urls:
                                 ^~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/proxy.py:390: error: "AkShareProxyProvider" has no attribute "worker_stats"  [attr-defined]
            if worker_url in provider.worker_stats:
                             ^~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/proxy.py:391: error: "AkShareProxyProvider" has no attribute "worker_stats"  [attr-defined]
                provider.worker_stats[worker_url]["state"] = "suspect"
                ^~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/proxy.py:392: error: "AkShareProxyProvider" has no attribute "worker_stats"  [attr-defined]
                provider.worker_stats[worker_url]["fail_streak"] = 0
                ^~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/proxy.py:393: error: "AkShareProxyProvider" has no attribute "worker_stats"  [attr-defined]
                provider.worker_stats[worker_url]["success_streak"] = 0
                ^~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/proxy.py:394: error: "AkShareProxyProvider" has no attribute "worker_stats"  [attr-defined]
                provider.worker_stats[worker_url]["next_retry_time"] = 0
                ^~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/proxy.py:395: error: "AkShareProxyProvider" has no attribute "worker_health"  [attr-defined]
                provider.worker_health[worker_url] = True
                ^~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/data/data_source_capability_api.py:305: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/endpoints/data/data_source_capability_api.py:314: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/endpoints/data/data_source_capability_api.py:341: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/endpoints/amazingdata/realtime.py:44: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/endpoints/amazingdata/realtime.py:45: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/endpoints/amazingdata/realtime.py:46: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/endpoints/amazingdata/realtime.py:144: error: "AmazingDataExtended" has no attribute
"subscribe_index_snapshot"  [attr-defined]
            await provider.subscribe_index_snapshot(code_list=request.code_list, callback=on_snapshot)
                  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/realtime.py:183: error: "AmazingDataExtended" has no attribute
"subscribe_stock_snapshot"  [attr-defined]
            await provider.subscribe_stock_snapshot(code_list=request.code_list, callback=on_snapshot)
                  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/realtime.py:222: error: "AmazingDataExtended" has no attribute
"subscribe_future_snapshot"  [attr-defined]
            await provider.subscribe_future_snapshot(code_list=request.code_list, callback=on_snapshot)
                  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/realtime.py:261: error: "AmazingDataExtended" has no attribute
"subscribe_etf_snapshot"  [attr-defined]
            await provider.subscribe_etf_snapshot(code_list=request.code_list, callback=on_snapshot)
                  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/realtime.py:300: error: "AmazingDataExtended" has no attribute
"subscribe_kzz_snapshot"  [attr-defined]
            await provider.subscribe_kzz_snapshot(code_list=request.code_list, callback=on_snapshot)
                  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/realtime.py:339: error: "AmazingDataExtended" has no attribute
"subscribe_hkt_snapshot"  [attr-defined]
            await provider.subscribe_hkt_snapshot(code_list=request.code_list, callback=on_snapshot)
                  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/realtime.py:379: error: "AmazingDataExtended" has no attribute "subscribe_kline" 
[attr-defined]
            await provider.subscribe_kline(
                  ^~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/realtime.py:412: error: "AmazingDataExtended" has no attribute "unsubscribe_all" 
[attr-defined]
            await provider.unsubscribe_all()
                  ^~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/amazingdata/margin.py:56: error: Returning Any from function declared to return
"DataFrame | None"  [no-any-return]
        return data.loc[:, valid]
        ^~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/backtest/engines/backtest_engine.py:106: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/backtest/engines/engine.py:75: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/infrastructure/providers/factory.py:185: error: Incompatible types in assignment (expression has type "Any | None",
variable has type "BaseDataProvider")  [assignment]
            provider = self.registry.get_provider_instance(name)
                       ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/infrastructure/providers/factory.py:381: error: Incompatible types in assignment (expression has type "float",
variable has type "int")  [assignment]
                        score *= 0.1  # 大幅降低分数
                        ^~~~~~~~~~~~
deepsearch/infrastructure/providers/factory.py:439: error: Item "None" of "dict[str, Any] | None" has no attribute "get" 
[union-attr]
                    return health.get("status") != "error"
                           ^~~~~~~~~~
deepsearch/backtest/components/component.py:38: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/backtest/components/component.py:39: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/backtest/components/component.py:40: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/backtest/components/component.py:41: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/backtest/components/component.py:42: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/backtest/components/component.py:44: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/components/backtest_components.py:25: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/components/backtest_components.py:26: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/components/backtest_components.py:27: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/components/backtest_components.py:28: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/components/backtest_components.py:34: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/database.py:552: error: Argument 1 to "get_columns" of "Inspector" has incompatible type "str | None";
expected "str"  [arg-type]
                            cols = inspector.get_columns(t["name"])
                                                         ^~~~~~~~~
deepsearch/webui/api/database.py:553: error: Incompatible types in assignment (expression has type "int", target has type
"str | None")  [assignment]
                            t["columns"] = len(cols)
                                           ^~~~~~~~~
deepsearch/webui/api/database.py:565: error: Argument 1 to "_quote_identifier" has incompatible type "str | None"; expected
"str"  [arg-type]
                            quoted_name = _quote_identifier(t["name"])
                                                            ^~~~~~~~~
deepsearch/webui/api/endpoints/monitor/monitor_api.py:562: error: Unsupported operand types for < ("list[float]" and "int") 
[operator]
                "status": "pass" if cpu_usage < 80 else "warn" if cpu_usage < 90 else "fail",
                                                ^~
deepsearch/webui/api/endpoints/monitor/monitor_api.py:562: note: Left operand is of type "float | list[float]"
deepsearch/webui/api/endpoints/monitor/monitor_api.py:567: error: Unsupported operand types for >= ("list[float]" and "int") 
[operator]
            if cpu_usage >= 90:
                            ^~
deepsearch/webui/api/endpoints/monitor/monitor_api.py:567: note: Left operand is of type "float | list[float]"
deepsearch/webui/api/endpoints/monitor/monitor_api.py:569: error: Unsupported operand types for >= ("list[float]" and "int") 
[operator]
            elif cpu_usage >= 80:
                              ^~
deepsearch/webui/api/endpoints/monitor/monitor_api.py:569: note: Left operand is of type "float | list[float]"
deepsearch/core/runtime/context.py:31: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/runtime/context.py:36: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/runtime/context.py:37: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/runtime/context.py:40: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/api/services/system_data_service.py:126: error: Argument 1 to "round" has incompatible type
"float | list[float]"; expected "_SupportsRound2[float]"  [arg-type]
                metrics["cpu_usage"] = round(psutil.cpu_percent(interval=0.1), 2)
                                             ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/system/database_manager.py:1069: error: Incompatible types in assignment (expression has type
"Connection", variable has type "AsyncConnection")  [assignment]
                            conn = psycopg2.connect(conn_string)
                                   ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~
deepsearch/webui/api/endpoints/data/data_source_monitor_api.py:274: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/components/gateway_components.py:31: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/core/runtime/engine.py:1002: error: "Server" has no attribute "should_exit"  [attr-defined]
                        server.should_exit = True
                        ^~~~~~~~~~~~~~~~~~
deepsearch/core/runtime/engine.py:1024: error: "Server" has no attribute "should_exit"  [attr-defined]
                    server.should_exit = True
                    ^~~~~~~~~~~~~~~~~~
deepsearch/core/runtime/engine.py:1031: error: "Server" has no attribute "should_exit"  [attr-defined]
                    server.should_exit = True
                    ^~~~~~~~~~~~~~~~~~
deepsearch/webui/server.py:93: error: "render" undefined in superclass  [misc]
            rendered = super().render(safe_content)
                       ^~~~~~~~~~~~~~
deepsearch/webui/server.py:404: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/server.py:405: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/server.py:406: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/server.py:407: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
deepsearch/webui/server.py:408: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
````

## 2025-10-11 - 继续治理进展

- 调整 `UnifiedQMTProvider` 的后端判空逻辑并补充 MiniQMT/标准 QMT 切换时的可空返回值处理，防止类型检查阶段访问 `None`。
- 为 AmazingData 安全包装器补全最小 `TypedDict` 声明，并在 `_fetch_data` 中显式校验请求参数，避免 `Optional[str]` 直接传入 SDK。
- 再次执行 `uv run mypy --hide-error-context --no-error-summary --pretty deepsearch`，仍有 MiniQMT 返回值、AkShare 缓存接口、Redis/Timeseries 类型桩与 SQLAlchemy Engine 操作等大量遗留错误，详见最新输出。

> 备注：当前主要卡在第三方依赖缺少桩文件与多个组件判空逻辑，后续需优先梳理 Redis/RediTimeSeries/psycopg/SQLAlchemy 的类型支持，并统一整理 `Optional` 配置模型的访问方式。

## 2025-10-11 - AmazingData 类型桩与领域实体兜底

- 为 `AmazingData` 模块补充最小 `.pyi` 类型桩，覆盖登录、登出、K 线查询、BaseData 以及实时订阅接口，修复 `Module has no attribute` 报错。
- 优化 AmazingData 优化版数据源的 SDK 获取流程，统一通过 `_require_sdk()` 收窄类型，并在心跳、登录与股票/行情查询中返回 `dict[str, Any]`，解决 `Module | None` 与覆写签名不匹配问题。
- 新增 `deepsearch.domain.entities` 包装层，实现 `Price`、`Stock`、`Trade`、`Order` 等值对象与实体，补齐单测导入依赖。
- 调整 `Settings.get_timeseries_config` 的兜底分支，避免对 `dict` 调用 `.config` 导致的联合类型访问错误。
- 最新一次 `uv run mypy --hide-error-context --no-error-summary --pretty deepsearch` 输出显示，剩余问题集中在数据库诊断接口、系统监控 API 与 QMT/AkShare 其它模块，将在后续批次继续清理。

