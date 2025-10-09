# AmazingData 模块硬化与自检改良方案

## 背景
AmazingData 是 DeepSearch 的核心数据源，当前启动流程在配置缺失或环境异常时仅记录「SystemExit」并自动降级，导致：
- 默认空配置被悄悄使用（例如 localhost:8888、空用户名），问题难以及时发现；
- TGW 初始化、推送端口、认证凭证的错误信息分散在不同日志中，排障成本高；
- 缺乏标准化的运行前自检，部署流程无法保证环境已经准备就绪。

为确保数据模块高可用，需要从配置、检测、监控、工具和文档五个方面系统加固。

## 改良目标
1. 启动前即阻断错误配置：核心字段缺失或显然无效时直接终止启动，并提示修复路径。
2. 运行前自检标准化：一条命令即可确认配置、端口、TGW 环境是否满足要求。
3. 告警信息具象化：将 TGW/SDK 的真实错误提示同步到 DeepSearch 日志与监控告警。
4. 部署与运维流程固化：提供脚本、文档、检查清单，降低多环境部署的出错率。
5. 验证闭环：新增测试用例与人工验证步骤，保证改良措施可长期维持。

## 改良项明细

### 1. 配置层硬校验
- Settings 校验：在 deepsearch/config/settings.py 中对 amazingdata.connection 的 username、password、host、port 做非空与格式校验，命中默认值时立即抛出 ValidationError。
- ProviderRegistry 兜底：若 provider_info.config 缺失关键信息，则拒绝创建实例，并在日志中指明配置文件路径。
- 示例文件提示：在 settings.<env>.yaml.example 中补充醒目注释，提醒复制后务必填写真实凭证。
### 2. 启动前自检命令
- 新增命令「uv run python -m deepsearch check-amazingdata」：
  - 校验配置文件存在性与字段完整性；
  - 检查 tgw.ini、授权文件是否存在且可读；
  - 使用 TCP 探测确认 host:port 可访问；
  - 输出 TGW 最近日志的关键行；
  - 以结构化结果呈现通过/失败/修复建议。
- 在 docs/development 目录补充部署流程说明，明确启动前必须执行自检并通过。

### 3. 告警与日志增强
- 在 AmazingDataProvider._login 失败流程中：
  - 自动抓取 TGW 日志最新若干行并附加到 SDK_EXIT 告警文本；
  - 若检测到常见错误（用户名为空、端口不可达等），追加定位提示与文档链接。
- ProviderHealthMonitor 增加故障标签，例如 MISSING_CONFIG、TGW_NETWORK_MODE_ERROR、PORT_UNREACHABLE，便于监控面板分类统筹。
- 将降级日志提升到 ERROR 级别，并在消息中明确推荐检查的配置文件。
### 4. 工具与文档
- 脚本：新增 scripts/check_amazingdata_env.py 与 scripts/check_amazingdata_env.ps1，封装端口检测、配置校验、日志提取，可独立运行。
- 文档：
  - 在 docs/development/BEST_PRACTICES.md 增加《AmazingData 环境准备与排障》章节；
  - 在 docs/operations 添加入侵检测与运维排查清单。
- 流程固化：在 README 与部署手册中加入“复制配置模板 → 填写凭证 → 运行自检 → 启动服务”的标准步骤。

### 5. 测试与验证
- 单元测试：
  - 为 Settings 校验编写测试，确保缺失字段时抛出异常；
  - 为自检命令模拟缺配置、端口拒绝、日志缺失等场景，校验输出。
- 集成测试：
  - 模拟登录失败，确认告警文本包含 TGW 日志片段；
  - 验证 ProviderHealthMonitor 正确写入故障标签。
- 人工验证清单：
  1. 复制 settings.prod.yaml.example，填入合法凭证；
  2. 运行「uv run python -m deepsearch check-amazingdata」，确保全部 PASS；
  3. 启动主进程，确认无 SDK_EXIT 告警且数据源为 AmazingData；
  4. 人为置空用户名，确认自检和启动逻辑会立即阻断。
## 实施计划
| 阶段 | 工作内容 | 负责人 | 预计耗时 |
| ---- | -------- | ------ | -------- |
| 第 1 阶段 | Settings 校验、ProviderRegistry 兜底、自检命令骨架 | Backend | 1 周 |
| 第 2 阶段 | 告警增强、TGW 日志整合、脚本工具 | Backend + Ops | 1 周 |
| 第 3 阶段 | 文档补全、测试用例、流程手册 | Backend + QA | 3 天 |
| 第 4 阶段 | 集成验证与回归，打包发布说明 | Backend + Ops | 3 天 |

## 风险与缓解
- 现有环境可能仍依赖旧默认配置：部署前通知业务团队准备真实凭证，必要时提供迁移脚本。
- 自检命令初期覆盖有限：保持模块化输出，方便运维补充定制检查项。
- TGW 日志读取权限：若部署账号权限不足，在运维手册中提前说明权限要求。

## 落地后的维护建议
- 在 CI/CD 流程中加入自检命令，阻止缺配置的变更上线。
- 每次 AmazingData SDK 升级后同步更新自检脚本与文档，确保兼容新的日志格式或配置项。
- 定期回顾 ProviderHealthMonitor 告警统计，根据故障标签调整运维重点与演练频率。

## 进度记录
- 2025-10-01：已确认优先推进配置层硬校验路线，准备为 Settings、ProviderRegistry 与示例配置补齐严格校验逻辑，目标为阻断默认凭证误用。
- 2025-10-01：完成 Settings 初始化异常前置终止、AmazingData 连接配置启用校验，以及 ProviderRegistry 阻断默认凭证降级；示例配置文件同步加入显著提示。
- 2025-10-01：新增 `deepsearch check-amazingdata` 自检命令骨架，实现配置加载、占位符校验与基础 TCP 连通性检测，后续阶段将补充日志抓取与更多诊断项。
- 2025-10-01：为 AmazingData 配置新增 `tgw_log_path`，自检输出最近 TGW 日志片段，并在运行期告警中附带日志摘录，完成第 1 阶段的 TGW 日志整合。
