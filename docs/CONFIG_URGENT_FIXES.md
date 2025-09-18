# DeepSearch 配置紧急修复清单

**生成时间**: 2025-09-18 21:45 UTC+8

## 立即修复项（生产环境）

### 1. 关闭Debug模式
**文件**: `settings.prod.yaml` 第4行
```yaml
# 修改前
debug: true
# 修改后
debug: false
```

### 2. 设置数据库强密码
**文件**: `settings.prod.yaml` 第23行
```yaml
# 修改前
password: '123456'
# 修改后
password: ${DB_PASSWORD}  # 使用环境变量
```
**环境变量**: `.env`
```bash
DB_PASSWORD=your_secure_password_min_16_chars_with_special
```

### 3. 设置Redis密码
**文件**: `settings.prod.yaml` 第32行
```yaml
# 修改前
password: ''
# 修改后
password: ${REDIS_PASSWORD}  # 使用环境变量
```
**环境变量**: `.env`
```bash
REDIS_PASSWORD=your_redis_password_min_16_chars
```

### 4. AmazingData密码环境变量
**文件**: `settings.prod.yaml` 第65行, 第101行, 第167行
```yaml
# 修改前
password: 212200038719@2025
# 修改后
password: ${AMAZINGDATA_PASSWORD}
```

### 5. 统一数据源配置
**操作**: 删除重复的amazingdata配置（第164-176行）

### 6. 增加日志保留时间
**文件**: `settings.prod.yaml` 第14行
```yaml
# 修改前
retention_days: 7
# 修改后
retention_days: 30
```

## 立即修复项（开发环境）

### 1. 数据库密码
**文件**: `settings.dev.yaml` 第23行
```yaml
# 修改前
password: '123456'
# 修改后
password: ${DB_PASSWORD:dev_password_2025}  # 开发环境可用默认值
```

### 2. 整理数据源配置
**操作**:
- 统一使用data_sources配置格式
- 调整优先级：amazingdata(1) > cloudflare(2) > akshare(3) > qmt(4)

## 执行步骤

```bash
# 1. 备份现有配置
cp deepsearch/config/settings.prod.yaml deepsearch/config/settings.prod.yaml.backup
cp deepsearch/config/settings.dev.yaml deepsearch/config/settings.dev.yaml.backup

# 2. 创建环境变量文件
cp .env.example .env

# 3. 编辑.env文件，设置实际密码

# 4. 修改配置文件，替换明文密码为环境变量

# 5. 运行验证脚本
python tools/validate_config.py --env prod
python tools/validate_config.py --env dev

# 6. 验证通过后重启服务
uv run python -m deepsearch run
```

## 验证清单

- [ ] 生产环境debug已关闭
- [ ] 数据库密码使用环境变量
- [ ] Redis密码已设置
- [ ] AmazingData凭证使用环境变量
- [ ] 配置文件无重复项
- [ ] 日志保留时间合理
- [ ] 验证脚本无错误
- [ ] 服务正常启动

## 后续优化

1. 实施密钥轮换机制
2. 添加配置加密
3. 建立配置审核流程
4. 部署配置管理系统（如Vault）
5. 添加配置变更监控