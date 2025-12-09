# 2025-11-09 AmazingData InfoData.get_stock_basic 阻塞复盘

## 起因

- 实时行情后台为保证板块字段齐全，会在 `ProcessIsolatedAmazingDataProvider.get_stock_list` 的尾部，通过
  `_fetch_board_metadata` 再次调用 InfoData 接口补充元数据（
  `deepsearch/infrastructure/providers/implementations/amazingdata/process/runtime.py:898` 以后）。
- `_fetch_board_metadata` 不区分批次，直接把刚刚获取到的全部沪深 A 股代码（通常 4000+ 条）封装成一次
  `ProcessCommand(method="InfoData.get_stock_basic")`，并沿用 `ProcessCommand.timeout` 默认值 30s（
  `deepsearch/ports/amazingdata_process.py:35`）。
- 处理该命令的 `AmazingDataProcessProxy` 只有一个 worker，会强制把 `is_local` 设为 False，绕过 SDK
  的本地缓存，导致所有数据都从远程服务器重新下载（
  `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_process_proxy.py:1423`）。
- 当 InfoData 远程请求网络抖动或磁盘 I/O 拖慢时，worker 没有任何可中断机制，只能同步阻塞；控制端虽然 30s 后会报超时并重试 3
  次，但 worker 仍卡死，后续命令排队堆积。

## 经过

1. WebUI 调用 `GET /api/amazingdata/stock-list` -> provider 触发 `get_stock_list`。
2. `get_stock_list` 在 BaseData 分支获取证券列表成功，但检测到记录缺少 `board` 字段，于是调用 `_fetch_board_metadata`。
3. `_fetch_board_metadata` 构造一次超大 `code_list` 的 `InfoData.get_stock_basic` 请求，此时 worker 会：
    - 强制远程拉取（`is_local=False`），绕过本地缓存；
    - 在 `_worker_loop` 中同步执行，直到 InfoData 返回（`amazingdata_process_proxy.py:1407-1456`）。
4. 若 InfoData 迟迟不返回（网络、服务器限流、磁盘慢），worker 一直阻塞；主进程等待 30s 后得到 “Request timeout after 30s”
   并开始下一次尝试，共 3 轮 ≈ 90s。
5. 由于 worker 仍占用在首个调用里，新的命令（例如后续兜底的 `BaseData.get_code_info` 或其他前端请求）无法入队执行，整个数据源进程被拖死，WebUI
   大量接口最终超时或 500。

## 结果

- 前端所有依赖 AmazingData 的接口都处于排队/超时报错状态，表现为 WebUI 列表加载失败、报 “后端 500”。
- 数据源进程无法处理新的订阅/查询，辅助兜底逻辑也无法执行，导致即使超时后切换 BaseData 分支，也拿不到结果。
- 日志特征：
    - `data/logs/datasource/amazingdata_worker_*.log` 最后一条为
      `InfoData call invoking method=InfoData.get_stock_basic`，之后无其他调用。
    - 主流程日志反复出现 `Request timeout after 30s`、
      `AmazingData execute exhausted retries method=InfoData.get_stock_basic`，并伴随 Web API 500。

## 构建处理方法

1. **调用拆分与并发控制**
    - 在 `_fetch_board_metadata` 中对 `code_list` 做分片（例如 200 条一批），并在 `ProcessCommand.timeout` 上施加更短的
      per-batch 超时；通过 `asyncio.gather` 或受控并发执行，避免单次长阻塞。
    - 记录每批失败的 symbol，并将剩余 symbol 尽快 fallback 到 `BaseData.get_code_info`，保证主流程可回退。

2. **恢复/引入本地缓存**
    - 允许 InfoData 复用 SDK 的离线缓存：将 `is_local` 默认值改为 “优先本地、失败再远程”（可通过 CachePolicy 按需覆盖），或在
      provider 层维护只读快取。
    - 按天生成板块缓存（可复用 `resolve_local_cache_path`），让 `_fetch_board_metadata` 直接读取最新缓存，减少对 InfoData
      的同步依赖。

3. **worker 看门狗与熔断**
    - 在 `AmazingDataProcessProxy._execute_local/_worker_loop` 内添加 per-call watchdog：若超过阈值仍未返回，主进程直接销毁
      worker 并重建，避免单次卡死拖垮整个池子。
    - 结合 `ProcessPool` 的健康检查，把连续超时视为严重异常，触发报警与自动重启。

4. **监控与限流**
    - 统计 `InfoData.get_stock_basic` 的请求体大小、耗时分位，在 Prometheus/日志中落地；当单次 symbol 数量过大时提前限流或分批。
    - WebUI 层对 AmazingData 状态做兜底：当检测到进程不可用时，提示用户稍后再试并禁用重复按钮，避免形成流量放大。

5. **应急策略**
    - 在 provider 层保留 `BaseData.get_code_info` 的快速路径，并允许跳过板块补全（以返回“缺板块”的数据为代价）来保证页面可加载。
    - 文档化一键切换到 Mock/只读缓存模式的流程，确保下次阻塞时能迅速恢复前端可用性。

以上措施结合实施，可以从源头减少大请求、让 SDK 有缓存可用，并在进程侧提供超时保护，避免 `InfoData.get_stock_basic` 成为单点阻塞。
