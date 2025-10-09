# AmazingData 数据源配置指南

> 更新时间：2025-10-10  
> 适用版本：AmazingData Python SDK ≥ V1.0.8 / DeepSearch 主干分支

## 概述
AmazingData 是银河证券提供的星耀数智数据接口，提供全面的金融市场数据服务。

## 配置步骤

### 1. 安装 AmazingData SDK

```bash
# 使用提供的 whl 文件安装
uv pip install third_party/amazingdata/AmazingData-1.0.10-cp313-none-any.whl
```

### 2. 获取访问凭证

请联系银河证券业务人员获取：
- 用户名（username）
- 密码（password）

### 3. 选择网络接入点

AmazingData SDK 支持互联网模式，提供两个接入点：

| 运营商 | IP地址 | 端口 | 适用网络 |
|--------|--------|------|----------|
| 电信 | 101.230.159.234 | 8600 | 电信网络用户 |
| 联通 | 140.206.44.234 | 8600 | 联通网络用户 |

选择与您的网络运营商对应的接入点可获得更好的连接质量。

### 4. 配置数据源

#### 方式一：通过Web界面配置

1. 打开数据源管理页面
2. 点击"添加数据源"或编辑现有的 AmazingData 配置
3. 填写以下信息：
   - **用户名**：您的 AmazingData 用户名
   - **密码**：您的 AmazingData 密码
   - **网络运营商**：选择"电信"、"联通"或"自定义"
     - 选择电信或联通会自动填充对应的服务器地址
     - 选择自定义可手动输入服务器地址
   - **主机地址**：自动填充或手动输入
   - **端口**：8600（默认）
   - **超时时间**：30000ms（建议值）
   - **心跳间隔**：60秒（保持连接活跃）
   - **自动重连**：开启（建议）
   - **本地数据路径**：D://AmazingData_local_data//（用于缓存）
   - **使用本地数据**：开启（提高性能）

4. 点击"测试连接"验证配置
5. 保存配置

#### 方式二：通过配置文件

编辑 `deepsearch/config/settings.dev.yaml` 或 `settings.prod.yaml`：

```yaml
amazingdata:
  enabled: true  # 启用 AmazingData
  username: "your_username"  # 您的用户名
  password: "your_password"  # 您的密码
  network_provider: "telecom"  # 选择运营商: telecom|unicom|custom
  # 互联网模式服务器地址
  servers:
    telecom:
      host: "101.230.159.234"
      port: 8600
    unicom:
      host: "140.206.44.234"
      port: 8600
  # 自定义服务器地址（network_provider为custom时使用）
  host: "101.230.159.234"  # 服务器地址
  port: 8600  # 服务器端口
  timeout: 10  # 连接超时（秒）
  heartbeat_interval: 60  # 心跳间隔（秒）
  auto_reconnect: true  # 自动重连
  reconnect_interval: 10  # 重连间隔（秒）
  local_path: "D://AmazingData_local_data//"  # 本地数据路径
  use_local: true  # 使用本地缓存
  max_retries: 3  # 最大重试次数
  subscription_enabled: true  # 启用订阅功能
  subscription_batch_size: 100  # 批量订阅大小
  max_subscriptions: 500  # 最大订阅数量
```

### 5. 验证连接

启动系统后，可以通过以下方式验证：

```python
import AmazingData as ad

# 选择服务器（根据您的网络运营商）
# 电信用户
host = "101.230.159.234"
# 联通用户
# host = "140.206.44.234"

# 登录测试
result = ad.login(
    username="your_username",
    password="your_password",
    host=host,
    port=8600
)

if result == 0 or result is True:
    print("连接成功！")

    # 测试获取数据
    base_data = ad.BaseData()
    code_list = base_data.get_code_list(security_type='EXTRA_STOCK_A')
    print(f"获取到 {len(code_list)} 只股票")

    # 登出
    ad.logout()
else:
    print(f"连接失败，错误码：{result}")
```

## 深入阅读
- **快速体验**：参见 [quick_start.md](./quick_start.md)，了解从配置到首个查询的完整流程。
- **接口详情**：参阅 [api_reference.md](./api_reference.md) 与 [data_types.md](./data_types.md) 获取函数签名、枚举取值与字段说明。
- **使用建议**：阅读 [api_guide.md](./api_guide.md) 了解缓存策略、错误处理与运维要点。

## 注意事项

1. **首次使用**：确保已安装 AmazingData SDK
2. **网络要求**：需要能够访问银河证券服务器
3. **数据缓存**：建议开启本地缓存以提高性能
4. **连接管理**：系统会自动管理连接和心跳
5. **错误处理**：如遇到连接问题，请检查：
   - 用户名密码是否正确
   - 网络是否可达服务器
   - 防火墙是否阻止了连接

## 故障排除

### 常见问题

1. **SDK未安装**
   ```
   错误：No module named 'AmazingData'
   解决：安装 third_party 目录下的 whl 文件
   ```

2. **连接失败**
   ```
   错误：登录失败，错误码: xxx
   解决：
   - 检查用户名密码
   - 确认服务器地址和端口
   - 检查网络连接
   ```

3. **数据获取失败**
   ```
   错误：获取数据超时
   解决：
   - 增加超时时间
   - 检查网络延迟
   - 启用本地缓存
   ```

## 联系支持

如需技术支持，请联系：
- 银河证券技术支持团队获取账号、最新 SDK 及服务器公告；
- DeepSearch 基础设施组，反馈配置模板或接入脚本的更新需求；
- 官方资料：`docs/datasources/amazingdata/AmazingData_API.md`（PDF 展开）及线上门户 https://cloud.chinastock.com.cn/p/DSG36jYQx2IY_Y8CIAA 。
