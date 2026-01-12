"""
T-Trading Engine Module

Components for intraday T-trading analysis and signaling:
- interfaces.py: Core protocols and abstract base classes
- analyzers.py: Technical analyzers (VWAP, MA, Support/Resistance, Volume)
- signal_generators.py: Signal generation from analysis results
- engine.py: Core T-trading engine orchestration
"""

from core.strategies.ttrading.analyzers import (
    CompositeIntradayAnalyzer,
    IntradayMAAnalyzer,
    SupportResistanceAnalyzer,
    VolumePriceAnalyzer,
    VWAPAnalyzer,
)
from core.strategies.ttrading.engine import (
    MockIntradayDataProvider,
    TTradingEngine,
    get_ttrading_engine,
    run_quick_analysis,
)
from core.strategies.ttrading.interfaces import (
    AnalysisResult,
    IntradayBar,
    IntradayDataProvider,
    MarketTrend,
    PriceLevel,
    QuoteSnapshot,
    SignalGenerator,
    SignalType,
    SuccessTracker,
    TechnicalAnalyzer,
    TTradingEngineProtocol,
)
from core.strategies.ttrading.providers import (
    MINIQMT_AVAILABLE,
    MiniQMTIntradayDataProvider,
    get_best_data_provider,
    get_miniqmt_provider,
)
from core.strategies.ttrading.signal_generators import (
    CompositeSignalGenerator,
    GridSignalGenerator,
    MADeviationSignalGenerator,
    SupportResistanceSignalGenerator,
    VolumePriceSignalGenerator,
)

__all__ = [
    # Interfaces
    "AnalysisResult",
    "IntradayBar",
    "IntradayDataProvider",
    "MarketTrend",
    "PriceLevel",
    "QuoteSnapshot",
    "SignalGenerator",
    "SignalType",
    "SuccessTracker",
    "TechnicalAnalyzer",
    "TTradingEngineProtocol",
    # Analyzers
    "CompositeIntradayAnalyzer",
    "IntradayMAAnalyzer",
    "SupportResistanceAnalyzer",
    "VolumePriceAnalyzer",
    "VWAPAnalyzer",
    # Signal Generators
    "CompositeSignalGenerator",
    "GridSignalGenerator",
    "MADeviationSignalGenerator",
    "SupportResistanceSignalGenerator",
    "VolumePriceSignalGenerator",
    # Engine
    "MockIntradayDataProvider",
    "TTradingEngine",
    "get_ttrading_engine",
    "run_quick_analysis",
    # Providers
    "MINIQMT_AVAILABLE",
    "MiniQMTIntradayDataProvider",
    "get_miniqmt_provider",
    "get_best_data_provider",
]
