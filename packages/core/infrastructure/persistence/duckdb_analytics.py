"""
DuckDB 分析数据库管理器

提供高性能的 OLAP 分析能力，用于历史数据分析、技术指标计算和回测
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional

import duckdb
import pandas as pd
from loguru import logger

from .duckdb_path import resolve_duckdb_path


class DuckDBAnalytics:
    """DuckDB 分析数据库管理器"""

    def __init__(self, db_path: Optional[str] = None, memory_limit: str = "4GB", threads: int = 4):
        """
        初始化 DuckDB 分析数据库

        Args:
            db_path: 数据库文件路径，None 表示内存数据库
            memory_limit: 内存限制
            threads: 线程数
        """
        default_path = db_path or str(
            Path(__file__).parent.parent / "data" / "analytics" / "market.duckdb"
        )
        self.db_path = resolve_duckdb_path(default_path)
        self.memory_limit = memory_limit
        self.threads = threads
        self.conn = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._schema_initialized = False

        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # 初始化连接
        self._init_connection()

    def _init_connection(self):
        """初始化数据库连接"""
        try:
            self.conn = duckdb.connect(self.db_path)
            self._schema_initialized = False

            # 设置配置
            self.conn.execute(f"SET memory_limit='{self.memory_limit}'")
            self.conn.execute(f"SET threads={self.threads}")

            # 启用扩展
            self.conn.execute("INSTALL httpfs")  # HTTP/S3 文件访问
            self.conn.execute("LOAD httpfs")

            logger.info(f"DuckDB connected successfully: {self.db_path}")

        except Exception as e:
            logger.error(f"DuckDB connection failed: {e}")
            raise

    def init_schema(self):
        """初始化数据库模式"""
        if self._schema_initialized:
            return

        try:
            # 创建历史K线表
            self.conn.execute("""
                              CREATE TABLE IF NOT EXISTS kline_history
                              (
                                  symbol
                                  VARCHAR
                                  NOT
                                  NULL,
                                  time
                                  TIMESTAMP
                                  NOT
                                  NULL,
                                  open
                                  DECIMAL
                              (
                                  10,
                                  2
                              ),
                                  high DECIMAL
                              (
                                  10,
                                  2
                              ),
                                  low DECIMAL
                              (
                                  10,
                                  2
                              ),
                                  close DECIMAL
                              (
                                  10,
                                  2
                              ),
                                  volume BIGINT,
                                  amount DECIMAL
                              (
                                  15,
                                  2
                              ),
                                  PRIMARY KEY
                              (
                                  symbol,
                                  time
                              )
                                  )
                              """)

            # 创建Tick归档表
            self.conn.execute("""
                              CREATE TABLE IF NOT EXISTS tick_archive
                              (
                                  symbol
                                  VARCHAR
                                  NOT
                                  NULL,
                                  time
                                  TIMESTAMP
                                  NOT
                                  NULL,
                                  last_price
                                  DECIMAL
                              (
                                  10,
                                  2
                              ),
                                  volume BIGINT,
                                  amount DECIMAL
                              (
                                  15,
                                  2
                              ),
                                  bid_price1 DECIMAL
                              (
                                  10,
                                  2
                              ),
                                  ask_price1 DECIMAL
                              (
                                  10,
                                  2
                              ),
                                  bid_volume1 BIGINT,
                                  ask_volume1 BIGINT,
                                  PRIMARY KEY
                              (
                                  symbol,
                                  time
                              )
                                  )
                              """)

            # 创建技术指标表
            self.conn.execute("""
                              CREATE TABLE IF NOT EXISTS indicators
                              (
                                  symbol
                                  VARCHAR
                                  NOT
                                  NULL,
                                  time
                                  TIMESTAMP
                                  NOT
                                  NULL,
                                  indicator_name
                                  VARCHAR
                                  NOT
                                  NULL,
                                  value
                                  DECIMAL
                              (
                                  20,
                                  6
                              ),
                                  params JSON,
                                  PRIMARY KEY
                              (
                                  symbol,
                                  time,
                                  indicator_name
                              )
                                  )
                              """)

            # 创建回测结果表
            self.conn.execute("""
                              CREATE TABLE IF NOT EXISTS backtest_results
                              (
                                  strategy_id
                                  VARCHAR
                                  NOT
                                  NULL,
                                  run_time
                                  TIMESTAMP
                                  NOT
                                  NULL,
                                  symbol
                                  VARCHAR,
                                  start_date
                                  DATE,
                                  end_date
                                  DATE,
                                  total_return
                                  DECIMAL
                              (
                                  10,
                                  4
                              ),
                                  sharpe_ratio DECIMAL
                              (
                                  10,
                                  4
                              ),
                                  max_drawdown DECIMAL
                              (
                                  10,
                                  4
                              ),
                                  win_rate DECIMAL
                              (
                                  10,
                                  4
                              ),
                                  trades JSON,
                                  metrics JSON,
                                  PRIMARY KEY
                              (
                                  strategy_id,
                                  run_time
                              )
                                  )
                              """)

            # 创建数据同步日志表
            self.conn.execute("""
                              CREATE TABLE IF NOT EXISTS sync_log
                              (
                                  sync_id
                                  VARCHAR
                                  PRIMARY
                                  KEY,
                                  table_name
                                  VARCHAR
                                  NOT
                                  NULL,
                                  sync_time
                                  TIMESTAMP
                                  NOT
                                  NULL,
                                  start_time
                                  TIMESTAMP,
                                  end_time
                                  TIMESTAMP,
                                  records_count
                                  BIGINT,
                                  status
                                  VARCHAR,
                                  error_message
                                  TEXT
                              )
                              """)

            self._schema_initialized = True
            logger.info("DuckDB 模式初始化完成")

        except Exception as e:
            logger.error(f"初始化模式失败: {e}")
            raise

    async def import_from_dataframe(
        self, df: pd.DataFrame, table_name: str, if_exists: str = "append"
    ):
        """
        从 DataFrame 导入数据

        Args:
            df: Pandas DataFrame
            table_name: 目标表名
            if_exists: 'append', 'replace', 'fail'
        """

        def _import():
            if if_exists == "replace":
                self.conn.execute(f"DELETE FROM {table_name}")

            self.conn.register("temp_df", df)
            self.conn.execute(f"INSERT INTO {table_name} SELECT * FROM temp_df")
            self.conn.unregister("temp_df")

            return len(df)

        loop = asyncio.get_event_loop()
        count = await loop.run_in_executor(self._executor, _import)
        logger.info(f"导入 {count} 条记录到 {table_name}")
        return count

    async def query(self, sql: str, params: Optional[tuple] = None) -> pd.DataFrame:
        """
        执行查询并返回 DataFrame

        Args:
            sql: SQL 查询语句
            params: 查询参数

        Returns:
            查询结果 DataFrame
        """

        def _query():
            if params:
                result = self.conn.execute(sql, params)
            else:
                result = self.conn.execute(sql)
            return result.df()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _query)

    async def calculate_indicators(
        self, symbol: str, start_date: str, end_date: str, indicators: List[str]
    ) -> pd.DataFrame:
        """
        计算技术指标

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            indicators: 指标列表 ['MA_20', 'RSI_14', 'MACD']

        Returns:
            包含指标的 DataFrame
        """
        # 获取基础数据
        sql = """
              SELECT time, open, high, low, close, volume
              FROM kline_history
              WHERE symbol = ? AND time BETWEEN ? AND ?
              ORDER BY time \
              """
        df = await self.query(sql, (symbol, start_date, end_date))

        if df.empty:
            return df

        # 计算各种指标
        for indicator in indicators:
            if indicator.startswith("MA_"):
                period = int(indicator.split("_")[1])
                df[indicator] = df["close"].rolling(window=period).mean()

            elif indicator.startswith("RSI_"):
                period = int(indicator.split("_")[1])
                close_series = df["close"].astype("float64")
                delta = close_series.diff()
                gain = delta.clip(lower=0.0).rolling(window=period).mean()
                loss = (-delta.clip(upper=0.0)).rolling(window=period).mean()
                rs = gain / loss
                df[indicator] = 100 - (100 / (1 + rs))

            elif indicator == "MACD":
                exp1 = df["close"].ewm(span=12, adjust=False).mean()
                exp2 = df["close"].ewm(span=26, adjust=False).mean()
                df["MACD"] = exp1 - exp2
                df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
                df["MACD_hist"] = df["MACD"] - df["MACD_signal"]

        return df

    async def aggregate_klines(
        self, symbol: str, source_period: str, target_period: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """
        聚合K线数据

        Args:
            symbol: 股票代码
            source_period: 源周期 (1m, 5m, 1d)
            target_period: 目标周期 (1h, 1d, 1w, 1M)
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            聚合后的K线数据
        """
        # 将周期转换为 DuckDB INTERVAL 格式
        period_map = {
            "1m": "1 MINUTE",
            "5m": "5 MINUTES",
            "15m": "15 MINUTES",
            "30m": "30 MINUTES",
            "1h": "1 HOUR",
            "1d": "1 DAY",
            "1w": "1 WEEK",
            "1M": "1 MONTH",
        }

        interval_str = period_map.get(target_period, "5 MINUTES")

        # 使用 DuckDB 的时间窗口函数进行高效聚合
        sql = f"""
            SELECT
                symbol,
                time_bucket(INTERVAL '{interval_str}', time) as time,
                first(open) as open,
                max(high) as high,
                min(low) as low,
                last(close) as close,
                sum(volume) as volume,
                sum(amount) as amount
            FROM kline_history
            WHERE symbol = ? AND time BETWEEN ? AND ?
            GROUP BY symbol, time_bucket(INTERVAL '{interval_str}', time)
            ORDER BY time
        """

        return await self.query(sql, (symbol, start_date, end_date))

    async def export_to_parquet(self, table_name: str, output_path: str):
        """
        导出表到 Parquet 文件

        Args:
            table_name: 表名
            output_path: 输出路径
        """

        def _export():
            self.conn.execute(f"""
                COPY {table_name}
                TO '{output_path}'
                (FORMAT PARQUET, COMPRESSION 'SNAPPY')
            """)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, _export)
        logger.info(f"导出 {table_name} 到 {output_path}")

    async def query_parquet(self, parquet_path: str, sql: str) -> pd.DataFrame:
        """
        直接查询 Parquet 文件

        Args:
            parquet_path: Parquet 文件路径
            sql: SQL 查询语句（使用 'parquet_data' 作为表名）

        Returns:
            查询结果
        """

        def _query():
            # 创建临时视图
            self.conn.execute(
                f"CREATE OR REPLACE VIEW parquet_data AS SELECT * FROM '{parquet_path}'"
            )
            # 执行查询
            result = self.conn.execute(sql)
            return result.df()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _query)

    async def get_statistics(self) -> dict[str, object]:
        """获取数据库统计信息"""
        stats: dict[str, object] = {}

        # 获取各表记录数
        tables = ["kline_history", "tick_archive", "indicators", "backtest_results"]
        for table in tables:
            try:
                count_df = await self.query(f"SELECT COUNT(*) as count FROM {table}")
                stats[f"{table}_count"] = int(count_df["count"][0]) if not count_df.empty else 0
            except Exception:
                stats[f"{table}_count"] = 0

        # 获取数据库文件大小
        if self.db_path and Path(self.db_path).exists():
            stats["database_size"] = Path(self.db_path).stat().st_size
        else:
            stats["database_size"] = 0

        # 获取内存使用
        stats["memory_limit"] = self.memory_limit
        stats["threads"] = self.threads

        return stats

    async def init_tables(self):
        """异步初始化表结构"""
        self.init_schema()

    def _close_connection(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("DuckDB 连接已关闭")

    async def close(self):
        """异步关闭数据库连接"""
        self._close_connection()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close_connection()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# 全局实例
_analytics_instance: Optional[DuckDBAnalytics] = None


def get_analytics_db(
    db_path: Optional[str] = None, memory_limit: str = "4GB", threads: int = 4
) -> DuckDBAnalytics:
    """获取全局 DuckDB 分析实例"""
    global _analytics_instance
    if _analytics_instance is None:
        _analytics_instance = DuckDBAnalytics(
            db_path=db_path, memory_limit=memory_limit, threads=threads
        )
        _analytics_instance.init_schema()
    return _analytics_instance


async def close_analytics_db() -> None:
    """关闭全局 DuckDB 分析实例

    应在应用关闭时调用此函数以正确释放资源。
    """
    global _analytics_instance
    if _analytics_instance is not None:
        await _analytics_instance.close()
        _analytics_instance = None
