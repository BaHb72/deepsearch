# 后端启动错误报告

**生成时间**：2026-01-13
**环境**：dev
**启动模式**：all mode（完整系统）
**命令**：`uv run deepsearch run dev --log-level DEBUG --no-frontend`

---

## 执行摘要

系统启动失败，在配置加载阶段遇到 ModuleNotFoundError。根本原因是配置模型 `__init__.py` 导入了不存在的 `akshare.py` 模块。

**状态**：启动阻塞（P0）
**影响**：系统完全无法启动
**修复优先级**：最高（必须立即修复）

---

## 错误详情

### 错误 #1：ModuleNotFoundError - 缺少 akshare 配置模块

**错误类型**：启动失败（P0 - 阻塞）

**错误位置**：`packages/core/config/models/__init__.py:7`

**完整堆栈**：

```
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "D:\Stock\code\deepsearch\.venv\Scripts\deepsearch.exe\__main__.py", line 10, in <module>
    sys.exit(main())
  File "D:\Stock\code\deepsearch\packages\core\main.py", line 10, in main
    cli(prog_name="deepsearch")
  File "D:\Stock\code\deepsearch\.venv\Lib\site-packages\click\core.py", line 1462, in __call__
    return self.main(*args, **kwargs)
  File "D:\Stock\code\deepsearch\.venv\Lib\site-packages\click\core.py", line 1383, in main
    rv = self.invoke(ctx)
  File "D:\Stock\code\deepsearch\.venv\Lib\site-packages\click\core.py", line 1850, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
  File "D:\Stock\code\deepsearch\.venv\Lib\site-packages\click\core.py", line 1246, in invoke
    return ctx.invoke(self.callback, **ctx.params)
  File "D:\Stock\code\deepsearch\.venv\Lib\site-packages\click\core.py", line 814, in invoke
    return callback(*args, **kwargs)
  File "D:\Stock\code\deepsearch\packages\core\cli\main.py", line 65, in run
    from core.config import get_config
  File "D:\Stock\code\deepsearch\packages\core\config\__init__.py", line 14, in <module>
    from .manager import ConfigManager, config_manager
  File "D:\Stock\code\deepsearch\packages\core\config\manager.py", line 18, in <module>
    from core.utils.system.singleton import Singleton
  File "D:\Stock\code\deepsearch\packages\core\utils\__init__.py", line 7, in <module>
    from .system.singleton import Singleton
  File "D:\Stock\code\deepsearch\packages\core\utils\system\__init__.py", line 3, in <module>
    from .redis_startup import RedisStartupError, ensure_redis_running
  File "D:\Stock\code\deepsearch\packages\core\utils\system\redis_startup.py", line 18, in <module>
    from core.config.models.database import CacheDatabaseConfig, CacheDatabaseWSLConfig
  File "D:\Stock\code\deepsearch\packages\core\config\models\__init__.py", line 7, in <module>
    from .akshare import (
ModuleNotFoundError: No module named 'core.config.models.akshare'
```

**问题分析**：

**表面问题**：

- 启动时导入 `core.config.models.akshare` 失败

**根本原因（第一性原理分析）**：

1. **模块缺失**：`packages/core/config/models/` 目录下不存在 `akshare.py` 文件
2. **导入声明过时**：`__init__.py` 第 7-15 行尝试从 `.akshare` 导入 8 个类：

   ```python
   from .akshare import (
       AkShareActorConfig,
       AkShareCacheConfig,
       AkShareCircuitBreakerConfig,
       AkShareConfig,
       AkShareDirectConfig,
       AkShareProxyConfig,
       AkShareRealtimeConfig,
   )
   ```

3. **目录结构不一致**：Glob 结果显示存在以下配置模块，但缺少 `akshare.py`：
   - `amazingdata.py` 存在
   - `qmt.py` 存在
   - **`akshare.py` 不存在**

**可能原因**：

- Monorepo v2 重构时删除了 `akshare.py` 文件，但忘记更新 `__init__.py` 导入
- AkShare 配置模型被合并到其他文件（如 `data_sources.py`），但导入未更新
- 文件被错误删除或未提交到 Git

**当前设计假设**：

- 假设每个数据源（AmazingData、MiniQMT、AkShare）都有独立的配置模块文件
- 假设配置模型与数据源实现一一对应

**是否存在更本质的解决方案**：

选项 1（临时补丁）：

- 注释掉 `__init__.py` 中的 akshare 导入

选项 2（恢复文件）：

- 创建缺失的 `akshare.py` 配置模块
- 定义所需的 8 个 Pydantic 配置类

选项 3（重构配置）：

- 检查 AkShare 配置是否已迁移到其他文件
- 更新导入路径，从实际位置导入
- 删除 `__init__.py` 中过时的导入

**建议修复方案**（符合第一性原理）：

**第一步：定位 AkShare 配置实际位置**

```powershell
# 搜索 AkShareConfig 类定义
grep -r "class AkShareConfig" packages/core/config/models/
```

**第二步：根据搜索结果决定方案**

**情况 A**：如果 AkShareConfig 在其他文件中（如 `data_sources.py`）

- 修改 `__init__.py` 第 7 行，从正确文件导入
- 示例：`from .data_sources import AkShareConfig, ...`

**情况 B**：如果 AkShareConfig 完全不存在

- 创建 `packages/core/config/models/akshare.py`
- 定义缺失的 8 个配置类（参考 `amazingdata.py` 和 `qmt.py` 的结构）
- 使用 Pydantic BaseSettings/BaseModel

**情况 C**：如果 AkShare 配置不再需要（已废弃）

- 从 `__init__.py` 删除所有 akshare 相关导入（第 7-15 行和第 76-82 行）
- 删除 `__all__` 中的 AkShare 导出
- 检查依赖此配置的代码，确认已迁移

**优先级**：P0 - 阻塞（必须立即修复）

**预计修复时间**：

- 情况 A/C：10 分钟（修改导入）
- 情况 B：30 分钟（创建配置模块）

---

## 未验证的潜在问题

由于系统在配置加载阶段失败，以下模块未能启动，可能存在额外错误：

1. **MainEngine 初始化**（未验证）
   - DI 容器构建
   - 组件注册

2. **数据源 Providers**（未验证）
   - AmazingData Provider（`packages/core/infrastructure/providers/implementations/amazingdata/`）
   - MiniQMT Provider（`packages/core/infrastructure/providers/implementations/qmt/`）
   - AkShare Provider（`packages/core/infrastructure/providers/implementations/akshare/`）

3. **Dask Worker 管理**（未验证）
   - Windows Workers 自动启动
   - 资源属性兼容性（WIN=1.0）

4. **EventEngine**（未验证）
   - 线程池初始化
   - 状态机管理

5. **FastAPI 路由**（未验证）
   - API 端点注册
   - 依赖注入

6. **数据库连接**（未验证）
   - PostgreSQL 连接池
   - asyncpg 初始化

7. **Redis 缓存**（未验证）
   - Redis 自检（auto-start Windows service/WSL）
   - 多级缓存初始化

---

## 修复后需要验证的项目

修复 ModuleNotFoundError 后，需要逐步验证以下启动流程：

**阶段 1：配置加载**

- [x] 修复 akshare 配置模块导入
- [ ] 验证配置文件加载（`settings.dev.yaml`、`infrastructure.dev.yaml`）
- [ ] 验证 Pydantic 验证通过（无 ValidationError）

**阶段 2：基础设施初始化**

- [ ] Redis 自检并启动（WSL/Windows Service）
- [ ] PostgreSQL 连接池初始化
- [ ] Dask Scheduler 连接（localhost:8786）

**阶段 3：引擎启动**

- [ ] MainEngine 初始化
- [ ] DI 容器构建（拓扑排序）
- [ ] 组件启动（Infrastructure → Business → WebUI）

**阶段 4：服务启动**

- [ ] EventEngine 启动（线程池模式）
- [ ] Dask Workers 自动启动（Windows Workers）
- [ ] FastAPI 服务器启动（端口 8000）

---

## 后续行动计划

### 立即修复（P0）

1. **修复 ModuleNotFoundError**
   - 执行搜索：`grep -r "class AkShareConfig" packages/core/config/models/`
   - 根据结果选择修复方案（A/B/C）
   - 修改 `packages/core/config/models/__init__.py`

2. **验证配置加载**
   - 再次启动：`uv run deepsearch run dev --log-level DEBUG --no-frontend`
   - 确认启动至少到达 MainEngine 初始化阶段

### 下一步（P1）

3. **收集后续错误**
   - 捕获完整启动日志
   - 记录所有 ERROR/WARNING 级别日志
   - 更新错误报告文档

4. **创建重构清单**
   - 搜索代码中的 TODO/FIXME 注释
   - 识别临时补丁代码（HACK/WORKAROUND）
   - 列出全局变量遗留问题

### 计划内（P2）

5. **优化启动流程**
   - 减少组件启动时间
   - 优化缓存预热策略
   - 改进错误提示信息

---

## 附录

### A. 相关文件路径

**配置模块**：

- `packages/core/config/models/__init__.py` - 配置模型导入
- `packages/core/config/models/*.py` - 各配置模块
- `packages/core/config/settings.dev.yaml` - 应用配置
- `packages/core/config/infrastructure.dev.yaml` - 基础设施配置

**启动入口**：

- `packages/core/cli/main.py` - CLI 入口
- `packages/core/main.py` - 主入口点

**引擎初始化**：

- `packages/core/core/runtime/engine.py` - MainEngine
- `packages/core/core/runtime/bootstrap.py` - 启动管理器
- `packages/core/core/utils/container.py` - DI 容器

### B. Git 状态参考

```
On branch dev
Changes to be committed:
  (use "git restore --staged <file>..." to unstage)
        modified:   packages/core/config/models/__init__.py  # 导入错误位置
```

### C. 环境信息

- **Python**：3.13
- **UV 版本**：最新
- **OS**：Windows
- **依赖服务状态**：
  - PostgreSQL：已启动（端口 5432）
  - Redis：已启动（端口 6379）
  - Dask Scheduler：已启动（端口 8786）

---

**报告结束**
