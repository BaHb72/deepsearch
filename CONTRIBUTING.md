# 贡献指南

感谢您对 DeepSearch 项目的关注！

## 开发环境设置

1. 克隆仓库

```bash
git clone https://github.com/BaHb/deepsearch.git
cd deepsearch
```

2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. 安装开发依赖

```bash
pip install -r requirements-dev.txt
pip install -e .
```

4. 安装数据库依赖（如需要）

```bash
# PostgreSQL 数据库驱动
pip install sqlalchemy>=2.0.41 asyncpg>=0.30.0 psycopg[binary]>=3.2.9

# DuckDB 分析数据库
pip install duckdb>=1.0.0

# 技术指标库（可选）
pip install TA-Lib>=0.4.32  # 需要先安装TA-Lib C库
```

## 代码规范

### 基本规范

- 使用 Black 进行代码格式化
- 使用 isort 进行导入排序
- 使用 mypy 进行类型检查
- 运行测试确保代码正确

```bash
# 格式化代码
black deepsearch tests
isort deepsearch tests

# 类型检查
mypy deepsearch

# 运行测试
pytest
pytest tests/test_event.py -v  # 运行特定测试
```

### 注释规范

- **中文注释**：所有注释应使用中文，便于团队协作
- **必要的英文单词**：技术术语可以使用英文（如 WebSocket、API 等）
- **文档字符串**：类和函数都应包含详细的中文文档字符串

```python
class DatabaseComponent(BaseComponent):
    """数据库组件 - 管理 PostgreSQL 连接和数据访问。
    
    该组件负责：
    - 数据库连接池管理
    - 健康检查
    - 事务管理
    """

    async def initialize(self):
        """初始化数据库连接。
        
        如果配置了 TimescaleDB，会尝试创建扩展。
        """
        pass
```

## 提交代码

1. 创建新分支

```bash
git checkout -b feature/your-feature
```

2. 提交更改

```bash
git add .
git commit -m "添加新功能"
```

3. 推送并创建 Pull Request

## 报告问题

请在 GitHub Issues 中报告问题，并提供：

- 问题描述
- 复现步骤
- 系统信息

## 数据库设置

### PostgreSQL 设置

1. 安装 PostgreSQL（推荐版本 14+）
2. 创建数据库：

```sql
CREATE
DATABASE deepsearch;
CREATE
USER deepsearch WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE
deepsearch TO deepsearch;
```

3. （可选）安装 TimescaleDB 扩展：

```sql
CREATE
EXTENSION IF NOT EXISTS timescaledb;
```

### DuckDB 设置

DuckDB 是嵌入式数据库，无需额外安装。首次运行时会自动创建数据库文件。

## 常见问题

### 1. PostgreSQL 连接失败

**错误**：`asyncpg.exceptions.InvalidPasswordError`

**解决方案**：

- 检查数据库密码是否正确
- 确认用户权限配置
- 检查 pg_hba.conf 认证方式

### 2. 端口冲突

**错误**：`[Errno 10048] 通常每个套接字地址只允许使用一次`

**解决方案**：

```bash
# 检查端口占用
python -m deepsearch check-ports

# 清理僵尸进程
python -m deepsearch cleanup
```

### 3. WebSocket 连接失败

**错误**：`WebSocket connection to 'ws://localhost:8000/api/logs/ws' failed`

**解决方案**：

- 确保 logs 目录存在
- 检查后端服务是否正常运行
- 查看浏览器控制台错误信息

### 4. DuckDB 内存限制

**错误**：`Out of Memory Error`

**解决方案**：

- 调整配置中的 memory_limit 参数
- 使用分批处理大数据集
- 考虑使用 Parquet 文件进行数据交换

## 最近更新

### 2025-07-28

- 添加 DuckDB 分析数据库支持
- 实现数据清洗模块
- 封装技术指标计算（TA-Lib）
- 创建数据管理 WebUI 页面
- 修复多个 bug（异常处理、资源泄漏等）
- 迁移到 Pydantic V2

详细更新请查看 CHANGELOG.md