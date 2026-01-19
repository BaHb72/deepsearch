# 后端运行错误报告

**生成时间**: 2026-01-16 20:12

## 执行命令

```bash
uv run python -m apps.api.runner
```

## 错误汇总

### 1. Redis 连接失败（ERROR）

**位置**: `apps/api/runner.py:242` → 系统初始化阶段

**错误信息**:

```
Redis 连接失败: Error 22 connecting to localhost:6379. 远程计算机拒绝网络连接。
```

**影响**:

- 系统以降级模式运行（无缓存）
- 功能仍可用，但性能可能受影响

**状态**: ⚠️ 警告级别（系统已降级处理）

**解决方案**:

1. 启动 Redis 服务：`redis-server`
2. 检查 Redis 配置：确认端口为 6379
3. 或修改配置文件以禁用 Redis

---

### 2. 端口 8000 已被占用（ERROR）

**位置**: `apps/api/runner.py:242` → 后端服务启动阶段

**错误信息**:

```
端口 8000 已被占用
占用进程: python.exe (PID: 36136)
```

**影响**:

- ❌ 后端服务启动失败
- 系统自动关闭

**状态**: 🔴 致命错误（阻止服务启动）

**解决方案**:

```bash
# 方案1：清理端口（推荐）
python -m deepsearch cleanup

# 方案2：手动结束进程
taskkill /PID 36136 /F

# 方案3：修改配置端口
# 编辑 configs/settings.dev.yaml
# 修改 webui.backend_port 为其他端口（如 8001）
```

---

## 成功启动的组件

✅ **前端服务**: <http://localhost:3000>
✅ **事件引擎**: 初始化成功
✅ **消息总线**: InMemory 模式运行
✅ **数据库连接**: PostgreSQL (localhost:5432) 连接成功
✅ **健康检查**: 4 个组件已注册

---

## 系统启动流程分析

```
1. UV 编译字节码 (12178 files, 442ms) ✅
2. 加载配置文件 ✅
   - infrastructure.dev.yaml
   - market_data.dev.yaml
   - data_sources.yaml
   - settings.dev.yaml
3. 初始化核心组件 ✅
   - StatisticsCollector
   - DataSourceMonitor
   - AmazingData SDK
4. 启动前端服务 ✅
   - Vite 开发服务器 (端口 3000)
5. 初始化引擎 ✅
   - EventEngine
   - MessageBus (inmem)
   - Database (PostgreSQL)
   - Cache (降级模式) ⚠️
6. 启动后端服务 ❌
   - 端口冲突导致失败
7. 系统优雅关闭 ✅
```

---

## 技术债务与设计问题

### 问题1：相对导入在主模块中失败

**受影响文件**:

- `apps/api/server.py:1481` - `from .server_manager import get_server_manager`
- `apps/api/runner.py:27` - `from .server import app, set_engine`

**原因**:
直接运行 `python server.py` 时，Python 不将其视为包的一部分，导致相对导入失败。

**当前解决方案**:
使用 `python -m apps.api.runner` 以模块方式运行 ✅

**建议优化**:

- 创建统一的 CLI 入口点
- 或修改为绝对导入（使用 `from apps.api.server_manager import ...`）

---

### 问题2：日志乱码

**表现**:

```
[1m����Դ������ĳ�ʼ�����[0m
[1m���ڹر����η�����...[0m
```

**原因**:
Windows 控制台编码问题（GBK vs UTF-8）

**影响**:
影响可读性，但不影响功能

**建议**:
在 `runner.py` 或配置中添加：

```python
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
```

---

## 快速修复指南

### 立即修复（让系统运行起来）

```bash
# 1. 清理端口
python -m deepsearch cleanup

# 2. 启动 Redis（可选，提升性能）
redis-server

# 3. 重新运行后端
uv run python -m apps.api.runner
```

### 验证修复

访问以下地址：

- 前端: <http://localhost:3000>
- 后端: <http://localhost:8000/docs> （FastAPI 文档）

---

## 问题优先级

| 问题 | 优先级 | 影响 | 修复难度 |
|------|--------|------|---------|
| 端口占用 | 🔴 P0 | 阻止启动 | 简单（清理进程） |
| Redis 未启动 | 🟡 P1 | 性能降级 | 简单（启动服务） |
| 日志乱码 | 🟢 P2 | 影响可读性 | 中等（编码配置） |
| 相对导入设计 | 🟢 P3 | 无（已有方案） | 复杂（重构） |

---

## 附加信息

**Python 版本**: 3.13
**平台**: Windows
**包管理**: UV
**Monorepo 结构**: ✅
**依赖安装**: ✅ 所有依赖已安装
