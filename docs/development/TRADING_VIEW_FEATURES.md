# Professional Trading View Features

## Overview

The Professional Trading View is a comprehensive financial charting solution built with Vue 3 and ECharts, providing institutional-grade trading analysis tools.

## Core Features

### 1. K-line Candlestick Chart
- **Hollow/Solid Toggle**: Dynamic switching between hollow and solid candlestick styles
- **Time Format Optimization**: Clean date display for daily charts (YYYY-MM-DD)
- **Color Coding**: Red for bullish, green for bearish (Chinese market convention)

### 2. Technical Indicators

#### Main Chart Indicators
- **Moving Averages (MA)**: 5, 10, 20-day with continuous lines
- **Bollinger Bands (BOLL)**: Dynamic upper/lower bands with middle line
- **EXPMA**: Exponential moving average
- **ENE**: Elastic Net Estimation bands

#### Sub-chart Indicators
- **Volume**: Color-coded bars synchronized with price movement
- **MACD**: DIF, DEA lines with histogram
- **RSI**: Relative Strength Index with overbought/oversold zones
- **KDJ**: Stochastic oscillator with K, D, J lines

### 3. Chip Distribution
- **Real-time Tracking**: Updates following mouse crosshair movement
- **Date-specific Analysis**: Shows chip distribution for any historical date
- **Price Alignment**: Y-axis synchronized with main chart prices
- **Color Coding**: Different colors for profit/loss chips

### 4. Stock Adjustment
- **Forward Adjustment (前复权)**: Adjusts historical prices to current level
- **Backward Adjustment (后复权)**: Maintains historical prices, adjusts current
- **No Adjustment (不复权)**: Raw prices without adjustment

### 5. Order Book Display
- **RAF Batching**: RequestAnimationFrame optimization for smooth updates
- **Stable Keys**: Prevents unnecessary re-renders
- **5-level Depth**: Shows top 5 bid/ask levels
- **Real-time Updates**: WebSocket/Socket.IO integration

## Technical Implementation

### Performance Optimizations

#### 1. Rendering Optimization
```javascript
// RAF batching for high-frequency updates
function scheduleOrderbookUpdate() {
  if (rafId != null) return
  rafId = requestAnimationFrame(() => {
    // Process queued updates
    if (orderbookUpdateQueue.length > 0) {
      const latestData = orderbookUpdateQueue[orderbookUpdateQueue.length - 1]
      orderbookUpdateQueue = []
      // Update UI
    }
    rafId = null
  })
}
```

#### 2. Resize Handling
```javascript
// Debounced resize to avoid ResizeObserver warnings
const debouncedResize = debounce(() => {
  requestAnimationFrame(() => {
    if (mainChartInstance) mainChartInstance.resize()
    if (chipChartInstance) chipChartInstance.resize()
    indicatorChartInstances.forEach(chart => chart.resize())
  })
}, 100)
```

#### 3. Vue Reactivity
```javascript
// Use shallowRef for large arrays
const buyOrders = shallowRef([])
const sellOrders = shallowRef([])
```

### Data Flow Architecture

```
User Interaction
       ↓
Vue Component (ProfessionalTradingView.vue)
       ↓
API Layer (chart.js)
       ↓
Backend Service (chart_service.py)
       ↓
Data Sources (AkShare/QMT)
```

### Chart Configuration

#### ECharts Options
```javascript
{
  animation: false,  // Disable animation for performance
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'cross' }
  },
  dataZoom: [{
    type: 'inside',
    start: 70,
    end: 100
  }]
}
```

#### Line Series Configuration
```javascript
{
  type: 'line',
  showSymbol: false,  // Hide dots for continuous lines
  symbol: 'none',     // Ensure no symbols
  smooth: false,      // No smoothing for accurate data
  lineStyle: {
    width: 1.5,
    opacity: 0.8
  }
}
```

## API Integration

### 1. Chip Distribution API
```python
@router.get("/chip-distribution")
async def get_chip_distribution(
    symbol: str,
    lookback_days: int = 120,
    price_bins: int = 100,
    target_date: Optional[str] = None  # Date-specific query
)
```

### 2. Adjust Factor Service
```python
class AdjustFactorService:
    async def get_adjust_factors(symbol, start_date, end_date)
    def apply_adjust(bars_df, adjust_type, factors_df)
```

### 3. Stock Info Integration
```python
# ChartService now uses StockInfoService for real listing dates
if self.stock_info_service:
    stock_info = self.stock_info_service.get(symbol)
    if stock_info and stock_info.get('listed_date'):
        meta["listing_date"] = stock_info['listed_date']
```

## Data Sources

### Primary Sources
- **AkShare**: Stock info, chip distribution (stock_cyq_em), adjust factors
- **QMT**: Real-time quotes, historical data, order book via Socket

### Fallback Strategy
1. Try primary data source (QMT if available)
2. Fallback to AkShare API
3. Use cached data if network fails
4. Return error with clear message

## WebSocket/Socket Architecture

### QMT Socket Bridge
```
QMT Socket Server → Socket.IO Bridge → WebSocket Client
```

### Message Format
```javascript
{
  type: 'tick' | 'orderbook' | 'trade',
  symbol: string,
  data: {
    // Type-specific payload
  }
}
```

## Future Enhancements

1. **Advanced Indicators**: Ichimoku Cloud, Pivot Points, Fibonacci Retracements
2. **Drawing Tools**: Trend lines, channels, patterns
3. **Alert System**: Price alerts, indicator signals
4. **Multi-timeframe Analysis**: Split screen with different periods
5. **Strategy Backtesting**: Visual strategy testing on historical data
6. **Option Chain Integration**: Options analysis alongside stock charts
7. **News Overlay**: Corporate events and news on chart timeline
8. **Social Sentiment**: Integration with social media sentiment data