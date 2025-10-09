# 在 Python 3.13 主环境下运行 AmazingData 的隔离方案

> 更新时间：2025-10-10  
> 适用场景：主框架运行在 Python 3.13，需通过 Python 3.9 Worker 调用 AmazingData SDK（V1.0.8 及以上）

## 背景
- 主系统要求使用 Python 3.13.7。  
- 银河证券星耀数智数据源（AmazingData）依赖 `tgw` 扩展；现有 SDK 仅提供 Python ≤3.9 的 `_tgw.pyd`。  
- 为保持主系统版本同时使用官方 SDK，需要将数据源逻辑隔离到兼容的解释器中。  
- 仓库已内置 `deepsearch/infrastructure/providers/implementations/amazingdata/py39_worker.py` 作为 3.9 Worker，需要准备独立解释器并配置运行路径。

## 方案概览
1. **独立解释器**：使用 `uv` 创建一个 Python 3.9 虚拟环境，专门承载 AmazingData/TGW。  
2. **子进程桥接**：主进程通过进程间通信（IPC）调用子进程执行数据请求。  
3. **接口保持不变**：对外 API/服务接口仍由 3.13 主进程提供，底层改为 RPC 调用。

## 实施步骤

### 1. 准备目录结构
- 推荐在仓库下创建 `runtime/interpreters/py39/` 作为 3.9 环境目录。  
- 确保 `.gitignore` 忽略该目录，避免误提交。

### 2. 创建 Python 3.9 虚拟环境
```powershell
uv venv --python 3.9 runtime/interpreters/py39
```
- `uv` 会自动下载/准备 Python 3.9 解释器，并生成独立虚拟环境。

### 3. 安装 AmazingData 依赖
- 建议在仓库中新增 `requirements-amazingdata.txt`，内容至少包含：
  ```
  AmazingData==1.0.10
  ```
- 进入虚拟环境安装：
  ```powershell
  runtime\interpreters\py39\Scripts\python -m pip install -r requirements-amazingdata.txt
  ```
- 安装完成后，确认 `runtime/interpreters/py39/Lib/site-packages/tgw/win_py39_x64_package/_tgw.pyd` 存在。

### 4. 实现子进程 Worker
- 复用现有 `AmazingDataProcessProxy` 架构，增加“解释器路径”参数：  
  - 主进程调用时将 Python 路径指向 `runtime/interpreters/py39/Scripts/python.exe`。  
  - Worker 内保持当前逻辑（导入 `AmazingData`、执行登录/查询），仅补充运行状态上报。  
- IPC 渠道：继续使用 `multiprocessing.Manager().Queue()` 或 ZeroMQ，确保序列化格式兼容。

### 5. 调整主进程调用
- 在统一数据源管理器 `EnhancedDataProviderManager` 中，实例化 `AmazingDataProcessProxy` 时传入 3.9 解释器路径。  
- 保障异常处理：若子进程无法启动，需返回明确错误并触发降级/告警。

### 6. 部署与运行
- 启动脚本需在主机上同时准备两个虚拟环境：  
  - 主环境：使用 `uv` 的默认 `.venv`（Python 3.13.7）。  
  - 子环境：`runtime/interpreters/py39`。  
- 运行时，主进程照常通过 `uv run python -m deepsearch ...` 启动；子进程由系统自动管理。

### 7. 运维与监控
- 为子进程增加健康检查与重启策略，避免长时间卡死。  
- 在日志系统中区分 3.9 Worker 的日志前缀，便于排障。  
- 定期同步 `requirements-amazingdata.txt` 与 `uv.lock`，保持依赖一致性。

## 注意事项
- 两个虚拟环境需保持隔离，避免将 3.9 依赖装进主环境。  
- 子进程编码与区域设置应与主进程一致，防止中文日志乱码。  
- 若未来 TGW 发布支持 3.13 的版本，可回退至单环境部署并移除子进程逻辑。

## 配置注意事项
- 在 `settings.*.yaml` 中配置 `amazingdata.connection.python_interpreter_path` 指向 Python 3.9 解释器，例如 `runtime/interpreters/py39/Scripts/python.exe`。  
- 如需为 Worker 注入额外环境变量，可通过 `amazingdata.worker_env` 定义键值对，并在启动时传递给子进程。  
- 配置改动需同步更新 `docs/overview/document_index.md` 与 PR 描述，确保团队知晓差异化部署。
