<template>
  <div class="professional-trading-view">
    <!-- 顶部导航栏 -->
    <div class="top-navbar">
      <div class="nav-left">
        <!-- 股票信息 -->
        <div class="stock-info">
          <el-autocomplete
              v-model="symbol"
              :fetch-suggestions="queryStock"
              :trigger-on-focus="false"
              clearable
              placeholder="代码/名称/拼音"
              size="small"
              style="width: 180px"
              value-key="value"
              @select="handleStockSelect"
              @keyup.enter="loadData"
          >
            <template #default="{ item }">
              <div style="display: flex; justify-content: space-between;">
                <span>{{ item.name }}</span>
                <span style="color: #909399; margin-left: 10px;">{{ item.code }}</span>
              </div>
            </template>
          </el-autocomplete>

          <div v-if="stockInfo" class="stock-title">
            <span class="stock-name">{{ stockInfo.name }}</span>
            <span class="stock-code">({{ stockInfo.symbol }})</span>
            <el-tag v-if="currentDataSource" size="small" style="margin-left: 10px" type="info">
              {{ currentDataSource }}
            </el-tag>
          </div>
        </div>

        <!-- 股票标签 -->
        <div class="stock-tags">
          <span v-if="stockInfo?.is_margin" class="tag margin">融</span>
          <span v-if="stockInfo?.is_hgt" class="tag hgt">沪股通</span>
          <span v-if="stockInfo?.is_sgt" class="tag sgt">深股通</span>
          <span v-if="stockInfo?.is_star" class="tag star">科创板</span>
          <span v-if="stockInfo?.is_gem" class="tag gem">创业板</span>
        </div>
      </div>

      <div class="nav-right">
        <!-- 实时价格 -->
        <div v-if="snapshot" class="price-info">
          <span :class="getPriceClass(snapshot.change_pct)" class="current-price">
            {{ formatNumber(snapshot.price) }}
          </span>
          <span :class="getPriceClass(snapshot.change_pct)" class="price-change">
            {{ snapshot.change > 0 ? '+' : '' }}{{ formatNumber(snapshot.change) }}
            ({{ snapshot.change_pct > 0 ? '+' : '' }}{{ formatPercent(snapshot.change_pct) }}%)
          </span>
        </div>

        <!-- 快速操作 -->
        <el-button-group size="small">
          <el-button @click="toggleSidePanel('info')">数据</el-button>
          <el-button @click="toggleSidePanel('news')">资讯</el-button>
        </el-button-group>
      </div>
    </div>

    <!-- 市场数据滚动条 -->
    <div class="market-ticker">
      <div class="ticker-content">
        <span v-for="item in marketData" :key="item.symbol" class="ticker-item">
          <span class="ticker-name">{{ item.name }}</span>
          <span :class="getPriceClass(item.change_pct)" class="ticker-price">
            {{ formatNumber(item.price) }}
            <span class="ticker-change">{{ item.change_pct > 0 ? '+' : '' }}{{ formatPercent(item.change_pct) }}%</span>
          </span>
        </span>
      </div>
    </div>

    <!-- 周期切换标签 -->
    <div class="period-tabs">
      <el-tabs v-model="activeTimeframe" @tab-click="handleTimeframeChange">
        <el-tab-pane label="分时" name="1m"></el-tab-pane>
        <el-tab-pane label="5分" name="5m"></el-tab-pane>
        <el-tab-pane label="15分" name="15m"></el-tab-pane>
        <el-tab-pane label="30分" name="30m"></el-tab-pane>
        <el-tab-pane label="60分" name="60m"></el-tab-pane>
        <el-tab-pane label="日K" name="1d"></el-tab-pane>
        <el-tab-pane label="周K" name="1w"></el-tab-pane>
        <el-tab-pane label="月K" name="1mo"></el-tab-pane>
      </el-tabs>

      <!-- 复权选择 -->
      <el-radio-group v-model="adjust" size="small" @change="loadData">
        <el-radio-button label="none">除权</el-radio-button>
        <el-radio-button label="qfq">前复权</el-radio-button>
        <el-radio-button label="hfq">后复权</el-radio-button>
      </el-radio-group>

      <!-- 数据源选择 -->
      <el-select
          v-model="selectedProvider"
          :loading="providersLoading"
          placeholder="选择数据源"
          size="small"
          style="width: 140px"
          @change="handleProviderChange"
      >
        <el-option
            v-for="provider in availableProviders"
            :key="provider.name"
            :disabled="!provider.enabled"
            :label="provider.label"
            :value="provider.name"
        >
          <span style="float: left">
            <el-icon v-if="provider.status === 'running'" style="color: #67C23A">
              <CircleCheck/>
            </el-icon>
            <el-icon v-else-if="provider.status === 'error'" style="color: #F56C6C">
              <CircleClose/>
            </el-icon>
            <el-icon v-else style="color: #909399">
              <Warning/>
            </el-icon>
            {{ provider.label }}
          </span>
          <span style="float: right; color: #8492a6; font-size: 12px">
            {{ provider.type }}
          </span>
        </el-option>
      </el-select>

      <!-- 主图指标选择 -->
      <el-select v-model="mainIndicator" size="small" style="width: 120px" @change="changeMainIndicator">
        <el-option label="不显示指标" value="none"/>
        <el-option label="均线" value="MA"/>
        <el-option label="EXPMA" value="EXPMA"/>
        <el-option label="BOLL" value="BOLL"/>
        <el-option label="ENE" value="ENE"/>
      </el-select>

      <!-- 指标管理 -->
      <el-button size="small" @click="showIndicatorManager = true">
        <el-icon>
          <Setting/>
        </el-icon>
        指标管理
      </el-button>

      <!-- 模板选择 -->
      <el-select v-model="currentTemplate" placeholder="选择模板" size="small" style="width: 120px"
                 @change="applyTemplate">
        <el-option
            v-for="tmpl in templates"
            :key="tmpl.id"
            :label="tmpl.name"
            :value="tmpl.id"
        />
      </el-select>

      <!-- 实时/历史切换 -->
      <el-switch
          v-model="realtime"
          active-text="实时"
          inactive-text="历史"
          size="small"
          @change="toggleRealtime"
      />
    </div>

    <!-- 主体内容区 -->
    <div class="main-content">
      <el-row :gutter="10">
        <!-- 左侧买卖面板 -->
        <el-col v-if="showOrderPanel" :span="4">
          <div class="order-panel">
            <!-- 买五卖五 -->
            <div class="order-book">
              <div class="order-header">委托档位</div>

              <el-skeleton :loading="orderbookLoading" :rows="0" animated>
                <template #template>
                  <!-- 卖盘骨架 -->
                  <div class="sell-orders">
                    <div v-for="i in 5" :key="'sell-skeleton-' + i" class="order-item">
                      <el-skeleton-item style="width: 30%" variant="text"/>
                      <el-skeleton-item style="width: 40%" variant="text"/>
                      <el-skeleton-item style="width: 30%" variant="text"/>
                    </div>
                  </div>
                  <!-- 价格分割线骨架 -->
                  <div class="current-price-divider">
                    <el-skeleton-item style="width: 60%; margin: 0 auto" variant="text"/>
                  </div>
                  <!-- 买盘骨架 -->
                  <div class="buy-orders">
                    <div v-for="i in 5" :key="'buy-skeleton-' + i" class="order-item">
                      <el-skeleton-item style="width: 30%" variant="text"/>
                      <el-skeleton-item style="width: 40%" variant="text"/>
                      <el-skeleton-item style="width: 30%" variant="text"/>
                    </div>
                  </div>
                </template>
                <template #default>
                  <!-- 卖盘 -->
                  <div class="sell-orders">
                    <div v-if="sellOrders.length > 0">
                      <div v-for="(order, index) in sellOrders" :key="'sell' + index" class="order-item sell">
                        <span class="order-label">卖{{ 5 - index }}</span>
                        <span class="order-price">{{ formatNumber(order.price) }}</span>
                        <span class="order-volume">{{ formatVolume(order.volume) }}</span>
                      </div>
                    </div>
                    <div v-else class="no-data">暂无卖盘数据</div>
                  </div>

                  <!-- 当前价格分割线 -->
                  <div class="current-price-divider">
                    <span :class="getPriceClass(snapshot?.change_pct)" class="price">
                      {{ formatNumber(snapshot?.price) || '--' }}
                    </span>
                    <span :class="getPriceClass(snapshot?.change_pct)" class="change">
                      {{ snapshot?.change_pct > 0 ? '↑' : '↓' }}{{
                        formatPercent(Math.abs(snapshot?.change_pct || 0))
                      }}%
                    </span>
                  </div>

                  <!-- 买盘 -->
                  <div class="buy-orders">
                    <div v-if="buyOrders.length > 0">
                      <div v-for="(order, index) in buyOrders" :key="'buy' + index" class="order-item buy">
                        <span class="order-label">买{{ index + 1 }}</span>
                        <span class="order-price">{{ formatNumber(order.price) }}</span>
                        <span class="order-volume">{{ formatVolume(order.volume) }}</span>
                      </div>
                    </div>
                    <div v-else class="no-data">暂无买盘数据</div>
                  </div>
                </template>
              </el-skeleton>
            </div>

            <!-- 股票基本信息 -->
            <div class="stock-basic-info">
              <div class="info-header">基本信息</div>
              <el-skeleton :loading="stockInfoLoading" :rows="0" animated>
                <template #template>
                  <div class="info-content">
                    <div v-for="i in 6" :key="'info-skeleton-' + i" class="info-item">
                      <el-skeleton-item style="width: 35%" variant="text"/>
                      <el-skeleton-item style="width: 45%; float: right" variant="text"/>
                    </div>
                  </div>
                </template>
                <template #default>
                  <div v-if="stockInfo" class="info-content">
                    <div class="info-item">
                      <span class="info-label">股票名称</span>
                      <span class="info-value">{{ stockInfo.name || '--' }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">所属行业</span>
                      <span class="info-value">{{ stockInfo.industry || '--' }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">上市日期</span>
                      <span class="info-value">{{ stockInfo.listed_date || '--' }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">总市值</span>
                      <span class="info-value">{{ formatMarketCap(stockInfo.market_cap) || '--' }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">市盈率</span>
                      <span class="info-value">{{ formatNumber(stockInfo.pe_ratio) || '--' }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">市净率</span>
                      <span class="info-value">{{ formatNumber(stockInfo.pb_ratio) || '--' }}</span>
                    </div>
                  </div>
                  <div v-else class="info-content">
                    <div class="no-data">暂无基本信息</div>
                  </div>
                </template>
              </el-skeleton>
            </div>
          </div>
        </el-col>

        <!-- 中间图表区 -->
        <el-col :span="showOrderPanel ? (showInfoPanel ? 14 : 16) : (showInfoPanel ? 16 : 20)">
          <div class="chart-area">
            <!-- 主K线图 -->
            <div ref="mainChart" class="main-chart"></div>

            <!-- 技术指标区域 -->
            <div class="indicator-charts">
              <div v-for="(indicator, index) in activeIndicators" :key="indicator.name" class="indicator-chart">
                <div class="indicator-header">
                  <span class="indicator-name">{{ indicator.label }}</span>
                  <el-icon class="close-btn" @click="removeIndicator(index)">
                    <Close/>
                  </el-icon>
                </div>
                <div :ref="`indicatorChart${index}`" class="indicator-chart-container"></div>
              </div>
            </div>
          </div>
        </el-col>

        <!-- 右侧筹码峰 -->
        <el-col v-if="showChipChart" :span="showChipChart ? 4 : 0">
          <div class="chip-panel">
            <div class="chip-header">
              <span>筹码分布</span>
              <el-icon class="close-btn" @click="showChipChart = false">
                <Close/>
              </el-icon>
            </div>
            <div ref="chipChart" class="chip-chart"></div>

            <!-- 筹码统计信息 -->
            <el-skeleton :loading="chipStatsLoading" :rows="0" animated>
              <template #template>
                <div class="chip-stats">
                  <div v-for="i in 5" :key="'chip-stat-skeleton-' + i" class="stat-item">
                    <el-skeleton-item style="width: 40%" variant="text"/>
                    <el-skeleton-item style="width: 35%; float: right" variant="text"/>
                  </div>
                </div>
              </template>
              <template #default>
                <div v-if="chipData" class="chip-stats">
                  <div class="stat-item">
                    <span class="label">平均成本</span>
                    <span class="value">{{ formatNumber(chipData.features?.average_cost) || '--' }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="label">获利比例</span>
                    <span :class="getPriceClass(chipData.features?.profit_ratio)" class="value">
                      {{ formatPercent(chipData.features?.profit_ratio) || '0' }}%
                    </span>
                  </div>
                  <div class="stat-item">
                    <span class="label">筹码集中度</span>
                    <span class="value">{{ formatPercent(chipData.features?.concentration) || '0' }}%</span>
                  </div>
                  <div class="stat-item">
                    <span class="label">90%成本</span>
                    <span class="value">
                      {{
                        formatNumber(chipData.features?.cost_90_low) || '--'
                      }} - {{ formatNumber(chipData.features?.cost_90_high) || '--' }}
                    </span>
                  </div>
                  <div class="stat-item">
                    <span class="label">70%成本</span>
                    <span class="value">
                      {{
                        formatNumber(chipData.features?.cost_70_low) || '--'
                      }} - {{ formatNumber(chipData.features?.cost_70_high) || '--' }}
                    </span>
                  </div>
                </div>
                <div v-else class="chip-stats">
                  <div class="no-data">暂无筹码统计</div>
                </div>
              </template>
            </el-skeleton>
          </div>
        </el-col>

        <!-- 右侧信息面板 -->
        <el-col v-if="showInfoPanel" :span="4">
          <div class="info-panel">
            <el-tabs v-model="activeInfoTab">
              <el-tab-pane label="明细" name="detail">
                <div class="trade-detail">
                  <div v-for="trade in tradeDetails" :key="trade.id" class="trade-item">
                    <span class="time">{{ trade.time }}</span>
                    <span :class="trade.direction === 'buy' ? 'buy' : 'sell'" class="price">
                      {{ formatNumber(trade.price) }}
                    </span>
                    <span class="volume">{{ formatVolume(trade.volume) }}</span>
                    <span :class="trade.direction" class="direction">
                      {{ trade.direction === 'buy' ? 'B' : 'S' }}
                    </span>
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane label="资金" name="capital">
                <div class="capital-flow">
                  <div class="flow-item">
                    <span class="label">主力净流入</span>
                    <span :class="getPriceClass(capitalFlow?.main_net)" class="value">
                      {{ formatAmount(capitalFlow?.main_net) }}
                    </span>
                  </div>
                  <div class="flow-item">
                    <span class="label">超大单</span>
                    <span :class="getPriceClass(capitalFlow?.xlarge_net)" class="value">
                      {{ formatAmount(capitalFlow?.xlarge_net) }}
                    </span>
                  </div>
                  <div class="flow-item">
                    <span class="label">大单</span>
                    <span :class="getPriceClass(capitalFlow?.large_net)" class="value">
                      {{ formatAmount(capitalFlow?.large_net) }}
                    </span>
                  </div>
                  <div class="flow-item">
                    <span class="label">中单</span>
                    <span :class="getPriceClass(capitalFlow?.medium_net)" class="value">
                      {{ formatAmount(capitalFlow?.medium_net) }}
                    </span>
                  </div>
                  <div class="flow-item">
                    <span class="label">小单</span>
                    <span :class="getPriceClass(capitalFlow?.small_net)" class="value">
                      {{ formatAmount(capitalFlow?.small_net) }}
                    </span>
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane label="资讯" name="news">
                <div class="news-list">
                  <div v-for="news in newsList" :key="news.id" class="news-item">
                    <div class="news-title">{{ news.title }}</div>
                    <div class="news-time">{{ news.time }}</div>
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane label="指标" name="indicators">
                <div class="indicator-values">
                  <div v-for="(value, key) in indicatorValues" :key="key" class="indicator-item">
                    <span class="label">{{ key }}</span>
                    <span class="value">{{ formatIndicatorValue(value) }}</span>
                  </div>
                  <div v-if="Object.keys(indicatorValues).length === 0" class="no-data">
                    暂无指标数据
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane label="信号" name="signals">
                <div class="signals-list">
                  <div v-for="signal in signals" :key="signal.id" class="signal-item">
                    <el-tag :type="signal.type" size="small">{{ signal.name }}</el-tag>
                    <span class="time">{{ signal.time }}</span>
                  </div>
                  <div v-if="signals.length === 0" class="no-data">
                    暂无交易信号
                  </div>
                </div>
              </el-tab-pane>
            </el-tabs>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 底部功能栏 -->
    <div class="bottom-toolbar">
      <div class="toolbar-left">
        <!-- 画线工具 -->
        <el-button-group size="small">
          <el-button @click="setDrawingTool('trend')">趋势线</el-button>
          <el-button @click="setDrawingTool('hline')">水平线</el-button>
          <el-button @click="setDrawingTool('vline')">垂直线</el-button>
          <el-button @click="setDrawingTool('rect')">矩形</el-button>
          <el-button @click="setDrawingTool('fib')">斐波那契</el-button>
          <el-button @click="clearDrawings()">清除</el-button>
        </el-button-group>
      </div>

      <div class="toolbar-center">
        <!-- 状态信息 -->
        <span class="status-item">
          <el-icon><Clock/></el-icon>
          更新时间: {{ lastUpdateTime }}
        </span>
        <span class="status-item">
          <el-icon><Connection/></el-icon>
          {{ connectionStatus }}
        </span>
      </div>

      <div class="toolbar-right">
        <!-- 视图控制 -->
        <el-button-group size="small">
          <el-button :type="showOrderPanel ? 'primary' : ''" @click="showOrderPanel = !showOrderPanel">
            盘口信息
          </el-button>
          <el-button :type="showChipChart ? 'primary' : ''" @click="showChipChart = !showChipChart">
            筹码分布
          </el-button>
          <el-button :type="showInfoPanel ? 'primary' : ''" @click="showInfoPanel = !showInfoPanel">
            信息面板
          </el-button>
          <el-button @click="toggleFullscreen">
            <el-icon>
              <FullScreen/>
            </el-icon>
          </el-button>
        </el-button-group>
      </div>
    </div>

    <!-- 指标管理器 -->
    <IndicatorManager
        v-if="showIndicatorManager"
        :selected-indicators="selectedIndicators"
        :visible="showIndicatorManager"
        @apply="applyIndicators"
        @close="showIndicatorManager = false"
    />
  </div>
</template>

<script setup>
import {nextTick, onMounted, onUnmounted, ref} from 'vue'
import {ElMessage} from 'element-plus'
import * as echarts from 'echarts'
import {calculateIndicators, chartApi, ChartWebSocket} from '@/api/chart'
import {qmtApi, QmtWebSocket} from '@/api/qmt'
import {formatAmount, formatMarketCap, formatNumber, formatPercent, formatVolume} from '@/utils/format'
import {Clock, Close, Connection, FullScreen, Setting} from '@element-plus/icons-vue'
import IndicatorManager from '@/components/IndicatorManager.vue'

// 状态管理
const symbol = ref('000001')
const activeTimeframe = ref('1d')
const adjust = ref('qfq')
const loading = ref(false)

// 数据源管理
const selectedProvider = ref('default')
const availableProviders = ref([])
const providersLoading = ref(false)
const currentDataSource = ref('')  // 当前使用的数据源

// 股票信息
const stockInfo = ref(null)
const snapshot = ref(null)
const stockList = ref([])

// 图表数据
const chartData = ref(null)
const chipData = ref(null)
const indicatorData = ref({})

// 买卖盘数据
const buyOrders = ref([])
const sellOrders = ref([])

// 交易明细
const tradeDetails = ref([])

// 资金流向
const capitalFlow = ref(null)

// 加载状态
const orderbookLoading = ref(true)
const stockInfoLoading = ref(true)
const chipStatsLoading = ref(true)

// 新闻列表
const newsList = ref([])

// 市场数据
const marketData = ref([])

// 面板显示控制
const showOrderPanel = ref(true)
const showChipChart = ref(true)
const showInfoPanel = ref(true)
const activeInfoTab = ref('detail')

// 指标值（用于显示在指标面板）
const indicatorValues = ref({})

// 指标管理
const showIndicatorManager = ref(false)
const mainIndicator = ref('BOLL')  // 默认主图指标
const selectedIndicators = ref([
  {name: 'BOLL', params: {period: 20, std_dev: 2}, pane: 'main'},
  {name: 'Volume', params: {}, pane: 'sub1'},
  {name: 'MACD', params: {}, pane: 'sub2'}
])

const availableIndicators = ref([
  {name: 'MA', label: '移动均线', pane: 'main'},
  {name: 'BOLL', label: '布林带', pane: 'main'},
  {name: 'EXPMA', label: 'EXPMA', pane: 'main'},
  {name: 'ENE', label: 'ENE', pane: 'main'},
  {name: 'MACD', label: 'MACD', pane: 'sub'},
  {name: 'RSI', label: 'RSI', pane: 'sub'},
  {name: 'KDJ', label: 'KDJ', pane: 'sub'},
  {name: 'VOL', label: '成交量', pane: 'sub'},
  {name: 'OBV', label: 'OBV', pane: 'sub'},
  {name: 'BRAR', label: 'BRAR', pane: 'sub'}
])

const activeIndicators = ref([
  {name: 'VOL', label: '成交量', pane: 'sub'},
  {name: 'MACD', label: 'MACD', pane: 'sub'},
])

// 模板管理
const currentTemplate = ref('default')
const templates = [
  {
    id: 'default', name: '默认', indicators: [
      {name: 'BOLL', params: {period: 20, std_dev: 2}, pane: 'main'},
      {name: 'Volume', params: {}, pane: 'sub1'}
    ]
  },
  {
    id: 'trend', name: '趋势', indicators: [
      {name: 'MA', params: {periods: [5, 10, 20, 60]}, pane: 'main'},
      {name: 'MACD', params: {}, pane: 'sub1'},
      {name: 'Volume', params: {}, pane: 'sub2'}
    ]
  },
  {
    id: 'oscillator', name: '震荡', indicators: [
      {name: 'BOLL', params: {period: 20, std_dev: 2}, pane: 'main'},
      {name: 'RSI', params: {period: 14}, pane: 'sub1'},
      {name: 'KDJ', params: {}, pane: 'sub2'}
    ]
  }
]

// 实时数据
const realtime = ref(false)
const signals = ref([])
let chartWs = null
let subscriptionId = null

// 图表实例
const mainChart = ref(null)
const chipChart = ref(null)
let mainChartInstance = null
let chipChartInstance = null
let indicatorChartInstances = []
let resizeObserver = null
let windowResizeHandler = null

// WebSocket连接
let ws = null
const connectionStatus = ref('未连接')
const lastUpdateTime = ref('')

// 初始化
onMounted(() => {
  loadProviders()
  loadStockList()
  loadData()
  initWebSocket()

  // 延迟初始化图表，确保DOM完全渲染
  setTimeout(() => {
    initCharts()
  }, 300)

  // 添加窗口resize监听
  windowResizeHandler = () => {
    if (mainChartInstance) mainChartInstance.resize()
    if (chipChartInstance) chipChartInstance.resize()
    indicatorChartInstances.forEach(chart => {
      if (chart) chart.resize()
    })
  }
  window.addEventListener('resize', windowResizeHandler)

  // 定时更新实时数据
  setInterval(() => {
    updateRealtime()
  }, 5000)
})

onUnmounted(() => {
  // 清理ResizeObserver
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }

  // 移除窗口resize监听
  if (windowResizeHandler) {
    window.removeEventListener('resize', windowResizeHandler)
  }

  // 关闭QMT WebSocket
  if (qmtWs) {
    qmtWs.disconnect()
    qmtWs = null
  }
  if (ws) {
    ws.close()
  }
  if (mainChartInstance) {
    mainChartInstance.dispose()
  }
  if (chipChartInstance) {
    chipChartInstance.dispose()
  }
  indicatorChartInstances.forEach(chart => {
    if (chart) chart.dispose()
  })
})

// 加载数据提供者列表
async function loadProviders() {
  providersLoading.value = true
  try {
    const response = await chartApi.getProviders()
    availableProviders.value = response.providers || []
    // 如果当前选中的provider不存在，选择第一个可用的
    if (!availableProviders.value.find(p => p.name === selectedProvider.value)) {
      selectedProvider.value = availableProviders.value[0]?.name || 'default'
    }
  } catch (error) {
    console.error('Failed to load providers:', error)
    // 默认提供者
    availableProviders.value = [{
      name: 'default',
      label: 'Cloudflare代理',
      type: 'proxy',
      enabled: true,
      status: 'running'
    }]
  } finally {
    providersLoading.value = false
  }
}

// 加载股票列表
async function loadStockList() {
  try {
    const response = await chartApi.getStockList()
    stockList.value = response
  } catch (error) {
    console.error('Failed to load stock list:', error)
  }
}

// 处理数据源切换
function handleProviderChange() {
  ElMessage.info(`切换到数据源: ${availableProviders.value.find(p => p.name === selectedProvider.value)?.label || selectedProvider.value}`)
  // 重新加载数据
  loadData()
}

// 拼音转换辅助函数
function getPinyin(str) {
  // 简化的拼音映射表
  const pinyinMap = {
    '平': 'ping', '安': 'an', '银': 'yin', '行': 'hang',
    '万': 'wan', '科': 'ke', '五': 'wu', '粮': 'liang', '液': 'ye',
    '贵': 'gui', '州': 'zhou', '茅': 'mao', '台': 'tai',
    '长': 'chang', '城': 'cheng', '军': 'jun', '工': 'gong',
    '中': 'zhong', '国': 'guo', '石': 'shi', '油': 'you', '化': 'hua',
    '招': 'zhao', '商': 'shang', '保': 'bao', '利': 'li',
    '发': 'fa', '展': 'zhan', '华': 'hua', '夏': 'xia',
    '建': 'jian', '设': 'she', '交': 'jiao', '通': 'tong',
    '工': 'gong', '商': 'shang', '农': 'nong', '业': 'ye',
    '海': 'hai', '康': 'kang', '威': 'wei', '视': 'shi',
    '宁': 'ning', '德': 'de', '时': 'shi', '代': 'dai',
    '比': 'bi', '亚': 'ya', '迪': 'di', '格': 'ge', '力': 'li',
    '电': 'dian', '器': 'qi', '美': 'mei', '的': 'de', '集': 'ji', '团': 'tuan'
  }
  return str.split('').map(char => pinyinMap[char] || char).join('')
}

// 获取拼音首字母
function getPinyinFirst(str) {
  const pinyin = getPinyin(str)
  return pinyin.split('').filter((char, index) => {
    // 简化实现：返回每个汉字拼音的首字母
    return index === 0 || /[a-z]/i.test(char)
  }).join('')
}

// 股票搜索
async function queryStock(queryString, cb) {
  if (!queryString) {
    cb(stockList.value.slice(0, 20))
    return
  }

  const query = queryString.toLowerCase()
  const results = stockList.value.filter(stock => {
    const pinyinStr = getPinyin(stock.name).toLowerCase()
    const pinyinFirst = getPinyinFirst(stock.name).toLowerCase()

    return stock.code.includes(query) ||
        stock.name.toLowerCase().includes(query) ||
        pinyinStr.includes(query) ||
        pinyinFirst.includes(query)
  })

  cb(results.slice(0, 20))
}

// 选择股票
function handleStockSelect(item) {
  symbol.value = item.code
  loadData()
}

// 加载数据
async function loadData() {
  if (!symbol.value) return

  loading.value = true
  // 初始设置所有加载状态
  orderbookLoading.value = true
  stockInfoLoading.value = true
  chipStatsLoading.value = true

  try {
    // QMT WebSocket订阅新股票
    if (qmtWs && qmtWs.ws && qmtWs.ws.readyState === WebSocket.OPEN) {
      // 取消订阅旧股票
      const oldSubscriptions = Array.from(qmtWs.subscriptions)
      if (oldSubscriptions.length > 0) {
        qmtWs.unsubscribe(oldSubscriptions)
      }
      // 订阅新股票
      qmtWs.subscribe([symbol.value])
    }

    // 加载股票信息
    const infoPromise = chartApi.getStockInfo(symbol.value)

    // 加载K线数据
    const seriesPromise = chartApi.getSeries({
      symbol: symbol.value,
      timeframe: activeTimeframe.value,
      adjust: adjust.value,
      limit: 1000,  // 增加到1000条，获取更多历史数据
      provider: selectedProvider.value
    })

    // 加载快照数据
    const snapshotPromise = chartApi.getSnapshot(symbol.value)

    // 加载筹码分布
    const chipPromise = chartApi.getChipDistribution(symbol.value)

    // 等待所有请求完成
    const [info, series, snap, chip] = await Promise.all([
      infoPromise.catch(e => null),
      seriesPromise,
      snapshotPromise.catch(e => null),
      chipPromise.catch(e => null)
    ])

    stockInfo.value = info
    stockInfoLoading.value = false  // 股票信息加载完成

    chartData.value = series
    snapshot.value = snap

    chipData.value = chip
    chipStatsLoading.value = false  // 筹码统计加载完成

    // 更新当前数据源信息
    if (series && series.source) {
      currentDataSource.value = series.source
    } else if (series && series.meta && series.meta.data_source) {
      currentDataSource.value = series.meta.data_source
    }

    // 加载指标数据
    if (selectedIndicators.value.length > 0) {
      await loadIndicators()
    }

    // 更新图表
    updateMainChart()
    updateChipChart()
    updateIndicatorCharts()

    lastUpdateTime.value = new Date().toLocaleTimeString()

  } catch (error) {
    console.error('数据加载失败:', error)

    // 更详细的错误处理
    if (error.response) {
      // 服务器返回错误
      const status = error.response.status
      if (status === 404) {
        ElMessage.error(`未找到股票 ${symbol.value} 的数据`)
      } else if (status === 503) {
        ElMessage.error('数据服务暂时不可用，请稍后重试')
      } else {
        ElMessage.error(`数据加载失败: ${error.response.data?.message || '未知错误'}`)
      }
    } else if (error.request) {
      // 请求未收到响应
      ElMessage.error('网络连接失败，请检查网络')
    } else {
      // 其他错误
      ElMessage.error(`数据加载失败: ${error.message}`)
    }

    // 清空数据避免显示错误信息
    if (error.response?.status === 404) {
      chartData.value = null
      snapshot.value = null
      chipData.value = null
    }
    // 如果数据加载失败，也要结束加载状态
    stockInfoLoading.value = false
    chipStatsLoading.value = false
  } finally {
    loading.value = false
  }
}

// 初始化图表
function initCharts() {
  // 初始化主图表
  if (mainChart.value && !mainChartInstance) {
    mainChartInstance = echarts.init(mainChart.value)

    // 使用ResizeObserver监听容器大小变化
    if (window.ResizeObserver && !resizeObserver) {
      resizeObserver = new ResizeObserver((entries) => {
        // 当容器大小改变时，调整所有图表
        if (mainChartInstance) mainChartInstance.resize()
        if (chipChartInstance) chipChartInstance.resize()
        indicatorChartInstances.forEach(chart => {
          if (chart) chart.resize()
        })
      })
      resizeObserver.observe(mainChart.value)
    }
  }

  // 初始化筹码图
  if (chipChart.value && !chipChartInstance) {
    chipChartInstance = echarts.init(chipChart.value)
  }

  // 确保图表在下一个tick后resize
  nextTick(() => {
    // 立即执行一次resize
    if (mainChartInstance) mainChartInstance.resize()
    if (chipChartInstance) chipChartInstance.resize()

    // 延迟再执行一次，确保完全渲染
    setTimeout(() => {
      if (mainChartInstance) mainChartInstance.resize()
      if (chipChartInstance) chipChartInstance.resize()

      // 初始化后更新图表数据
      if (chartData.value) {
        updateMainChart()
        updateChipChart()
      }
    }, 200)
  })
}

// 更新主图表
function updateMainChart() {
  if (!mainChartInstance || !chartData.value) return

  const data = chartData.value.bars || []

  // 处理时间轴数据，确保没有undefined
  const timeAxisData = data.map(item => {
    // 优先使用time字段，如果没有就使用date，ts等其他字段
    const timeValue = item.time || item.date || item.ts || item.datetime
    if (!timeValue) {
      return ''  // 如果都没有，返回空字符串
    }
    // 如果是日K线，只显示日期部分
    if (activeTimeframe.value === '1d' && timeValue.includes(' ')) {
      return timeValue.split(' ')[0]
    }
    return timeValue
  })

  const option = {
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      }
    },
    legend: {
      data: ['日K', 'MA5', 'MA10', 'MA20'],
      top: 10,
      left: 'center',
      textStyle: {
        color: '#c9d1d9'
      }
    },
    grid: {
      left: '10%',
      right: '10%',
      top: '15%',
      bottom: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: timeAxisData,
      scale: true,
      boundaryGap: false,
      axisLine: {
        onZero: false,
        lineStyle: {
          color: '#30363d'
        }
      },
      splitLine: {show: false},
      min: 'dataMin',
      max: 'dataMax',
      axisLabel: {
        color: '#8b949e'
      }
    },
    yAxis: {
      scale: true,
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(255,255,255,0.01)', 'rgba(255,255,255,0.02)']
        }
      },
      splitLine: {
        lineStyle: {
          color: '#30363d'
        }
      },
      axisLabel: {
        color: '#8b949e'
      }
    },
    dataZoom: [
      {
        type: 'inside',
        start: 90,  // 默认显示最近10%的数据（约2个月，总数据为2年）
        end: 100,
        zoomOnMouseWheel: true,  // 启用鼠标滑轮缩放
        moveOnMouseMove: true,   // 启用鼠标移动拖拽
        moveOnMouseWheel: 'shift', // 按住shift+滑轮移动时间轴
        zoomLock: false,         // 不锁定缩放
        throttle: 100,           // 节流，提高性能
        minSpan: 1,              // 最小显示1%的数据（约7天）
        maxSpan: 100,            // 最大显示100%的数据（全部2年）
        filterMode: 'filter'     // 缩放时过滤数据，提高性能
      },
      {
        show: true,
        type: 'slider',
        bottom: '2%',
        start: 90,  // 与inside保持一致，显示最近10%
        end: 100,
        handleSize: '80%',
        handleStyle: {
          color: '#30363d',
          shadowBlur: 3,
          shadowColor: 'rgba(0, 0, 0, 0.6)',
          shadowOffsetX: 2,
          shadowOffsetY: 2
        },
        textStyle: {
          color: '#8b949e'
        },
        borderColor: '#30363d',
        fillerColor: 'rgba(48, 54, 61, 0.25)',
        dataBackground: {
          lineStyle: {
            color: '#30363d'
          },
          areaStyle: {
            color: 'rgba(48, 54, 61, 0.2)'
          }
        }
      }
    ],
    series: [
      {
        name: '日K',
        type: 'candlestick',
        data: data.map(item => [
          item.open,
          item.close,
          item.low,
          item.high
        ]),
        itemStyle: {
          color: '#ef232a',
          color0: '#14b143',
          borderColor: '#ef232a',
          borderColor0: '#14b143'
        }
      },
      // MA5
      {
        name: 'MA5',
        type: 'line',
        data: calculateMA(data, 5),
        smooth: true,
        lineStyle: {
          opacity: 0.5
        }
      },
      // MA10
      {
        name: 'MA10',
        type: 'line',
        data: calculateMA(data, 10),
        smooth: true,
        lineStyle: {
          opacity: 0.5
        }
      },
      // MA20
      {
        name: 'MA20',
        type: 'line',
        data: calculateMA(data, 20),
        smooth: true,
        lineStyle: {
          opacity: 0.5
        }
      }
    ]
  }

  mainChartInstance.setOption(option)
  // 设置选项后立即调整大小
  nextTick(() => {
    if (mainChartInstance) mainChartInstance.resize()
  })
}

// 更新筹码图
function updateChipChart() {
  if (!chipChartInstance || !chipData.value) return

  // 处理不同格式的筹码数据
  let distributionData = []
  let priceData = []

  // 检查数据格式
  if (chipData.value.price_levels && chipData.value.distribution) {
    // 新格式：分离的price_levels和distribution数组
    const priceLevels = chipData.value.price_levels || []
    const distribution = chipData.value.distribution || []

    // 组合数据
    for (let i = 0; i < Math.min(priceLevels.length, distribution.length); i++) {
      if (priceLevels[i] != null && distribution[i] != null) {
        priceData.push(priceLevels[i].toFixed(2))
        distributionData.push(distribution[i])
      }
    }
  } else if (Array.isArray(chipData.value.distribution)) {
    // 旧格式：distribution是对象数组
    const distribution = chipData.value.distribution || []
    for (const item of distribution) {
      if (item && item.price != null) {
        priceData.push(item.price.toFixed(2))
        distributionData.push(item.volume || item.ratio || 0)
      }
    }
  }

  // 如果没有数据，显示空图表
  if (priceData.length === 0) {
    chipChartInstance.setOption({
      title: {
        text: '暂无筹码分布数据',
        left: 'center',
        top: 'center'
      },
      xAxis: {show: false},
      yAxis: {show: false},
      series: []
    })
    return
  }

  const option = {
    animation: false,
    tooltip: {
      trigger: 'axis',
      formatter: function (params) {
        const index = params[0].dataIndex
        const price = priceData[index]
        const volume = distributionData[index]
        return `价格: ${price}<br/>筹码: ${volume.toFixed(2)}%`
      }
    },
    grid: {
      left: '15%',
      right: '10%',
      top: '10%',
      bottom: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      position: 'top',
      name: '筹码分布 (%)',
      nameTextStyle: {
        color: '#c9d1d9'
      },
      axisLabel: {
        color: '#8b949e'
      }
    },
    yAxis: {
      type: 'category',
      data: priceData,
      inverse: true,
      name: '价格',
      nameTextStyle: {
        color: '#c9d1d9'
      },
      axisLabel: {
        color: '#8b949e'
      }
    },
    series: [
      {
        type: 'bar',
        data: distributionData,
        itemStyle: {
          color: function (params) {
            const priceValue = parseFloat(priceData[params.dataIndex])
            const currentPrice = chipData.value.current_price || snapshot.value?.price || 0
            return priceValue < currentPrice ? '#ef232a' : '#14b143'
          }
        }
      }
    ]
  }

  chipChartInstance.setOption(option)
  // 设置选项后立即调整大小
  nextTick(() => {
    if (chipChartInstance) chipChartInstance.resize()
  })
}

// 更新指标图表
function updateIndicatorCharts() {
  // 实现指标图表更新逻辑
}

// 获取买卖盘数据
async function loadOrderBook() {
  orderbookLoading.value = true
  try {
    // 从QMT API获取真实的买卖盘数据
    const response = await qmtApi.getOrderbook(symbol.value)

    if (response && response.data) {
      // 处理买盘数据
      if (response.data.bid_levels && Array.isArray(response.data.bid_levels)) {
        buyOrders.value = response.data.bid_levels.slice(0, 5).map((level, index) => ({
          price: level.price || 0,
          volume: level.volume || 0,
          level: index + 1
        }))
      } else {
        buyOrders.value = []
      }

      // 处理卖盘数据
      if (response.data.ask_levels && Array.isArray(response.data.ask_levels)) {
        sellOrders.value = response.data.ask_levels.slice(0, 5).map((level, index) => ({
          price: level.price || 0,
          volume: level.volume || 0,
          level: index + 1
        }))
      } else {
        sellOrders.value = []
      }
    } else {
      // 如果没有数据，清空盘口
      buyOrders.value = []
      sellOrders.value = []
    }
    orderbookLoading.value = false
  } catch (error) {
    console.error('Failed to load order book:', error)

    // 根据错误类型显示不同提示
    if (error.response?.status === 503) {
      console.warn('QMT服务未启动，盘口数据不可用')
    } else if (error.response?.status === 404) {
      console.warn(`未找到股票 ${symbol.value} 的盘口数据`)
    }

    // 失败时清空数据，但不显示错误消息，避免干扰用户
    buyOrders.value = []
    sellOrders.value = []
    orderbookLoading.value = false
  }
}

// 加载指标
async function loadIndicators() {
  try {
    const response = await calculateIndicators({
      symbol: symbol.value,
      timeframe: activeTimeframe.value,
      adjust: adjust.value,
      indicators: selectedIndicators.value
    })

    indicatorData.value = response
    updateIndicatorValues()
  } catch (error) {
    console.error('计算指标失败:', error)
    ElMessage.error('计算指标失败')
  }
}

// 更新指标值
function updateIndicatorValues() {
  if (!mainChartInstance || !chartData.value) return

  const dataIndex = chartData.value.bars ? chartData.value.bars.length - 1 : 0
  const values = {}

  Object.entries(indicatorData.value).forEach(([name, indicator]) => {
    Object.entries(indicator.series || {}).forEach(([key, data]) => {
      if (data && data[dataIndex] !== undefined) {
        values[key] = data[dataIndex]
      }
    })
  })

  indicatorValues.value = values
}

// 应用模板
function applyTemplate() {
  const template = templates.find(t => t.id === currentTemplate.value)
  if (template) {
    selectedIndicators.value = [...template.indicators]
    loadData()
  }
}

// 应用指标
function applyIndicators(indicators) {
  selectedIndicators.value = indicators
  loadIndicators()
  updateMainChart()
}

// 切换主图指标
function changeMainIndicator(indicator) {
  // 移除当前主图指标
  selectedIndicators.value = selectedIndicators.value.filter(ind => ind.pane !== 'main')

  // 添加新的主图指标
  if (indicator !== 'none') {
    let indicatorConfig = null
    switch (indicator) {
      case 'MA':
        indicatorConfig = {name: 'MA', params: {periods: [5, 10, 20, 60]}, pane: 'main'}
        break
      case 'EXPMA':
        indicatorConfig = {name: 'EXPMA', params: {periods: [12, 50]}, pane: 'main'}
        break
      case 'BOLL':
        indicatorConfig = {name: 'BOLL', params: {period: 20, std_dev: 2}, pane: 'main'}
        break
      case 'ENE':
        indicatorConfig = {name: 'ENE', params: {period: 10, k1: 11, k2: 9}, pane: 'main'}
        break
    }
    if (indicatorConfig) {
      selectedIndicators.value.unshift(indicatorConfig)
    }
  }
  mainIndicator.value = indicator
  loadData()
}

// 切换实时模式
async function toggleRealtime() {
  if (realtime.value) {
    // 开启实时模式
    if (!chartWs) {
      chartWs = new ChartWebSocket()
      await chartWs.connect()
    }

    subscriptionId = chartWs.subscribe(symbol.value, activeTimeframe.value, (data) => {
      handleWebSocketMessage(data)
    })
  } else {
    // 关闭实时模式
    if (chartWs && subscriptionId) {
      chartWs.unsubscribe(subscriptionId)
      subscriptionId = null
    }
  }
}

// 处理WebSocket消息
function handleWebSocketMessage(data) {
  if (data.type === 'bar_update' && chartData.value) {
    // 更新最新的K线
    const lastBar = chartData.value.bars[chartData.value.bars.length - 1]
    if (lastBar) {
      Object.assign(lastBar, data.data)
      updateMainChart()
    }
  }
}

// 更新实时数据
async function updateRealtime() {
  if (!symbol.value) return

  try {
    const snap = await chartApi.getSnapshot(symbol.value)
    snapshot.value = snap

    // 更新买卖盘
    await loadOrderBook()

    // 从QMT WebSocket获取实时交易明细
    try {
      // 如果已连接QMT WebSocket，请求交易明细
      if (qmtWs && qmtWs.isConnected()) {
        // 通过WebSocket请求最新交易明细
        qmtWs.requestTradeDetails(symbol.value)
      } else {
        // 如果WebSocket未连接，尝试从API获取
        try {
          const response = await qmtApi.getTradeDetails(symbol.value)
          if (response && response.data && response.data.length > 0) {
            tradeDetails.value = response.data.map(trade => ({
              time: formatTime(trade.timestamp),
              price: trade.price,
              volume: trade.volume,
              amount: (trade.price * trade.volume).toFixed(2),
              direction: trade.side === 'BUY' ? 'up' : 'down'
            })).slice(0, 20) // 只显示最近20条
          } else {
            // 静默处理空数据
            tradeDetails.value = []
          }
        } catch (apiError) {
          // 静默处理API错误，不打印到控制台
          if (apiError.response && apiError.response.status === 404) {
            // 404错误静默处理
            tradeDetails.value = []
          } else {
            // 其他错误可以打印但降低级别
            console.debug('Trade details API not available:', apiError.message)
            tradeDetails.value = []
          }
        }
      }
    } catch (error) {
      // 降低错误日志级别
      console.debug('Failed to get trade details:', error.message)
      tradeDetails.value = []
    }

    lastUpdateTime.value = new Date().toLocaleTimeString()
  } catch (error) {
    console.error('Failed to update realtime data:', error)
  }
}

// WebSocket连接
let qmtWs = null

async function initWebSocket() {
  try {
    // 初始化QMT WebSocket
    if (!qmtWs) {
      qmtWs = new QmtWebSocket()

      // 设置回调函数
      qmtWs.on('onConnected', () => {
        connectionStatus.value = 'QMT已连接'
        ElMessage.success('QMT实时数据连接成功')

        // 订阅当前股票
        if (symbol.value) {
          qmtWs.subscribe([symbol.value])
        }
      })

      qmtWs.on('onDisconnected', () => {
        connectionStatus.value = 'QMT断开'
        ElMessage.warning('QMT实时数据连接断开')
      })

      qmtWs.on('onTick', (tickData) => {
        // 处理实时Tick数据
        handleRealtimeTick(tickData)
      })

      qmtWs.on('onOrderbook', (orderbookData) => {
        // 处理实时盘口数据
        handleRealtimeOrderbook(orderbookData)
      })

      qmtWs.on('onTrade', (tradeData) => {
        // 处理实时成交数据
        handleRealtimeTrade(tradeData)
      })

      qmtWs.on('onError', (error) => {
        console.error('QMT WebSocket错误:', error)
        connectionStatus.value = 'QMT错误'
      })

      // 连接WebSocket
      qmtWs.connect()
    }
  } catch (error) {
    console.error('WebSocket连接失败:', error)
    connectionStatus.value = '连接失败'
  }
}

// 处理实时Tick数据
function handleRealtimeTick(tickData) {
  if (!tickData || tickData.symbol !== symbol.value) return

  // 更新快照数据
  snapshot.value = {
    ...snapshot.value,
    last: tickData.last_price,
    open: tickData.open_price,
    high: tickData.high_price,
    low: tickData.low_price,
    volume: tickData.volume,
    amount: tickData.amount,
    change: tickData.change,
    pct_change: tickData.pct_change
  }

  // 更新最后更新时间
  lastUpdateTime.value = new Date().toLocaleTimeString()
}

// 处理实时盘口数据
function handleRealtimeOrderbook(orderbookData) {
  if (!orderbookData || orderbookData.symbol !== symbol.value) return

  // 更新买盘
  buyOrders.value = orderbookData.bid_levels?.slice(0, 10).map((level, index) => ({
    price: level.price,
    volume: level.volume,
    level: index + 1
  })) || []

  // 更新卖盘
  sellOrders.value = orderbookData.ask_levels?.slice(0, 10).map((level, index) => ({
    price: level.price,
    volume: level.volume,
    level: index + 1
  })) || []
}

// 处理实时成交数据
function handleRealtimeTrade(tradeData) {
  if (!tradeData || tradeData.symbol !== symbol.value) return

  // 添加到成交明细（保留最新100条）
  tradeDetails.value.unshift({
    time: formatTime(tradeData.timestamp),
    price: tradeData.price,
    volume: tradeData.volume,
    amount: tradeData.amount || (tradeData.price * tradeData.volume).toFixed(2),
    direction: tradeData.side === 'BUY' ? 'up' : 'down'
  })

  if (tradeDetails.value.length > 100) {
    tradeDetails.value.pop()
  }
}

// 格式化时间戳
function formatTime(timestamp) {
  if (!timestamp) return '--:--:--'

  // 如果是数字，认为是Unix时间戳
  if (typeof timestamp === 'number') {
    const date = new Date(timestamp * 1000)
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  // 如果是字符串，尝试解析
  const date = new Date(timestamp)
  if (!isNaN(date.getTime())) {
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  return timestamp // 如果无法解析，返回原值
}

// 计算移动均线
function calculateMA(data, period) {
  const result = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null)
    } else {
      let sum = 0
      let validCount = 0
      for (let j = 0; j < period; j++) {
        const closeValue = data[i - j]?.close
        if (closeValue !== undefined && closeValue !== null && !isNaN(closeValue)) {
          sum += parseFloat(closeValue)
          validCount++
        }
      }
      // 只有当有足够的有效数据时才计算均值
      if (validCount > 0) {
        result.push((sum / validCount).toFixed(2))
      } else {
        result.push(null)
      }
    }
  }
  return result
}

// 周期切换
function handleTimeframeChange() {
  loadData()
}

// 切换指标
function toggleIndicator(indicator) {
  const index = activeIndicators.value.findIndex(i => i.name === indicator.name)
  if (index >= 0) {
    activeIndicators.value.splice(index, 1)
  } else {
    activeIndicators.value.push(indicator)
  }
  updateIndicatorCharts()
}

// 检查指标是否选中
function isIndicatorSelected(name) {
  return activeIndicators.value.some(i => i.name === name)
}

// 移除指标
function removeIndicator(index) {
  activeIndicators.value.splice(index, 1)
  updateIndicatorCharts()
}

// 设置画线工具
function setDrawingTool(tool) {
  ElMessage.info(`画线工具: ${tool}`)
}

// 清除画线
function clearDrawings() {
  ElMessage.success('已清除所有画线')
}

// 切换侧边面板
function toggleSidePanel(panel) {
  if (panel === 'order') {
    showOrderPanel.value = !showOrderPanel.value
  } else if (panel === 'position') {
    ElMessage.info('持仓功能开发中')
  } else if (panel === 'news') {
    showInfoPanel.value = true
    activeInfoTab.value = 'news'
  }
}

// 全屏切换
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
  } else {
    document.exitFullscreen()
  }
}

// 窗口大小变化处理
function handleResize() {
  if (mainChartInstance) {
    mainChartInstance.resize()
  }
  if (chipChartInstance) {
    chipChartInstance.resize()
  }
  indicatorChartInstances.forEach(chart => {
    if (chart) chart.resize()
  })
}

// 价格样式类
function getPriceClass(value) {
  if (value > 0) return 'price-up'
  if (value < 0) return 'price-down'
  return 'price-flat'
}

// 格式化指标值
function formatIndicatorValue(value) {
  if (value === null || value === undefined) return '-'

  if (typeof value === 'boolean') {
    return value ? '是' : '否'
  }

  if (typeof value === 'number') {
    if (Math.abs(value) >= 10000) {
      return formatLargeNumber(value)
    }
    return formatNumber(value)
  }

  if (Array.isArray(value)) {
    return value.map(v => formatIndicatorValue(v)).join(', ')
  }

  return String(value)
}

// 格式化大数字
function formatLargeNumber(num) {
  if (!num || num === 0) return '0'

  const abs = Math.abs(num)
  const sign = num < 0 ? '-' : ''

  if (abs >= 1000000000) {
    return sign + (abs / 1000000000).toFixed(2) + 'B'
  } else if (abs >= 1000000) {
    return sign + (abs / 1000000).toFixed(2) + 'M'
  } else if (abs >= 1000) {
    return sign + (abs / 1000).toFixed(2) + 'K'
  } else {
    return sign + abs.toString()
  }
}
</script>

<style lang="scss" scoped>
.professional-trading-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0a0e1a;
  color: #c9d1d9;
  font-size: 12px;

  // 顶部导航栏
  .top-navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 48px;
    padding: 0 20px;
    background: #161b22;
    border-bottom: 1px solid #30363d;

    .nav-left {
      display: flex;
      align-items: center;
      gap: 20px;

      .stock-info {
        display: flex;
        align-items: center;
        gap: 10px;

        .stock-title {
          display: flex;
          align-items: center;
          gap: 5px;

          .stock-name {
            font-size: 16px;
            font-weight: bold;
            color: #fff;
          }

          .stock-code {
            color: #8b949e;
          }
        }
      }

      .stock-tags {
        display: flex;
        gap: 5px;

        .tag {
          padding: 2px 6px;
          border-radius: 3px;
          font-size: 11px;

          &.margin {
            background: #1f6feb;
          }

          &.hgt {
            background: #8957e5;
          }

          &.sgt {
            background: #da3633;
          }

          &.star {
            background: #f85149;
          }

          &.gem {
            background: #3fb950;
          }
        }
      }
    }

    .nav-right {
      display: flex;
      align-items: center;
      gap: 20px;

      .price-info {
        display: flex;
        align-items: baseline;
        gap: 10px;

        .current-price {
          font-size: 24px;
          font-weight: bold;
        }

        .price-change {
          font-size: 14px;
        }
      }
    }
  }

  // 市场数据滚动条
  .market-ticker {
    height: 30px;
    background: #0d1117;
    border-bottom: 1px solid #30363d;
    overflow: hidden;

    .ticker-content {
      display: flex;
      align-items: center;
      height: 100%;
      animation: ticker 30s linear infinite;

      .ticker-item {
        display: flex;
        align-items: center;
        gap: 5px;
        margin-right: 30px;
        white-space: nowrap;

        .ticker-name {
          color: #8b949e;
        }

        .ticker-price {
          font-weight: bold;
        }

        .ticker-change {
          font-size: 11px;
        }
      }
    }
  }

  @keyframes ticker {
    0% {
      transform: translateX(0);
    }
    100% {
      transform: translateX(-50%);
    }
  }

  // 周期切换标签
  .period-tabs {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 20px;
    background: #0d1117;
    border-bottom: 1px solid #30363d;

    :deep(.el-tabs) {
      flex: 1;

      .el-tabs__header {
        margin: 0;
        border: none;
      }

      .el-tabs__nav {
        border: none;
      }

      .el-tabs__item {
        color: #8b949e;
        border: none;

        &.is-active {
          color: #58a6ff;
        }

        &:hover {
          color: #58a6ff;
        }
      }

      .el-tabs__active-bar {
        background: #58a6ff;
      }
    }
  }

  // 主体内容区
  .main-content {
    flex: 1;
    padding: 10px;
    overflow: hidden;

    .order-panel {
      height: 100%;
      min-height: 400px; // 设置最小高度防止布局跳动
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 6px;

      .order-book {
        padding: 10px;
        min-height: 380px; // 内容最小高度

        .order-header {
          text-align: center;
          padding: 5px;
          border-bottom: 1px solid #30363d;
          margin-bottom: 10px;
        }

        .order-item {
          display: grid;
          grid-template-columns: 1fr 2fr 2fr;
          gap: 5px;
          padding: 3px 0;

          &.sell {
            .order-price {
              color: #3fb950;
            }
          }

          &.buy {
            .order-price {
              color: #f85149;
            }
          }

          .order-volume {
            text-align: right;
            color: #8b949e;
          }
        }

        .current-price-divider {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 0;
          margin: 10px 0;
          border-top: 1px solid #30363d;
          border-bottom: 1px solid #30363d;

          .price {
            font-size: 16px;
            font-weight: bold;
          }

          .change {
            font-size: 12px;
          }
        }
      }

      .stock-basic-info {
        padding: 10px;

        .info-header {
          text-align: center;
          font-weight: bold;
          padding: 8px;
          background: #21262d;
          margin-bottom: 10px;
          border-radius: 4px;
        }

        .info-content {
          .info-item {
            display: flex;
            justify-content: space-between;
            padding: 6px 8px;
            margin-bottom: 4px;
            background: #0d1117;
            border-radius: 4px;
            font-size: 12px;

            &:hover {
              background: #161b22;
            }

            .info-label {
              color: #8b949e;
            }

            .info-value {
              color: #f0f6fc;
              font-weight: 500;
            }
          }
        }
      }
    }

    .chart-area {
      height: 100%;

      .main-chart {
        height: 60%;
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
      }

      .indicator-charts {
        height: 38%;
        margin-top: 10px;
        display: flex;
        flex-direction: column;
        gap: 10px;

        .indicator-chart {
          flex: 1;
          background: #161b22;
          border: 1px solid #30363d;
          border-radius: 6px;

          .indicator-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 5px 10px;
            border-bottom: 1px solid #30363d;

            .close-btn {
              cursor: pointer;

              &:hover {
                color: #f85149;
              }
            }
          }

          .indicator-chart-container {
            height: calc(100% - 30px);
          }
        }
      }
    }

    .chip-panel {
      height: 100%;
      min-height: 400px; // 设置最小高度防止布局跳动
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 6px;

      .chip-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px;
        border-bottom: 1px solid #30363d;

        .close-btn {
          cursor: pointer;

          &:hover {
            color: #f85149;
          }
        }
      }

      .chip-chart {
        height: 60%;
      }

      .chip-stats {
        padding: 10px;
        min-height: 350px; // 内容最小高度

        .stat-item {
          display: flex;
          justify-content: space-between;
          padding: 5px 0;

          .label {
            color: #8b949e;
          }

          .value {
            font-weight: bold;
          }
        }
      }
    }

    .info-panel {
      height: 100%;
      min-height: 400px; // 设置最小高度防止布局跳动
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 6px;

      :deep(.el-tabs) {
        height: 100%;

        .el-tabs__content {
          height: calc(100% - 40px);
          overflow-y: auto;
        }
      }

      .trade-detail {
        padding: 10px;

        .trade-item {
          display: grid;
          grid-template-columns: 2fr 2fr 2fr 1fr;
          gap: 5px;
          padding: 3px 0;

          .time {
            color: #8b949e;
            font-size: 11px;
          }

          .direction {
            text-align: center;
            font-weight: bold;

            &.buy {
              color: #f85149;
            }

            &.sell {
              color: #3fb950;
            }
          }
        }
      }

      .capital-flow {
        padding: 10px;

        .flow-item {
          display: flex;
          justify-content: space-between;
          padding: 8px 0;
          border-bottom: 1px solid #30363d;

          .label {
            color: #8b949e;
          }

          .value {
            font-weight: bold;
          }
        }
      }

      .news-list {
        padding: 10px;

        .news-item {
          padding: 8px 0;
          border-bottom: 1px solid #30363d;
          cursor: pointer;

          &:hover {
            .news-title {
              color: #58a6ff;
            }
          }

          .news-title {
            margin-bottom: 5px;
          }

          .news-time {
            color: #8b949e;
            font-size: 11px;
          }
        }
      }

      .indicator-values {
        padding: 10px;

        .indicator-item {
          display: flex;
          justify-content: space-between;
          padding: 5px 0;
          border-bottom: 1px solid #30363d;

          .label {
            color: #8b949e;
            font-size: 11px;
          }

          .value {
            font-weight: bold;
            font-size: 12px;
          }
        }
      }

      .signals-list {
        padding: 10px;

        .signal-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 0;
          border-bottom: 1px solid #30363d;

          .time {
            color: #8b949e;
            font-size: 11px;
          }
        }
      }

      .no-data {
        text-align: center;
        color: #8b949e;
        padding: 20px;
        font-size: 12px;
      }
    }
  }

  // 底部功能栏
  .bottom-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 40px;
    padding: 0 20px;
    background: #161b22;
    border-top: 1px solid #30363d;

    .toolbar-left,
    .toolbar-center,
    .toolbar-right {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .status-item {
      display: flex;
      align-items: center;
      gap: 5px;
      color: #8b949e;
    }
  }

  // 价格颜色
  .price-up {
    color: #f85149;
  }

  .price-down {
    color: #3fb950;
  }

  .price-flat {
    color: #8b949e;
  }
}

// 暗色主题适配
:deep(.el-button) {
  background: #21262d;
  border-color: #30363d;
  color: #c9d1d9;

  &:hover {
    background: #30363d;
    border-color: #8b949e;
  }

  &.el-button--primary {
    background: #238636;
    border-color: #238636;

    &:hover {
      background: #2ea043;
    }
  }
}

:deep(.el-input__inner),
:deep(.el-input-number__decrease),
:deep(.el-input-number__increase) {
  background: #0d1117;
  border-color: #30363d;
  color: #c9d1d9;
}

:deep(.el-select-dropdown),
:deep(.el-dropdown-menu) {
  background: #161b22;
  border-color: #30363d;

  .el-select-dropdown__item,
  .el-dropdown-menu__item {
    color: #c9d1d9;

    &:hover {
      background: #21262d;
    }
  }

  // 骨架屏样式 - 适配暗色主题
  :deep(.el-skeleton) {
    .el-skeleton__item {
      background: linear-gradient(90deg, #1c2128 25%, #2a3139 37%, #1c2128 63%);
      background-size: 400% 100%;
      animation: el-skeleton-loading 1.4s ease infinite;
    }

    // 文本骨架
    .el-skeleton__text {
      background: linear-gradient(90deg, #1c2128 25%, #2a3139 37%, #1c2128 63%);
      background-size: 400% 100%;
      animation: el-skeleton-loading 1.4s ease infinite;
    }

    // 段落骨架
    .el-skeleton__paragraph {
      .el-skeleton__item {
        background: linear-gradient(90deg, #1c2128 25%, #2a3139 37%, #1c2128 63%);
        background-size: 400% 100%;
        animation: el-skeleton-loading 1.4s ease infinite;
      }
    }
  }

  // 确保骨架屏动画
  @keyframes el-skeleton-loading {
    0% {
      background-position: 100% 50%;
    }
    100% {
      background-position: 0 50%;
    }
  }
}
</style>