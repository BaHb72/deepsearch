"""
Strategy API Endpoints

FastAPI routes for strategy management and backtesting.
"""

from typing import Any, Dict, List, cast

from fastapi import APIRouter, BackgroundTasks, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from deepsearch.strategies.implementations.mean_reversion import MeanReversionStrategy
from deepsearch.strategies.implementations.momentum import MomentumStrategy
from deepsearch.strategies.implementations.moving_average import MovingAverageStrategy
from deepsearch.strategies.managers.manager import get_strategy_manager
from deepsearch.strategies.services.backtest_service import (
    StrategyComparisonConfig,
    get_backtest_service,
)

# API Router
router = APIRouter(prefix="/api/strategy", tags=["strategy"])


# Request/Response Models
class StrategyConfig(BaseModel):
    """Strategy configuration model"""

    strategy_type: str = Field(..., description="Strategy type (MA, MeanReversion, Momentum)")
    params: Dict[str, Any] = Field(default_factory=dict, description="Strategy parameters")
    auto_start: bool = Field(False, description="Auto start after adding")


class BacktestRequest(BaseModel):
    """Backtest request model"""

    strategy_type: str = Field(..., description="Strategy type")
    symbols: List[str] = Field(..., description="List of symbols")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    initial_capital: float = Field(100000, description="Initial capital")
    strategy_params: Dict[str, Any] = Field(default_factory=dict, description="Strategy parameters")
    commission: float = Field(0.001, description="Commission rate")


class CompareRequest(BaseModel):
    """Strategy comparison request"""

    strategies: List[Dict[str, Any]] = Field(..., description="List of strategies to compare")
    symbols: List[str] = Field(..., description="Symbols to test")
    start_date: str = Field(..., description="Start date")
    end_date: str = Field(..., description="End date")
    initial_capital: float = Field(100000, description="Initial capital")


# Strategy type mapping
STRATEGY_TYPES = {
    "MA": MovingAverageStrategy,
    "MovingAverage": MovingAverageStrategy,
    "MeanReversion": MeanReversionStrategy,
    "Momentum": MomentumStrategy,
}


@router.get("/types")
async def get_strategy_types():
    """Get available strategy types"""
    return {
        "strategies": [
            {
                "type": "MA",
                "name": "Moving Average",
                "description": "Classic trend-following strategy using MA crossovers",
                "params": {
                    "short_period": {
                        "type": "int",
                        "default": 10,
                        "description": "Short MA period",
                    },
                    "long_period": {"type": "int", "default": 30, "description": "Long MA period"},
                    "position_size": {
                        "type": "int",
                        "default": 100,
                        "description": "Position size",
                    },
                    "max_positions": {"type": "int", "default": 5, "description": "Max positions"},
                },
            },
            {
                "type": "MeanReversion",
                "name": "Mean Reversion",
                "description": "Statistical arbitrage based on price mean reversion",
                "params": {
                    "lookback_period": {
                        "type": "int",
                        "default": 20,
                        "description": "Lookback period",
                    },
                    "std_multiplier": {
                        "type": "float",
                        "default": 2.0,
                        "description": "Std multiplier",
                    },
                    "rsi_period": {"type": "int", "default": 14, "description": "RSI period"},
                    "rsi_oversold": {"type": "int", "default": 30, "description": "RSI oversold"},
                    "rsi_overbought": {
                        "type": "int",
                        "default": 70,
                        "description": "RSI overbought",
                    },
                },
            },
            {
                "type": "Momentum",
                "name": "Momentum",
                "description": "Breakout trading with momentum confirmation",
                "params": {
                    "momentum_period": {
                        "type": "int",
                        "default": 20,
                        "description": "Momentum period",
                    },
                    "volume_period": {"type": "int", "default": 20, "description": "Volume period"},
                    "breakout_period": {
                        "type": "int",
                        "default": 50,
                        "description": "Breakout period",
                    },
                    "momentum_threshold": {
                        "type": "float",
                        "default": 0.05,
                        "description": "Momentum threshold",
                    },
                    "stop_loss_pct": {
                        "type": "float",
                        "default": 0.02,
                        "description": "Stop loss %",
                    },
                },
            },
        ]
    }


@router.get("/list")
async def list_strategies():
    """List all strategies and their status"""
    manager = get_strategy_manager()
    all_status = manager.get_all_status()

    strategies = []
    for strategy_id, status in all_status.items():
        strategy = manager.get_strategy(strategy_id)
        strategies.append(
            {
                "id": strategy_id,
                "class": status["class"],
                "status": status["status"],
                "created_at": status["created_at"].isoformat() if status["created_at"] else None,
                "started_at": status["started_at"].isoformat() if status["started_at"] else None,
                "error": status["error"],
                "metrics": status["metrics"],
                "params": strategy.params if strategy else {},
            }
        )

    return {"strategies": strategies}


@router.post("/add")
async def add_strategy(config: StrategyConfig):
    """Add a new strategy instance"""
    manager = get_strategy_manager()

    # Get strategy class
    strategy_class = STRATEGY_TYPES.get(config.strategy_type)
    if not strategy_class:
        raise HTTPException(
            status_code=400, detail=f"Unknown strategy type: {config.strategy_type}"
        )

    try:
        # Add strategy
        strategy_id = manager.add_strategy(
            strategy_class=strategy_class, params=config.params, auto_start=config.auto_start
        )

        return {
            "success": True,
            "strategy_id": strategy_id,
            "message": f"Strategy {strategy_id} added successfully",
        }

    except Exception as e:
        logger.error(f"Failed to add strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start/{strategy_id}")
async def start_strategy(strategy_id: str):
    """Start a strategy"""
    manager = get_strategy_manager()

    try:
        manager.start_strategy(strategy_id)
        return {"success": True, "message": f"Strategy {strategy_id} started"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop/{strategy_id}")
async def stop_strategy(strategy_id: str):
    """Stop a strategy"""
    manager = get_strategy_manager()

    try:
        manager.stop_strategy(strategy_id)
        return {"success": True, "message": f"Strategy {strategy_id} stopped"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to stop strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pause/{strategy_id}")
async def pause_strategy(strategy_id: str):
    """Pause a strategy"""
    manager = get_strategy_manager()

    try:
        manager.pause_strategy(strategy_id)
        return {"success": True, "message": f"Strategy {strategy_id} paused"}
    except Exception as e:
        logger.error(f"Failed to pause strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume/{strategy_id}")
async def resume_strategy(strategy_id: str):
    """Resume a paused strategy"""
    manager = get_strategy_manager()

    try:
        manager.resume_strategy(strategy_id)
        return {"success": True, "message": f"Strategy {strategy_id} resumed"}
    except Exception as e:
        logger.error(f"Failed to resume strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/remove/{strategy_id}")
async def remove_strategy(strategy_id: str, force: bool = False):
    """Remove a strategy"""
    manager = get_strategy_manager()

    try:
        manager.remove_strategy(strategy_id, force=force)
        return {"success": True, "message": f"Strategy {strategy_id} removed"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to remove strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_all_status():
    """Get status of all strategies"""
    manager = get_strategy_manager()
    return manager.get_all_status()


@router.get("/status/{strategy_id}")
async def get_strategy_status(strategy_id: str):
    """Get status of a specific strategy"""
    manager = get_strategy_manager()
    status = manager.get_strategy_status(strategy_id)

    if not status:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    return status


@router.get("/metrics/{strategy_id}")
async def get_strategy_metrics(strategy_id: str):
    """Get performance metrics of a strategy"""
    manager = get_strategy_manager()
    strategy = manager.get_strategy(strategy_id)

    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    return strategy.get_metrics()


@router.get("/positions/{strategy_id}")
async def get_strategy_positions(strategy_id: str):
    """Get positions of a strategy"""
    manager = get_strategy_manager()
    strategy = manager.get_strategy(strategy_id)

    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    return strategy.get_all_positions()


@router.post("/backtest")
async def run_backtest(request: BacktestRequest, background_tasks: BackgroundTasks):
    """Run a strategy backtest"""
    # Get strategy class
    strategy_class = STRATEGY_TYPES.get(request.strategy_type)
    if not strategy_class:
        raise HTTPException(
            status_code=400, detail=f"Unknown strategy type: {request.strategy_type}"
        )

    try:
        # Get backtest service
        service = get_backtest_service()

        # Run backtest
        result = await service.run_backtest(
            strategy_class=strategy_class,
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            strategy_params=request.strategy_params,
            commission=request.commission,
            plot=True,
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_strategies(request: CompareRequest):
    """Compare multiple strategies"""
    try:
        # Get backtest service
        service = get_backtest_service()

        # Prepare strategy configurations
        strategies = []
        for strategy_config in request.strategies:
            strategy_type_value = strategy_config.get("type")
            if not isinstance(strategy_type_value, str):
                raise ValueError(f"Unknown strategy type: {strategy_type_value!r}")
            strategy_class = STRATEGY_TYPES.get(strategy_type_value)

            if not strategy_class:
                raise ValueError(f"Unknown strategy type: {strategy_type_value}")

            strategies.append(
                {
                    "class": strategy_class,
                    "params": strategy_config.get("params", {}),
                    "name": strategy_config.get("name", strategy_type_value),
                }
            )

        # Run comparison
        typed_strategies = cast(list[StrategyComparisonConfig], strategies)

        results = await service.compare_strategies(
            strategies=typed_strategies,
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
        )

        return {"results": [result.to_dict() for result in results]}

    except Exception as e:
        logger.error(f"Strategy comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_strategy_summary():
    """Get overall strategy system summary"""
    manager = get_strategy_manager()
    return manager.get_summary()
