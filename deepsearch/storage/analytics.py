"""DuckDB 分析数据库集成

用于日级别数据的分析和存储
"""
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import pandas as pd
import duckdb

from deepsearch.observability.logger import logger


class AnalyticsDB:
    """DuckDB 分析数据库
    
    用于存储和分析日级别的市场数据
    """

    def __init__(self, db_path: Optional[str] = None):
        """初始化分析数据库
        
        Args:
            db_path: 数据库文件路径，默认为 data/analytics.duckdb
        """
        if db_path is None:
            # 确保数据目录存在
            data_dir = os.path.join(os.path.dirname(__file__), '../../data')
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'analytics.duckdb')

        self.db_path = db_path
        self.conn: Optional[duckdb.DuckDBPyConnection] = None
        self.logger = logger.bind(module="analytics_db")

    def connect(self) -> None:
        """连接到数据库"""
        try:
            self.conn = duckdb.connect(self.db_path)
            self._init_schema()
            self.logger.info(f"连接到 DuckDB: {self.db_path}")
        except Exception as e:
            self.logger.error(f"连接 DuckDB 失败: {e}")
            raise

    def _init_schema(self) -> None:
        """初始化数据库架构"""
        if not self.conn:
            raise RuntimeError("未连接到数据库")

        # 创建日线数据表
        self.conn.execute("""
                          CREATE TABLE IF NOT EXISTS market_daily
                          (
                              date
                              DATE
                              NOT
                              NULL,
                              symbol
                              VARCHAR
                              NOT
                              NULL,
                              open
                              DECIMAL
                          (
                              10,
                              2
                          ) NOT NULL,
                              high DECIMAL
                          (
                              10,
                              2
                          ) NOT NULL,
                              low DECIMAL
                          (
                              10,
                              2
                          ) NOT NULL,
                              close DECIMAL
                          (
                              10,
                              2
                          ) NOT NULL,
                              volume BIGINT NOT NULL,
                              turnover DECIMAL
                          (
                              15,
                              2
                          ) NOT NULL,
                              pre_close DECIMAL
                          (
                              10,
                              2
                          ),
                              change DECIMAL
                          (
                              10,
                              2
                          ),
                              pct_change DECIMAL
                          (
                              6,
                              2
                          ),
                              vwap DECIMAL
                          (
                              10,
                              2
                          ),
                              trade_count BIGINT,
                              buy_volume BIGINT,
                              sell_volume BIGINT,
                              neutral_volume BIGINT,
                              PRIMARY KEY
                          (
                              symbol,
                              date
                          )
                              )
                          """)

        # 创建因子数据表
        self.conn.execute("""
                          CREATE TABLE IF NOT EXISTS factor_data
                          (
                              date
                              DATE
                              NOT
                              NULL,
                              symbol
                              VARCHAR
                              NOT
                              NULL,
                              factor_name
                              VARCHAR
                              NOT
                              NULL,
                              factor_value
                              DOUBLE,
                              PRIMARY
                              KEY
                          (
                              symbol,
                              date,
                              factor_name
                          )
                              )
                          """)

        # 创建指标数据表
        self.conn.execute("""
                          CREATE TABLE IF NOT EXISTS indicator_data
                          (
                              date
                              DATE
                              NOT
                              NULL,
                              symbol
                              VARCHAR
                              NOT
                              NULL,
                              indicator_name
                              VARCHAR
                              NOT
                              NULL,
                              indicator_value
                              DOUBLE,
                              parameters
                              JSON,
                              PRIMARY
                              KEY
                          (
                              symbol,
                              date,
                              indicator_name
                          )
                              )
                          """)

        self.logger.info("DuckDB 架构初始化完成")

    def close(self) -> None:
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.logger.info("DuckDB 连接已关闭")

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()

    def insert_daily_data(self, df: pd.DataFrame) -> int:
        """插入日线数据
        
        Args:
            df: 包含日线数据的 DataFrame
            
        Returns:
            插入的记录数
        """
        if not self.conn:
            raise RuntimeError("未连接到数据库")

        # 确保必要的列存在
        required_cols = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'turnover']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"DataFrame 必须包含以下列: {required_cols}")

        # 插入数据
        self.conn.execute("INSERT OR REPLACE INTO market_daily SELECT * FROM df")

        count = len(df)
        self.logger.info(f"插入 {count} 条日线数据")
        return count

    def query_daily_data(
            self,
            symbols: Optional[List[str]] = None,
            start_date: Optional[date] = None,
            end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """查询日线数据
        
        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            查询结果 DataFrame
        """
        if not self.conn:
            raise RuntimeError("未连接到数据库")

        # 构建查询条件
        conditions = []
        params = {}

        if symbols:
            placeholders = [f"${i + 1}" for i in range(len(symbols))]
            conditions.append(f"symbol IN ({','.join(placeholders)})")
            for i, symbol in enumerate(symbols):
                params[f"${i + 1}"] = symbol

        if start_date:
            conditions.append(f"date >= ${len(params) + 1}")
            params[f"${len(params) + 1}"] = start_date

        if end_date:
            conditions.append(f"date <= ${len(params) + 1}")
            params[f"${len(params) + 1}"] = end_date

        # 构建查询语句
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT * FROM market_daily 
            {where_clause}
            ORDER BY symbol, date
        """

        # 执行查询
        result = self.conn.execute(query, list(params.values())).df()

        self.logger.info(f"查询到 {len(result)} 条日线数据")
        return result

    def calculate_returns(self, symbols: List[str], period: int = 1) -> pd.DataFrame:
        """计算收益率
        
        Args:
            symbols: 股票代码列表
            period: 计算周期（天数）
            
        Returns:
            包含收益率的 DataFrame
        """
        if not self.conn:
            raise RuntimeError("未连接到数据库")

        query = f"""
            WITH lagged_data AS (
                SELECT 
                    date,
                    symbol,
                    close,
                    LAG(close, {period}) OVER (PARTITION BY symbol ORDER BY date) as prev_close
                FROM market_daily
                WHERE symbol IN ({','.join(['?' for _ in symbols])})
            )
            SELECT 
                date,
                symbol,
                close,
                prev_close,
                (close - prev_close) / prev_close * 100 as return_{period}d
            FROM lagged_data
            WHERE prev_close IS NOT NULL
            ORDER BY symbol, date
        """

        result = self.conn.execute(query, symbols).df()
        self.logger.info(f"计算了 {len(result)} 条 {period} 日收益率")
        return result

    def export_to_parquet(self, table_name: str, output_path: str) -> None:
        """导出表到 Parquet 文件
        
        Args:
            table_name: 表名
            output_path: 输出文件路径
        """
        if not self.conn:
            raise RuntimeError("未连接到数据库")

        self.conn.execute(f"""
            COPY {table_name} TO '{output_path}' (FORMAT PARQUET, COMPRESSION 'SNAPPY')
        """)

        self.logger.info(f"导出 {table_name} 到 {output_path}")

    def import_from_parquet(self, table_name: str, file_path: str) -> int:
        """从 Parquet 文件导入数据
        
        Args:
            table_name: 表名
            file_path: 文件路径
            
        Returns:
            导入的记录数
        """
        if not self.conn:
            raise RuntimeError("未连接到数据库")

        # 先获取记录数
        count_before = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

        # 导入数据
        self.conn.execute(f"""
            INSERT OR REPLACE INTO {table_name} 
            SELECT * FROM read_parquet('{file_path}')
        """)

        # 计算新增记录数
        count_after = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        imported = count_after - count_before

        self.logger.info(f"从 {file_path} 导入 {imported} 条记录到 {table_name}")
        return imported

    def get_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        if not self.conn:
            raise RuntimeError("未连接到数据库")

        stats = {}

        # 获取各表记录数
        tables = ['market_daily', 'factor_data', 'indicator_data']
        for table in tables:
            count = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            stats[f"{table}_count"] = count

        # 获取日线数据的时间范围
        date_range = self.conn.execute("""
                                       SELECT MIN(date) as min_date, MAX(date) as max_date
                                       FROM market_daily
                                       """).fetchone()

        if date_range[0]:
            stats['date_range'] = {
                'start': str(date_range[0]),
                'end': str(date_range[1])
            }

        # 获取股票数量
        symbol_count = self.conn.execute("""
                                         SELECT COUNT(DISTINCT symbol)
                                         FROM market_daily
                                         """).fetchone()[0]
        stats['symbol_count'] = symbol_count

        # 获取数据库文件大小
        if os.path.exists(self.db_path):
            stats['db_size_mb'] = os.path.getsize(self.db_path) / 1024 / 1024

        return stats
