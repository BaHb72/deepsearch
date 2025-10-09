# DeepSearch API 规范文档

## 📋 目录
- [基础约定](#基础约定)
- [URL规范](#url规范)
- [请求响应格式](#请求响应格式)
- [错误处理](#错误处理)
- [API分类与路由](#api分类与路由)
- [前后端协作流程](#前后端协作流程)

## 基础约定

### 版本控制
- API版本通过URL路径控制：`/api/v1/`（当前使用v1，未显式标注）
- 重大变更需要新版本：`/api/v2/`

### HTTP方法语义
| 方法 | 用途 | 示例 |
|------|------|------|
| GET | 获取资源 | `GET /api/data-sources` |
| POST | 创建资源/执行操作 | `POST /api/data-sources` |
| PUT | 完整更新资源 | `PUT /api/data-sources/{id}` |
| PATCH | 部分更新资源 | `PATCH /api/data-sources/{id}` |
| DELETE | 删除资源 | `DELETE /api/data-sources/{id}` |

### 认证与授权
- 当前系统未启用认证（待实现）
- 预留认证头：`Authorization: Bearer {token}`

## URL规范

### 路径结构
```
/api/{模块}/{资源}/{操作}
```

示例：
- `/api/data-sources` - 数据源列表
- `/api/data-sources/{id}` - 特定数据源
- `/api/data-sources/{id}/test` - 测试特定数据源

### 命名规范
- **使用kebab-case**：`data-sources`而非`dataSources`或`data_sources`
- **资源名用复数**：`sources`而非`source`
- **动作用动词**：`/test`、`/refresh`、`/validate`

### 查询参数
- 分页：`?page=1&size=20`
- 排序：`?sort=name&order=asc`
- 过滤：`?status=online&type=akshare`
- 时间范围：`?start_time=2025-01-01&end_time=2025-01-31`

## 请求响应格式

### 标准请求头
```http
Content-Type: application/json
Accept: application/json
X-Request-ID: uuid-v4
```

### 标准响应格式

#### 成功响应
```json
{
  "status": "success",
  "data": {
    // 实际数据
  },
  "message": "操作成功",
  "timestamp": "2025-09-17T10:30:00Z"
}
```

#### 错误响应
```json
{
  "status": "error",
  "error": {
    "code": "DATASOURCE_NOT_FOUND",
    "message": "数据源未找到",
    "details": {
      "source_id": "unknown_source"
    }
  },
  "timestamp": "2025-09-17T10:30:00Z"
}
```

#### 分页响应
```json
{
  "status": "success",
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "size": 20,
      "total": 100,
      "pages": 5
    }
  }
}
```

### 状态码规范
| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| 200 | 成功 | GET/PUT/PATCH成功 |
| 201 | 已创建 | POST创建资源成功 |
| 204 | 无内容 | DELETE成功 |
| 400 | 错误请求 | 参数验证失败 |
| 401 | 未认证 | 需要登录 |
| 403 | 禁止访问 | 权限不足 |
| 404 | 未找到 | 资源不存在 |
| 409 | 冲突 | 资源状态冲突 |
| 422 | 无法处理 | 业务逻辑错误 |
| 500 | 服务器错误 | 系统异常 |
| 503 | 服务不可用 | 系统维护/过载 |

## 错误处理

### 错误码规范
格式：`{MODULE}_{ERROR_TYPE}`

示例：
- `DATASOURCE_NOT_FOUND` - 数据源未找到
- `DATASOURCE_CONNECTION_FAILED` - 数据源连接失败
- `VALIDATION_FAILED` - 参数验证失败
- `SYSTEM_ERROR` - 系统错误

### 错误响应示例
```json
{
  "status": "error",
  "error": {
    "code": "DATASOURCE_CONNECTION_FAILED",
    "message": "无法连接到 AmazingData 数据源",
    "details": {
      "source": "amazingdata",
      "error_type": "timeout",
      "retry_after": 30
    }
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## API分类与路由

### 1. 数据源管理 (`/api/data-sources`)
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` | 获取数据源列表 |
| POST | `/` | 创建数据源 |
| GET | `/{id}` | 获取数据源详情 |
| PUT | `/{id}` | 更新数据源 |
| DELETE | `/{id}` | 删除数据源 |
| POST | `/{id}/test` | 测试数据源连接 |
| POST | `/{id}/switch` | 切换为主数据源 |
| GET | `/status` | 获取所有数据源状态 |
| GET | `/monitor` | 获取监控数据 |

### 2. 数据源监控 (`/api/monitor/datasources`)
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/health` | 健康状态 |
| GET | `/metrics` | 性能指标 |
| GET | `/statistics` | 访问统计 |
| GET | `/realtime` | 实时监控 |
| WebSocket | `/ws` | 实时推送 |

### 3. 系统管理 (`/api/system`)
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/health` | 系统健康检查 |
| GET | `/info` | 系统信息 |
| GET | `/config` | 系统配置 |
| PUT | `/config` | 更新配置 |
| GET | `/logs` | 系统日志 |

### 4. 市场数据 (`/api/market`)
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/quote/{symbol}` | 实时行情 |
| GET | `/kline/{symbol}` | K线数据 |
| GET | `/orderbook/{symbol}` | 买卖盘 |
| GET | `/trades/{symbol}` | 成交明细 |

### 5. 交易功能 (`/api/trading`)
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/strategies` | 策略列表 |
| POST | `/strategies` | 创建策略 |
| POST | `/backtest` | 运行回测 |
| GET | `/signals` | 交易信号 |

## 前后端协作流程

### 1. API开发流程
```mermaid
graph LR
    A[需求分析] --> B[API设计]
    B --> C[编写API文档]
    C --> D[后端实现]
    D --> E[前端对接]
    E --> F[联调测试]
    F --> G[更新文档]
```

### 2. 新增API检查清单
- [ ] 遵循URL命名规范
- [ ] 使用正确的HTTP方法
- [ ] 定义请求/响应格式
- [ ] 实现错误处理
- [ ] 编写API文档
- [ ] 添加到路由注册
- [ ] 前端添加对应调用
- [ ] 更新API映射文档

### 3. 前端API调用规范

#### 基础配置
```javascript
// request.js
const baseURL = '/api'
const timeout = 30000

// 请求拦截器
request.interceptors.request.use(config => {
  // 添加认证头
  // config.headers.Authorization = `Bearer ${token}`

  // 添加请求ID
  config.headers['X-Request-ID'] = generateUUID()

  return config
})

// 响应拦截器
request.interceptors.response.use(
  response => {
    const { status, data, error } = response.data

    if (status === 'success') {
      return data
    } else {
      throw new Error(error.message)
    }
  },
  error => {
    // 统一错误处理
    handleAPIError(error)
    return Promise.reject(error)
  }
)
```

#### API定义示例
```javascript
// dataSource.js
export const dataSourceAPI = {
  // 获取列表
  list: () => request.get('/data-sources'),

  // 获取详情
  get: (id) => request.get(`/data-sources/${id}`),

  // 创建
  create: (data) => request.post('/data-sources', data),

  // 更新
  update: (id, data) => request.put(`/data-sources/${id}`, data),

  // 删除
  delete: (id) => request.delete(`/data-sources/${id}`),

  // 测试连接
  test: (id) => request.post(`/data-sources/${id}/test`),

  // 获取监控数据
  monitor: () => request.get('/data-sources/monitor')
}
```

### 4. 后端API实现规范

#### 路由定义示例
```python
from fastapi import APIRouter, HTTPException
from typing import List, Optional

router = APIRouter(prefix="/api/data-sources", tags=["DataSource"])

@router.get("/", response_model=List[DataSource])
async def list_data_sources(
    status: Optional[str] = None,
    page: int = 1,
    size: int = 20
):
    """获取数据源列表"""
    try:
        # 业务逻辑
        sources = await get_sources(status, page, size)
        return {
            "status": "success",
            "data": {
                "items": sources,
                "pagination": {
                    "page": page,
                    "size": size,
                    "total": total
                }
            }
        }
    except Exception as e:
        logger.error(f"获取数据源列表失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DATASOURCE_LIST_ERROR",
                "message": str(e)
            }
        )
```

## 维护指南

### API文档更新
1. 修改API后立即更新文档
2. 运行 `python tools/generate_api_documentation.py` 生成最新映射
3. 检查前后端匹配情况
4. 更新 `DATA_SOURCE_API_MAPPING.md`

### 定期审查
- 每月检查未使用的API
- 清理废弃的端点
- 合并功能重复的API
- 优化性能瓶颈

### 版本迁移
当需要重大变更时：
1. 新建v2版本路由
2. 保持v1兼容性
3. 逐步迁移前端调用
4. 设置废弃期限
5. 最终移除旧版本

## 附录

### 常见问题

#### Q: 前端请求路径应该如何配置？
A: 使用相对路径，baseURL统一配置为 `/api`，由Vite代理转发到后端。

#### Q: 如何处理跨域问题？
A: 开发环境通过Vite代理解决，生产环境通过Nginx反向代理。

#### Q: API响应慢如何优化？
A:
1. 添加缓存层
2. 实现分页
3. 使用异步处理
4. 添加请求去重

### 相关文档
- [API映射关系](./DATA_SOURCE_API_MAPPING.md)
- [前端API使用](./frontend_mapping.md)
- [OpenAPI规范](./openapi.json)
- [统计报告](./statistics.md)