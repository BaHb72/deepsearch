# AmazingData 本地数据路径跨平台改造详细设计与实施说明

- **版本**：v1.0（方案确认稿）
- **状态**：仅文档与方案设计，尚未在仓库内执行任何代码或配置改动
- **适用范围**：AmazingData 适配器（`deepsearch/infrastructure/providers/implementations/amazingdata`），不涉及领域层及其他数据源

---

## 背景与问题定位

### 问题概述

- 代码中存在 Windows 专用硬编码本地路径 `D://AmazingData_local_data//`，导致在 macOS / Linux 环境无法直接运行，也不利于容器化和后续多平台部署。
- 相关硬编码会出现在适配器默认参数、常量定义以及示例配置中，影响可移植性。

### 已定位的主要硬编码位置（示例）

- `deepsearch/infrastructure/providers/implementations/amazingdata/common.py:13`
    - `DEFAULT_LOCAL_DATA_PATH = "D://AmazingData_local_data//"`
- `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:819`
    - `get_block_trading(..., local_path: str = DEFAULT_LOCAL_DATA_PATH, ...)`
- `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`
    - `:190-:195` `get_backward_factor(..., local_path: str = "D://AmazingData_local_data//", ...)`
    - `:226-:231` `get_adj_factor(..., local_path: str = "D://AmazingData_local_data//", ...)`
    - `:262-:267` `get_history_stock_status(..., local_path: str = "D://AmazingData_local_data//", ...)`
    - `:298-:304` `get_hist_code_list(..., local_path: str = "D://AmazingData_local_data//", ...)`
    - `:393-:395` `get_bj_code_mapping(..., local_path: str = "D://AmazingData_local_data//", ...)`
    - 注：文件后续仍有多处同类定义，实际改造时需统一检索。
- `.env.example:38`
    - `AMAZINGDATA_LOCAL_PATH=D://AmazingData_local_data//`
- `deepsearch/infrastructure/providers/implementations/amazingdata/config.py:108`
    - `resolve_local_cache_path(...)` 在缺省情况下直接回退到 `DEFAULT_LOCAL_DATA_PATH`，未考虑环境变量或平台默认路径。

---

## 目标与非目标

### 目标

- 提供跨平台、可配置的本地数据存储路径，彻底移除 Windows 专用硬编码。
- 引入统一的路径解析流程，按「方法入参 > 配置 > 环境变量 > 平台默认」的优先级解析。
- 默认路径遵循各操作系统惯例（通过 `platformdirs`），避免写死盘符和分隔符。
- 变动仅限 adapters 层，保持领域层与其他模块无感知，符合 ports + adapters 架构约束。

### 非目标

- 不变更 AmazingData SDK 的行为与接口协议。
- 不自动迁移历史数据，仅通过配置/解析器指向目标目录。

---

## 设计方案总览

### 单一解析器策略

- 在 adapters 层新增路径解析工具函数，所有需要本地缓存路径的接口统一通过解析器获取值，避免在函数签名中写死默认路径。

### 路径解析优先级（从高到低）

1. 方法入参 `local_path`（调用方显式传入）
2. Provider 配置对象（`config.local.path` 或 `config.config["local_cache_path"]` 等）
3. 环境变量 `AMAZINGDATA_LOCAL_PATH`（.env 配置）
4. 平台默认路径（`platformdirs.user_data_dir(appname="DeepSearch", appauthor="DeepSearch") / "AmazingData"`）

### 平台默认路径说明

| 平台      | 默认目录示例（实际由 `platformdirs` 决定）                          |
|---------|--------------------------------------------------------|
| Windows | `%LOCALAPPDATA%\DeepSearch\DeepSearch\AmazingData`     |
| macOS   | `~/Library/Application Support/DeepSearch/AmazingData` |
| Linux   | `~/.local/share/DeepSearch/AmazingData`                |

> 目录在首次使用时按需创建，避免 import 阶段产生副作用。

---

## 详细实施步骤

### 第 1 步：新增路径解析工具

- 位置：`deepsearch/infrastructure/providers/implementations/amazingdata/common.py`
- 新增函数示例：

```python
from pathlib import Path
from platformdirs import user_data_dir


def get_default_local_data_path() -> str:
    base = Path(user_data_dir(appname="DeepSearch", appauthor="DeepSearch"))
    return str(base.joinpath("AmazingData"))
```

- 常量兼容策略：
    - `DEFAULT_LOCAL_DATA_PATH = get_default_local_data_path()`（仅作兼容别名，代码中不再直接引用此常量，未来可标记为
      deprecated）。
    - 注释说明：「请使用统一解析器，不再直接依赖该常量」。

### 第 2 步：增强统一解析逻辑

- 位置：`deepsearch/infrastructure/providers/implementations/amazingdata/config.py:108`
- 更新 `resolve_local_cache_path` 实现，包含环境变量读取与平台默认路径回退：

```python
import os
from pathlib import Path
from .common import get_default_local_data_path


def resolve_local_cache_path(
        config: AmazingDataConfig | None,
        candidate: object | None,
) -> str:
    for item in (
            candidate,
            getattr(config, "local_path", None) if config else None,
            getattr(config, "config", {}).get("local_path") if config else None,
            getattr(config, "config", {}).get("local_cache_path") if config else None,
            os.environ.get("AMAZINGDATA_LOCAL_PATH"),
    ):
        if not item:
            continue
        text = str(item).strip()
        if text:
            return text
    return get_default_local_data_path()
```

- 解析结果不强制追加尾部分隔符，由调用者使用 `Path` 进行规范化。

### 第 3 步：替换所有方法默认参数

- 原默认值类型：`local_path: str = "D://AmazingData_local_data//"` 或 `= DEFAULT_LOCAL_DATA_PATH`
- 新写法：`local_path: str | None = None`，方法体内首行解析：

```python
local_path = resolve_local_cache_path(self.config, local_path)
Path(local_path).mkdir(parents=True, exist_ok=True)
```

- 需覆盖的位置：
    - `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:819`
    - `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py:190-:195`
    - `:226-:231`
    - `:262-:267`
    - `:298-:304`
    - `:393-:395`
    - 以及该文件内其他所有 `local_path: str = "D://AmazingData_local_data//"` 定义（建议统一检索确认）。

### 第 4 步：目录创建与路径规范化

- 在解析出最终路径后，再进行目录创建，避免 import 阶段产生副作用。
- 使用 `Path(local_path).mkdir(parents=True, exist_ok=True)`；若遇无权限或只读系统，捕获异常并转化为易读日志或
  `DataProviderError`。
- 避免在路径字符串上手动拼接分隔符，统一依靠 `Path`。

### 第 5 步：更新示例与文档

- `.env.example:38` 修改建议：

```dotenv
# AMAZINGDATA_LOCAL_PATH 可选：不设置则使用系统默认数据目录
# Windows 示例：AMAZINGDATA_LOCAL_PATH=C:\Data\AmazingData
# macOS 示例：AMAZINGDATA_LOCAL_PATH=/Users/<you>/Library/Application Support/DeepSearch/AmazingData
# Linux 示例：AMAZINGDATA_LOCAL_PATH=/home/<you>/.local/share/DeepSearch/AmazingData
AMAZINGDATA_LOCAL_PATH=
```

- `settings.<env>.yaml`（如有）可同步提供示例片段：

```yaml
providers:
  amazingdata:
    connection:
      username: ${AMAZINGDATA_USERNAME}
      password: ${AMAZINGDATA_PASSWORD}
      host: ${AMAZINGDATA_HOST}
      port: ${AMAZINGDATA_PORT}
    local:
      path: ${AMAZINGDATA_LOCAL_PATH}  # 留空则回退到系统默认目录
      use_local: ${AMAZINGDATA_USE_LOCAL}
```

- README 不增加正文内容，可视情况在文档导航中加入该文件的链接。

### 第 6 步：兼容与提示机制

- 若 `AMAZINGDATA_LOCAL_PATH` 或配置中已指定旧目录（例如 `D://AmazingData_local_data//`），系统会直接使用该路径，不影响旧环境。
- 可选增强：当使用平台默认路径且检测到旧目录仍存在时，输出一次性提示日志，建议用户迁移或者通过配置显式指向旧路径。
    - 示例日志：
        - `datasource=amazingdata 使用本地缓存目录: C:\Users\...\AmazingData`
        - `检测到历史目录 D://AmazingData_local_data//。如需复用旧数据，请设置 AMAZINGDATA_LOCAL_PATH 或迁移数据。`

### 第 7 步：测试与验证（执行阶段再落实）

- 单元测试：
    - `resolve_local_cache_path` 覆盖 candidate/config/env/默认路径四种场景。
- 集成测试：
    - 在 Windows、macOS、Linux 分别验证路径解析与目录创建行为。
- 回归测试：
    - 核心接口如 `get_hist_code_list`、`get_history_stock_status`、`get_bj_code_mapping`、`get_block_trading` 等需覆盖本地缓存读写流程。

---

## 兼容性与回滚策略

- **向后兼容**：
    - 方法签名参数名保持不变，仅将默认值移入解析器内部，调用方无需修改。
    - 若调用方显式传入旧路径或通过配置/环境变量指定路径，将被优先使用。
- **回滚方案**：
    - 如需临时代码层面回滚，可将 `resolve_local_cache_path` 的最终回退改回 `DEFAULT_LOCAL_DATA_PATH`（不推荐）。
    - 运维侧可通过环境变量或配置快速恢复到任意路径，避免影响业务。

---

## 测试计划与验收标准（说明性）

- **单元测试**
    - 新增/更新适配器层测试文件，验证不同优先级来源的解析结果是否符合预期。
- **跨平台手测**
    - 分别在 Windows / macOS / Linux 上执行典型数据拉取流程，确认默认路径与目录创建行为正常。
- **验收标准**
    - 在不设置任何配置和环境变量的前提下，三大平台均应工作正常，且不会抛出硬编码路径相关错误。
    - 设置 `.env` 或 `settings.<env>.yaml` 后，实际使用的路径需与预期一致，并在日志中可见。

---

## 运维与部署指南

- **覆盖默认路径的方式**（优先级从高到低）：
    1. 调用方在方法中显式传入 `local_path="..."`。
    2. `settings.<env>.yaml` 中配置 `providers.amazingdata.local.path`。
    3. `.env` 中设置 `AMAZINGDATA_LOCAL_PATH=/data/amazingdata`。
- **容器化建议**：
    - 将解析器返回的目录映射到持久卷，避免容器重建导致数据丢失。
    - 确保目标目录具备读写权限。
- **权限问题排查**：
    - 如遇写入失败，根据日志提示检查目录权限或改用具备写权限的路径。

---

## 风险与缓解措施

| 风险             | 影响           | 缓解策略                                          |
|----------------|--------------|-----------------------------------------------|
| 旧脚本/运维流程依赖固定路径 | 升级后可能无法找到旧数据 | 在日志中提示新路径并建议设置 `AMAZINGDATA_LOCAL_PATH` 指向旧目录 |
| 目标目录无写权限       | 数据缓存失败       | 在目录创建失败时抛出明确错误，运维调整目录或权限                      |
| 未迁移历史数据        | 需重新下载数据      | 通过提示日志提醒用户手动迁移或配置旧目录                          |

---

## 计划中的变更清单（尚未实施）

- 常量与解析
    - `deepsearch/infrastructure/providers/implementations/amazingdata/common.py:13`
        - 新增 `get_default_local_data_path()`，调整 `DEFAULT_LOCAL_DATA_PATH` 定义。
- 解析流程增强
    - `deepsearch/infrastructure/providers/implementations/amazingdata/config.py:108`
        - `resolve_local_cache_path` 增加环境变量读取与平台默认路径回退。
- 方法默认参数改造（示例）
    - `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py:819`
    - `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py:190-:395` 及其他同类方法。
- 示例配置
    - `.env.example:38` 更新注释及跨平台示例。
- 文档
    - 本文档即为改造执行与回归的详细参考。

---

## 与仓库规范的一致性说明

- 改动全部发生在 adapters 层，遵守「领域层依赖 ports + adapters」的约束。
- 不引入新的第三方依赖，`platformdirs` 已在 `pyproject.toml` 中声明。
- 不留下跨层的 `Any` / `dict[str, Any]` 长链路；路径解析结果为普通字符串，仅在适配器内部使用。
- 配置管理保持 `.env` + `settings.<env>.yaml` 的统一入口，符合仓库开发流程要求。

---

## 附录

### 附录 A：各操作系统默认路径示例

- Windows：`C:\Users\<you>\AppData\Local\DeepSearch\DeepSearch\AmazingData`
- macOS：`/Users/<you>/Library/Application Support/DeepSearch/AmazingData`
- Linux：`/home/<you>/.local/share/DeepSearch/AmazingData`

> 实际路径取决于 `platformdirs` 的实现；上述仅为常见示例。

### 附录 B：方法改造模板

- **旧模式（不推荐）**

```python
def foo(..., local_path: str = "D://AmazingData_local_data//", ...) -> ...:
```

- **新模式（推荐）**

```python
from pathlib import Path
from .config import resolve_local_cache_path

def foo(..., local_path: str | None = None, ...) -> ...:
    local_path = resolve_local_cache_path(self.config, local_path)
    Path(local_path).mkdir(parents=True, exist_ok=True)
    ...
```

### 附录 C：排查与定位命令示例

```powershell
# PowerShell 检索所有硬编码默认路径
Select-String -Path deepsearch\**\*.py -Pattern 'local_path:\s*str\s*=\s*"D://AmazingData_local_data//' -CaseSensitive
```

```bash
# Git 检索（跨平台）
git grep -n 'local_path:.*D://AmazingData_local_data//'
```

---

> 注：本文档为执行指导，后续若实现方案有迭代，请同步更新此文档并记录版本。
