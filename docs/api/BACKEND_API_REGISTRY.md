# 后端API接口文档
更新时间：2025-09-13 00:36:44

## 概述
本文档记录了所有后端API路由定义。

- 总模块数：8
- 总接口数：25

## base

文件：`webui/api/base.py`

| 函数名 | 路由路径 | 方法 |
|--------|----------|------|

## database

文件：`webui/api/database.py`

| 函数名 | 路由路径 | 方法 |
|--------|----------|------|
| get_database_status | /api/status | GET |
| connect_database | /api/connect | POST |
| disconnect_database | /api/disconnect | POST |
| reconnect_database | /api/reconnect | POST |
| get_database_tables | /api/tables | GET |

## errors

文件：`webui/api/errors.py`

| 函数名 | 路由路径 | 方法 |
|--------|----------|------|
| log_frontend_error | /api/errors | POST |
| get_frontend_errors | /api/errors | GET |
| clear_frontend_errors | /api/errors | DELETE |
| error_event_stream | /api/errors/stream | GET |
| get_error_stats | /api/errors/stats | GET |

## exception_handlers

文件：`webui/api/exception_handlers.py`

| 函数名 | 路由路径 | 方法 |
|--------|----------|------|

## providers

文件：`webui/api/providers.py`

| 函数名 | 路由路径 | 方法 |
|--------|----------|------|

## proxy

文件：`webui/api/proxy.py`

| 函数名 | 路由路径 | 方法 |
|--------|----------|------|
| get_status | /api/status | GET |
| update_config | /api/config | POST |
| toggle_proxy | /api/toggle | POST |
| test_connection | /api/test | GET |
| clear_cache | /api/clear-cache | POST |
| reset_statistics | /api/reset-statistics | POST |
| list_workers | /api/workers | GET |
| test_worker | /api/workers/{worker_id}/test | POST |
| reset_worker | /api/workers/{worker_id}/reset | POST |
| get_strategy | /api/strategy | GET |

## stock_comment

文件：`webui/api/stock_comment.py`

| 函数名 | 路由路径 | 方法 |
|--------|----------|------|
| get_stock_comment_list | /api/list | GET |
| get_stock_detail | /api/detail/{symbol} | GET |
| get_fund_flow | /api/fund-flow | GET |
| get_intraday_desire | /api/intraday-desire/{symbol} | GET |
| export_stock_comment | /api/export | GET |

## utils

文件：`webui/api/utils.py`

| 函数名 | 路由路径 | 方法 |
|--------|----------|------|

