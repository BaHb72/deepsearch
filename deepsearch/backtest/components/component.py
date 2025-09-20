"""
BacktestComponent - 回测组件

将 Backtrader 集成到 DeepSearch 组件系统中
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from deepsearch.core.async_component import AsyncComponent
from deepsearch.core.utils.exceptions import error_context
from deepsearch.core.interfaces.component import ComponentType, ComponentStatus
from deepsearch.event.engine.engine import Event
from ..engines.engine import BacktestEngine
from ..utils.results import BacktestResult


class BacktestComponent(AsyncComponent):
    """
    回测组件 - 提供策略回测功能
    
    功能特性：
    1. 管理多个回测引擎实例
    2. 与事件系统集成，发布回测事件
    3. 缓存回测结果
    4. 支持并发回测
    """

    def __init__(self):
        super().__init__(
            name="backtest",
            component_type=ComponentType.BUSINESS,
            display_name="回测引擎"
        )
        self._logger = logging.getLogger(f"deepsearch.{self.__class__.__name__}")
        self._engines: Dict[str, BacktestEngine] = {}
        self._results: Dict[str, BacktestResult] = {}
        self._event_engine = None
        self._message_bus = None
        self._data_provider = None
        self._max_concurrent_backtests = 5
        self._running_backtests = set()

    def set_dependencies(self, event_engine, message_bus, data_provider):
        """设置组件依赖"""
        self._event_engine = event_engine
        self._message_bus = message_bus
        self._data_provider = data_provider

    async def _do_initialize(self) -> Optional[Any]:
        """初始化回测组件"""
        self._logger.info("初始化回测组件")
        return None

    async def _do_start(self) -> None:
        """启动回测组件"""
        self._logger.info("启动回测组件")

    async def _do_stop(self) -> None:
        """停止回测组件"""
        self._logger.info("停止回测组件")
        # 清理所有运行中的回测
        for engine_id in list(self._engines.keys()):
            try:
                engine = self._engines.pop(engine_id)
                if hasattr(engine, 'stop'):
                    engine.stop()
            except Exception as e:
                self._logger.error(f"停止回测引擎 {engine_id} 失败: {e}")

    async def _initialize(self) -> None:
        """初始化回测组件"""
        with error_context(self.name, "initialize"):
            self._logger.info("初始化回测组件")

            # 注册事件处理器
            if self._event_engine:
                self._register_event_handlers()

            self._logger.info("回测组件初始化完成")

    async def _start(self) -> None:
        """启动回测组件"""
        with error_context(self.name, "start"):
            self._logger.info("启动回测组件")

            # 清理过期的回测结果
            await self._cleanup_old_results()

            self._logger.info("回测组件启动完成")

    async def _stop(self) -> None:
        """停止回测组件"""
        with error_context(self.name, "stop"):
            self._logger.info("停止回测组件")

            # 等待所有运行中的回测完成
            if self._running_backtests:
                self._logger.info(f"等待 {len(self._running_backtests)} 个回测任务完成")
                await asyncio.gather(*[
                    self._wait_for_backtest(backtest_id)
                    for backtest_id in self._running_backtests
                ], return_exceptions=True)

            # 清理引擎实例
            self._engines.clear()
            self._results.clear()

            self._logger.info("回测组件停止完成")

    def _health_check(self) -> bool:
        """健康检查"""
        return self.status == ComponentStatus.RUNNING

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """获取额外状态信息"""
        return {
            "engines_count": len(self._engines),
            "results_cached": len(self._results),
            "running_backtests": len(self._running_backtests),
            "max_concurrent": self._max_concurrent_backtests
        }

    def _register_event_handlers(self):
        """注册事件处理器"""
        # 注册回测请求事件处理器
        self._event_engine.register(
            event_type="BACKTEST_REQUEST",
            handler=self._handle_backtest_request,
            priority=10
        )

        # 注册回测取消事件处理器
        self._event_engine.register(
            event_type="BACKTEST_CANCEL",
            handler=self._handle_backtest_cancel,
            priority=10
        )

        # 注册回测查询事件处理器
        self._event_engine.register(
            event_type="BACKTEST_QUERY",
            handler=self._handle_backtest_query,
            priority=10
        )

    def _handle_backtest_request(self, event: Event):
        """处理回测请求事件"""
        asyncio.create_task(self._process_backtest_request(event))

    async def _process_backtest_request(self, event: Event):
        """异步处理回测请求"""
        data = event.data
        backtest_id = data.get('backtest_id')
        strategy_class = data.get('strategy_class')
        params = data.get('params', {})

        try:
            # 检查并发限制
            if len(self._running_backtests) >= self._max_concurrent_backtests:
                await self._send_backtest_error(
                    backtest_id,
                    "回测任务已达到最大并发数限制"
                )
                return

            # 创建回测引擎
            engine = await self.create_backtest_engine(
                backtest_id=backtest_id,
                strategy_class=strategy_class,
                **params
            )

            # 运行回测
            self._running_backtests.add(backtest_id)
            result = await engine.run_async()

            # 保存结果
            self._results[backtest_id] = result

            # 发送完成事件
            await self._send_backtest_complete(backtest_id, result)

        except Exception as e:
            self._logger.error(f"回测失败 {backtest_id}: {e}")
            await self._send_backtest_error(backtest_id, str(e))

        finally:
            self._running_backtests.discard(backtest_id)

    def _handle_backtest_cancel(self, event: Event):
        """处理回测取消事件"""
        backtest_id = event.data.get('backtest_id')
        if backtest_id in self._engines:
            engine = self._engines[backtest_id]
            engine.cancel()
            self._logger.info(f"已取消回测 {backtest_id}")

    def _handle_backtest_query(self, event: Event):
        """处理回测查询事件"""
        backtest_id = event.data.get('backtest_id')

        if backtest_id in self._results:
            result = self._results[backtest_id]
            # 发送查询结果事件
            response_event = Event(
                type="BACKTEST_QUERY_RESPONSE",
                data={
                    'backtest_id': backtest_id,
                    'result': result.to_dict(),
                    'status': 'completed'
                }
            )
            self._event_engine.put(response_event)
        elif backtest_id in self._running_backtests:
            # 回测还在运行中
            response_event = Event(
                type="BACKTEST_QUERY_RESPONSE",
                data={
                    'backtest_id': backtest_id,
                    'status': 'running'
                }
            )
            self._event_engine.put(response_event)
        else:
            # 回测不存在
            response_event = Event(
                type="BACKTEST_QUERY_RESPONSE",
                data={
                    'backtest_id': backtest_id,
                    'status': 'not_found'
                }
            )
            self._event_engine.put(response_event)

    async def create_backtest_engine(
            self,
            backtest_id: str,
            strategy_class,
            symbol: str,
            start_date: datetime,
            end_date: datetime,
            initial_cash: float = 100000,
            commission: float = 0.001,
            **kwargs
    ) -> BacktestEngine:
        """
        创建回测引擎实例
        
        Args:
            backtest_id: 回测ID
            strategy_class: 策略类
            symbol: 交易标的
            start_date: 开始日期
            end_date: 结束日期
            initial_cash: 初始资金
            commission: 手续费率
            **kwargs: 其他参数
            
        Returns:
            BacktestEngine: 回测引擎实例
        """
        engine = BacktestEngine(
            data_provider=self._data_provider,
            event_engine=self._event_engine
        )

        # 配置回测参数
        await engine.configure(
            strategy_class=strategy_class,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            commission=commission,
            **kwargs
        )

        self._engines[backtest_id] = engine
        return engine

    async def run_backtest(
            self,
            backtest_id: str,
            strategy_class,
            **params
    ) -> BacktestResult:
        """
        运行回测
        
        Args:
            backtest_id: 回测ID
            strategy_class: 策略类
            **params: 回测参数
            
        Returns:
            BacktestResult: 回测结果
        """
        # 创建引擎
        engine = await self.create_backtest_engine(
            backtest_id=backtest_id,
            strategy_class=strategy_class,
            **params
        )

        # 运行回测
        self._running_backtests.add(backtest_id)
        try:
            result = await engine.run_async()
            self._results[backtest_id] = result
            return result
        finally:
            self._running_backtests.discard(backtest_id)

    def get_backtest_result(self, backtest_id: str) -> Optional[BacktestResult]:
        """获取回测结果"""
        return self._results.get(backtest_id)

    def list_backtests(self) -> List[Dict[str, Any]]:
        """列出所有回测"""
        backtests = []

        # 已完成的回测
        for backtest_id, result in self._results.items():
            backtests.append({
                'id': backtest_id,
                'status': 'completed',
                'start_date': result.start_date,
                'end_date': result.end_date,
                'total_return': result.total_return,
                'sharpe_ratio': result.sharpe_ratio
            })

        # 运行中的回测
        for backtest_id in self._running_backtests:
            if backtest_id not in self._results:
                backtests.append({
                    'id': backtest_id,
                    'status': 'running'
                })

        return backtests

    async def _wait_for_backtest(self, backtest_id: str, timeout: float = 60):
        """等待回测完成"""
        start_time = asyncio.get_event_loop().time()
        while backtest_id in self._running_backtests:
            if asyncio.get_event_loop().time() - start_time > timeout:
                self._logger.warning(f"等待回测 {backtest_id} 超时")
                break
            await asyncio.sleep(0.1)

    async def _cleanup_old_results(self):
        """清理过期的回测结果"""
        # 保留最近100个回测结果
        if len(self._results) > 100:
            sorted_results = sorted(
                self._results.items(),
                key=lambda x: x[1].timestamp,
                reverse=True
            )
            self._results = dict(sorted_results[:100])
            self._logger.info(f"清理了 {len(sorted_results) - 100} 个过期回测结果")

    async def _send_backtest_complete(self, backtest_id: str, result: BacktestResult):
        """发送回测完成事件"""
        event = Event(
            type="BACKTEST_COMPLETE",
            data={
                'backtest_id': backtest_id,
                'result': result.to_dict()
            }
        )
        self._event_engine.put(event)

    async def _send_backtest_error(self, backtest_id: str, error_message: str):
        """发送回测错误事件"""
        event = Event(
            type="BACKTEST_ERROR",
            data={
                'backtest_id': backtest_id,
                'error': error_message
            }
        )
        self._event_engine.put(event)
