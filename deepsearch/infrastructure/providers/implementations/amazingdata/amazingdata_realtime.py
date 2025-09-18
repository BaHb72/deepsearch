# encoding:utf-8
"""
AmazingData 实时行情接口实现
实现所有实时订阅接口

Author: DeepSearch Team
Version: 1.0.0
Date: 2025-09-18
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable, Union
import pandas as pd
from loguru import logger
from datetime import datetime

# AmazingData SDK
try:
    import AmazingData as ad
    HAS_AMAZINGDATA = True
except ImportError:
    HAS_AMAZINGDATA = False
    ad = None
    logger.error("AmazingData SDK 未安装，请先安装: pip install AmazingData")


class AmazingDataRealtime:
    """AmazingData 实时行情接口实现"""

    def __init__(self, parent):
        """
        初始化实时行情接口

        Args:
            parent: 父类AmazingDataExtended实例
        """
        self.parent = parent
        self._subscription_data = None
        self._subscription_callbacks = {}
        self._subscription_active = False
        self._subscription_lock = asyncio.Lock()

    async def _init_subscription(self):
        """初始化订阅对象"""
        if not self._subscription_data and self.parent._connected:
            try:
                loop = asyncio.get_event_loop()
                self._subscription_data = await loop.run_in_executor(
                    None, ad.SubscribeData
                )
                logger.info("实时订阅对象初始化成功")
            except Exception as e:
                logger.error(f"初始化订阅对象失败: {e}")

    async def _run_subscription(self):
        """运行订阅循环"""
        if self._subscription_data and not self._subscription_active:
            self._subscription_active = True
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, self._subscription_data.run
                )
            except Exception as e:
                logger.error(f"运行订阅失败: {e}")
            finally:
                self._subscription_active = False

    # ================== 实时行情接口 ==================

    async def onSnapshotindex(
        self,
        code_list: List[str],
        callback: Optional[Callable] = None
    ) -> bool:
        """
        3.5.3.1 指数实时快照
        订阅指数实时快照数据

        Args:
            code_list: 指数代码列表
            callback: 回调函数

        Returns:
            是否订阅成功
        """
        await self._init_subscription()

        if not callback:
            # 默认回调函数
            async def default_callback(data, period):
                logger.info(f"指数快照 - {period}: {data}")
            callback = default_callback

        try:
            # 使用装饰器注册回调
            @self._subscription_data.register(
                code_list=code_list,
                period=ad.constant.Period.snapshot.value
            )
            def onSnapshotindex(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
                # 调用用户回调
                asyncio.create_task(callback(data, period))

            self._subscription_callbacks['index_snapshot'] = onSnapshotindex
            logger.info(f"成功订阅{len(code_list)}个指数快照")

            # 启动订阅循环
            asyncio.create_task(self._run_subscription())
            return True

        except Exception as e:
            logger.error(f"订阅指数快照失败: {e}")
            return False

    async def onSnapshot(
        self,
        code_list: List[str],
        callback: Optional[Callable] = None
    ) -> bool:
        """
        3.5.3.2 股票实时快照
        订阅股票level-1行情数据

        Args:
            code_list: 股票代码列表
            callback: 回调函数

        Returns:
            是否订阅成功
        """
        await self._init_subscription()

        if not callback:
            async def default_callback(data, period):
                logger.info(f"股票快照 - {period}: {data}")
            callback = default_callback

        try:
            @self._subscription_data.register(
                code_list=code_list,
                period=ad.constant.Period.snapshot.value
            )
            def onSnapshot(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
                asyncio.create_task(callback(data, period))

            self._subscription_callbacks['stock_snapshot'] = onSnapshot
            logger.info(f"成功订阅{len(code_list)}个股票快照")

            # 启动订阅循环
            asyncio.create_task(self._run_subscription())
            return True

        except Exception as e:
            logger.error(f"订阅股票快照失败: {e}")
            return False

    async def onSnapshotfuture(
        self,
        code_list: List[str],
        callback: Optional[Callable] = None
    ) -> bool:
        """
        3.5.3.3 期货实时快照
        订阅期货level-1行情数据

        Args:
            code_list: 期货代码列表
            callback: 回调函数

        Returns:
            是否订阅成功
        """
        await self._init_subscription()

        if not callback:
            async def default_callback(data, period):
                logger.info(f"期货快照 - {period}: {data}")
            callback = default_callback

        try:
            @self._subscription_data.register(
                code_list=code_list,
                period=ad.constant.Period.snapshotfuture.value
            )
            def onSnapshotfuture(data: ad.constant.SnapshotFuture, period):
                asyncio.create_task(callback(data, period))

            self._subscription_callbacks['future_snapshot'] = onSnapshotfuture
            logger.info(f"成功订阅{len(code_list)}个期货快照")

            # 启动订阅循环
            asyncio.create_task(self._run_subscription())
            return True

        except Exception as e:
            logger.error(f"订阅期货快照失败: {e}")
            return False

    async def onSnapshotetf(
        self,
        code_list: List[str],
        callback: Optional[Callable] = None
    ) -> bool:
        """
        3.5.3.4 ETF实时快照
        订阅ETF level-1行情数据

        Args:
            code_list: ETF代码列表
            callback: 回调函数

        Returns:
            是否订阅成功
        """
        await self._init_subscription()

        if not callback:
            async def default_callback(data, period):
                logger.info(f"ETF快照 - {period}: {data}")
            callback = default_callback

        try:
            @self._subscription_data.register(
                code_list=code_list,
                period=ad.constant.Period.snapshot.value
            )
            def onSnapshotetf(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
                asyncio.create_task(callback(data, period))

            self._subscription_callbacks['etf_snapshot'] = onSnapshotetf
            logger.info(f"成功订阅{len(code_list)}个ETF快照")

            # 启动订阅循环
            asyncio.create_task(self._run_subscription())
            return True

        except Exception as e:
            logger.error(f"订阅ETF快照失败: {e}")
            return False

    async def onSnapshotkzz(
        self,
        code_list: List[str],
        callback: Optional[Callable] = None
    ) -> bool:
        """
        3.5.3.5 可转债实时快照
        订阅可转债level-1行情数据

        Args:
            code_list: 可转债代码列表
            callback: 回调函数

        Returns:
            是否订阅成功
        """
        await self._init_subscription()

        if not callback:
            async def default_callback(data, period):
                logger.info(f"可转债快照 - {period}: {data}")
            callback = default_callback

        try:
            @self._subscription_data.register(
                code_list=code_list,
                period=ad.constant.Period.snapshot.value
            )
            def onSnapshotkzz(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
                asyncio.create_task(callback(data, period))

            self._subscription_callbacks['kzz_snapshot'] = onSnapshotkzz
            logger.info(f"成功订阅{len(code_list)}个可转债快照")

            # 启动订阅循环
            asyncio.create_task(self._run_subscription())
            return True

        except Exception as e:
            logger.error(f"订阅可转债快照失败: {e}")
            return False

    async def onSnapshothkt(
        self,
        code_list: List[str],
        callback: Optional[Callable] = None
    ) -> bool:
        """
        3.5.3.6 港股通实时快照
        订阅港股通行情数据

        Args:
            code_list: 港股通代码列表
            callback: 回调函数

        Returns:
            是否订阅成功
        """
        await self._init_subscription()

        if not callback:
            async def default_callback(data, period):
                logger.info(f"港股通快照 - {period}: {data}")
            callback = default_callback

        try:
            @self._subscription_data.register(
                code_list=code_list,
                period=ad.constant.Period.snapshot.value
            )
            def onSnapshothkt(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
                asyncio.create_task(callback(data, period))

            self._subscription_callbacks['hkt_snapshot'] = onSnapshothkt
            logger.info(f"成功订阅{len(code_list)}个港股通快照")

            # 启动订阅循环
            asyncio.create_task(self._run_subscription())
            return True

        except Exception as e:
            logger.error(f"订阅港股通快照失败: {e}")
            return False

    async def OnKLine(
        self,
        code_list: List[str],
        period: str = None,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        3.5.3.7 实时K线
        订阅K线数据

        Args:
            code_list: 代码列表
            period: K线周期，默认为1分钟
            callback: 回调函数

        Returns:
            是否订阅成功
        """
        await self._init_subscription()

        if period is None:
            period = ad.constant.Period.min1.value

        if not callback:
            async def default_callback(data, period):
                logger.info(f"K线数据 - {period}: {data}")
            callback = default_callback

        try:
            @self._subscription_data.register(
                code_list=code_list,
                period=period
            )
            def OnKLine(data: ad.constant.Kline, period):
                asyncio.create_task(callback(data, period))

            self._subscription_callbacks[f'kline_{period}'] = OnKLine
            logger.info(f"成功订阅{len(code_list)}个K线数据，周期：{period}")

            # 启动订阅循环
            asyncio.create_task(self._run_subscription())
            return True

        except Exception as e:
            logger.error(f"订阅K线数据失败: {e}")
            return False

    async def stop_subscription(self):
        """停止所有订阅"""
        if self._subscription_data and self._subscription_active:
            try:
                if hasattr(self._subscription_data, 'stop'):
                    self._subscription_data.stop()
                self._subscription_active = False
                self._subscription_callbacks.clear()
                logger.info("已停止所有订阅")
            except Exception as e:
                logger.error(f"停止订阅失败: {e}")

    def get_subscription_status(self) -> Dict[str, Any]:
        """获取订阅状态"""
        return {
            'active': self._subscription_active,
            'subscriptions': list(self._subscription_callbacks.keys()),
            'subscription_count': len(self._subscription_callbacks)
        }