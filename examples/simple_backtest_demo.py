"""
Simple Backtest Demo - All in English
"""
import asyncio
from datetime import datetime, timedelta
import sys
import os

# Add project path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from deepsearch.backtest import BacktestEngine, SimpleMovingAverageStrategy


async def run_demo():
    """Run a simple backtest demo"""
    
    print("=" * 80)
    print("DeepSearch Backtrader Integration - Simple Demo")
    print("=" * 80)
    
    # Create backtest engine
    print("\n1. Creating backtest engine...")
    engine = BacktestEngine(data_provider=None, event_engine=None)
    print("   [OK] Engine created")
    
    # Configure backtest
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)  # One year backtest
    
    print("\n2. Configuring backtest...")
    print(f"   Strategy: SimpleMovingAverageStrategy")
    print(f"   Symbol: TEST_STOCK")
    print(f"   Period: {start_date.date()} to {end_date.date()}")
    print(f"   Initial Cash: 100,000")
    print(f"   Commission: 0.1%")
    
    await engine.configure(
        strategy_class=SimpleMovingAverageStrategy,
        symbol='TEST_STOCK',
        start_date=start_date,
        end_date=end_date,
        initial_cash=100000,
        commission=0.001,
        slippage=0.001,
        strategy_params={
            'short_period': 10,
            'long_period': 30
        }
    )
    print("   [OK] Configuration complete")
    
    # Run backtest
    print("\n3. Running backtest...")
    result = await engine.run_async()
    print("   [OK] Backtest complete")
    
    # Display results
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)
    
    print(f"\nPerformance Summary:")
    print(f"  Total Return: {result.total_return:.2%}")
    print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {result.max_drawdown:.2%}")
    print(f"  Win Rate: {result.win_rate:.2%}")
    
    print(f"\nTrading Statistics:")
    print(f"  Total Trades: {result.total_trades}")
    print(f"  Profit Trades: {result.profit_trades}")
    print(f"  Loss Trades: {result.loss_trades}")
    
    print(f"\nCapital Summary:")
    print(f"  Initial Cash: {result.initial_cash:,.0f}")
    print(f"  Final Cash: {result.final_cash:,.0f}")
    print(f"  Net Profit: {result.final_cash - result.initial_cash:,.0f}")
    
    print("\n" + "=" * 80)
    print("SUCCESS! Backtest completed successfully.")
    print("=" * 80)
    
    return result


async def run_parameter_optimization():
    """Run parameter optimization"""
    
    print("\n" + "=" * 80)
    print("PARAMETER OPTIMIZATION")
    print("=" * 80)
    
    # Test different parameter combinations
    param_sets = [
        {'short_period': 5, 'long_period': 20},
        {'short_period': 10, 'long_period': 30},
        {'short_period': 20, 'long_period': 60},
    ]
    
    results = []
    
    for params in param_sets:
        print(f"\nTesting: Short={params['short_period']}, Long={params['long_period']}")
        
        engine = BacktestEngine(data_provider=None, event_engine=None)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        await engine.configure(
            strategy_class=SimpleMovingAverageStrategy,
            symbol='TEST_STOCK',
            start_date=start_date,
            end_date=end_date,
            initial_cash=100000,
            commission=0.001,
            strategy_params=params
        )
        
        result = await engine.run_async()
        results.append({
            'params': params,
            'return': result.total_return,
            'sharpe': result.sharpe_ratio,
            'drawdown': result.max_drawdown
        })
        
        print(f"  Return: {result.total_return:.2%}")
        print(f"  Sharpe: {result.sharpe_ratio:.2f}")
        print(f"  Drawdown: {result.max_drawdown:.2%}")
    
    # Find best parameters
    best = max(results, key=lambda x: x['sharpe'])
    
    print("\n" + "=" * 80)
    print("BEST PARAMETERS")
    print("=" * 80)
    print(f"  Parameters: {best['params']}")
    print(f"  Sharpe Ratio: {best['sharpe']:.2f}")
    print(f"  Total Return: {best['return']:.2%}")
    print(f"  Max Drawdown: {best['drawdown']:.2%}")
    
    return results


async def main():
    """Main function"""
    
    try:
        # Check if backtrader is installed
        import backtrader
        print(f"Backtrader version: {backtrader.__version__}")
    except ImportError:
        print("ERROR: Please install backtrader first")
        print("Run: pip install backtrader")
        return
    
    # Run simple backtest
    print("\n>>> SIMPLE BACKTEST DEMO <<<")
    await run_demo()
    
    # Run parameter optimization
    print("\n>>> PARAMETER OPTIMIZATION <<<")
    await run_parameter_optimization()
    
    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("DeepSearch Backtrader Integration is Working!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())