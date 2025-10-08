# 2025-09-21 运行时异步引擎代码审查记录

## 问题一：WebUI 模式重复启动后端服务
- **现象**：执行命令 uv run python -m deepsearch run --mode webui 时，MainEngine 先通过 AsyncRunner._start_webui_mode 直接创建 WebUI 服务，随后 WebUIRunner 再调用 _run_backend_server() 绑定同一端口，触发端口占用报错。
- **原因**：AsyncRunner._start_webui_mode 将 include_webui 参数硬编码为 True，破坏了“引擎负责基础设施，WebUIRunner 负责可视化”的原有边界。
- **解决方案**：恢复 include_webui 的默认值为 False，并允许通过配置显式开启。这样在默认流程中仍由 WebUIRunner 独立管理 WebUI 生命周期。

## 问题二：生产配置意外禁用 AmazingData 数据源
- **现象**：deepsearch/config/settings.prod.yaml 中将 amazingdata.enabled 设置为 false，启动生产环境后无任何数据源可用。
- **原因**：手动禁用了默认启用的 AmazingData 数据源，违反《数据源策略》中“优先使用 AmazingData，如无法满足再回退 AkShare”的要求。
- **解决方案**：重新启用 amazingdata，并保持其他未批准供应商为禁用状态，确保环境仍符合单数据源策略。

## 问题三：网关组件缺少消息总线兜底逻辑
- **现象**：GatewayComponent 在初始化时直接要求上下文中存在并已初始化的 message_bus 组件，单元测试或手工脚本未准备上下文时会报 ComponentLifecycleError。
- **原因**：新实现强制依赖 ApplicationContext，没有考虑在精简环境下运行网关的场景。
- **解决方案**：在无法解析到消息总线时回退到默认的内存消息总线实现，同时输出警告日志，保持与旧版本相同的容错能力。

## 验证说明
- 通过静态检查和代码追踪确认每个问题的触发路径。
- 修改后重新阅读执行路径，确保恢复原有职责边界并符合 AmazingData 单数据源策略。

## 后续建议
1. 为 WebUI 模式补充端到端测试，覆盖 WebUIRunner 与引擎之间的职责划分。
2. 在配置加载阶段增加数据源校验，避免生产配置意外禁用所有 provider。
3. 针对 GatewayComponent 编写最小化集成测试，验证在无全局上下文时仍能成功实例化。

