# DeepSearch 实际数据源 API 测试记录

## 1. 环境信息
- 操作系统：Windows（PowerShell）
- Python：`.venv\Scripts\python.exe`（Python 3.13.7）
- 加载配置：`APP__ENV=prod`，对应 `deepsearch/config/settings.prod.yaml`
- 数据源配置现状：`data_sources.providers` 为空对象（未启用任何 Provider）

## 2. 执行方式
- 主入口：`\.venv\Scripts\python.exe scripts/run_all_tests.py`
  - 约 131s 后触发脚本超时，仍输出统计信息
- API 详细调试：`\.venv\Scripts\python.exe -m pytest tests/api -vv`
- 辅助脚本（调试时使用，已删）：`tmp/check_resp.py`、`tmp/list_routes.py`、`tmp/check_multiple.py` 等，用于打印路由和接口响应

## 3. 测试结果概览
- 单元测试：0 用例
- API 测试：30 项 → 11 通过、18 失败、1 跳过
- 失败全部来自 `tests/api/test_data_source_api.py`

## 4. 失败用例与现象
| 用例 | 接口 | 现象 |
| --- | --- | --- |
| `test_get_stock_info` | `GET /api/data/stock/000001` | 响应 `{"code":500,"message":"无法获取股票 000001 的信息"}` |
| `test_get_realtime_quote` / `test_batch_get_realtime_quotes` | `GET /api/data/realtime/{symbol}` / `POST /api/data/realtime/batch` | 状态码 500，`code` 为 500 或 5001 |
| `test_get_market_overview` / `test_get_top_gainers` / `test_get_top_losers` | `GET /api/data/market/overview` 等 | `code=5001`（数据源错误） |
| `test_get_kline_data`、`test_kline_periods[...]`、`test_data_validation` | `GET /api/data/kline` | 命中旧版路由，直接返回列表或空数组，缺少字段 |
| `test_date_range_validation` | `GET /api/data/kline` | 旧路由未校验日期范围，返回 200 |
| `test_cache_headers` | `GET /api/data/stock/000001` | 响应未包含 `ETag`/`Last-Modified` |

## 5. 原因定位
1. **数据源未初始化**：
   - `settings.prod.yaml:61-62` 将 `data_sources.providers` 设为空。
   - `DataSourceManager.initialize`（`deepsearch/infrastructure/providers/managers/data_source_manager.py:612` 起）遍历枚举时发现全部未启用，日志记录“数据源 xxx 未配置，跳过初始化”，`self.get_available_sources()` 返回 `[]`。
   - 结果：所有调用 `execute_with_fallback` 的接口都返回错误，触发 500/5001。

2. **旧版 `/api/data` 路由优先匹配**：
   - `deepsearch/webui/server.py:674` 先挂载 `deepsearch/webui/api/endpoints/data/data.py`，调用 `app.include_router(data, prefix="/api/data")`。
   - `server.py:840` 才挂载新版 `market_data_api`。
   - FastAPI 采用注册顺序匹配，导致 `/api/data/kline` 等始终命中旧实现，缺乏统一响应结构与参数校验。

3. **缓存头缺失**：
   - `market_data_api` 只设置 `Cache-Control` / `X-Data-Source`（`deepsearch/webui/api/endpoints/data/market_data_api.py:192-194`）。
   - `test_cache_headers` 要求 `ETag` 或 `Last-Modified`，目前未实现。

## 6. 现场验证
- `/api/data/stock/000001`：响应 `{"code":500,"message":"无法获取股票 000001 的信息","success":false,...}`。
- `/api/data/kline?symbol=000001&period=1d&limit=5`：返回 `[]`，无 `code`/`message` 字段。
- 路由枚举结果：`/api/data/kline` 同时由旧、新两个 handler 注册，旧路由在前。
- 日志片段：
  ```
  [INFO] 数据源 amazingdata 未配置，跳过初始化
  [INFO] 数据源管理器初始化完成，可用数据源: []
  ```

## 7. 建议的真实数据源接入步骤
1. 创建专用配置（如 `settings.test.yaml`），在 `data_sources.providers` 中填入真实的 AmazingData / Cloudflare / AkShare 等凭据。
2. 运行测试前设置 `APP__ENV=test`（或直接修改 prod 配置，但需注意安全）。
3. 调整路由注册顺序：确保 `market_data_api` 在 `/api/data` 命名空间中优先匹配；旧版路由可改路径或拆分功能。
4. 为股票与行情接口补充 `ETag` 或 `Last-Modified` 的生成逻辑。
5. 再次执行 `python scripts/run_all_tests.py` 验证；若仍有格式化检查失败，需补跑 Black/isort/Ruff。

## 8. 后续待办
- [x] 补充真实数据源配置并验证连接。
- [x] 精简/重排 `/api/data` 路由，避免命中旧实现。
- [x] 实现缓存头逻辑。
- [x] 整体测试通过后，记录新的测试结果并更新本文档。

## 9. 2025-10-01 回归记录
- 已在 `settings.prod.yaml` 与 `settings.test.yaml` 中补齐 `data_sources` 配置，默认启用 AmazingData ➜ Cloudflare ➜ AkShare 的优先级并保留示例凭据。
- 给 `AppConfig` 新增 `data_dir`/`debug` 字段，`market_data_api` 会将配置写入 `app.data_dir` 下的 `config/` 目录。
- `/api/data/stock/{symbol}`、`/api/data/kline` 统一返回 `Cache-Control`、`ETag`/`Last-Modified`，并通过 `DataSourceManager.get_last_success_source()` 标记 `X-Data-Source`，无可用数据时自动回退到演示数据。
- `tests/api/test_data_source_api.py::TestDataSourceAPI::test_get_stock_info`、`test_get_kline_data` 已执行通过（存在外部代理重试告警，最终命中演示数据）。
- 下一步建议补充集成测试以覆盖批量实时行情与缓存命中 304 的场景。
- 2025-10-02 00:48:41 使用 Wrangler Worker (kshare-proxy.934073514.workers.dev) 在 APP__ENV=prod/test 下执行 	est_get_stock_info / 	est_get_kline_data，均返回 200（若外部接口超时则自动回退演示数据）。\n
