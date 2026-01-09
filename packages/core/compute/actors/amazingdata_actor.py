"""
AmazingData Dask Actor

在 Windows Worker 上保持 AmazingData SDK 登录状态的有状态 Actor。
通过消息总线转发实时订阅数据到主进程。
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Sequence, TypeVar

from loguru import logger

if TYPE_CHECKING:
    pass

# 登录点标识符，用于调试追踪
_LOGIN_POINT_ID = "ACTOR"


# 泛型类型变量，用于超时包装器返回值
_T = TypeVar("_T")

# InfoData SDK 调用的默认超时时间（秒）
_SDK_TIMEOUT_SECONDS = 30.0


class AmazingDataActor:
    """AmazingData Dask Actor

    在 Dask Windows Worker 上运行，保持 SDK 登录状态。
    支持以下功能：
    - 持久化登录会话
    - 历史 K 线数据查询
    - 实时行情订阅（通过消息总线转发）
    - 交易日历查询

    注意：这是一个 Dask Actor，其状态保持在 Worker 上。

    Example:
        >>> from dask.distributed import Client
        >>> client = Client("tcp://127.0.0.1:8786")
        >>> future = client.submit(AmazingDataActor, config, actor=True, resources={"WIN": 1})
        >>> actor = await future
        >>> await actor.login(username, password)
        >>> data = await actor.get_kline("000001", "1d")
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """初始化 Actor

        Args:
            config: 配置字典，包含登录信息和消息总线配置
        """
        self._config = config or {}
        self._sdk: Any = None
        self._base_data: Any = None  # BaseData 实例
        self._market_data: Any = None  # MarketData 实例
        self._info_data: Any = None  # InfoData 实例
        self._logged_in = False
        self._subscribed_symbols: set[str] = set()
        self._message_bus: Any = None
        self._last_activity = time.time()
        self._error_count = 0
        self._tgw: Any = None  # TGW 实例（如果使用）

        # 分布式会话管理
        self._worker_id = f"actor-{os.getpid()}"
        self._redis: Any = None  # Redis 连接（延迟初始化）
        self._redis_session_key = "amazingdata:session"
        self._session_ttl = 60  # 秒

        logger.info(
            "[LOGIN_TRACE][{}] AmazingDataActor 实例已创建 | worker_id={}",
            _LOGIN_POINT_ID,
            self._worker_id,
        )

    # ==================== API 层兼容属性 ====================

    @property
    def _connected(self) -> bool:
        """是否已连接（API 层检查用）"""
        return self._logged_in

    @property
    def _degraded_mode(self) -> bool:
        """是否处于降级模式"""
        return False

    @property
    def _sdk_available(self) -> bool:
        """SDK 是否可用"""
        return True

    # ==================== IDataFeed 接口兼容层 ====================

    @property
    def name(self) -> str:
        """数据源名称 (IDataFeed)"""
        return "amazingdata"

    @property
    def is_connected(self) -> bool:
        """是否已连接 (IDataFeed)"""
        return self._logged_in

    def normalize_symbol(self, symbol: str) -> str:
        """将任意格式转为 SDK 需要的格式 (IDataFeed)

        输入: SH.600000 或 600000.SH 或 600000
        输出: 600000.SH (SDK 期望的后缀格式)
        """
        return self._convert_code_to_sdk_format(symbol)

    def standardize_symbol(self, symbol: str) -> str:
        """将 SDK 返回的格式转为标准后缀格式 (IDataFeed)

        SDK 已使用标准后缀格式，直接返回。
        """
        return symbol

    async def get_stock_info(self, symbols: list[str]) -> list[dict]:
        """获取股票基础信息 (IDataFeed)

        代理到 get_stock_basic 方法。
        """
        return await self.get_stock_basic(symbols)

    # ==================== 代码格式转换 ====================

    @staticmethod
    def _convert_code_to_sdk_format(code: str) -> str:
        """将统一格式 (SH.600000 或 SZ.000001) 转换为 AmazingData SDK 格式 (600000.SH)

        支持的输入格式:
        - SH.600000 -> 600000.SH
        - SZ.000001 -> 000001.SZ
        - BJ.430047 -> 430047.BJ
        - 600000.SH -> 600000.SH (已是目标格式，直接返回)
        - 600000 -> 600000 (无市场前缀，原样返回)
        """
        if not code:
            return code

        # 如果已经是后缀格式 (600000.SH)，直接返回
        if "." in code:
            parts = code.split(".")
            if len(parts) == 2:
                first, second = parts
                # 检查是否是前缀格式 (SH.600000)
                if first.upper() in ("SH", "SZ", "BJ"):
                    # 转换为后缀格式
                    return f"{second}.{first.upper()}"
                # 已经是后缀格式，直接返回
                return code

        # 无市场标识，原样返回
        return code

    @staticmethod
    def _convert_codes_to_sdk_format(codes: list[str]) -> list[str]:
        """批量转换代码格式"""
        return [AmazingDataActor._convert_code_to_sdk_format(c) for c in codes]

    async def login(
        self,
        username: str | None = None,
        password: str | None = None,
        tgw_url: str | None = None,
    ) -> bool:
        """登录 AmazingData SDK

        Args:
            username: 用户名（或使用配置中的值）
            password: 密码（或使用配置中的值）
            tgw_url: TGW 服务地址

        Returns:
            登录是否成功
        """
        logger.info(
            "[LOGIN_TRACE][{}] ===== 登录请求开始 ===== | _logged_in={}",
            _LOGIN_POINT_ID,
            self._logged_in,
        )

        if self._logged_in:
            logger.info(
                "[LOGIN_TRACE][{}] 本地已登录，跳过重复登录",
                _LOGIN_POINT_ID,
            )
            return True

        # 初始化 Redis 并检查分布式会话
        redis_available = await self._init_redis()
        if redis_available:
            session_valid = await self._check_distributed_session()
            if session_valid:
                logger.info(
                    "[LOGIN_TRACE][{}] 复用分布式会话，跳过 SDK 登录",
                    _LOGIN_POINT_ID,
                )
                # 仍需初始化 SDK 数据对象（不调用 login）
                try:
                    import AmazingData as sdk

                    self._sdk = sdk
                    self._base_data = sdk.BaseData()  # type: ignore[misc]
                    calendar = self._base_data.get_calendar()
                    logger.info(
                        "[LOGIN_TRACE][{}] calendar 类型={}, 长度={}, 非空={}",
                        _LOGIN_POINT_ID,
                        type(calendar).__name__,
                        len(calendar) if hasattr(calendar, "__len__") else "N/A",
                        bool(calendar) if calendar is not None else False,
                    )
                    # 确保 calendar 是 list 类型
                    if isinstance(calendar, dict):
                        calendar = calendar.get("data", calendar.get("calendar", []))
                    self._market_data = sdk.MarketData(calendar) if calendar else None  # type: ignore[misc]
                    self._info_data = sdk.InfoData()  # type: ignore[misc]
                    self._logged_in = True
                    self._last_activity = time.time()
                    logger.info(
                        "[LOGIN_TRACE][{}] SDK 数据对象初始化成功（复用会话）",
                        _LOGIN_POINT_ID,
                    )
                    return True
                except Exception as e:
                    logger.warning(
                        "[LOGIN_TRACE][{}] 复用会话失败，回退到完整登录: {}",
                        _LOGIN_POINT_ID,
                        e,
                    )

        username = username or self._config.get("username")
        password = password or self._config.get("password")
        tgw_url = tgw_url or self._config.get("tgw_url")

        if not username or not password:
            logger.error(
                "[LOGIN_TRACE][{}] 登录失败：缺少用户名或密码",
                _LOGIN_POINT_ID,
            )
            return False

        try:
            # 延迟导入 SDK (只在 Windows Worker 上可用)
            import AmazingData as sdk

            host = self._config.get("host", "101.230.159.234")
            port = self._config.get("port", 8600)

            logger.info(
                "[LOGIN_TRACE][{}] 准备调用 sdk.login() | host={}:{} username={}",
                _LOGIN_POINT_ID,
                host,
                port,
                username,
            )

            # 调用 SDK 登录
            sdk.login(
                username=username,
                password=password,
                host=host,
                port=port,
            )

            logger.info(
                "[LOGIN_TRACE][{}] sdk.login() 调用完成",
                _LOGIN_POINT_ID,
            )

            # 保存 SDK 引用
            self._sdk = sdk

            # 初始化数据对象
            self._base_data = sdk.BaseData()  # type: ignore[misc]
            calendar = self._base_data.get_calendar()
            logger.info(
                "[LOGIN_TRACE][{}] calendar 类型={}, 长度={}",
                _LOGIN_POINT_ID,
                type(calendar).__name__,
                len(calendar) if hasattr(calendar, "__len__") else "N/A",
            )
            # 确保 calendar 是 list 类型
            if isinstance(calendar, dict):
                calendar = calendar.get("data", calendar.get("calendar", []))
            self._market_data = sdk.MarketData(calendar) if calendar else None  # type: ignore[misc]
            self._info_data = sdk.InfoData()  # type: ignore[misc]

            self._logged_in = True
            self._last_activity = time.time()

            # 发布会话状态到 Redis
            await self._publish_session_state()

            logger.info(
                "[LOGIN_TRACE][{}] ===== 登录成功 =====",
                _LOGIN_POINT_ID,
            )
            return True

        except ImportError as e:
            logger.error(
                "[LOGIN_TRACE][{}] 无法导入 AmazingData SDK: {}",
                _LOGIN_POINT_ID,
                e,
            )
            return False
        except Exception as e:
            logger.error(
                "[LOGIN_TRACE][{}] 登录异常: {}",
                _LOGIN_POINT_ID,
                e,
            )
            self._error_count += 1
            return False

    async def _init_redis(self) -> bool:
        """初始化 Redis 连接用于分布式会话检查"""
        if self._redis is not None:
            return True

        redis_url = self._config.get("redis_url", "redis://localhost:6379")
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
            await self._redis.ping()
            logger.debug(
                "[LOGIN_TRACE][{}] Redis 连接成功 | url={}",
                _LOGIN_POINT_ID,
                redis_url,
            )
            return True
        except ImportError:
            logger.warning(
                "[LOGIN_TRACE][{}] redis 包不可用，跳过分布式会话检查",
                _LOGIN_POINT_ID,
            )
            return False
        except Exception as exc:
            logger.warning(
                "[LOGIN_TRACE][{}] Redis 连接失败: {} | url={}",
                _LOGIN_POINT_ID,
                exc,
                redis_url,
            )
            return False

    async def _check_distributed_session(self) -> bool:
        """检查 Redis 中是否存在有效的分布式会话"""
        if self._redis is None:
            return False

        try:
            session_data = await self._redis.get(self._redis_session_key)
            if not session_data:
                logger.debug(
                    "[LOGIN_TRACE][{}] 未找到分布式会话",
                    _LOGIN_POINT_ID,
                )
                return False

            session = json.loads(session_data)
            if not session.get("logged_in"):
                return False

            # 检查心跳是否过期
            heartbeat_str = session.get("heartbeat", "")
            if not heartbeat_str:
                return False

            heartbeat_time = datetime.fromisoformat(heartbeat_str)
            age = (datetime.now() - heartbeat_time).total_seconds()

            if age > self._session_ttl:
                logger.warning(
                    "[LOGIN_TRACE][{}] 分布式会话已过期 | age={:.1f}s > TTL={}s",
                    _LOGIN_POINT_ID,
                    age,
                    self._session_ttl,
                )
                return False

            holder_id = session.get("holder_id", "unknown")
            logger.info(
                "[LOGIN_TRACE][{}] 发现有效分布式会话 | holder={} age={:.1f}s",
                _LOGIN_POINT_ID,
                holder_id,
                age,
            )
            return True

        except Exception as exc:
            logger.warning(
                "[LOGIN_TRACE][{}] 检查分布式会话失败: {}",
                _LOGIN_POINT_ID,
                exc,
            )
            return False

    async def _publish_session_state(self) -> None:
        """发布会话状态到 Redis"""
        if self._redis is None:
            return

        try:
            session = {
                "logged_in": True,
                "holder_id": self._worker_id,
                "login_time": datetime.now().isoformat(),
                "heartbeat": datetime.now().isoformat(),
                "source": "AmazingDataActor",
            }
            await self._redis.set(
                self._redis_session_key,
                json.dumps(session),
                ex=self._session_ttl * 2,
            )
            logger.info(
                "[LOGIN_TRACE][{}] 已发布会话状态到 Redis | worker_id={}",
                _LOGIN_POINT_ID,
                self._worker_id,
            )
        except Exception as exc:
            logger.warning(
                "[LOGIN_TRACE][{}] 发布会话状态失败: {}",
                _LOGIN_POINT_ID,
                exc,
            )

    async def logout(self) -> None:
        """登出 AmazingData SDK"""
        if not self._logged_in:
            return

        try:
            if self._sdk:
                self._sdk.logout()
            self._logged_in = False
            self._sdk = None
            self._base_data = None
            self._market_data = None
            self._info_data = None
            logger.info("AmazingData 已登出")
        except Exception as e:
            logger.warning("AmazingData 登出异常: {}", e)

    async def is_logged_in(self) -> bool:
        """检查登录状态"""
        return self._logged_in

    async def get_kline(
        self,
        symbol: str,
        period: str = "1d",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> dict[str, list]:
        """获取 K 线数据

        Args:
            symbol: 股票代码
            period: 周期
            start_date: 开始日期
            end_date: 结束日期
            limit: 数量限制

        Returns:
            K 线数据字典
        """
        if not self._logged_in or not self._base_data:
            raise RuntimeError("未登录 AmazingData")

        try:
            self._last_activity = time.time()

            # 规范化代码
            code = symbol.split(".")[0] if "." in symbol else symbol

            # 调用 SDK
            df = self._base_data.get_history(
                code=code,
                period=period,
                count=limit,
            )

            if df is None or df.empty:
                return {}

            # 转换为字典
            result = {}
            for col in df.columns:
                result[col] = df[col].tolist()
            return result

        except Exception as e:
            logger.error("获取 K 线失败 ({}): {}", symbol, e)
            self._error_count += 1
            raise

    async def get_realtime_quotes(
        self,
        symbols: Sequence[str],
    ) -> list[dict[str, Any]]:
        """获取实时行情

        Args:
            symbols: 股票代码列表

        Returns:
            行情数据列表
        """
        if not self._logged_in or not self._tgw:
            raise RuntimeError("未登录 AmazingData")

        try:
            self._last_activity = time.time()

            # 规范化代码
            codes = [s.split(".")[0] if "." in s else s for s in symbols]

            # 调用 SDK
            data = self._tgw.get_snapshot(codes)

            if not data:
                return []

            # 转换格式
            result = []
            for code, snapshot in data.items():
                result.append(
                    {
                        "code": code,
                        "last_price": snapshot.get("last", 0),
                        "open": snapshot.get("open", 0),
                        "high": snapshot.get("high", 0),
                        "low": snapshot.get("low", 0),
                        "volume": snapshot.get("volume", 0),
                        "amount": snapshot.get("amount", 0),
                        "bid_prices": snapshot.get("bid_prices", []),
                        "ask_prices": snapshot.get("ask_prices", []),
                    }
                )
            return result

        except Exception as e:
            logger.error("获取实时行情失败: {}", e)
            self._error_count += 1
            raise

    async def get_calendar(self, market: str = "SH") -> list[int]:
        """获取交易日历

        Args:
            market: 市场代码

        Returns:
            交易日列表
        """
        if not self._logged_in or not self._base_data:
            raise RuntimeError("未登录 AmazingData")

        try:
            self._last_activity = time.time()

            calendar = self._base_data.get_calendar(market=market)
            if calendar is None:
                return []

            return [int(d) for d in calendar if d]

        except Exception as e:
            logger.error("获取交易日历失败: {}", e)
            self._error_count += 1
            raise

    async def subscribe(
        self,
        symbols: Sequence[str],
        callback_topic: str,
    ) -> None:
        """订阅实时行情

        通过消息总线将行情推送到指定主题。

        Args:
            symbols: 股票代码列表
            callback_topic: 消息总线回调主题
        """
        if not self._logged_in or not self._tgw:
            raise RuntimeError("未登录 AmazingData")

        try:
            # 懒加载消息总线
            if self._message_bus is None:
                from core.messaging import create_message_bus

                bus_config = self._config.get("message_bus", {})
                self._message_bus = create_message_bus(
                    bus_type=bus_config.get("type", "rabbitmq"),
                    **bus_config.get("config", {}),
                )
                self._message_bus.start()

            codes = [s.split(".")[0] if "." in s else s for s in symbols]

            def on_snapshot(data: dict):
                """行情回调，转发到消息总线"""
                try:
                    self._message_bus.publish(callback_topic, data)
                except Exception as e:
                    logger.warning("行情消息转发失败: {}", e)

            # 订阅
            self._tgw.subscribe(codes, on_snapshot)
            self._subscribed_symbols.update(codes)

            logger.info("已订阅 {} 只股票，回调主题: {}", len(codes), callback_topic)

        except Exception as e:
            logger.error("订阅失败: {}", e)
            self._error_count += 1
            raise

    async def unsubscribe(self, symbols: Sequence[str]) -> None:
        """取消订阅

        Args:
            symbols: 股票代码列表
        """
        if not self._logged_in or not self._tgw:
            return

        try:
            codes = [s.split(".")[0] if "." in s else s for s in symbols]
            self._tgw.unsubscribe(codes)
            self._subscribed_symbols.difference_update(codes)
            logger.info("已取消订阅 {} 只股票", len(codes))
        except Exception as e:
            logger.warning("取消订阅失败: {}", e)

    async def get_status(self) -> dict[str, Any]:
        """获取 Actor 状态

        Returns:
            状态信息字典
        """
        return {
            "logged_in": self._logged_in,
            "subscribed_count": len(self._subscribed_symbols),
            "subscribed_symbols": list(self._subscribed_symbols)[:20],  # 限制返回数量
            "last_activity": self._last_activity,
            "error_count": self._error_count,
            "uptime_seconds": time.time() - self._last_activity if self._logged_in else 0,
        }

    async def shutdown(self) -> None:
        """关闭 Actor

        清理资源并登出。
        """
        logger.info("正在关闭 AmazingDataActor...")

        # 取消所有订阅
        if self._subscribed_symbols:
            await self.unsubscribe(list(self._subscribed_symbols))

        # 关闭消息总线
        if self._message_bus:
            try:
                self._message_bus.stop()
            except Exception:
                pass
            self._message_bus = None

        # 登出
        await self.logout()

        logger.info("AmazingDataActor 已关闭")

    # ==================== 财务数据接口 ====================

    async def get_profit_express(
        self,
        code_list: list[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """业绩快报

        Args:
            code_list: 股票代码列表
            local_path: 本地存储数据的路径，需绝对路径
            is_local: 是否使用本地缓存，默认True
            begin_date: 报告期开始日期 YYYYMMDD
            end_date: 报告期结束日期 YYYYMMDD
        """
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            kwargs: dict = {"local_path": local_path, "is_local": is_local}
            if begin_date is not None:
                kwargs["begin_date"] = begin_date
            if end_date is not None:
                kwargs["end_date"] = end_date
            result = self._info_data.get_profit_express(code_list, **kwargs)
            return self._to_records(result)
        except Exception as e:
            logger.error("获取业绩快报失败: {}", e)
            self._error_count += 1
            raise

    async def get_profit_notice(
        self,
        code_list: list[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """业绩预告

        Args:
            code_list: 股票代码列表
            local_path: 本地存储数据的路径，需绝对路径
            is_local: 是否使用本地缓存，默认True
            begin_date: 报告期开始日期 YYYYMMDD
            end_date: 报告期结束日期 YYYYMMDD
        """
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            kwargs: dict = {"local_path": local_path, "is_local": is_local}
            if begin_date is not None:
                kwargs["begin_date"] = begin_date
            if end_date is not None:
                kwargs["end_date"] = end_date
            result = self._info_data.get_profit_notice(code_list, **kwargs)
            return self._to_records(result)
        except Exception as e:
            logger.error("获取业绩预告失败: {}", e)
            self._error_count += 1
            raise

    async def get_balance_sheet(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """资产负债表"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_balance_sheet(
                    code_list, begin_date=begin_date, end_date=end_date
                ),
                "InfoData.get_balance_sheet",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取资产负债表失败: {}", e)
            self._error_count += 1
            raise

    async def get_cash_flow(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """现金流量表"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_cash_flow(
                    code_list, begin_date=begin_date, end_date=end_date
                ),
                "InfoData.get_cash_flow",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取现金流量表失败: {}", e)
            self._error_count += 1
            raise

    async def get_income(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """利润表"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_income(
                    code_list, begin_date=begin_date, end_date=end_date
                ),
                "InfoData.get_income",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取利润表失败: {}", e)
            self._error_count += 1
            raise

    # ==================== 股东数据接口 ====================

    async def get_share_holder(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """股东信息"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_share_holder(
                    code_list, begin_date=begin_date, end_date=end_date
                ),
                "InfoData.get_share_holder",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取股东信息失败: {}", e)
            self._error_count += 1
            raise

    async def get_holder_num(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """股东人数"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_holder_num(
                    code_list, begin_date=begin_date, end_date=end_date
                ),
                "InfoData.get_holder_num",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取股东人数失败: {}", e)
            self._error_count += 1
            raise

    # ==================== 股权数据接口 ====================

    async def get_equity_structure(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """股本结构"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_equity_structure(
                    code_list, begin_date=begin_date, end_date=end_date
                ),
                "InfoData.get_equity_structure",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取股本结构失败: {}", e)
            self._error_count += 1
            raise

    async def get_equity_pledge_freeze(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """股权质押冻结"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = self._info_data.get_equity_pledge_freeze(
                code_list, begin_date=begin_date, end_date=end_date
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取股权质押冻结失败: {}", e)
            self._error_count += 1
            raise

    async def get_equity_restricted(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """限售股解禁"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = self._info_data.get_equity_restricted(
                code_list, begin_date=begin_date, end_date=end_date
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取限售股解禁失败: {}", e)
            self._error_count += 1
            raise

    # ==================== 分红配股接口 ====================

    async def get_dividend(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """分红送股"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = self._info_data.get_dividend(
                code_list, begin_date=begin_date, end_date=end_date
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取分红送股失败: {}", e)
            self._error_count += 1
            raise

    async def get_right_issue(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """配股"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = self._info_data.get_right_issue(
                code_list, begin_date=begin_date, end_date=end_date
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取配股失败: {}", e)
            self._error_count += 1
            raise

    # ==================== 融资融券接口 ====================

    async def get_margin_summary(
        self,
        code_list: list[str] | None = None,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """融资融券汇总"""
        import time as _time

        _start = _time.time()
        logger.info(
            f"[get_margin_summary] 开始: code_list={code_list}, begin={begin_date}, end={end_date}"
        )

        if not self._logged_in or not self._info_data:
            logger.error("[get_margin_summary] 未登录 AmazingData")
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = _time.time()
        try:
            # 如果 code_list 为空，使用默认空列表
            codes = code_list or []
            logger.info(f"[get_margin_summary] 调用 SDK InfoData.get_margin_summary, codes={codes}")
            _sdk_start = _time.time()
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_margin_summary(
                    codes, begin_date=begin_date, end_date=end_date
                ),
                "InfoData.get_margin_summary",
            )
            _sdk_elapsed = _time.time() - _sdk_start
            logger.info(
                f"[get_margin_summary] SDK 返回, 耗时={_sdk_elapsed:.2f}s, result_type={type(result).__name__}"
            )
            records = self._to_records(result)
            logger.info(
                f"[get_margin_summary] 完成, 总耗时={_time.time() - _start:.2f}s, count={len(records) if records else 0}"
            )
            return records
        except Exception as e:
            logger.error(f"[get_margin_summary] 异常: {e}")
            self._error_count += 1
            raise

    async def get_margin_detail(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """融资融券明细"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = self._info_data.get_margin_detail(
                code_list, begin_date=begin_date, end_date=end_date
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取融资融券明细失败: {}", e)
            self._error_count += 1
            raise

    # ==================== 特色数据接口 ====================

    async def get_long_hu_bang(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """龙虎榜"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = self._info_data.get_long_hu_bang(
                code_list, begin_date=begin_date, end_date=end_date
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取龙虎榜失败: {}", e)
            self._error_count += 1
            raise

    async def get_block_trading(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """大宗交易"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = self._info_data.get_block_trading(
                code_list, begin_date=begin_date, end_date=end_date
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取大宗交易失败: {}", e)
            self._error_count += 1
            raise

    # ==================== 行业数据接口 ====================

    async def get_industry_daily(
        self,
        industry_code: str | None = None,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """行业日行情"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = self._info_data.get_industry_daily(
                industry_code=industry_code, begin_date=begin_date, end_date=end_date
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取行业日行情失败: {}", e)
            self._error_count += 1
            raise

    async def get_industry_weight(
        self,
        industry_code: str | None = None,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """行业成分权重"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = self._info_data.get_industry_weight(
                industry_code=industry_code, begin_date=begin_date, end_date=end_date
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取行业成分权重失败: {}", e)
            self._error_count += 1
            raise

    # ==================== K线数据接口 (使用 MarketData) ====================

    async def query_kline(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
        period: Any = None,
        adjust: Any = None,
    ) -> dict[str, list]:
        """查询 K 线数据"""
        import time as _time

        _start = _time.time()
        logger.info(
            f"[query_kline] 开始: code_list={code_list}, begin={begin_date}, end={end_date}, period={period}"
        )

        if not self._logged_in:
            logger.error("[query_kline] 未登录 AmazingData")
            raise RuntimeError("未登录 AmazingData")
        if not self._market_data:
            logger.error("[query_kline] MarketData 未初始化")
            raise RuntimeError("MarketData 未初始化（可能交易日历为空）")

        self._last_activity = _time.time()
        try:
            # 转换代码格式：SH.600000 -> 600000.SH
            sdk_codes = self._convert_codes_to_sdk_format(code_list)
            logger.info(f"[query_kline] 代码转换: {code_list} -> {sdk_codes}")

            # Period 字符串到 SDK 整数值的映射
            # 根据 SDK 文档: 10000=1min, 10002=5min, 10008=day 等
            PERIOD_MAP = {
                "1min": 10000,
                "min1": 10000,
                "5min": 10002,
                "min5": 10002,
                "15min": 10003,
                "min15": 10003,
                "30min": 10004,
                "min30": 10004,
                "60min": 10005,
                "min60": 10005,
                "daily": 10008,
                "day": 10008,
                "weekly": 10009,
                "week": 10009,
                "monthly": 10010,
                "month": 10010,
            }

            # 转换 period 参数
            effective_period = period
            if isinstance(effective_period, str):
                effective_period = PERIOD_MAP.get(effective_period.lower(), 10008)  # 默认日线
            elif effective_period is None:
                effective_period = 10008  # 默认日线

            logger.info(
                f"[query_kline] 调用 SDK: codes={sdk_codes}, begin={begin_date}, end={end_date}, period={effective_period}"
            )
            _sdk_start = _time.time()
            # SDK query_kline 需要位置参数: code_list, begin_date, end_date, period
            result = self._market_data.query_kline(
                sdk_codes, begin_date, end_date, effective_period
            )
            _sdk_elapsed = _time.time() - _sdk_start
            logger.info(
                f"[query_kline] SDK 返回, 耗时={_sdk_elapsed:.2f}s, result_type={type(result).__name__}, is_none={result is None}"
            )

            # 转为字典格式
            if result is None:
                logger.warning("[query_kline] SDK 返回 None")
                return {}
            if isinstance(result, dict):
                record_count = sum(len(v) if hasattr(v, "__len__") else 0 for v in result.values())
                logger.info(
                    f"[query_kline] 转换结果: {len(result)} 个代码, 共 {record_count} 条记录"
                )
                converted = {k: self._to_records(v) for k, v in result.items()}
                _total_elapsed = _time.time() - _start
                logger.info(f"[query_kline] 完成, 总耗时={_total_elapsed:.2f}s")
                return converted
            logger.warning(f"[query_kline] 非预期返回类型: {type(result)}")
            return {}
        except Exception as e:
            import traceback

            logger.error(f"[query_kline] 异常: {e}\n{traceback.format_exc()}")
            self._error_count += 1
            raise

    # ==================== 辅助方法 ====================

    def _to_records(self, data: Any) -> list[dict]:
        """将 DataFrame 或其他数据转为 records 列表"""
        if data is None:
            return []
        try:
            import pandas as pd

            if isinstance(data, pd.DataFrame):
                return data.to_dict(orient="records")  # type: ignore[return-value]
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
        except Exception:
            pass
        return []

    async def _run_sdk_with_timeout(
        self,
        func: Callable[[], _T],
        method_name: str,
        timeout: float = _SDK_TIMEOUT_SECONDS,
    ) -> _T:
        """在线程池中执行阻塞式 SDK 调用，并应用超时保护。

        SDK 的 InfoData 方法使用 SPI 回调机制，可能导致无限期阻塞。
        此方法通过 asyncio.to_thread 将调用移至线程池，并用 wait_for 设置超时。

        Args:
            func: 零参数可调用对象，包装实际的 SDK 调用
            method_name: 方法名称，用于日志记录
            timeout: 超时时间（秒），默认 30s

        Returns:
            SDK 调用的返回值

        Raises:
            TimeoutError: 超时时抛出
            Exception: 其他 SDK 异常向上传播
        """
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(func),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "SDK 调用超时 | method={} timeout={}s",
                method_name,
                timeout,
            )
            self._error_count += 1
            raise TimeoutError(
                f"SDK call '{method_name}' timed out after {timeout}s. "
                "The SDK SPI callback may have failed to respond."
            )

    # ==================== Basic Data 接口 ====================

    async def get_code_info(self, security_type: str = "EXTRA_STOCK_A") -> list[dict]:
        """获取每日证券信息"""
        if not self._logged_in or not self._base_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._base_data.get_code_info(security_type=security_type),
                "BaseData.get_code_info",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取证券信息失败: {}", e)
            self._error_count += 1
            raise

    async def get_code_list(self, security_type: str = "EXTRA_STOCK_A") -> list[str]:
        """获取当日代码列表"""
        if not self._logged_in or not self._base_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._base_data.get_code_list(security_type=security_type),
                "BaseData.get_code_list",
            )
            if result is None:
                return []
            if isinstance(result, list):
                return result
            return []
        except Exception as e:
            logger.error("获取代码列表失败: {}", e)
            self._error_count += 1
            raise

    async def get_stock_basic(self, code_list: list[str]) -> list[dict]:
        """获取股票基础信息"""
        import time as _time

        _start = _time.time()
        logger.info(f"[get_stock_basic] 开始: code_list={code_list}")

        if not self._logged_in or not self._info_data:
            logger.error("[get_stock_basic] 未登录 AmazingData")
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = _time.time()
        try:
            # 转换代码格式：SH.600000 -> 600000.SH
            sdk_codes = self._convert_codes_to_sdk_format(code_list)
            logger.info(f"[get_stock_basic] 代码转换: {code_list} -> {sdk_codes}")
            logger.info(f"[get_stock_basic] 调用 SDK InfoData.get_stock_basic({sdk_codes})")
            _sdk_start = _time.time()
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_stock_basic(sdk_codes),
                "InfoData.get_stock_basic",
            )
            _sdk_elapsed = _time.time() - _sdk_start
            logger.info(
                f"[get_stock_basic] SDK 返回, 耗时={_sdk_elapsed:.2f}s, result_type={type(result).__name__}, is_none={result is None}"
            )

            # 打印原始结果帮助诊断
            if result is None:
                logger.warning("[get_stock_basic] SDK 返回 None")
            elif hasattr(result, "empty") and result.empty:
                logger.warning("[get_stock_basic] SDK 返回空 DataFrame")
            else:
                logger.info(
                    f"[get_stock_basic] SDK 返回数据, shape={getattr(result, 'shape', 'N/A')}"
                )

            records = self._to_records(result)
            logger.info(
                f"[get_stock_basic] 完成, 总耗时={_time.time() - _start:.2f}s, count={len(records) if records else 0}"
            )
            return records
        except Exception as e:
            logger.error(f"[get_stock_basic] 异常: {e}")
            self._error_count += 1
            raise

    async def get_future_code_list(self, security_type: str = "EXTRA__FUTURE") -> list[str]:
        """获取期货代码列表"""
        if not self._logged_in or not self._base_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._base_data.get_code_list(security_type=security_type),
                "BaseData.get_future_code_list",
            )
            if result is None:
                return []
            if isinstance(result, list):
                return result
            return []
        except Exception as e:
            logger.error("获取期货代码列表失败: {}", e)
            self._error_count += 1
            raise

    async def get_bj_code_mapping(
        self, local_path: str | None = None, is_local: bool = True
    ) -> list[dict]:
        """获取北交所代码映射

        Args:
            local_path: 本地存储路径
            is_local: 是否使用本地数据
        """
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            # 根据反编译确认，get_bj_code_mapping 在 InfoData 中
            kwargs: dict[str, Any] = {}
            if local_path:
                kwargs["local_path"] = local_path
            if is_local is not None:
                kwargs["is_local"] = is_local
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_bj_code_mapping(**kwargs),
                "InfoData.get_bj_code_mapping",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取北交所代码映射失败: {}", e)
            self._error_count += 1
            raise

    async def get_backward_factor(
        self, code_list: list[str], local_path: str | None = None, is_local: bool = True
    ) -> list[dict]:
        """获取后复权因子

        Args:
            code_list: 代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地数据
        """
        if not self._logged_in or not self._base_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            kwargs: dict[str, Any] = {"code_list": code_list}
            if local_path:
                kwargs["local_path"] = local_path
            if is_local is not None:
                kwargs["is_local"] = is_local
            result = await self._run_sdk_with_timeout(
                lambda: self._base_data.get_backward_factor(**kwargs),
                "BaseData.get_backward_factor",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取后复权因子失败: {}", e)
            self._error_count += 1
            raise

    async def get_adj_factor(
        self, code_list: list[str], local_path: str | None = None, is_local: bool = True
    ) -> list[dict]:
        """获取前复权因子

        Args:
            code_list: 代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地数据
        """
        if not self._logged_in or not self._base_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            kwargs: dict[str, Any] = {"code_list": code_list}
            if local_path:
                kwargs["local_path"] = local_path
            if is_local is not None:
                kwargs["is_local"] = is_local
            result = await self._run_sdk_with_timeout(
                lambda: self._base_data.get_adj_factor(**kwargs),
                "BaseData.get_adj_factor",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取前复权因子失败: {}", e)
            self._error_count += 1
            raise

    async def get_history_stock_status(self, code_list: list[str]) -> list[dict]:
        """获取历史证券状态"""
        if not self._logged_in or not self._base_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._base_data.get_history_stock_status(code_list),
                "BaseData.get_history_stock_status",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取历史证券状态失败: {}", e)
            self._error_count += 1
            raise

    async def get_hist_code_list(
        self,
        security_type: str = "EXTRA_STOCK_A_SH_SZ",
        start_date: int | None = None,
        end_date: int | None = None,
    ) -> list[str]:
        """获取历史代码列表"""
        if not self._logged_in or not self._base_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            kwargs: dict[str, Any] = {"security_type": security_type}
            if start_date is not None:
                kwargs["start_date"] = start_date
            if end_date is not None:
                kwargs["end_date"] = end_date
            result = await self._run_sdk_with_timeout(
                lambda: self._base_data.get_hist_code_list(**kwargs),
                "BaseData.get_hist_code_list",
            )
            if result is None:
                return []
            if isinstance(result, list):
                return result
            return []
        except Exception as e:
            logger.error("获取历史代码列表失败: {}", e)
            self._error_count += 1
            raise

    # ==================== History 接口 ====================

    async def query_snapshot(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
        period: str = "day",
    ) -> list[dict]:
        """查询历史快照"""
        if not self._logged_in or not self._market_data:
            raise RuntimeError("未登录 AmazingData 或 MarketData 未初始化")
        self._last_activity = time.time()
        try:
            kwargs: dict[str, Any] = {}
            if begin_date is not None:
                kwargs["begin_date"] = begin_date
            if end_date is not None:
                kwargs["end_date"] = end_date
            result = await self._run_sdk_with_timeout(
                lambda: self._market_data.query_snapshot(code_list, **kwargs),
                "MarketData.query_snapshot",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("查询历史快照失败: {}", e)
            self._error_count += 1
            raise

    # ==================== Option 接口 ====================

    async def get_option_code_list(self, security_type: str = "EXTRA_OPTION") -> list[str]:
        """获取期权代码列表"""
        if not self._logged_in or not self._base_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._base_data.get_code_list(security_type=security_type),
                "BaseData.get_option_code_list",
            )
            if result is None:
                return []
            if isinstance(result, list):
                return result
            return []
        except Exception as e:
            logger.error("获取期权代码列表失败: {}", e)
            self._error_count += 1
            raise

    async def get_option_basic_info(
        self, code_list: list[str], begin_date: int | None = None, end_date: int | None = None
    ) -> list[dict]:
        """获取期权基础信息"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_option_basic_info(
                    code_list, begin_date=begin_date, end_date=end_date
                ),
                "InfoData.get_option_basic_info",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取期权基础信息失败: {}", e)
            self._error_count += 1
            raise

    async def get_option_std_ctr_specs(
        self, code_list: list[str], begin_date: int | None = None, end_date: int | None = None
    ) -> list[dict]:
        """获取期权标准合约规格"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_option_std_ctr_specs(
                    code_list, begin_date=begin_date, end_date=end_date
                ),
                "InfoData.get_option_std_ctr_specs",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取期权标准合约规格失败: {}", e)
            self._error_count += 1
            raise

    async def get_option_mon_ctr_specs(
        self,
        code_list: list[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> list[dict]:
        """获取期权月合约属性变动

        Args:
            code_list: ETF期权代码列表
            local_path: 本地存储数据的路径，需绝对路径
            is_local: 是否使用本地缓存，默认True
        """
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_option_mon_ctr_specs(
                    code_list, local_path=local_path, is_local=is_local
                ),
                "InfoData.get_option_mon_ctr_specs",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取期权月合约属性变动失败: {}", e)
            self._error_count += 1
            raise

    # ==================== ETF 接口 ====================

    async def get_etf_pcf(self, code_list: list[str]) -> list[dict]:
        """获取 ETF 成分股"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_etf_pcf(code_list),
                "InfoData.get_etf_pcf",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取 ETF 成分股失败: {}", e)
            self._error_count += 1
            raise

    async def get_fund_share(
        self,
        code_list: list[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """获取基金份额变动

        Args:
            code_list: ETF代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地缓存
            begin_date: 变动日期开始 YYYYMMDD
            end_date: 变动日期结束 YYYYMMDD
        """
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            kwargs: dict = {"local_path": local_path, "is_local": is_local}
            if begin_date is not None:
                kwargs["begin_date"] = begin_date
            if end_date is not None:
                kwargs["end_date"] = end_date
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_fund_share(code_list, **kwargs),
                "InfoData.get_fund_share",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取基金份额失败: {}", e)
            self._error_count += 1
            raise

    async def get_fund_iopv(
        self,
        code_list: list[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """获取基金收盘IOPV

        Args:
            code_list: ETF代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地缓存
            begin_date: 变动日期开始 YYYYMMDD
            end_date: 变动日期结束 YYYYMMDD
        """
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            kwargs: dict = {"local_path": local_path, "is_local": is_local}
            if begin_date is not None:
                kwargs["begin_date"] = begin_date
            if end_date is not None:
                kwargs["end_date"] = end_date
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_fund_iopv(code_list, **kwargs),
                "InfoData.get_fund_iopv",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取基金IOPV失败: {}", e)
            self._error_count += 1
            raise

    # ==================== 交易所指数接口 ====================

    async def get_index_constituent(
        self,
        code_list: list[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> list[dict]:
        """获取指数成分股

        Args:
            code_list: 指数代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地缓存
        """
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_index_constituent(
                    code_list, local_path=local_path, is_local=is_local
                ),
                "InfoData.get_index_constituent",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取指数成分股失败: {}", e)
            self._error_count += 1
            raise

    async def get_index_weight(
        self,
        code_list: list[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """获取指数成分股日权重

        Args:
            code_list: 指数代码列表 (支持5个指数: 000016.SH, 000300.SH, 000905.SH, 000906.SH, 000852.SH)
            local_path: 本地存储路径
            is_local: 是否使用本地缓存
            begin_date: 变动日期开始 YYYYMMDD
            end_date: 变动日期结束 YYYYMMDD
        """
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            kwargs: dict = {"local_path": local_path, "is_local": is_local}
            if begin_date is not None:
                kwargs["begin_date"] = begin_date
            if end_date is not None:
                kwargs["end_date"] = end_date
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_index_weight(code_list, **kwargs),
                "InfoData.get_index_weight",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取指数成分股权重失败: {}", e)
            self._error_count += 1
            raise

    # ==================== 行业指数接口 ====================

    async def get_industry_base_info(
        self,
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> list[dict]:
        """获取行业指数基本信息

        Args:
            local_path: 本地存储路径
            is_local: 是否使用本地缓存
        """
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_industry_base_info(
                    local_path=local_path, is_local=is_local
                ),
                "InfoData.get_industry_base_info",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取行业基本信息失败: {}", e)
            self._error_count += 1
            raise

    async def get_industry_constituent(
        self,
        code_list: list[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> list[dict]:
        """获取行业成分股

        Args:
            code_list: 行业代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地缓存
        """
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_industry_constituent(
                    code_list, local_path=local_path, is_local=is_local
                ),
                "InfoData.get_industry_constituent",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取行业成分股失败: {}", e)
            self._error_count += 1
            raise

    async def get_industry_weight_batch(
        self,
        code_list: list[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """批量获取行业成分股权重

        Args:
            code_list: 行业代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地缓存
            begin_date: 日期开始 YYYYMMDD
            end_date: 日期结束 YYYYMMDD
        """
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            kwargs: dict = {"local_path": local_path, "is_local": is_local}
            if begin_date is not None:
                kwargs["begin_date"] = begin_date
            if end_date is not None:
                kwargs["end_date"] = end_date
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_industry_weight(code_list, **kwargs),
                "InfoData.get_industry_weight",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取行业成分股权重失败: {}", e)
            self._error_count += 1
            raise

    async def get_industry_daily_batch(
        self,
        code_list: list[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """批量获取行业指数日行情

        Args:
            code_list: 行业代码列表（从 get_industry_base_info 获取）
            local_path: 本地存储路径
            is_local: 是否使用本地缓存
            begin_date: 交易日期开始 YYYYMMDD
            end_date: 交易日期结束 YYYYMMDD
        """
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            kwargs: dict = {"local_path": local_path, "is_local": is_local}
            if begin_date is not None:
                kwargs["begin_date"] = begin_date
            if end_date is not None:
                kwargs["end_date"] = end_date
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_industry_daily(code_list, **kwargs),
                "InfoData.get_industry_daily",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取行业日行情失败: {}", e)
            self._error_count += 1
            raise

    # ==================== Realtime 订阅接口 ====================

    async def subscribe_index_snapshot(self, code_list: list[str]) -> None:
        """订阅指数快照"""
        logger.info("订阅指数快照: {} 只", len(code_list))
        # TODO: 实现实际订阅逻辑

    async def subscribe_stock_snapshot(self, code_list: list[str]) -> None:
        """订阅股票快照"""
        logger.info("订阅股票快照: {} 只", len(code_list))
        # TODO: 实现实际订阅逻辑

    async def subscribe_future_snapshot(self, code_list: list[str]) -> None:
        """订阅期货快照"""
        logger.info("订阅期货快照: {} 只", len(code_list))
        # TODO: 实现实际订阅逻辑

    async def subscribe_etf_snapshot(self, code_list: list[str]) -> None:
        """订阅 ETF 快照"""
        logger.info("订阅 ETF 快照: {} 只", len(code_list))
        # TODO: 实现实际订阅逻辑

    async def subscribe_kzz_snapshot(self, code_list: list[str]) -> None:
        """订阅可转债快照"""
        logger.info("订阅可转债快照: {} 只", len(code_list))
        # TODO: 实现实际订阅逻辑

    async def subscribe_hkt_snapshot(self, code_list: list[str]) -> None:
        """订阅港股通快照"""
        logger.info("订阅港股通快照: {} 只", len(code_list))
        # TODO: 实现实际订阅逻辑

    async def subscribe_option_snapshot(self, code_list: list[str]) -> None:
        """订阅期权快照"""
        logger.info("订阅期权快照: {} 只", len(code_list))
        # TODO: 实现实际订阅逻辑

    async def subscribe_kline(self, code_list: list[str]) -> None:
        """订阅 K 线"""
        logger.info("订阅 K 线: {} 只", len(code_list))
        # TODO: 实现实际订阅逻辑

    async def unsubscribe_all(self) -> None:
        """取消所有订阅"""
        if self._subscribed_symbols:
            await self.unsubscribe(list(self._subscribed_symbols))
        logger.info("已取消所有订阅")

    # ==================== Concept 接口 ====================

    async def get_sector_capital_flow_rank(
        self, sector_type: str = "industry", limit: int = 20
    ) -> list[dict]:
        """获取板块资金流排行"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_sector_capital_flow_rank(
                    sector_type=sector_type, limit=limit
                ),
                "InfoData.get_sector_capital_flow_rank",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取板块资金流排行失败: {}", e)
            self._error_count += 1
            raise

    # ==================== 根据 SDK 反编译补充的方法 ====================

    async def get_future_code_info(self, security_type: str = "EXTRA_FUTURE") -> list[dict]:
        """获取期货代码信息（BaseData）"""
        if not self._logged_in or not self._base_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            result = await self._run_sdk_with_timeout(
                lambda: self._base_data.get_future_code_info(security_type=security_type),
                "BaseData.get_future_code_info",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取期货代码信息失败: {}", e)
            self._error_count += 1
            raise

    async def get_treasury_yield(
        self,
        code_list: list[str] | None = None,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """获取国债收益率（InfoData）"""
        if not self._logged_in or not self._info_data:
            raise RuntimeError("未登录 AmazingData")
        self._last_activity = time.time()
        try:
            kwargs: dict[str, Any] = {}
            if code_list:
                kwargs["code_list"] = code_list
            if begin_date is not None:
                kwargs["begin_date"] = begin_date
            if end_date is not None:
                kwargs["end_date"] = end_date
            result = await self._run_sdk_with_timeout(
                lambda: self._info_data.get_treasury_yield(**kwargs),
                "InfoData.get_treasury_yield",
            )
            return self._to_records(result)
        except Exception as e:
            logger.error("获取国债收益率失败: {}", e)
            self._error_count += 1
            raise
