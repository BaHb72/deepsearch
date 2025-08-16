<template>
  <div class="quant-trading-view">
    <el-container class="main-container">
      <!-- 顶部导航栏 -->
      <el-header class="top-navbar" height="50px">
        <div class="nav-left">
          <!-- Logo -->
          <div class="logo">
            <span class="logo-text">DeepQuant</span>
          </div>

          <!-- 股票搜索 -->
          <el-autocomplete
              v-model="searchSymbol"
              :fetch-suggestions="queryStockSearch"
              :trigger-on-focus="false"
              class="stock-search"
              clearable
              placeholder="股票代码/名称/拼音"
              value-key="value"
              @select="handleStockSelect"
          >
            <template #default="{ item }">
              <div class="stock-search-item">
                <span class="stock-code">{{ item.code }}</span>
                <span class="stock-name">{{ item.name }}</span>
              </div>
            </template>
          </el-autocomplete>
        </div>

        <div class="nav-right">
          <!-- 市场切换 -->
          <el-button-group class="market-switch">
            <el-button
                v-for="market in markets"
                :key="market.value"
                :type="currentMarket === market.value ? 'primary' : ''"
                @click="switchMarket(market.value)"
            >
              {{ market.label }}
            </el-button>
          </el-button-group>
        </div>
      </el-header>

      <el-container class="content-container">
        <!-- 左侧自选股面板 -->
        <el-aside class="watchlist-panel" width="260px">
          <div class="panel-header">
            <span class="panel-title">自选股</span>
            <el-button
                circle
                icon="Plus"
                size="small"
                type="primary"
                @click="showAddStock = true"
            />
          </div>

          <el-scrollbar class="watchlist-scroll">
            <div class="watchlist-content">
              <div
                  v-for="stock in watchlist"
                  :key="stock.code"
                  :class="{ active: stock.code === currentStock.code }"
                  class="stock-item"
                  @click="selectStock(stock)"
              >
                <div class="stock-info">
                  <div class="stock-header">
                    <span class="code">{{ stock.code }}</span>
                    <span class="name">{{ stock.name }}</span>
                  </div>
                  <div class="stock-price">
                    <span :class="getPriceClass(stock.changePct)" class="price">
                      {{ formatPrice(stock.price) }}
                    </span>
                    <span :class="getPriceClass(stock.changePct)" class="change">
                      {{ stock.change > 0 ? '+' : '' }}{{ formatPrice(stock.change) }}
                    </span>
                    <span :class="getPriceClass(stock.changePct)" class="change-pct">
                      {{ stock.changePct > 0 ? '+' : '' }}{{ formatPercent(stock.changePct) }}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </el-scrollbar>
        </el-aside>

        <!-- 主内容区 -->
        <el-main class="main-content">
          <!-- 股票信息头部 -->
          <div class="stock-header-info">
            <div class="stock-basic">
              <span class="stock-code">{{ currentStock.code }}</span>
              <span class="stock-name">{{ currentStock.name }}</span>
              <span :class="getPriceClass(currentStock.changePct)" class="current-price">
                {{ formatPrice(currentStock.price) }}
              </span>
              <span :class="getPriceClass(currentStock.changePct)" class="price-change">
                {{ currentStock.change > 0 ? '+' : '' }}{{ formatPrice(currentStock.change) }}
                ({{ currentStock.changePct > 0 ? '+' : '' }}{{ formatPercent(currentStock.changePct) }}%)
              </span>
            </div>
            <div class="stock-stats">
              <div class="stat-item">
                <span class="stat-label">最高</span>
                <span class="stat-value">{{ formatPrice(currentStock.high) }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">最低</span>
                <span class="stat-value">{{ formatPrice(currentStock.low) }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">成交量</span>
                <span class="stat-value">{{ formatVolume(currentStock.volume) }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">成交额</span>
                <span class="stat-value">{{ formatAmount(currentStock.amount) }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">换手率</span>
                <span class="stat-value">{{ formatPercent(currentStock.turnover) }}%</span>
              </div>
            </div>
          </div>

          <!-- 行业概念面板 -->
          <div class="industry-concept-panel">
            <div class="industry-section">
              <span class="section-label">所属行业：</span>
              <el-tag v-for="industry in currentStock.industries" :key="industry">
                {{ industry }}
              </el-tag>
            </div>
            <div class="concept-section">
              <span class="section-label">概念板块：</span>
              <el-tag
                  v-for="concept in currentStock.concepts"
                  :key="concept.name"
                  :type="concept.hot ? 'danger' : 'info'"
              >
                {{ concept.name }}
              </el-tag>
            </div>
            <div class="sector-change">
              板块涨幅：<span class="change-value">+{{ currentStock.sectorChange }}%</span>
            </div>
          </div>

          <!-- 主图表区域 -->
          <div class="chart-container">
            <el-row :gutter="0" class="chart-row">
              <!-- 价格轴 -->
              <el-col :span="2" class="price-axis">
                <div class="price-scale">
                  <div v-for="price in priceScale" :key="price" class="price-tick">
                    {{ formatPrice(price) }}
                  </div>
                </div>
              </el-col>

              <!-- K线图主体 -->
              <el-col :span="15" class="kline-chart">
                <!-- 周期切换工具栏 -->
                <div class="chart-toolbar">
                  <el-button-group size="small">
                    <el-button
                        v-for="period in periods"
                        :key="period.value"
                        :type="currentPeriod === period.value ? 'primary' : ''"
                        @click="switchPeriod(period.value)"
                    >
                      {{ period.label }}
                    </el-button>
                  </el-button-group>

                  <el-radio-group v-model="adjustType" class="adjust-radio" size="small">
                    <el-radio-button label="none">不复权</el-radio-button>
                    <el-radio-button label="qfq">前复权</el-radio-button>
                    <el-radio-button label="hfq">后复权</el-radio-button>
                  </el-radio-group>
                </div>

                <!-- K线图 -->
                <div ref="klineChart" class="kline-chart-container"></div>
              </el-col>

              <!-- 筹码分布 -->
              <el-col :span="7" class="chip-distribution">
                <el-card class="chip-card">
                  <template #header>
                    <span class="chip-title">筹码分布</span>
                  </template>

                  <!-- 筹码峰图 -->
                  <div class="chip-chart">
                    <div v-for="chip in chipData" :key="chip.price" class="chip-bar">
                      <span class="chip-price">{{ formatPrice(chip.price) }}</span>
                      <el-progress
                          :color="getChipColor(chip.type)"
                          :percentage="chip.percentage"
                          :show-text="false"
                          :stroke-width="10"
                      />
                    </div>

                    <!-- 平均成本线 -->
                    <div :style="{ top: avgCostPosition + '%' }" class="avg-cost-line">
                      <span class="avg-cost-value">{{ formatPrice(avgCost) }}</span>
                    </div>
                  </div>

                  <!-- 统计信息 -->
                  <div class="chip-stats">
                    <el-row>
                      <el-col :span="12">
                        <el-statistic :precision="2" :value="avgCost" title="平均成本"/>
                      </el-col>
                      <el-col :span="12">
                        <el-statistic
                            :value="profitRatio"
                            :value-style="{ color: '#00ff88' }"
                            suffix="%"
                            title="获利比例"
                        />
                      </el-col>
                    </el-row>
                    <el-row>
                      <el-col :span="12">
                        <div class="stat-item">
                          <span class="stat-label">90%成本</span>
                          <span class="stat-value">{{ costRange }}</span>
                        </div>
                      </el-col>
                      <el-col :span="12">
                        <el-statistic :value="concentration" suffix="%" title="集中度"/>
                      </el-col>
                    </el-row>
                  </div>

                  <!-- 五档盘口 -->
                  <div class="market-depth">
                    <el-table :data="marketDepth" :show-header="false" size="mini">
                      <el-table-column prop="level" width="40"/>
                      <el-table-column prop="price" width="70">
                        <template #default="{ row }">
                          <span :class="row.type === 'buy' ? 'buy-price' : 'sell-price'">
                            {{ formatPrice(row.price) }}
                          </span>
                        </template>
                      </el-table-column>
                      <el-table-column align="right" prop="volume" width="80"/>
                    </el-table>

                    <!-- 当前价居中显示 -->
                    <div class="current-price-display">
                      <span class="price-value">{{ formatPrice(currentStock.price) }}</span>
                    </div>
                  </div>
                </el-card>
              </el-col>
            </el-row>
          </div>

          <!-- 技术指标副图 -->
          <div class="indicator-container">
            <el-tabs v-model="activeIndicator" class="indicator-tabs">
              <el-tab-pane label="MACD" name="macd">
                <div ref="macdChart" class="indicator-chart"></div>
              </el-tab-pane>
              <el-tab-pane label="KDJ" name="kdj">
                <div ref="kdjChart" class="indicator-chart"></div>
              </el-tab-pane>
              <el-tab-pane label="RSI" name="rsi">
                <div ref="rsiChart" class="indicator-chart"></div>
              </el-tab-pane>
              <el-tab-pane label="BOLL" name="boll">
                <div ref="bollChart" class="indicator-chart"></div>
              </el-tab-pane>
            </el-tabs>

            <!-- 指标数值显示 -->
            <div class="indicator-values">
              <span v-for="(value, key) in indicatorValues" :key="key" class="indicator-value">
                {{ key }}: <span :class="getIndicatorClass(value)">{{ formatNumber(value) }}</span>
              </span>
            </div>
          </div>

          <!-- 底部信息面板 -->
          <div class="bottom-info-panel">
            <el-tabs v-model="activeInfoTab" class="info-tabs">
              <el-tab-pane label="逐笔成交" name="trades">
                <el-table :data="recentTrades" height="120" size="mini">
                  <el-table-column label="时间" prop="time" width="80"/>
                  <el-table-column label="价格" prop="price" width="70">
                    <template #default="{ row }">
                      <span :class="row.direction === 'buy' ? 'buy-price' : 'sell-price'">
                        {{ formatPrice(row.price) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column label="手数" prop="volume" width="60"/>
                  <el-table-column label="方向" prop="direction" width="50">
                    <template #default="{ row }">
                      <el-tag :type="row.direction === 'buy' ? 'success' : 'danger'" size="mini">
                        {{ row.direction === 'buy' ? '买入' : '卖出' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>

              <el-tab-pane label="分价表" name="priceTable">
                <el-table :data="priceDistribution" height="120" size="mini">
                  <el-table-column label="价格" prop="price" width="70"/>
                  <el-table-column label="成交量" prop="volume" width="80"/>
                  <el-table-column label="占比" prop="ratio" width="60">
                    <template #default="{ row }">
                      {{ formatPercent(row.ratio) }}%
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>

              <el-tab-pane label="资金流向" name="moneyFlow">
                <div class="money-flow-content">
                  <el-row :gutter="20">
                    <el-col :span="6">
                      <el-statistic :value="moneyFlow.mainIn" suffix="万" title="主力流入"/>
                    </el-col>
                    <el-col :span="6">
                      <el-statistic :value="moneyFlow.mainOut" suffix="万" title="主力流出"/>
                    </el-col>
                    <el-col :span="6">
                      <el-statistic
                          :value="moneyFlow.mainNet"
                          :value-style="{ color: moneyFlow.mainNet > 0 ? '#00ff88' : '#ff4444' }"
                          suffix="万"
                          title="主力净流入"
                      />
                    </el-col>
                    <el-col :span="6">
                      <el-statistic :value="moneyFlow.retailNet" suffix="万" title="散户净流入"/>
                    </el-col>
                  </el-row>
                </div>
              </el-tab-pane>

              <el-tab-pane label="龙虎榜" name="topList">
                <el-table :data="dragonTigerList" height="120" size="mini">
                  <el-table-column label="排名" prop="rank" width="50"/>
                  <el-table-column label="营业部" prop="name"/>
                  <el-table-column label="买入" prop="buyAmount" width="80">
                    <template #default="{ row }">
                      {{ formatAmount(row.buyAmount) }}
                    </template>
                  </el-table-column>
                  <el-table-column label="卖出" prop="sellAmount" width="80">
                    <template #default="{ row }">
                      {{ formatAmount(row.sellAmount) }}
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>

              <el-tab-pane label="大单统计" name="bigOrders">
                <el-table :data="bigOrders" height="120" size="mini">
                  <el-table-column label="时间" prop="time" width="80"/>
                  <el-table-column label="价格" prop="price" width="70"/>
                  <el-table-column label="数量" prop="volume" width="80"/>
                  <el-table-column label="金额" prop="amount" width="100">
                    <template #default="{ row }">
                      {{ formatAmount(row.amount) }}
                    </template>
                  </el-table-column>
                  <el-table-column label="类型" prop="type" width="60">
                    <template #default="{ row }">
                      <el-tag :type="row.type === 'buy' ? 'success' : 'danger'" size="mini">
                        {{ row.type === 'buy' ? '买入' : '卖出' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>
            </el-tabs>
          </div>
        </el-main>
      </el-container>
    </el-container>

    <!-- 量化信号浮动面板 -->
    <div v-if="showQuantSignal" class="quant-signal-panel">
      <el-card class="signal-card">
        <template #header>
          <div class="signal-header">
            <span class="signal-title">量化信号</span>
            <el-button
                icon="Close"
                type="text"
                @click="showQuantSignal = false"
            />
          </div>
        </template>

        <div class="signal-content">
          <el-button
              :class="{ 'pulse-animation': quantSignal.strength >= 4 }"
              class="signal-button"
              type="primary"
          >
            {{ quantSignal.signal }}
          </el-button>

          <el-rate
              v-model="quantSignal.strength"
              disabled
              score-template="{value}星"
              show-score
          />

          <div class="signal-params">
            <div class="param-item">
              <span class="param-label">建议仓位：</span>
              <span class="param-value">{{ quantSignal.position }}%</span>
            </div>
            <div class="param-item">
              <span class="param-label">止盈价格：</span>
              <span class="param-value profit">{{ formatPrice(quantSignal.takeProfit) }}</span>
            </div>
            <div class="param-item">
              <span class="param-label">止损价格：</span>
              <span class="param-value loss">{{ formatPrice(quantSignal.stopLoss) }}</span>
            </div>
            <div class="param-item">
              <span class="param-label">准确率：</span>
              <el-progress
                  :color="quantSignal.accuracy > 70 ? '#00ff88' : '#ffd700'"
                  :percentage="quantSignal.accuracy"
              />
            </div>
          </div>

          <el-button class="execute-button" type="success">
            执行策略
          </el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import {computed, nextTick, onMounted, onUnmounted, reactive, ref} from 'vue'
import * as echarts from 'echarts'
import {ElMessage} from 'element-plus'

// 状态管理
const searchSymbol = ref('')
const currentMarket = ref('A股')
const currentStock = reactive({
  code: '600519',
  name: '贵州茅台',
  price: 1725.50,
  change: 25.30,
  changePct: 1.49,
  high: 1738.00,
  low: 1708.20,
  volume: 125680,
  amount: 2156789000,
  turnover: 0.85,
  industries: ['白酒', '食品饮料'],
  concepts: [
    {name: '白马股', hot: true},
    {name: '消费升级', hot: false},
    {name: '外资重仓', hot: true},
    {name: 'MSCI中国', hot: false},
    {name: '沪股通', hot: false}
  ],
  sectorChange: 2.35
})

// 市场列表
const markets = [
  {label: 'A股', value: 'A股'},
  {label: '港股', value: '港股'},
  {label: '美股', value: '美股'}
]

// 周期列表
const periods = [
  {label: '分时', value: '1m'},
  {label: '5分', value: '5m'},
  {label: '15分', value: '15m'},
  {label: '30分', value: '30m'},
  {label: '60分', value: '60m'},
  {label: '日K', value: '1d'},
  {label: '周K', value: '1w'},
  {label: '月K', value: '1M'}
]

const currentPeriod = ref('1d')
const adjustType = ref('qfq')
const showAddStock = ref(false)
const showQuantSignal = ref(true)
const activeIndicator = ref('macd')
const activeInfoTab = ref('trades')

// 自选股列表
const watchlist = ref([
  {code: '600519', name: '贵州茅台', price: 1725.50, change: 25.30, changePct: 1.49},
  {code: '000858', name: '五粮液', price: 168.20, change: -2.10, changePct: -1.23},
  {code: '000001', name: '平安银行', price: 12.35, change: 0.15, changePct: 1.23},
  {code: '000002', name: '万科A', price: 15.68, change: -0.32, changePct: -2.00},
  {code: '600036', name: '招商银行', price: 32.45, change: 0.28, changePct: 0.87}
])

// 价格刻度
const priceScale = computed(() => {
  const min = currentStock.low
  const max = currentStock.high
  const step = (max - min) / 9
  return Array.from({length: 10}, (_, i) => min + step * i).reverse()
})

// 筹码数据
const chipData = ref([
  {price: 1750, percentage: 20, type: 'profit'},
  {price: 1740, percentage: 35, type: 'profit'},
  {price: 1730, percentage: 50, type: 'profit'},
  {price: 1720, percentage: 80, type: 'dense'},
  {price: 1710, percentage: 90, type: 'dense'},
  {price: 1700, percentage: 75, type: 'dense'},
  {price: 1690, percentage: 45, type: 'loss'},
  {price: 1680, percentage: 30, type: 'loss'},
  {price: 1670, percentage: 15, type: 'loss'}
])

const avgCost = ref(1715.28)
const avgCostPosition = computed(() => {
  const min = currentStock.low
  const max = currentStock.high
  return ((max - avgCost.value) / (max - min)) * 100
})

const profitRatio = ref(68.5)
const costRange = ref('1680-1750')
const concentration = ref(82.3)

// 五档盘口
const marketDepth = ref([
  {level: '卖5', price: 1730.00, volume: 580, type: 'sell'},
  {level: '卖4', price: 1729.00, volume: 420, type: 'sell'},
  {level: '卖3', price: 1728.00, volume: 350, type: 'sell'},
  {level: '卖2', price: 1727.00, volume: 280, type: 'sell'},
  {level: '卖1', price: 1726.00, volume: 150, type: 'sell'},
  {level: '买1', price: 1725.00, volume: 200, type: 'buy'},
  {level: '买2', price: 1724.00, volume: 320, type: 'buy'},
  {level: '买3', price: 1723.00, volume: 450, type: 'buy'},
  {level: '买4', price: 1722.00, volume: 380, type: 'buy'},
  {level: '买5', price: 1721.00, volume: 520, type: 'buy'}
])

// 指标数值
const indicatorValues = ref({
  DIF: 12.35,
  DEA: 10.28,
  MACD: 2.07
})

// 逐笔成交
const recentTrades = ref([
  {time: '14:59:58', price: 1725.50, volume: 10, direction: 'buy'},
  {time: '14:59:55', price: 1725.30, volume: 5, direction: 'sell'},
  {time: '14:59:52', price: 1725.40, volume: 8, direction: 'buy'},
  {time: '14:59:50', price: 1725.20, volume: 12, direction: 'sell'},
  {time: '14:59:48', price: 1725.30, volume: 15, direction: 'buy'}
])

// 分价表
const priceDistribution = ref([
  {price: 1726.00, volume: 1250, ratio: 15.2},
  {price: 1725.50, volume: 2380, ratio: 28.9},
  {price: 1725.00, volume: 1850, ratio: 22.5},
  {price: 1724.50, volume: 1420, ratio: 17.3},
  {price: 1724.00, volume: 1320, ratio: 16.1}
])

// 资金流向
const moneyFlow = reactive({
  mainIn: 5628.35,
  mainOut: 4235.20,
  mainNet: 1393.15,
  retailNet: -1393.15
})

// 龙虎榜
const dragonTigerList = ref([
  {rank: 1, name: '机构专用1', buyAmount: 8562.35, sellAmount: 0},
  {rank: 2, name: '机构专用2', buyAmount: 6235.20, sellAmount: 0},
  {rank: 3, name: '华泰证券深圳益田路', buyAmount: 5126.80, sellAmount: 2365.10}
])

// 大单统计
const bigOrders = ref([
  {time: '14:58:30', price: 1725.50, volume: 500, amount: 862750, type: 'buy'},
  {time: '14:55:20', price: 1725.00, volume: 800, amount: 1380000, type: 'buy'},
  {time: '14:52:15', price: 1724.80, volume: 600, amount: 1034880, type: 'sell'}
])

// 量化信号
const quantSignal = reactive({
  signal: '强烈买入',
  strength: 4,
  position: 60,
  takeProfit: 1785,
  stopLoss: 1680,
  accuracy: 78.5
})

// 图表实例
const klineChart = ref(null)
const macdChart = ref(null)
const kdjChart = ref(null)
const rsiChart = ref(null)
const bollChart = ref(null)

let klineChartInstance = null
let macdChartInstance = null
let updateTimer = null
let resizeObserver = null
let windowResizeHandler = null

// 方法
const queryStockSearch = (queryString, cb) => {
  // 模拟股票搜索
  const results = [
    {code: '600519', name: '贵州茅台', value: '600519 贵州茅台'},
    {code: '000858', name: '五粮液', value: '000858 五粮液'}
  ]
  cb(results)
}

const handleStockSelect = (item) => {
  currentStock.code = item.code
  currentStock.name = item.name
  loadStockData()
}

const selectStock = (stock) => {
  Object.assign(currentStock, stock)
  loadStockData()
}

const switchMarket = (market) => {
  currentMarket.value = market
  ElMessage.success(`切换到${market}市场`)
}

const switchPeriod = (period) => {
  currentPeriod.value = period
  updateKlineChart()
}

const loadStockData = () => {
  // 加载股票数据
  ElMessage.success('加载数据中...')
  updateKlineChart()
  updateIndicatorChart()
}

const getPriceClass = (changePct) => {
  if (changePct > 0) return 'price-up'
  if (changePct < 0) return 'price-down'
  return 'price-flat'
}

const getChipColor = (type) => {
  const colors = {
    profit: '#00ff88',
    loss: '#ff4444',
    dense: '#ffd700'
  }
  return colors[type] || '#666'
}

const getIndicatorClass = (value) => {
  return value > 0 ? 'positive' : 'negative'
}

const formatPrice = (value) => {
  return value ? value.toFixed(2) : '0.00'
}

const formatPercent = (value) => {
  return value ? value.toFixed(2) : '0.00'
}

const formatVolume = (value) => {
  if (value > 10000) {
    return (value / 10000).toFixed(2) + '万'
  }
  return value
}

const formatAmount = (value) => {
  if (value > 100000000) {
    return (value / 100000000).toFixed(2) + '亿'
  }
  if (value > 10000) {
    return (value / 10000).toFixed(2) + '万'
  }
  return value
}

const formatNumber = (value) => {
  return value ? value.toFixed(2) : '0.00'
}

// 初始化K线图
const initKlineChart = () => {
  if (!klineChart.value || klineChartInstance) return

  klineChartInstance = echarts.init(klineChart.value)

  // 使用ResizeObserver监听容器大小变化
  if (window.ResizeObserver && !resizeObserver) {
    resizeObserver = new ResizeObserver(() => {
      if (klineChartInstance) klineChartInstance.resize()
      if (macdChartInstance) macdChartInstance.resize()
    })
    resizeObserver.observe(klineChart.value)
  }

  const option = {
    backgroundColor: '#0a0a0a',
    grid: {
      left: 10,
      right: 10,
      top: 10,
      bottom: 30
    },
    xAxis: {
      type: 'category',
      data: generateDates(),
      axisLine: {lineStyle: {color: '#333'}},
      axisLabel: {color: '#888'}
    },
    yAxis: {
      type: 'value',
      position: 'right',
      axisLine: {show: false},
      axisTick: {show: false},
      splitLine: {lineStyle: {color: '#1a1a1a'}},
      axisLabel: {color: '#888'}
    },
    series: [
      {
        type: 'candlestick',
        data: generateKlineData(),
        itemStyle: {
          color: '#00ff88',
          color0: '#ff4444',
          borderColor: '#00ff88',
          borderColor0: '#ff4444'
        }
      },
      {
        name: 'MA5',
        type: 'line',
        data: generateMAData(5),
        smooth: true,
        lineStyle: {color: '#fff', width: 1},
        showSymbol: false
      },
      {
        name: 'MA10',
        type: 'line',
        data: generateMAData(10),
        smooth: true,
        lineStyle: {color: '#ffd700', width: 1},
        showSymbol: false
      },
      {
        name: 'MA20',
        type: 'line',
        data: generateMAData(20),
        smooth: true,
        lineStyle: {color: '#00ccff', width: 1},
        showSymbol: false
      }
    ]
  }

  klineChartInstance.setOption(option)

  // 设置选项后立即调整大小
  nextTick(() => {
    if (klineChartInstance) klineChartInstance.resize()
  })
}

// 初始化MACD图
const initMacdChart = () => {
  if (!macdChart.value || macdChartInstance) return

  macdChartInstance = echarts.init(macdChart.value)

  const option = {
    backgroundColor: '#0a0a0a',
    grid: {
      left: 70,
      right: 10,
      top: 10,
      bottom: 20
    },
    xAxis: {
      type: 'category',
      data: generateDates(),
      axisLine: {lineStyle: {color: '#333'}},
      axisLabel: {show: false}
    },
    yAxis: {
      type: 'value',
      axisLine: {show: false},
      axisTick: {show: false},
      splitLine: {lineStyle: {color: '#1a1a1a'}},
      axisLabel: {color: '#888'}
    },
    series: [
      {
        name: 'MACD',
        type: 'bar',
        data: generateMacdBarData(),
        itemStyle: {
          color: (params) => params.value >= 0 ? '#00ff88' : '#ff4444'
        }
      },
      {
        name: 'DIF',
        type: 'line',
        data: generateRandomData(80, -5, 5),
        lineStyle: {color: '#fff', width: 1},
        showSymbol: false
      },
      {
        name: 'DEA',
        type: 'line',
        data: generateRandomData(80, -5, 5),
        lineStyle: {color: '#ffd700', width: 1},
        showSymbol: false
      }
    ]
  }

  macdChartInstance.setOption(option)

  // 设置选项后立即调整大小
  nextTick(() => {
    if (macdChartInstance) macdChartInstance.resize()
  })
}

// 生成测试数据
const generateDates = () => {
  const dates = []
  const now = new Date()
  for (let i = 79; i >= 0; i--) {
    const date = new Date(now - i * 24 * 3600 * 1000)
    dates.push(`${date.getMonth() + 1}/${date.getDate()}`)
  }
  return dates
}

const generateKlineData = () => {
  const basePrice = 1700
  const data = []
  for (let i = 0; i < 80; i++) {
    const open = basePrice + Math.random() * 50
    const close = open + (Math.random() - 0.5) * 20
    const low = Math.min(open, close) - Math.random() * 10
    const high = Math.max(open, close) + Math.random() * 10
    data.push([open, close, low, high])
  }
  return data
}

const generateMAData = (period) => {
  return generateRandomData(80, 1680, 1750)
}

const generateMacdBarData = () => {
  return generateRandomData(80, -2, 2)
}

const generateRandomData = (count, min, max) => {
  const data = []
  for (let i = 0; i < count; i++) {
    data.push(min + Math.random() * (max - min))
  }
  return data
}

const updateKlineChart = () => {
  if (klineChartInstance) {
    klineChartInstance.setOption({
      series: [{
        data: generateKlineData()
      }]
    })
  }
}

const updateIndicatorChart = () => {
  if (macdChartInstance) {
    macdChartInstance.setOption({
      series: [{
        data: generateMacdBarData()
      }]
    })
  }
}

// 实时更新
const startRealtimeUpdate = () => {
  updateTimer = setInterval(() => {
    // 更新价格
    currentStock.price += (Math.random() - 0.5) * 2
    currentStock.change = currentStock.price - 1700.20
    currentStock.changePct = (currentStock.change / 1700.20) * 100

    // 更新成交
    recentTrades.value.unshift({
      time: new Date().toLocaleTimeString(),
      price: currentStock.price,
      volume: Math.floor(Math.random() * 20) + 1,
      direction: Math.random() > 0.5 ? 'buy' : 'sell'
    })
    recentTrades.value = recentTrades.value.slice(0, 5)
  }, 3000)
}

// 生命周期
onMounted(() => {
  // 延迟初始化图表，确保DOM完全渲染
  setTimeout(() => {
    initKlineChart()
    initMacdChart()
    startRealtimeUpdate()
  }, 300)

  // 添加窗口resize监听
  windowResizeHandler = () => {
    if (klineChartInstance) klineChartInstance.resize()
    if (macdChartInstance) macdChartInstance.resize()
  }
  window.addEventListener('resize', windowResizeHandler)
})

onUnmounted(() => {
  clearInterval(updateTimer)

  // 清理ResizeObserver
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }

  // 移除窗口resize监听
  if (windowResizeHandler) {
    window.removeEventListener('resize', windowResizeHandler)
  }

  klineChartInstance?.dispose()
  macdChartInstance?.dispose()
})
</script>

<style lang="scss" scoped>
.quant-trading-view {
  width: 100%;
  height: 100vh;
  background: #0a0a0a;
  color: #e0e0e0;
  font-family: 'Microsoft YaHei', sans-serif;
  overflow: hidden;

  .main-container {
    height: 100%;
  }

  // 顶部导航栏
  .top-navbar {
    background: linear-gradient(to bottom, #1a1a1a, #151515);
    border-bottom: 1px solid #2a2a2a;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 20px;

    .nav-left {
      display: flex;
      align-items: center;
      gap: 20px;

      .logo {
        .logo-text {
          font-size: 20px;
          font-weight: bold;
          background: linear-gradient(90deg, #00ff88, #00ccff);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
      }

      .stock-search {
        width: 300px;

        :deep(.el-input__wrapper) {
          background: #0a0a0a;
          border: 1px solid #333;

          &:hover {
            border-color: #00ff88;
          }

          &.is-focus {
            border-color: #00ff88;
            box-shadow: 0 0 10px rgba(0, 255, 136, 0.3);
          }
        }

        :deep(.el-input__inner) {
          color: #e0e0e0;
        }
      }

      .stock-search-item {
        display: flex;
        gap: 10px;

        .stock-code {
          color: #00ccff;
          font-weight: bold;
        }

        .stock-name {
          color: #e0e0e0;
        }
      }
    }

    .nav-right {
      display: flex;
      align-items: center;
      gap: 20px;

      .market-switch {
        :deep(.el-button) {
          background: transparent;
          color: #888;
          border-color: #333;

          &:hover {
            color: #00ff88;
            border-color: #00ff88;
          }

          &.el-button--primary {
            background: linear-gradient(90deg, #00ff88, #00ccff);
            border: none;
            color: #0a0a0a;
          }
        }
      }
    }
  }

  .content-container {
    height: calc(100% - 50px);
  }

  // 左侧自选股面板
  .watchlist-panel {
    background: #111;
    border-right: 1px solid #2a2a2a;
    display: flex;
    flex-direction: column;

    .panel-header {
      height: 45px;
      padding: 0 15px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #2a2a2a;

      .panel-title {
        font-size: 16px;
        font-weight: bold;
      }

      :deep(.el-button) {
        background: #00ff88;
        border: none;

        &:hover {
          background: #00cc66;
        }
      }
    }

    .watchlist-scroll {
      flex: 1;

      .watchlist-content {
        padding: 10px;

        .stock-item {
          padding: 10px;
          margin-bottom: 8px;
          background: #151515;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.3s;

          &:hover {
            background: #1a1a1a;
          }

          &.active {
            background: linear-gradient(135deg, rgba(0, 255, 136, 0.1), rgba(0, 204, 255, 0.1));
            border: 1px solid #00ff88;
          }

          .stock-info {
            .stock-header {
              display: flex;
              justify-content: space-between;
              margin-bottom: 5px;

              .code {
                font-size: 12px;
                color: #888;
              }

              .name {
                font-size: 13px;
                color: #e0e0e0;
              }
            }

            .stock-price {
              display: flex;
              flex-direction: column;
              gap: 2px;

              .price {
                font-size: 16px;
                font-weight: bold;
              }

              .change, .change-pct {
                font-size: 12px;
              }
            }
          }
        }
      }
    }
  }

  // 主内容区
  .main-content {
    background: #0a0a0a;
    padding: 0;
    display: flex;
    flex-direction: column;

    // 股票信息头部
    .stock-header-info {
      height: 60px;
      padding: 10px 20px;
      background: #151515;
      border-bottom: 1px solid #2a2a2a;
      display: flex;
      justify-content: space-between;
      align-items: center;

      .stock-basic {
        display: flex;
        align-items: baseline;
        gap: 15px;

        .stock-code {
          font-size: 14px;
          color: #888;
        }

        .stock-name {
          font-size: 16px;
          font-weight: bold;
        }

        .current-price {
          font-size: 32px;
          font-weight: bold;
        }

        .price-change {
          font-size: 20px;
        }
      }

      .stock-stats {
        display: flex;
        gap: 30px;

        .stat-item {
          display: flex;
          flex-direction: column;

          .stat-label {
            font-size: 11px;
            color: #666;
          }

          .stat-value {
            font-size: 14px;
            color: #e0e0e0;
            font-weight: bold;
          }
        }
      }
    }

    // 行业概念面板
    .industry-concept-panel {
      height: 50px;
      padding: 10px 20px;
      background: #151515;
      border-bottom: 1px solid #2a2a2a;
      display: flex;
      align-items: center;
      gap: 30px;

      .section-label {
        font-size: 12px;
        color: #888;
      }

      :deep(.el-tag) {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid #333;
        color: #e0e0e0;

        &.el-tag--danger {
          background: rgba(255, 68, 68, 0.2);
          border-color: #ff4444;
          color: #ff4444;
        }
      }

      .sector-change {
        margin-left: auto;

        .change-value {
          color: #00ff88;
          font-weight: bold;
        }
      }
    }

    // 图表容器
    .chart-container {
      flex: 1;
      padding: 10px;

      .chart-row {
        height: 100%;

        // 价格轴
        .price-axis {
          display: flex;
          align-items: center;

          .price-scale {
            width: 100%;
            height: 90%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;

            .price-tick {
              font-size: 10px;
              color: #666;
              text-align: right;
              padding-right: 5px;
            }
          }
        }

        // K线图
        .kline-chart {
          display: flex;
          flex-direction: column;

          .chart-toolbar {
            height: 40px;
            display: flex;
            align-items: center;
            gap: 20px;
            padding: 0 10px;
            background: #151515;
            border-radius: 4px;

            :deep(.el-button) {
              background: transparent;
              border-color: #333;
              color: #888;

              &:hover {
                border-color: #00ff88;
                color: #00ff88;
              }

              &.el-button--primary {
                background: #00ff88;
                border: none;
                color: #0a0a0a;
              }
            }

            .adjust-radio {
              :deep(.el-radio-button__inner) {
                background: transparent;
                border-color: #333;
                color: #888;

                &:hover {
                  color: #00ff88;
                }
              }

              :deep(.el-radio-button__original:checked + .el-radio-button__inner) {
                background: #00ff88;
                border-color: #00ff88;
                color: #0a0a0a;
              }
            }
          }

          .kline-chart-container {
            flex: 1;
            margin-top: 10px;
          }
        }

        // 筹码分布
        .chip-distribution {
          .chip-card {
            height: 100%;
            background: #111;
            border: 1px solid #2a2a2a;

            :deep(.el-card__header) {
              background: #151515;
              padding: 10px 15px;
              border-bottom: 1px solid #2a2a2a;

              .chip-title {
                font-size: 14px;
                font-weight: bold;
              }
            }

            :deep(.el-card__body) {
              padding: 15px;
              height: calc(100% - 50px);
              display: flex;
              flex-direction: column;

              .chip-chart {
                flex: 1;
                position: relative;

                .chip-bar {
                  display: flex;
                  align-items: center;
                  gap: 10px;
                  margin-bottom: 5px;

                  .chip-price {
                    font-size: 10px;
                    color: #666;
                    width: 45px;
                    text-align: right;
                  }

                  :deep(.el-progress) {
                    flex: 1;

                    .el-progress-bar__outer {
                      background: rgba(255, 255, 255, 0.05);
                    }
                  }
                }

                .avg-cost-line {
                  position: absolute;
                  left: 55px;
                  right: 10px;
                  height: 1px;
                  background: #ffd700;

                  .avg-cost-value {
                    position: absolute;
                    right: -50px;
                    top: -8px;
                    font-size: 11px;
                    color: #ffd700;
                  }
                }
              }

              .chip-stats {
                padding-top: 10px;
                border-top: 1px solid #2a2a2a;

                :deep(.el-statistic) {
                  .el-statistic__head {
                    color: #666;
                    font-size: 11px;
                  }

                  .el-statistic__content {
                    color: #e0e0e0;

                    .el-statistic__value {
                      font-size: 16px;
                    }
                  }
                }

                .stat-item {
                  margin-top: 10px;

                  .stat-label {
                    font-size: 11px;
                    color: #666;
                  }

                  .stat-value {
                    font-size: 13px;
                    color: #e0e0e0;
                  }
                }
              }

              .market-depth {
                margin-top: 15px;
                padding-top: 15px;
                border-top: 1px solid #2a2a2a;
                position: relative;

                :deep(.el-table) {
                  background: transparent;

                  &::before {
                    display: none;
                  }

                  .el-table__body-wrapper {
                    background: transparent;
                  }

                  .el-table__row {
                    background: transparent;

                    td {
                      border: none;
                      padding: 2px 0;
                      background: transparent;
                    }
                  }
                }

                .current-price-display {
                  position: absolute;
                  left: 0;
                  right: 0;
                  top: 50%;
                  transform: translateY(-50%);
                  text-align: center;
                  background: rgba(0, 255, 136, 0.1);
                  padding: 5px;

                  .price-value {
                    font-size: 18px;
                    font-weight: bold;
                    color: #00ff88;
                  }
                }

                .buy-price {
                  color: #00ff88;
                }

                .sell-price {
                  color: #ff4444;
                }
              }
            }
          }
        }
      }
    }

    // 技术指标
    .indicator-container {
      height: 180px;
      padding: 10px;
      background: #111;
      border-top: 1px solid #2a2a2a;

      :deep(.el-tabs) {
        height: 100%;

        .el-tabs__header {
          margin: 0;
          background: #151515;

          .el-tabs__nav-wrap {
            &::after {
              background: #2a2a2a;
            }
          }

          .el-tabs__item {
            color: #888;

            &:hover {
              color: #00ff88;
            }

            &.is-active {
              color: #00ff88;
            }
          }

          .el-tabs__active-bar {
            background: #00ff88;
          }
        }

        .el-tabs__content {
          height: calc(100% - 40px);
          padding: 0;

          .indicator-chart {
            height: 100%;
          }
        }
      }

      .indicator-values {
        position: absolute;
        top: 15px;
        right: 20px;
        display: flex;
        gap: 20px;

        .indicator-value {
          font-size: 12px;
          color: #888;

          span {
            font-weight: bold;

            &.positive {
              color: #00ff88;
            }

            &.negative {
              color: #ff4444;
            }
          }
        }
      }
    }

    // 底部信息面板
    .bottom-info-panel {
      height: 160px;
      padding: 10px;
      background: #111;
      border-top: 1px solid #2a2a2a;

      :deep(.el-tabs) {
        height: 100%;

        .el-tabs__header {
          margin: 0;
          height: 35px;

          .el-tabs__item {
            height: 35px;
            line-height: 35px;
            color: #888;
            font-size: 12px;

            &.is-active {
              color: #00ff88;
            }
          }
        }

        .el-tabs__content {
          height: calc(100% - 35px);
          padding: 10px 0;
        }

        .el-table {
          background: transparent;
          font-size: 12px;

          &::before {
            display: none;
          }

          th {
            background: #151515;
            color: #888;
            border-bottom: 1px solid #2a2a2a;
          }

          td {
            border-bottom: 1px solid #1a1a1a;
            color: #e0e0e0;
          }

          .el-table__row {
            background: transparent;

            &:hover > td {
              background: rgba(255, 255, 255, 0.02);
            }
          }
        }

        .money-flow-content {
          padding: 10px;

          :deep(.el-statistic) {
            .el-statistic__head {
              color: #666;
              font-size: 11px;
            }

            .el-statistic__content {
              color: #e0e0e0;

              .el-statistic__value {
                font-size: 18px;
              }
            }
          }
        }
      }
    }
  }

  // 量化信号浮动面板
  .quant-signal-panel {
    position: fixed;
    right: 20px;
    bottom: 20px;
    z-index: 1000;

    .signal-card {
      width: 280px;
      background: rgba(17, 17, 17, 0.95);
      border: 1px solid #2a2a2a;
      backdrop-filter: blur(10px);

      :deep(.el-card__header) {
        background: rgba(21, 21, 21, 0.95);
        border-bottom: 1px solid #2a2a2a;
        padding: 10px 15px;

        .signal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;

          .signal-title {
            font-size: 14px;
            font-weight: bold;
            color: #00ff88;
          }
        }
      }

      :deep(.el-card__body) {
        padding: 15px;

        .signal-content {
          display: flex;
          flex-direction: column;
          gap: 15px;

          .signal-button {
            width: 100%;
            height: 40px;
            font-size: 16px;
            font-weight: bold;
            background: linear-gradient(135deg, #00ff88, #00ccff);
            border: none;
            color: #0a0a0a;

            &.pulse-animation {
              animation: pulse 2s infinite;
            }
          }

          :deep(.el-rate) {
            text-align: center;

            .el-rate__icon {
              color: #ffd700;
            }

            .el-rate__text {
              color: #ffd700;
            }
          }

          .signal-params {
            .param-item {
              display: flex;
              justify-content: space-between;
              margin-bottom: 8px;

              .param-label {
                font-size: 12px;
                color: #888;
              }

              .param-value {
                font-size: 13px;
                font-weight: bold;
                color: #e0e0e0;

                &.profit {
                  color: #00ff88;
                }

                &.loss {
                  color: #ff4444;
                }
              }
            }

            :deep(.el-progress) {
              .el-progress__text {
                color: #e0e0e0;
              }
            }
          }

          .execute-button {
            width: 100%;
            background: #00ff88;
            border: none;
            color: #0a0a0a;
            font-weight: bold;

            &:hover {
              background: #00cc66;
            }
          }
        }
      }
    }
  }

  // 价格颜色类
  .price-up {
    color: #00ff88;
  }

  .price-down {
    color: #ff4444;
  }

  .price-flat {
    color: #e0e0e0;
  }

  // 动画
  @keyframes pulse {
    0% {
      box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.7);
    }
    50% {
      box-shadow: 0 0 20px 10px rgba(0, 255, 136, 0);
    }
    100% {
      box-shadow: 0 0 0 0 rgba(0, 255, 136, 0);
    }
  }
}

// 覆盖 Element UI 深色主题
:deep(.el-button),
:deep(.el-input),
:deep(.el-select),
:deep(.el-tag),
:deep(.el-card) {
  --el-bg-color: #151515;
  --el-text-color-primary: #e0e0e0;
  --el-text-color-regular: #ccc;
  --el-text-color-secondary: #999;
  --el-text-color-placeholder: #666;
  --el-border-color: #333;
  --el-border-color-light: #2a2a2a;
  --el-border-color-lighter: #1a1a1a;
}
</style>