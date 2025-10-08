# DeepSearch 模块技术说明索引

本目录按 DeepSearch 后端主要模块划分文档，覆盖架构职责、内部数据结构、运行流程与扩展方式。每个文件聚焦一个模块，推荐配合 `docs/architecture/` 与 `docs/api/` 查看跨模块交互。后续新增模块或重要改动时，请同步补充对应文档。

## 文档列表

- [core 模块](core.md)
- [event 模块](event.md)
- [gateway 模块](gateway.md)
- [infrastructure 模块](infrastructure.md)
- [messaging 模块](messaging.md)
- [observability 模块](observability.md)
- [strategies 模块](strategies.md)
- [webui 模块](webui.md)
- [cli 模块](cli.md)
- [config 模块](config.md)
- [constants 模块](constants.md)
- [data 模块](data.md)
- [debug 模块](debug.md)
- [memory 模块](memory.md)
- [utils 模块](utils.md)
- [workers 模块](workers.md)
- [backtest 模块](backtest.md)
- [tools 模块](tools.md)

> 维护约定：修改模块内部接口或引入新子系统时，请先更新对应文档，再在本索引中登记文件路径，确保团队成员可迅速了解系统结构。
