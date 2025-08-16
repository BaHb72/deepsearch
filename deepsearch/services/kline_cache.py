"""
K线数据分层缓存管理器

实现三层缓存架构：
- L1: 内存缓存（热数据）
- L2: Redis缓存（温数据）
- L3: 本地数据库（冷数据）
"""
import hashlib
import pickle
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Tuple

import pandas as pd
from loguru import logger


class KlineCache:
    """K线数据分层缓存管理器"""

    def __init__(self, redis_client=None, db_path: str = "./data/kline_cache.db"):
        """
        初始化缓存管理器
        
        Args:
            redis_client: Redis客户端
            db_path: 本地数据库路径
        """
        # L1: 内存缓存
        self.memory_cache = {}
        self.memory_ttl = {
            "1m": 5,  # 1分钟线缓存5秒
            "5m": 10,  # 5分钟线缓存10秒
            "15m": 30,  # 15分钟线缓存30秒
            "30m": 60,  # 30分钟线缓存60秒
            "60m": 120,  # 60分钟线缓存2分钟
            "1d": 300,  # 日线缓存5分钟
            "1w": 3600,  # 周线缓存1小时
            "1mo": 3600  # 月线缓存1小时
        }

        # L2: Redis缓存
        self.redis_client = redis_client
        self.redis_enabled = redis_client is not None

        # L3: 本地SQLite数据库
        self.db_path = db_path
        self._init_database()

        # 配置
        self.config = {
            "initial_days": 60,  # 初始加载60天
            "chunk_days": 365,  # 每次加载1年
            "max_memory_items": 100,  # 内存最多缓存100个股票
            "preload_threshold": 0.8  # 滚动到80%时预加载
        }

        # 统计
        self.stats = {
            "l1_hits": 0,
            "l2_hits": 0,
            "l3_hits": 0,
            "api_calls": 0,
            "total_requests": 0
        }

    def _init_database(self):
        """初始化本地数据库"""
        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建K线数据表
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS kline_data
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           symbol
                           TEXT
                           NOT
                           NULL,
                           timeframe
                           TEXT
                           NOT
                           NULL,
                           date
                           TEXT
                           NOT
                           NULL,
                           open
                           REAL,
                           high
                           REAL,
                           low
                           REAL,
                           close
                           REAL,
                           volume
                           REAL,
                           amount
                           REAL,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           UNIQUE
                       (
                           symbol,
                           timeframe,
                           date
                       )
                           )
                       """)

        # 创建元数据表
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS stock_meta
                       (
                           symbol
                           TEXT
                           PRIMARY
                           KEY,
                           name
                           TEXT,
                           listing_date
                           TEXT,
                           total_bars
                           INTEGER,
                           last_update
                           TIMESTAMP,
                           data_range_start
                           TEXT,
                           data_range_end
                           TEXT,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
                       )
                       """)

        # 创建索引
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_kline_symbol_timeframe_date
                           ON kline_data(symbol, timeframe, date)
                       """)

        conn.commit()
        conn.close()
        logger.info(f"本地K线数据库初始化完成: {self.db_path}")

    async def get_stock_meta(self, symbol: str) -> Dict:
        """
        获取股票元数据
        
        Returns:
            包含上市日期、数据范围等信息的字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
                       SELECT name,
                              listing_date,
                              total_bars,
                              last_update,
                              data_range_start,
                              data_range_end
                       FROM stock_meta
                       WHERE symbol = ?
                       """, (symbol,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "symbol": symbol,
                "name": row[0],
                "listing_date": row[1],
                "total_bars": row[2],
                "last_update": row[3],
                "data_range_start": row[4],
                "data_range_end": row[5],
                "has_cache": True
            }

        # 如果没有元数据，返回默认值
        return {
            "symbol": symbol,
            "name": f"股票{symbol}",
            "listing_date": "2000-01-01",
            "total_bars": 0,
            "last_update": None,
            "data_range_start": None,
            "data_range_end": None,
            "has_cache": False
        }

    async def get_data(
            self,
            symbol: str,
            timeframe: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            limit: Optional[int] = None
    ) -> Tuple[pd.DataFrame, str]:
        """
        分层获取K线数据
        
        Returns:
            (数据DataFrame, 数据来源)
        """
        self.stats["total_requests"] += 1

        # 生成缓存键
        cache_key = self._generate_cache_key(symbol, timeframe, start_date, end_date, limit)

        # 1. 尝试从L1内存缓存获取
        data = self._get_from_memory(cache_key, timeframe)
        if data is not None:
            self.stats["l1_hits"] += 1
            logger.debug(f"L1命中: {symbol} {timeframe}")
            return data, "L1_MEMORY"

        # 2. 尝试从L2 Redis缓存获取
        if self.redis_enabled:
            data = await self._get_from_redis(cache_key)
            if data is not None:
                self.stats["l2_hits"] += 1
                logger.debug(f"L2命中: {symbol} {timeframe}")
                # 写入L1
                self._set_memory_cache(cache_key, data, timeframe)
                return data, "L2_REDIS"

        # 3. 尝试从L3本地数据库获取
        data = self._get_from_database(symbol, timeframe, start_date, end_date, limit)
        if data is not None and not data.empty:
            self.stats["l3_hits"] += 1
            logger.debug(f"L3命中: {symbol} {timeframe}, 获取 {len(data)} 条记录")
            # 写入L1和L2
            self._set_memory_cache(cache_key, data, timeframe)
            if self.redis_enabled:
                await self._set_redis_cache(cache_key, data, timeframe)
            return data, "L3_DATABASE"

        # 4. 缓存未命中，返回None（由调用方从API获取）
        self.stats["api_calls"] += 1
        logger.debug(f"缓存未命中: {symbol} {timeframe}, 需要从API获取")
        return None, "MISS"

    async def save_data(
            self,
            symbol: str,
            timeframe: str,
            data: pd.DataFrame,
            update_meta: bool = True
    ):
        """
        保存数据到所有缓存层
        """
        if data is None or data.empty:
            return

        # 生成缓存键
        cache_key = self._generate_cache_key(
            symbol, timeframe,
            data.iloc[0]['date'] if 'date' in data.columns else None,
            data.iloc[-1]['date'] if 'date' in data.columns else None,
            len(data)
        )

        # 1. 保存到L1内存
        self._set_memory_cache(cache_key, data, timeframe)

        # 2. 保存到L2 Redis
        if self.redis_enabled:
            await self._set_redis_cache(cache_key, data, timeframe)

        # 3. 保存到L3数据库
        self._save_to_database(symbol, timeframe, data)

        # 4. 更新元数据
        if update_meta:
            self._update_stock_meta(symbol, data)

        logger.info(f"保存 {symbol} {timeframe} 数据完成，共 {len(data)} 条")

    def _generate_cache_key(
            self,
            symbol: str,
            timeframe: str,
            start_date: Optional[str],
            end_date: Optional[str],
            limit: Optional[int]
    ) -> str:
        """生成缓存键"""
        key_parts = [symbol, timeframe]
        if start_date:
            key_parts.append(start_date)
        if end_date:
            key_parts.append(end_date)
        if limit:
            key_parts.append(str(limit))

        key_str = ":".join(key_parts)
        return f"kline:{hashlib.md5(key_str.encode()).hexdigest()}"

    def _get_from_memory(self, key: str, timeframe: str) -> Optional[pd.DataFrame]:
        """从内存缓存获取"""
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            ttl = self.memory_ttl.get(timeframe, 60)
            if time.time() - entry["timestamp"] < ttl:
                return entry["data"]
        return None

    def _set_memory_cache(self, key: str, data: pd.DataFrame, timeframe: str):
        """设置内存缓存"""
        self.memory_cache[key] = {
            "data": data,
            "timestamp": time.time()
        }

        # 限制内存缓存大小
        if len(self.memory_cache) > self.config["max_memory_items"]:
            # 删除最老的缓存
            oldest_key = min(self.memory_cache.keys(),
                             key=lambda k: self.memory_cache[k]["timestamp"])
            del self.memory_cache[oldest_key]

    async def _get_from_redis(self, key: str) -> Optional[pd.DataFrame]:
        """从Redis获取"""
        try:
            data = await self.redis_client.get(key)
            if data:
                return pickle.loads(data)
        except Exception as e:
            logger.warning(f"Redis读取失败: {e}")
        return None

    async def _set_redis_cache(self, key: str, data: pd.DataFrame, timeframe: str):
        """设置Redis缓存"""
        try:
            ttl = self.memory_ttl.get(timeframe, 60) * 10  # Redis TTL是内存的10倍
            serialized = pickle.dumps(data)
            await self.redis_client.setex(key, ttl, serialized)
        except Exception as e:
            logger.warning(f"Redis写入失败: {e}")

    def _get_from_database(
            self,
            symbol: str,
            timeframe: str,
            start_date: Optional[str],
            end_date: Optional[str],
            limit: Optional[int]
    ) -> Optional[pd.DataFrame]:
        """从数据库获取"""
        conn = sqlite3.connect(self.db_path)

        query = """
                SELECT date, open, high, low, close, volume, amount
                FROM kline_data
                WHERE symbol = ? AND timeframe = ? \
                """
        params = [symbol, timeframe]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC"

        if limit:
            query += f" LIMIT {limit}"

        try:
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            if not df.empty:
                # 转换数据类型
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')
                return df
        except Exception as e:
            logger.error(f"数据库查询失败: {e}")
            conn.close()

        return None

    def _save_to_database(self, symbol: str, timeframe: str, data: pd.DataFrame):
        """保存到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for _, row in data.iterrows():
            try:
                # 处理日期格式
                date_str = row.get('date', row.get('time', row.get('ts', '')))
                if pd.isna(date_str):
                    continue

                if isinstance(date_str, pd.Timestamp):
                    date_str = date_str.strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute("""
                    INSERT OR REPLACE INTO kline_data 
                    (symbol, timeframe, date, open, high, low, close, volume, amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, timeframe, date_str,
                    float(row.get('open', 0)),
                    float(row.get('high', 0)),
                    float(row.get('low', 0)),
                    float(row.get('close', 0)),
                    float(row.get('volume', 0)),
                    float(row.get('amount', 0))
                ))
            except Exception as e:
                logger.warning(f"插入数据失败: {e}, row: {row}")

        conn.commit()
        conn.close()

    def _update_stock_meta(self, symbol: str, data: pd.DataFrame):
        """更新股票元数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 获取数据范围
        dates = pd.to_datetime(data['date'] if 'date' in data.columns else data['time'])
        start_date = dates.min().strftime('%Y-%m-%d')
        end_date = dates.max().strftime('%Y-%m-%d')

        cursor.execute("""
            INSERT OR REPLACE INTO stock_meta 
            (symbol, total_bars, last_update, data_range_start, data_range_end)
            VALUES (?, ?, datetime('now'), ?, ?)
        """, (symbol, len(data), start_date, end_date))

        conn.commit()
        conn.close()

    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        total_hits = self.stats["l1_hits"] + self.stats["l2_hits"] + self.stats["l3_hits"]
        hit_rate = total_hits / max(self.stats["total_requests"], 1)

        return {
            "total_requests": self.stats["total_requests"],
            "l1_hits": self.stats["l1_hits"],
            "l2_hits": self.stats["l2_hits"],
            "l3_hits": self.stats["l3_hits"],
            "api_calls": self.stats["api_calls"],
            "hit_rate": f"{hit_rate:.2%}",
            "memory_items": len(self.memory_cache)
        }

    async def preload_stock_data(self, symbol: str, data_provider=None):
        """
        预加载股票全量历史数据（后台异步执行）
        """
        logger.info(f"开始预加载 {symbol} 全量历史数据...")

        if not data_provider:
            logger.warning("未提供数据提供者，无法预加载")
            return

        # 获取股票元数据
        meta = await self.get_stock_meta(symbol)

        # 确定起始日期
        if meta.get("listing_date"):
            start_date = meta["listing_date"]
        else:
            # 默认从2010年开始
            start_date = "2010-01-01"

        # 分批获取数据，每批1年
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.now()

        while current_date < end_date:
            batch_end = min(current_date + timedelta(days=365), end_date)

            try:
                # 从数据提供者获取数据
                data = await data_provider.get_bars(
                    symbol=symbol,
                    timeframe="1d",
                    start_date=current_date.strftime("%Y-%m-%d"),
                    end_date=batch_end.strftime("%Y-%m-%d")
                )

                if data is not None and not data.empty:
                    # 保存到缓存
                    await self.save_data(symbol, "1d", data, update_meta=True)
                    logger.info(f"预加载 {symbol} {current_date.year} 年数据完成")

            except Exception as e:
                logger.error(f"预加载 {symbol} 数据失败: {e}")

            current_date = batch_end

        logger.info(f"{symbol} 全量历史数据预加载完成")
