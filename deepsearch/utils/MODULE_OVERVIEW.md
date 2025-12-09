# 工具函数模块概览

## 模块定位

`deepsearch/utils` 汇总跨模块复用的通用工具，涵盖数据源配置、金融计算、网络访问、模式封装、系统操作与交易时段计算等。工具模块不依赖具体业务逻辑，便于在
CLI、核心引擎、脚本间共享。

## 子模块说明

- `data_sources.py`：维护数据源常量、别名与配置帮助函数，为 providers 与 CLI 提供统一映射。
- `finance/decimal_utils.py`：针对金融场景的 `Decimal` 运算封装（安全除法、四舍五入、百分比换算等），避免浮点误差。
- `network/`：
    - `akshare_proxy.py`：封装 AkShare 请求代理逻辑（重试、速率控制、断线重连）。
    - `connection_pool.py`：提供可配置的 `requests` 连接池，并处理代理、超时参数。
    - `proxy_client.py`：从配置或代理池中获取可用代理，支持健康检查与禁用机制。
- `patterns/`：
    - `request_batcher.py`：实现请求批处理（队列+定时触发）模式，常用于统一调用外部 API。
    - `retry_handler.py`：通用重试装饰器，支持指数退避、异常白名单、同步/异步调用。
- `system/`：
    - `port_checker.py`：检测关键端口占用情况（HTTP、ZeroMQ、Redis等），供 CLI `check-ports` 使用。
    - `redis_startup.py`：辅助启动本地 Redis、检测连接失败原因。
    - `singleton.py`：线程安全的单例元类（被配置管理等模块使用）。
- `time/market_time.py`：封装交易日历、集合竞价/连续竞价时间段判定，提供 `is_trading_time`, `get_next_session_start` 等函数。

## 使用建议

- 在基础设施层调用 `network` 与 `patterns`，实现稳定的外部请求模式；`retry_handler` 与 `request_batcher` 可组合使用。
- CLI 与脚本可依赖 `system.port_checker`、`redis_startup` 进行环境检查。
- 策略或领域层处理金融数据时，可使用 `finance.decimal_utils` 确保高精度计算。
- 行情应用层需判断交易时段时应复用 `time.market_time`，避免硬编码时区与节假日逻辑。

## 扩展方向

- 若新增数据源或代理逻辑，应在 `network` 子模块中实现并与配置配合。
- 如需支持更多交易市场，可在 `market_time.py` 扩展日历与特殊时段处理。
