# QMT Scripts 脚本目录

## ⚠️ 重要：编码要求

**本目录下的所有 Python 脚本必须使用 GBK 编码！**

这是因为 QMT 终端只支持 GBK 编码，使用其他编码会导致中文注释乱码。

### 编码规范

1. **文件编码**：必须保存为 GBK
2. **编码声明**：文件第一行必须是 `# encoding:gbk`
3. **中文注释**：使用简体中文，避免特殊字符

### 文件列表

| 文件名 | 用途 | 编码 | 状态 |
|--------|------|------|------|
| qmt_collector.py | 生产环境数据采集脚本 | GBK | ✅ 正常 |
| qmt_test.py | 测试和调试脚本 | GBK | ✅ 正常 |
| qmt_config.json | 配置文件 | UTF-8 | ✅ 正常 |

### 修改注意事项

当修改这些脚本时，请注意：

1. **使用正确的编码打开文件**

   ```python
   with open('qmt_collector.py', 'r', encoding='gbk') as f:
       content = f.read()
   ```

2. **保存时保持 GBK 编码**

   ```python
   with open('qmt_collector.py', 'w', encoding='gbk') as f:
       f.write(content)
   ```

3. **避免使用 UTF-8 特有字符**
   - ❌ 不要使用：emoji 表情、特殊符号
   - ✅ 可以使用：中文、英文、基本标点

### 最近修改记录

#### 2025-08-18

- **qmt_collector.py**
  - 修复了认证消息发送问题
  - 在 `send_message` 函数中特殊处理 AUTH 消息
  - 允许 AUTH 消息在 `g_connected=False` 时发送

### 配置说明

#### 连接配置

- **服务器地址**: 127.0.0.1
- **端口**: 9999
- **认证令牌**: prod-secure-token-change-this（生产环境请修改）

#### 认证流程

1. 建立 TCP 连接
2. 发送 AUTH 消息（包含 token 和客户端信息）
3. 等待 AUTH_RESPONSE
4. 开始数据传输

### 常见问题

#### Q: 脚本在 QMT 终端中显示乱码

A: 确保文件使用 GBK 编码保存，并且第一行有 `# encoding:gbk` 声明

#### Q: 连接失败 "Failed to send authentication"

A: 这是因为 `send_message` 函数在连接建立但未认证时拒绝发送。已在最新版本中修复。

#### Q: 每5秒重连一次

A: 这是正常的重连机制，当认证失败或连接断开时会自动重连。

### 测试方法

1. **启动 DeepSearch 系统**

   ```bash
   python -m deepsearch run --no-frontend
   ```

2. **在 QMT 终端运行脚本**
   - 打开 QMT 终端
   - 导航到脚本目录
   - 运行 `qmt_collector.py`

3. **检查连接状态**
   - 查看 DeepSearch 日志中的 "新客户端连接" 消息
   - 查看 QMT 终端输出的连接状态

### 维护指南

- 定期检查脚本编码是否正确
- 更新认证令牌为安全的值
- 根据需要调整重连延迟和批量大小参数
