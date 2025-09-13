"""
Strategy Manager

Manages the lifecycle of multiple strategies, including adding, removing,
starting, stopping, and monitoring strategies.
"""
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List, Type

from loguru import logger

from deepsearch.strategies.interfaces.base import BaseStrategy
from deepsearch.utils.system.singleton import Singleton


class StrategyManager(metaclass=Singleton):
    """
    Centralized strategy management system
    
    Responsibilities:
    - Strategy lifecycle management
    - Strategy registration and instantiation
    - Status monitoring and reporting
    - Resource allocation and cleanup
    """

    def __init__(self):
        """Initialize strategy manager"""
        self.strategies: Dict[str, BaseStrategy] = {}
        self.strategy_classes: Dict[str, Type[BaseStrategy]] = {}
        self.strategy_status: Dict[str, Dict[str, Any]] = {}
        self.event_engine = None
        self.is_running = False
        self._lock = asyncio.Lock()

        logger.info("StrategyManager initialized")

    def register_strategy_class(self,
                                name: str,
                                strategy_class: Type[BaseStrategy]):
        """
        Register a strategy class for later instantiation
        
        Args:
            name: Strategy class name
            strategy_class: Strategy class (not instance)
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError(f"{strategy_class} must inherit from BaseStrategy")

        self.strategy_classes[name] = strategy_class
        logger.info(f"Registered strategy class: {name}")

    def add_strategy(self,
                     strategy_class: Type[BaseStrategy],
                     strategy_id: Optional[str] = None,
                     params: Optional[Dict[str, Any]] = None,
                     auto_start: bool = False) -> str:
        """
        Add a new strategy instance
        
        Args:
            strategy_class: Strategy class or registered name
            strategy_id: Unique strategy ID (auto-generated if None)
            params: Strategy parameters
            auto_start: Whether to start strategy immediately
            
        Returns:
            str: Strategy ID
        """
        # Handle string class names
        if isinstance(strategy_class, str):
            if strategy_class not in self.strategy_classes:
                raise ValueError(f"Strategy class {strategy_class} not registered")
            strategy_class = self.strategy_classes[strategy_class]

        # Create strategy instance
        strategy = strategy_class(strategy_id=strategy_id, params=params)

        # Check for duplicate ID
        if strategy.strategy_id in self.strategies:
            raise ValueError(f"Strategy {strategy.strategy_id} already exists")

        # Store strategy
        self.strategies[strategy.strategy_id] = strategy

        # Initialize status
        self.strategy_status[strategy.strategy_id] = {
            'id': strategy.strategy_id,
            'class': strategy.__class__.__name__,
            'status': 'STOPPED',
            'created_at': datetime.now(),
            'started_at': None,
            'stopped_at': None,
            'error': None,
            'metrics': {}
        }

        # Set event engine if available
        if self.event_engine:
            strategy.event_engine = self.event_engine

        # Initialize strategy
        try:
            strategy.on_init()
            logger.info(f"Strategy {strategy.strategy_id} initialized")

            if auto_start:
                self.start_strategy(strategy.strategy_id)

        except Exception as e:
            logger.error(f"Failed to initialize strategy {strategy.strategy_id}: {e}")
            self.strategy_status[strategy.strategy_id]['error'] = str(e)
            raise

        return strategy.strategy_id

    def remove_strategy(self, strategy_id: str, force: bool = False):
        """
        Remove a strategy
        
        Args:
            strategy_id: Strategy ID to remove
            force: Force removal even if running
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} not found")

        strategy = self.strategies[strategy_id]
        status = self.strategy_status[strategy_id]

        # Check if running
        if status['status'] == 'RUNNING' and not force:
            raise RuntimeError(f"Cannot remove running strategy {strategy_id}")

        # Stop if running
        if status['status'] == 'RUNNING':
            self.stop_strategy(strategy_id)

        # Clean up
        del self.strategies[strategy_id]
        del self.strategy_status[strategy_id]

        logger.info(f"Strategy {strategy_id} removed")

    def start_strategy(self, strategy_id: str):
        """
        Start a strategy
        
        Args:
            strategy_id: Strategy ID to start
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} not found")

        strategy = self.strategies[strategy_id]
        status = self.strategy_status[strategy_id]

        if status['status'] == 'RUNNING':
            logger.warning(f"Strategy {strategy_id} already running")
            return

        try:
            strategy.on_start()
            strategy.is_running = True

            status['status'] = 'RUNNING'
            status['started_at'] = datetime.now()
            status['error'] = None

            logger.info(f"Strategy {strategy_id} started")

            # Emit event
            self._emit_strategy_event('STRATEGY_STARTED', {
                'strategy_id': strategy_id,
                'timestamp': datetime.now()
            })

        except Exception as e:
            logger.error(f"Failed to start strategy {strategy_id}: {e}")
            status['status'] = 'ERROR'
            status['error'] = str(e)
            raise

    def stop_strategy(self, strategy_id: str):
        """
        Stop a strategy
        
        Args:
            strategy_id: Strategy ID to stop
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} not found")

        strategy = self.strategies[strategy_id]
        status = self.strategy_status[strategy_id]

        if status['status'] != 'RUNNING':
            logger.warning(f"Strategy {strategy_id} not running")
            return

        try:
            strategy.on_stop()
            strategy.is_running = False

            status['status'] = 'STOPPED'
            status['stopped_at'] = datetime.now()

            logger.info(f"Strategy {strategy_id} stopped")

            # Emit event
            self._emit_strategy_event('STRATEGY_STOPPED', {
                'strategy_id': strategy_id,
                'timestamp': datetime.now()
            })

        except Exception as e:
            logger.error(f"Failed to stop strategy {strategy_id}: {e}")
            status['error'] = str(e)
            raise

    def pause_strategy(self, strategy_id: str):
        """
        Pause a running strategy
        
        Args:
            strategy_id: Strategy ID to pause
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} not found")

        status = self.strategy_status[strategy_id]

        if status['status'] != 'RUNNING':
            raise RuntimeError(f"Can only pause running strategy")

        status['status'] = 'PAUSED'
        self.strategies[strategy_id].is_running = False

        logger.info(f"Strategy {strategy_id} paused")

    def resume_strategy(self, strategy_id: str):
        """
        Resume a paused strategy
        
        Args:
            strategy_id: Strategy ID to resume
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} not found")

        status = self.strategy_status[strategy_id]

        if status['status'] != 'PAUSED':
            raise RuntimeError(f"Can only resume paused strategy")

        status['status'] = 'RUNNING'
        self.strategies[strategy_id].is_running = True

        logger.info(f"Strategy {strategy_id} resumed")

    def get_strategy(self, strategy_id: str) -> Optional[BaseStrategy]:
        """Get strategy instance by ID"""
        return self.strategies.get(strategy_id)

    def get_all_strategies(self) -> Dict[str, BaseStrategy]:
        """Get all strategy instances"""
        return self.strategies.copy()

    def get_strategy_status(self, strategy_id: str) -> Dict[str, Any]:
        """Get strategy status"""
        if strategy_id not in self.strategy_status:
            return None
        return self.strategy_status[strategy_id].copy()

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all strategies"""
        return self.strategy_status.copy()

    def get_running_strategies(self) -> List[str]:
        """Get list of running strategy IDs"""
        return [
            sid for sid, status in self.strategy_status.items()
            if status['status'] == 'RUNNING'
        ]

    async def process_market_data(self, data_type: str, data: Dict[str, Any]):
        """
        Process market data for all running strategies
        
        Args:
            data_type: Type of data ('bar', 'tick', 'depth')
            data: Market data
        """
        running_strategies = self.get_running_strategies()

        if not running_strategies:
            return

        # Process data for each strategy
        tasks = []
        for strategy_id in running_strategies:
            strategy = self.strategies[strategy_id]

            if data_type == 'bar':
                tasks.append(self._process_bar_async(strategy, data))
            elif data_type == 'tick':
                tasks.append(self._process_tick_async(strategy, data))

        # Execute in parallel
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_bar_async(self, strategy: BaseStrategy, bar: Dict[str, Any]):
        """Process bar data asynchronously"""
        try:
            strategy.on_bar(bar)
        except Exception as e:
            logger.error(f"Strategy {strategy.strategy_id} error processing bar: {e}")
            self.strategy_status[strategy.strategy_id]['error'] = str(e)

    async def _process_tick_async(self, strategy: BaseStrategy, tick: Dict[str, Any]):
        """Process tick data asynchronously"""
        try:
            strategy.on_tick(tick)
        except Exception as e:
            logger.error(f"Strategy {strategy.strategy_id} error processing tick: {e}")
            self.strategy_status[strategy.strategy_id]['error'] = str(e)

    def update_metrics(self, strategy_id: str, metrics: Dict[str, Any]):
        """Update strategy metrics"""
        if strategy_id in self.strategy_status:
            self.strategy_status[strategy_id]['metrics'] = metrics

    def set_event_engine(self, event_engine):
        """Set event engine for all strategies"""
        self.event_engine = event_engine

        # Update existing strategies
        for strategy in self.strategies.values():
            strategy.event_engine = event_engine

    def _emit_strategy_event(self, event_type: str, data: Dict[str, Any]):
        """Emit strategy-related event"""
        if self.event_engine:
            from deepsearch.event.engine.engine import Event
            event = Event(type=event_type, data=data)
            self.event_engine.put(event)

    def start_all(self):
        """Start all strategies"""
        for strategy_id in self.strategies:
            if self.strategy_status[strategy_id]['status'] == 'STOPPED':
                self.start_strategy(strategy_id)

    def stop_all(self):
        """Stop all strategies"""
        for strategy_id in self.get_running_strategies():
            self.stop_strategy(strategy_id)

    def reset_all(self):
        """Reset all strategies"""
        for strategy in self.strategies.values():
            strategy.reset()

    def get_summary(self) -> Dict[str, Any]:
        """Get manager summary"""
        return {
            'total_strategies': len(self.strategies),
            'running': len(self.get_running_strategies()),
            'stopped': len([s for s in self.strategy_status.values()
                            if s['status'] == 'STOPPED']),
            'error': len([s for s in self.strategy_status.values()
                          if s['status'] == 'ERROR']),
            'strategies': list(self.strategies.keys())
        }


# Global manager instance
_strategy_manager = None


def get_strategy_manager() -> StrategyManager:
    """Get global strategy manager instance"""
    global _strategy_manager
    if _strategy_manager is None:
        _strategy_manager = StrategyManager()
    return _strategy_manager
