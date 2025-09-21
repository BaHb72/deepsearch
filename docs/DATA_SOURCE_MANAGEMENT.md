# 数据源管理系统文档

## 概述

基于星耀数智(AmazingData) API设计的完整数据源管理系统，提供了数据源的配置、管理、监控和测试功能。

## 系统架构

```
数据源管理系统
├── 前端页面 (React + TypeScript + Ant Design)
│   └── DataSourceManagement.tsx        # 管理界面
├── 后端API (FastAPI)
│   ├── datasource_management_api.py    # 管理API
│   ├── datasource_config_service.py    # 配置服务
│   └── datasource_monitor_service.py   # 监控服务
└── 数据接口层
    ├── base.py                         # 接口定义
    ├── amazingdata_impl.py             # 星耀数智实现
    └── cache.py                        # 缓存机制
```

## 功能特性

### 1. 数据源管理

#### 支持的数据源类型
- **星耀数智 (AmazingData)** - 中国银河证券官方数据源
- **AkShare** - 开源财经数据接口
- **QMT** - 迅投QMT交易系统
- **Tushare** - 金融数据接口

#### 管理功能
- **添加数据源** - 配置新的数据源连接
- **编辑配置** - 修改现有数据源设置
- **删除数据源** - 移除不需要的数据源
- **启用/禁用** - 控制数据源的激活状态
- **优先级设置** - 设置数据源的使用优先级

### 2. 连接配置

#### 星耀数智配置项
```yaml
基本配置:
  - 服务器地址: 120.86.124.106
  - 端口: 8600
  - 用户名: 必需
  - 密码: 必需（加密存储）

高级配置:
  - 连接超时: 30秒
  - 最大重试: 3次
  - 心跳间隔: 60秒
  - 自动重连: 启用
  - 本地缓存路径: D://AmazingData_local_data//

缓存配置:
  - 启用缓存: 是
  - 缓存TTL: 300秒
  - 缓存层级: L1(内存) + L2(Redis)
```

### 3. 实时监控

#### 监控指标
- **连接状态** - 实时显示连接健康状况
- **查询统计** - 总查询数、错误数、成功率
- **性能指标** - 平均延迟、P95、P99延迟
- **缓存性能** - 命中率、命中数、未命中数
- **运行时间** - 数据源持续运行时间

#### 告警机制
- 高延迟告警（>1000ms）
- 高错误率告警（>10%）
- 连续错误告警（连续3次失败）
- 低缓存命中率告警（<50%）

### 4. 数据权限

#### 星耀数智数据权限
- ✅ Level1 实时行情
- ✅ Level2 逐笔数据（需额外授权）
- ✅ 历史K线数据（日/周/月/分钟）
- ✅ 财务报表数据（资产负债表、利润表、现金流量表）
- ✅ 主要财务指标
- ✅ 股东数据（十大股东、十大流通股东）
- ✅ 龙虎榜数据
- ✅ 北向资金数据
- ✅ 融资融券数据
- ✅ 大宗交易数据

## 使用指南

### 1. 访问管理页面

```
URL: http://localhost:3000/data-source-management
```

### 2. 添加数据源

1. 点击"添加数据源"按钮
2. 填写基本信息：
   - 名称：例如"生产环境-星耀数智"
   - 类型：选择"星耀数智"
   - 服务器：120.86.124.106
   - 端口：8600
   - 用户名/密码：您的认证信息
3. 配置高级选项（可选）
4. 点击"确定"保存

### 3. 测试连接

1. 在数据源列表中找到目标数据源
2. 点击"测试连接"按钮
3. 查看测试结果：
   - 连接延迟
   - 数据权限
   - 错误信息（如有）

### 4. 监控数据源

1. 点击"查看详情"按钮
2. 查看三个标签页：
   - **概览** - 基本信息和连接状态
   - **统计** - 查询统计和性能指标
   - **配置** - 详细配置参数

## API接口

### RESTful API端点

```
GET    /api/datasource/list              # 获取数据源列表
POST   /api/datasource/add               # 添加数据源
PUT    /api/datasource/update/{id}       # 更新数据源
DELETE /api/datasource/delete/{id}       # 删除数据源
POST   /api/datasource/toggle/{id}       # 切换启用状态
POST   /api/datasource/test/{id}         # 测试连接
GET    /api/datasource/statistics/{id}   # 获取统计信息
GET    /api/datasource/health/{id}       # 健康检查
POST   /api/datasource/batch-test        # 批量测试
```

### 数据接口使用示例

```python
from deepsearch.interfaces.data import (
    AmazingDataProvider,
    AmazingDataConfig,
    SecurityType,
    PeriodType
)

# 创建配置
config = AmazingDataConfig(
    username="your_username",
    password="your_password",
    host="120.86.124.106",
    port=8600
)

# 初始化提供者
provider = AmazingDataProvider(config)
await provider.initialize()

# 获取数据
stock_list = await provider.get_code_list(SecurityType.STOCK_A)
kline_df = await provider.get_kline('000001', PeriodType.DAILY)
snapshot = await provider.get_snapshot(['000001', '600000'])
```

## 配置管理

### 配置文件位置
```
config/datasources/
├── datasources.yaml    # 主配置文件
├── backups/           # 配置备份
└── .key               # 加密密钥
```

### 配置示例
```yaml
version: '1.0'
updated_at: '2025-01-15T10:00:00'
datasources:
  - id: 'uuid-1234'
    name: '生产环境-星耀数智'
    type: 'amazingdata'
    enabled: true
    priority: 1
    config:
      host: '120.86.124.106'
      port: 8600
      username: 'user001'
      password: 'encrypted:xxxxx'  # 加密存储
      cacheEnabled: true
      cacheTTL: 300
```

## 性能优化

### 1. 缓存策略
- L1缓存：内存LRU缓存，1000条记录
- L2缓存：Redis缓存（可选）
- 缓存键：自动生成，包含查询参数
- 过期策略：TTL + LRU淘汰

### 2. 连接池
- 复用连接，减少建立开销
- 自动重连机制
- 心跳保活

### 3. 批量查询
- 支持批量获取多个股票数据
- 异步并发处理
- 自动限流保护

### 4. 监控优化
- 异步监控，不影响主流程
- 采样监控，降低开销
- 告警聚合，避免告警风暴

## 故障处理

### 常见问题

#### 1. 连接失败
- 检查网络连通性
- 验证服务器地址和端口
- 确认用户名密码正确
- 检查防火墙设置

#### 2. 数据权限不足
- 确认账户权限等级
- 检查是否需要额外授权
- 联系数据提供商

#### 3. 高延迟问题
- 检查网络质量
- 启用本地缓存
- 调整批量查询大小
- 使用就近的服务器节点

#### 4. 缓存未生效
- 确认缓存已启用
- 检查Redis连接（如使用）
- 查看缓存命中率
- 调整缓存TTL

## 安全性

### 1. 认证安全
- 密码加密存储（AES-256）
- 密钥文件保护
- 支持环境变量配置

### 2. 传输安全
- HTTPS/TLS加密传输
- 请求签名验证
- 防重放攻击

### 3. 访问控制
- 基于角色的权限管理
- API访问限流
- 审计日志记录

## 扩展开发

### 添加新数据源

1. 实现数据接口：
```python
from deepsearch.interfaces.data.base import ICompleteDataProvider

class NewDataProvider(ICompleteDataProvider):
    async def initialize(self):
        # 初始化逻辑
        pass

    # 实现其他接口方法
```

2. 注册到管理器：
```python
manager.register_provider('new_source', NewDataProvider)
```

3. 更新前端配置：
```typescript
dataSourceTypes['new_source'] = {
    name: '新数据源',
    icon: <Icon />,
    color: '#color',
    fields: ['host', 'port']
}
```

## 最佳实践

1. **定期测试连接** - 确保数据源可用性
2. **合理设置优先级** - 根据数据质量和成本
3. **启用缓存** - 提高查询性能
4. **监控告警** - 及时发现问题
5. **定期备份配置** - 防止配置丢失
6. **加密敏感信息** - 保护认证信息
7. **记录操作日志** - 便于问题追踪
8. **性能基准测试** - 了解数据源性能

---

*文档版本：1.0.0*
*更新日期：2025-01-15*
*作者：DeepSearch Team*