# DeepSearch 数据库基础设施实施进度

## 项目概述

DeepSearch 量化交易系统的数据库基础设施建设，包含时序数据库(TimescaleDB)、分析数据库(DuckDB)、数据清洗、技术指标计算等完整数据处理链路。

## 已完成的工作

### 1. 数据库配置页面优化 ✅

- **文件**: `deepsearch/webui/frontend/src/views/Config.vue`
- **完成内容**:
    - 优化了数据库连接错误提示，提供友好的中文错误信息
    - 添加了"记住密码"功能，允许保存主数据库密码到配置文件
    - 美化了配置页面UI，添加了卡片悬浮效果、表单样式优化
    - 实现了配置变更检测，有修改时保存按钮会高亮提示
    - 为主数据库和缓存数据库添加了独立的保存按钮

### 2. 后端错误处理优化 ✅

- **文件**: `deepsearch/webui/api/config.py`
- **完成内容**:
    - 增强了 `parse_database_error` 函数，支持更多错误场景
    - 实现了条件密码保存逻辑（根据"记住密码"选项）
    - 优化了数据库连接测试的错误反馈

### 3. 数据库配置模型 ✅

- **文件**: `deepsearch/config/models/database.py`
- **现有结构**:
  ```python
  - MainDatabaseConfig: PostgreSQL/MySQL/SQLite 配置
  - CacheDatabaseConfig: Redis 配置
  - DatabaseConfig: 统一配置模型
  ```

### 4. 数据库组件实现 ✅

- **文件**: `deepsearch/core/components.py`
- **完成内容**:
    - 创建了 DatabaseComponent 类，支持 PostgreSQL 连接
    - 实现了异步数据库引擎和会话管理
    - 添加了 TimescaleDB 扩展检测和安装逻辑
    - 实现了健康检查机制
    - 创建了测试脚本 `test_database_component.py`

- **测试结果**:
    - 数据库连接成功 ✓
    - 组件生命周期管理正常 ✓
    - 健康检查功能正常 ✓
    - TimescaleDB 检测正常（未安装，符合预期）✓

### 5. 数据模型创建 ✅

- **文件结构**:
  ```
  deepsearch/storage/
  ├── __init__.py
  ├── models/
  │   ├── __init__.py
  │   ├── base.py      # 基础模型类
  │   ├── market.py    # 行情数据模型
  │   └── trading.py   # 交易数据模型
  ├── database.py      # 数据库服务层
  └── init_db.py       # 数据库初始化脚本
  ```

- **完成内容**:
    - **base.py**: BaseModel, TimeSeriesBase, TimestampMixin
    - **market.py**: MarketTick, Market1Min, Market5Min, MarketDaily, MarketSnapshot
    - **trading.py**: Order, Position, Trade, Account, DailySettlement
    - **database.py**: DatabaseService 统一数据库访问接口
    - **init_db.py**: 数据库初始化和测试数据生成

### 6. 数据库初始化 ✅

- **测试结果**:
    - 成功创建所有数据库表结构
    - 创建的表包括:
        - 行情数据: market_tick, market_1min, market_5min, market_daily, market_snapshot
        - 交易数据: orders, positions, trades, accounts, daily_settlements
    - 所有索引和约束正确创建
    - TimescaleDB 未安装，使用普通 PostgreSQL 表

### 7. DuckDB 分析数据库集成 ✅

- **文件**: `deepsearch/storage/analytics.py`
- **完成内容**:
    - 实现了 AnalyticsDB 类，支持 DuckDB 操作
    - 创建了日线数据表、因子表、指标表
    - 实现了数据插入、查询、导入导出功能
    - 实现了收益率计算和复杂分析查询
    - 支持 Parquet 文件格式导入导出

- **测试结果**:
    - 成功创建并连接 DuckDB
    - 插入 240 条测试数据成功
    - 数据查询、筛选、收益率计算正常
    - 移动平均线计算成功
    - Parquet 文件导出成功

### 8. 数据清洗模块 ✅

- **文件**: `deepsearch/data/cleaner.py`
- **完成内容**:
    - DataCleaner 类提供全面的数据清洗功能
    - Tick 数据清洗：异常值、零成交量、集合竞价数据处理
    - K线数据清洗：OHLC 关系修正、缺失数据填充
    - 异常值检测：IQR、Z-score、MAD 方法
    - 股票代码标准化
    - 数据完整性验证

### 9. 技术指标封装 ✅

- **文件**:
    - `deepsearch/indicators/technical.py` - TA-Lib 封装
    - `deepsearch/indicators/simple.py` - 纯 Python 实现
- **完成内容**:
    - 移动平均线：SMA、EMA、WMA
    - 趋势指标：MaCD、ADX
    - 震荡指标：RSI、Stochastic、CCI
    - 波动率指标：布林带、ATR
    - 成交量指标：OBV、A/D Line、VWAP
    - 形态识别（TA-Lib）
    - 批量计算和信号分析

### 10. MainEngine 集成 ✅

- **文件**: `deepsearch/core/engine.py`
- **完成内容**:
    - 在 MainEngine 中添加 DatabaseComponent 初始化
    - 数据库组件作为基础设施组件自动启动
    - 完成生命周期管理集成

### 11. WebUI 数据管理页面 ✅

- **文件**:
    - `deepsearch/webui/api/data.py` - 数据管理 API
    - `deepsearch/webui/frontend/src/api/data.js` - 前端 API 客户端
    - `deepsearch/webui/frontend/src/views/DataManagement.vue` - 数据管理页面
- **完成内容**:
    - 数据统计展示（股票数量、记录数、日期范围、最后更新）
    - 数据查询功能（支持多股票、日期范围筛选）
    - CSV 数据导入（支持拖拽上传、数据清洗选项）
    - 数据导出功能（CSV 格式）
    - 技术指标计算（SMA、EMA、RSI、MACD、布林带）
    - 指标结果可视化（ECharts 图表）
    - 集成到主路由和导航菜单

### 12. 测试脚本和示例数据 ✅

- **文件**:
    - `test_data_import.py` - 数据导入测试脚本
    - `sample_market_data.csv` - 示例市场数据
- **完成内容**:
    - 生成一年的测试数据（5个股票）
    - 测试完整的数据导入流程
    - 验证数据清洗功能
    - 测试技术指标计算
    - API 端点测试
    - 数据导出验证

## 成果总结

经过这次开发，DeepSearch 系统现在拥有了完整的数据基础设施：

1. **数据库层**：
    - PostgreSQL 作为主数据库（支持 TimescaleDB）
    - DuckDB 作为分析数据库
    - 完整的数据模型（行情、交易）

2. **数据处理**：
    - 全面的数据清洗功能
    - 技术指标计算（支持 TA-Lib 和纯 Python）
    - 数据标准化和验证

3. **系统集成**：
    - 数据库组件已集成到 MainEngine
    - 完整的生命周期管理
    - 健康检查和监控

## 待实施任务

### 第一阶段：创建数据库核心组件

#### 1.1 创建数据库组件 (`deepsearch/core/components/database.py`)

```python
class DatabaseComponent(BaseComponent):
    """数据库组件 - 管理 PostgreSQL + TimescaleDB"""
    
    def __init__(self):
        - 组件类型: ComponentType.INFRASTRUCTURE
        - 依赖: 无
        - 初始化 SQLAlchemy 引擎
        - 创建连接池（异步）
        
    async def initialize(self):
        - 创建数据库引擎
        - 测试连接
        - 安装 TimescaleDB 扩展（如果需要）
        - 创建基础表结构
        
    async def start(self):
        - 启动连接池
        - 启动健康检查任务
        - 注册到组件管理器
        
    async def stop(self):
        - 关闭所有连接
        - 清理资源
        
    async def health_check(self):
        - 检查连接状态
        - 检查 TimescaleDB 扩展
        - 返回健康状态
```

#### 1.2 创建数据模型目录结构

```
deepsearch/storage/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── base.py          # 基础模型类
│   ├── market.py        # 行情数据模型
│   └── trading.py       # 交易数据模型
├── database.py          # 数据库服务
├── timeseries.py        # 时序数据库操作
├── analytics.py         # 分析数据库操作
└── transfer.py          # 数据转储服务
```

#### 1.3 基础模型类 (`deepsearch/storage/models/base.py`)

```python
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime, func

Base = declarative_base()

class TimestampMixin:
    """时间戳混入类"""
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

#### 1.4 行情数据模型 (`deepsearch/storage/models/market.py`)

```python
# Tick 数据表
class MarketTick(Base):
    __tablename__ = 'market_tick'
    
    time = Column(DateTime(timezone=True), primary_key=True)
    symbol = Column(String(20), primary_key=True)
    last_price = Column(Numeric(10, 2))
    volume = Column(BigInteger)
    turnover = Column(Numeric(15, 2))
    bid_prices = Column(ARRAY(Numeric))  # 买价队列
    ask_prices = Column(ARRAY(Numeric))  # 卖价队列
    bid_volumes = Column(ARRAY(BigInteger))  # 买量队列
    ask_volumes = Column(ARRAY(BigInteger))  # 卖量队列

# 1分钟 K线表
class Market1Min(Base):
    __tablename__ = 'market_1min'
    
    time = Column(DateTime(timezone=True), primary_key=True)
    symbol = Column(String(20), primary_key=True)
    open = Column(Numeric(10, 2))
    high = Column(Numeric(10, 2))
    low = Column(Numeric(10, 2))
    close = Column(Numeric(10, 2))
    volume = Column(BigInteger)
    turnover = Column(Numeric(15, 2))

# 日线数据表（用于 DuckDB）
class MarketDaily(Base):
    __tablename__ = 'market_daily'
    
    date = Column(Date, primary_key=True)
    symbol = Column(String(20), primary_key=True)
    open = Column(Numeric(10, 2))
    high = Column(Numeric(10, 2))
    low = Column(Numeric(10, 2))
    close = Column(Numeric(10, 2))
    volume = Column(BigInteger)
    turnover = Column(Numeric(15, 2))
```

### 第二阶段：集成 TimescaleDB 和 DuckDB

#### 2.1 TimescaleDB 初始化脚本

```sql
-- 创建 TimescaleDB 扩展
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 将表转换为超表
SELECT create_hypertable('market_tick', 'time');
SELECT create_hypertable('market_1min', 'time');

-- 创建连续聚合（1分钟 -> 5分钟）
CREATE MATERIALIZED VIEW market_5min
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('5 minutes', time) AS time,
    symbol,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume,
    sum(turnover) as turnover
FROM market_1min
GROUP BY time_bucket('5 minutes', time), symbol;

-- 添加刷新策略
SELECT add_continuous_aggregate_policy('market_5min',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '5 minutes');
```

#### 2.2 DuckDB 集成 (`deepsearch/storage/analytics.py`)

```python
import duckdb
import pandas as pd

class AnalyticsDB:
    """DuckDB 分析数据库"""
    
    def __init__(self, db_path: str = "data/analytics.duckdb"):
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        self.conn = duckdb.connect(self.db_path)
        self._init_schema()
        
    def _init_schema(self):
        """初始化数据库架构"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS market_daily (
                date DATE,
                symbol VARCHAR,
                open DECIMAL(10,2),
                high DECIMAL(10,2),
                low DECIMAL(10,2),
                close DECIMAL(10,2),
                volume BIGINT,
                turnover DECIMAL(15,2),
                PRIMARY KEY (symbol, date)
            )
        """)
```

### 第三阶段：数据标准化和技术指标

#### 3.1 统一行情接口 (`deepsearch/data/market_interface.py`)

```python
from typing import Optional, List
from datetime import datetime
import pandas as pd

class MarketDataInterface:
    """统一的行情数据接口"""
    
    def __init__(self, db_component):
        self.db = db_component
        
    async def get_tick(
        self, 
        symbol: str, 
        start: datetime, 
        end: datetime
    ) -> pd.DataFrame:
        """获取 tick 数据"""
        pass
        
    async def get_kline(
        self,
        symbol: str,
        freq: str,  # '1min', '5min', '30min', '1h', '1d'
        start: datetime,
        end: datetime
    ) -> pd.DataFrame:
        """获取 K 线数据"""
        pass
```

#### 3.2 数据清洗模块 (`deepsearch/data/cleaner.py`)

```python
class DataCleaner:
    """数据清洗器"""
    
    def clean_tick(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗 tick 数据"""
        # 1. 去除价格异常值（涨跌幅超过 20%）
        # 2. 去除成交量为 0 的记录
        # 3. 时间戳标准化
        # 4. 去重
        pass
        
    def fill_missing(self, df: pd.DataFrame, method='ffill') -> pd.DataFrame:
        """填充缺失数据"""
        pass
```

#### 3.3 技术指标封装 (`deepsearch/indicators/technical.py`)

```python
import talib
import pandas as pd
import numpy as np

class TechnicalIndicators:
    """技术指标计算器 - 基于 TA-Lib"""
    
    @staticmethod
    def sma(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """简单移动平均"""
        return talib.SMA(df['close'].values, timeperiod=period)
        
    @staticmethod
    def ema(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """指数移动平均"""
        return talib.EMA(df['close'].values, timeperiod=period)
        
    @staticmethod
    def macd(df: pd.DataFrame, fast=12, slow=26, signal=9):
        """MACD 指标"""
        macd, signal, hist = talib.MACD(
            df['close'].values,
            fastperiod=fast,
            slowperiod=slow,
            signalperiod=signal
        )
        return pd.DataFrame({
            'macd': macd,
            'signal': signal,
            'hist': hist
        })
        
    @staticmethod
    def rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """RSI 指标"""
        return talib.RSI(df['close'].values, timeperiod=period)
        
    @staticmethod
    def bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: int = 2):
        """布林带"""
        upper, middle, lower = talib.BBANDS(
            df['close'].values,
            timeperiod=period,
            nbdevup=std_dev,
            nbdevdn=std_dev
        )
        return pd.DataFrame({
            'upper': upper,
            'middle': middle,
            'lower': lower
        })
```

### 第四阶段：WebUI 集成

#### 4.1 数据管理页面路由

- **文件**: `deepsearch/webui/frontend/src/router/index.js`
- 添加新路由:
  ```javascript
  {
    path: '/data-management',
    name: 'DataManagement',
    component: () => import('../views/DataManagement.vue')
  },
  {
    path: '/market-monitor',
    name: 'MarketMonitor',
    component: () => import('../views/MarketMonitor.vue')
  }
  ```

#### 4.2 API 路由

- **文件**: `deepsearch/webui/api/database.py`
  ```python
  @router.get("/status")
  async def get_database_status():
      """获取数据库状态"""
      
  @router.post("/init-timescale")
  async def init_timescaledb():
      """初始化 TimescaleDB"""
  ```

## 测试计划

### 1. 数据库组件测试脚本

```python
# test_database_component.py
import asyncio
from deepsearch.core.components.database import DatabaseComponent

async def test_database():
    db_component = DatabaseComponent()
    
    # 初始化
    await db_component.initialize()
    print("✓ 数据库组件初始化成功")
    
    # 启动
    await db_component.start()
    print("✓ 数据库组件启动成功")
    
    # 健康检查
    health = await db_component.health_check()
    print(f"✓ 健康检查: {health}")
    
    # 停止
    await db_component.stop()
    print("✓ 数据库组件停止成功")

if __name__ == "__main__":
    asyncio.run(test_database())
```

### 2. TimescaleDB 测试

```python
# test_timescaledb.py
import asyncio
from deepsearch.storage.timeseries import TimeSeriesDB

async def test_timescale():
    ts_db = TimeSeriesDB()
    
    # 创建超表
    await ts_db.create_hypertables()
    print("✓ TimescaleDB 超表创建成功")
    
    # 插入测试数据
    await ts_db.insert_tick_data(...)
    print("✓ Tick 数据插入成功")

if __name__ == "__main__":
    asyncio.run(test_timescale())
```

## 下一步行动

1. 首先创建 `deepsearch/storage/` 目录结构
2. 实现 DatabaseComponent 基础框架
3. 创建数据模型
4. 编写测试脚本
5. 逐步测试每个组件

## 注意事项

- 所有数据库操作使用异步方式
- 错误处理要完善，提供友好的错误信息
- 每个组件都要有健康检查机制
- 所有功能都要在 WebUI 中可视化展示