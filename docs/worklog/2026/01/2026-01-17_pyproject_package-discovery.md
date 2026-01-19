# pyproject.toml: 启用自动包发现

> 日期: 2026-01-17
> 模块: pyproject.toml, Dask Worker
> 类型: fix | configuration

---

## 为什么要改

### 遇到的问题

Dask Worker 子进程启动时报错：

```
ModuleNotFoundError: No module named 'core.infrastructure.providers.implementations'
```

导致 amazingdata 和 miniqmt Plugin 注册失败，Dask 分布式计算功能完全不可用。

### 现有方案的问题

`pyproject.toml` 中手动列出的包列表不完整：

```toml
[tool.setuptools]
package-dir = {"core" = "packages/core", "apps" = "apps"}
packages = ["core", "apps", "apps.api"]  # 只有 3 个顶级包
```

Python 打包系统要求**显式声明每一个子包**。上述配置缺少：

- `core.infrastructure`
- `core.infrastructure.providers`
- `core.infrastructure.providers.implementations`
- ...等数十个子包

主进程能正常运行是因为 Python 直接从文件系统导入，而 Dask Worker 作为独立子进程，只能依赖正确安装的包。

---

## 尝试过的方案

### 方案 A: 手动列出所有子包

**思路**: 在 `packages = [...]` 中添加所有子包

**问题**:

- 维护噩梦：目前有 50+ 个子包，手动维护极易遗漏
- 新增子包时容易忘记更新配置
- 违反 DRY 原则

### 方案 B: 使用 setuptools 自动包发现（采用）

**思路**: 使用 `[tool.setuptools.packages.find]` 配置，让 setuptools 自动扫描发现所有包

**优点**:

- 一劳永逸，新增子包自动被发现
- 符合 Python 打包最佳实践
- 无需手动维护包列表

---

## 最终方案

### 选择: 方案 B - 自动包发现

**原因**: 彻底解决问题，无维护负担，符合社区最佳实践

### 关键改动

#### 文件: `pyproject.toml`

```toml
# 改之前
[tool.setuptools]
package-dir = {"core" = "packages/core", "apps" = "apps"}
packages = ["core", "apps", "apps.api"]

# 改之后
[tool.setuptools]
package-dir = {"core" = "packages/core", "apps" = "apps"}

[tool.setuptools.packages.find]
where = ["packages", "."]
include = ["core*", "apps*"]
exclude = ["tests*", "docs*", "scripts*"]
```

**为什么这样改**:

- `where`: 指定扫描目录（packages 目录下的 core，根目录下的 apps）
- `include`: 使用 glob 模式包含所有 core 和 apps 开头的包
- `exclude`: 排除测试、文档等非代码目录

---

## 注意事项

### 这个方案的局限

- 依赖 `__init__.py` 文件存在（Python 3.3+ 的 namespace packages 除外）
- 如果目录结构不规范（如非标准的包命名），可能需要调整 include/exclude 模式

### 如果要改回去

不建议改回手动列出的方式。如果必须改回：

1. 使用 `python -c "import setuptools; print(setuptools.find_packages())"` 获取完整包列表
2. 每次新增子包都要更新配置

### 验证命令

修改后需要执行以下命令使配置生效：

```bash
uv sync
```

验证成功的标志是日志中出现：

```
状态转换: starting -> registering
amazingdata Plugin 已注册
miniqmt Plugin 已注册
状态转换: registering -> running
```

---

## 关键结论

> 使用 `setuptools.packages.find` 自动发现包，而不是手动维护包列表。这是 Python 打包的标准做法，可以避免子模块导入失败的问题。
