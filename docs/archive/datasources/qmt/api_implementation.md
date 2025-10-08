# QMT 接口实现概览

> 最后更新：2025-09-24

## 📌 当前状态
- ✅ 支持 MiniQMT/QMT 的行情订阅、快照推送及基础指令
- ✅ 提供 `UnifiedQMTProvider`，自动检测本地终端能力并统一路由
- ✅ 与 `EnhancedDataProviderManager` 集成，作为 AmazingData 的备份数据源
- ⏳ 特色数据（龙虎榜、北向资金等）仍在规划阶段

## 🧱 代码结构
```
deepsearch/infrastructure/providers/
├─ implementations/qmt/
│  ├─ unified_qmt_provider.py      # UnifiedQMTProvider / QMTMode
│  ├─ adapters/...
│  └─ cache/...
├─ datafeed/qmt/scripts/
│  ├─ qmt_collector.py             # GBK 版本采集脚本
│  ├─ qmt_collector_utf8.py        # UTF-8 兼容采集脚本
│  └─ README.md
└─ managers/enhanced_manager.py    # 与 QMT 集成的管理器
```

## 🔌 UnifiedQMTProvider 核心方法
| 方法 | 说明 | 状态 |
|------|------|------|
| `initialize()` | 启动终端连接、加载配置 | ✅ |
| `get_snapshot(symbols)` | 获取实时快照 | ✅ |
| `get_kline(symbol, period, start, end)` | 下载历史行情 | ✅ |
| `subscribe_quote(symbols, callback)` | 注册订阅回调 | ✅ |
| `unsubscribe_quote(symbols)` | 取消订阅 | ✅ |
| `get_special_data(data_type, **kwargs)` | 龙虎榜、北向资金等特色数据 | ⏳ |

## 🛠️ 集成方式
1. `EnhancedDataProviderManager` 在初始化阶段调用 `_init_qmt_provider()`：
   - 优先尝试标准 QMT
   - 回退到 MiniQMT（脚本模式）
2. 统一 Provider 暴露异步方法给上层使用：
   ```python
   from deepsearch.infrastructure.providers.managers.enhanced_manager import get_data_manager

   manager = await get_data_manager()
   snapshot = await manager.get_realtime_quotes(["000001", "600000"], source="qmt")
   ```
3. 缓存与批处理：结合 `SmartCacheManager` 与 `RequestBatcher`，降低终端调用频率

## 🎯 待办与规划
- [ ] 完成龙虎榜、北向资金、港股通等特色数据对接
- [ ] 为订阅接口补充断线重连与状态快照
- [ ] 增加终端运行前置检查（登录状态、网关权限）
- [ ] 扩展测试覆盖 MiniQMT 全路径

## 🧪 测试与调试
- 单元测试：`tests/unit/infrastructure/providers/qmt`
- 集成测试：`tests/integration/qmt`
- 快速验证脚本：`deepsearch/infrastructure/providers/datafeed/qmt/scripts/qmt_test.py`
- 常用命令：
  ```bash
  uv run pytest tests/integration/qmt -k "login or snapshot"
  python deepsearch/infrastructure/providers/datafeed/qmt/scripts/qmt_collector.py
  ```

## ⚠️ 注意事项
- QMT 相关脚本全部使用 **GBK** 编码，编写时需声明 `# encoding:gbk`
- 运行采集脚本需在终端所在机器执行，确保 QMT 客户端开机且保持登录
- 订阅回调需在事件循环中运行，避免阻塞主线程

---
若需回溯旧的实施计划，请查看 `docs/archive/datasources/qmt/`。
