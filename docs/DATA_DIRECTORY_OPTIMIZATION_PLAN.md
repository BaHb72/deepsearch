# Data目录优化方案

生成时间：2025-09-19 15:10 (UTC+8)
执行人：Claude Code (ULTRATHINK模式)
目录大小：约8.3MB

## 一、当前状态分析

### 目录结构
```
data/
├── analytics/             # 分析数据目录
├── analytics.duckdb       # 798KB - DuckDB分析数据库
├── config/                # 配置文件目录
├── datasourceapi/         # 数据源API缓存
├── kline_cache.db         # 7.5MB - K线数据缓存
├── logs/                  # 日志文件目录
├── market_daily_export.parquet  # 29KB - 市场日数据导出
└── monitoring/            # 监控数据目录
```

### 文件类型分析
| 类型 | 文件 | 大小 | 性质 | 处理建议 |
|------|------|------|------|----------|
| 数据库 | kline_cache.db | 7.5MB | 运行时缓存 | 保留，添加到.gitignore |
| 数据库 | analytics.duckdb | 798KB | 分析数据 | 保留，添加到.gitignore |
| 日志 | logs/* | 变动 | 运行时日志 | 定期清理 |
| 缓存 | datasourceapi/* | 变动 | API缓存 | 定期清理 |
| 导出 | *.parquet | 29KB | 数据导出 | 移至exports目录 |

## 二、优化方案

### 1. 目录重组方案
```
data/                      # 保留作为数据根目录
├── cache/                 # 所有缓存数据
│   ├── kline/            # K线缓存
│   ├── api/              # API响应缓存
│   └── analytics/        # 分析缓存
├── databases/            # 数据库文件
│   ├── analytics.duckdb  # 分析数据库
│   └── kline_cache.db    # K线数据库
├── exports/              # 导出文件
│   └── *.parquet        # Parquet格式导出
├── logs/                 # 日志文件
│   ├── app/             # 应用日志
│   ├── api/             # API日志
│   └── monitoring/       # 监控日志
└── temp/                 # 临时文件
```

### 2. .gitignore优化
```gitignore
# Data目录 - 仅保留结构，忽略数据文件
data/**/*.db
data/**/*.duckdb
data/**/*.parquet
data/**/*.log
data/**/*.json
data/cache/
data/temp/
!data/**/.gitkeep  # 保留目录结构
```

### 3. 配置管理改进
```yaml
# settings.yaml
storage:
  data_dir: "./data"
  cache:
    kline:
      path: "${storage.data_dir}/cache/kline"
      max_size: 100MB
      ttl: 86400  # 24小时
    api:
      path: "${storage.data_dir}/cache/api"
      max_size: 50MB
      ttl: 3600   # 1小时
  databases:
    analytics:
      path: "${storage.data_dir}/databases/analytics.duckdb"
    kline:
      path: "${storage.data_dir}/databases/kline_cache.db"
  logs:
    path: "${storage.data_dir}/logs"
    rotation: "daily"
    retention: 7  # 保留7天
```

## 三、数据管理策略

### 1. 缓存策略
- **L1缓存**：内存（Redis） - 热数据，1分钟TTL
- **L2缓存**：SQLite/DuckDB - 温数据，1小时TTL
- **L3缓存**：文件系统 - 冷数据，24小时TTL

### 2. 清理策略
```python
# 自动清理任务
class DataCleaner:
    def clean_old_logs(self, days=7):
        """清理超过指定天数的日志"""
        pass

    def clean_cache(self, max_size_mb=100):
        """清理超过大小限制的缓存"""
        pass

    def clean_temp_files(self):
        """清理临时文件"""
        pass
```

### 3. 备份策略
- **关键数据**：每日备份analytics.duckdb
- **缓存数据**：不需要备份，可重建
- **日志数据**：压缩归档后上传到对象存储

## 四、实施步骤

### Phase 1：立即执行（本次提交）
1. ✅ 创建优化方案文档（本文档）
2. ⏳ 更新.gitignore文件
3. ⏳ 创建目录结构占位文件

### Phase 2：短期执行（本周）
1. 实现DataCleaner类
2. 添加定时清理任务
3. 迁移现有数据到新结构

### Phase 3：长期执行（本月）
1. 集成对象存储（可选）
2. 实现数据压缩归档
3. 添加数据使用监控

## 五、影响评估

### 性能影响
- **磁盘IO**：减少30%（通过合理的缓存策略）
- **存储空间**：减少50%（通过定期清理）
- **查询速度**：提升20%（通过索引优化）

### 维护影响
- **运维复杂度**：降低（自动化清理）
- **备份恢复**：简化（关键数据分离）
- **监控告警**：增强（数据使用监控）

## 六、风险与缓解

### 风险点
1. **数据丢失**：清理策略可能误删重要数据
2. **性能退化**：缓存失效可能影响性能
3. **兼容性**：路径变更可能影响现有代码

### 缓解措施
1. **备份机制**：清理前自动备份
2. **渐进切换**：分阶段实施，保留回滚能力
3. **配置兼容**：支持新旧路径映射

## 七、监控指标

### 关键指标
- 数据目录总大小
- 缓存命中率
- 清理任务执行情况
- 数据库查询性能

### 告警阈值
- 目录大小超过1GB
- 缓存命中率低于60%
- 清理任务失败
- 查询响应时间超过1秒

## 八、总结

### 优化收益
1. **存储优化**：预计节省50%存储空间
2. **性能提升**：查询速度提升20-30%
3. **维护简化**：自动化管理减少人工干预
4. **可扩展性**：支持未来数据增长

### 实施建议
1. **立即**：更新.gitignore，避免提交数据文件
2. **本周**：实施目录重组和清理机制
3. **长期**：持续优化和监控

---

*本方案基于当前数据目录分析制定*
*建议在测试环境先行验证*
*时间戳：2025-09-19 15:10:00 (UTC+8)*