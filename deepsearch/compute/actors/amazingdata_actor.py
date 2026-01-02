"""
AmazingData Dask Actor

在 Windows Worker 上保持 AmazingData SDK 登录状态的有状态 Actor。
通过消息总线转发实时订阅数据到主进程。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Sequence

from loguru import logger

if TYPE_CHECKING:
    pass


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
        self._tgw: Any = None  # TGW 实例
        self._base_data: Any = None  # BaseData 实例
        self._logged_in = False
        self._subscribed_symbols: set[str] = set()
        self._message_bus: Any = None
        self._last_activity = time.time()
        self._error_count = 0

        logger.info("AmazingDataActor 实例已创建")

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
        if self._logged_in:
            logger.info("AmazingData 已登录，跳过重复登录")
            return True

        username = username or self._config.get("username")
        password = password or self._config.get("password")
        tgw_url = tgw_url or self._config.get("tgw_url")

        if not username or not password:
            logger.error("登录失败：缺少用户名或密码")
            return False

        try:
            # 延迟导入 SDK (只在 Windows Worker 上可用)
            from amazingdata import TGW, BaseData

            logger.info("正在登录 AmazingData (TGW: {})...", tgw_url or "default")

            # 初始化 TGW
            self._tgw = TGW()
            if tgw_url:
                self._tgw.set_server(tgw_url)

            # 登录
            login_result = self._tgw.login(username, password)
            if not login_result:
                logger.error("AmazingData 登录失败")
                return False

            # 初始化 BaseData
            self._base_data = BaseData()

            self._logged_in = True
            self._last_activity = time.time()
            logger.info("AmazingData 登录成功")
            return True

        except ImportError as e:
            logger.error("无法导入 AmazingData SDK: {}", e)
            return False
        except Exception as e:
            logger.error("AmazingData 登录异常: {}", e)
            self._error_count += 1
            return False

    async def logout(self) -> None:
        """登出 AmazingData SDK"""
        if not self._logged_in:
            return

        try:
            if self._tgw:
                self._tgw.logout()
            self._logged_in = False
            self._tgw = None
            self._base_data = None
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
                from deepsearch.messaging import create_message_bus

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
