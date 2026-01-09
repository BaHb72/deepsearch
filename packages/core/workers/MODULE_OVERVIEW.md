# Workers 模块概览

## 模块定位

`deepsearch/workers` 管理 Cloudflare Workers 代理服务以及相关的数据模型。该模块负责将 AkShare 等数据请求通过 Workers
转发，提供缓存、统计和健康检测能力，供后端或 CLI 在需要时启用云端代理。

## 核心组件

- `models.py`
  - `WorkersConfig`：Workers 运行配置（开关、URL、超时、重试、缓存、API Key 等）。
  - `ProxyStatus`、`ProxyStatistics`、`ProxyTestResult`：跟踪代理状态、请求统计与健康检查结果。
  - `AkShareRequest/AkShareResponse`：包装 AkShare API 请求/响应，包含源、响应时间、缓存标记等元信息。
- `proxy_manager.py`
  - `WorkersProxyManager`：核心管理类，负责会话管理、请求转发、缓存、统计、故障降级。
    - `initialize()/shutdown()`：创建/关闭 `aiohttp` 会话。
    - `test_connection()`：测试 Workers 可用性（HTTP 调用 + 响应解析）。
    - `request_akshare()`：根据配置在 Workers 与直接访问之间切换，处理缓存、重试和错误记录。
    - 提供 `enable/disable/toggle`、`clear_cache`、`get_status`、`reset_statistics` 等辅助方法。
  - 内置简单缓存（按 AkShare 函数 + 参数生成 key，TTL 默认为 `cache_ttl`），并维护命中状态。
  - 统计指标包括总请求数、成功/失败次数、平均响应时间、回退次数等。

## 使用流程

1. 根据配置实例化 `WorkersProxyManager` 并调用 `initialize()`；若启用自动测试会发起一次健康检查。
2. 外部在发起 AkShare 请求时调用 `request_akshare(function, params)`：
    - 如果 Workers 被启用且可用，优先通过 Workers 转发；
    - 当 Workers 不可用或请求失败时自动回退到本地/直连模式 (`fallback_to_direct`)。
3. 请求结果或错误信息会被缓存并写入 `ProxyStatistics`，可通过 `get_status()` 查询。
4. 停止服务时调用 `shutdown()` 关闭 HTTP 会话。

## 扩展建议

- 可在 `WorkersProxyManager` 中增加更多 API 支持（非 AkShare 请求），或将缓存策略改为多级缓存。
- 将健康检查与监控指标接入 `observability` 模块，以便在 WebUI/CLI 中统一展示。
