<template>
  <div class="data-management">
    <el-page-header :icon="null" @back="() => $router.back()">
      <template #content>
        <div class="page-header">
          <el-icon>
            <DataAnalysis/>
          </el-icon>
          <span class="title">数据管理</span>
        </div>
      </template>
    </el-page-header>

    <!-- 数据统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card class="stats-card">
          <el-statistic :value="stats.totalSymbols" title="股票数量">
            <template #prefix>
              <el-icon>
                <Coin/>
              </el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stats-card">
          <el-statistic :value="stats.totalRecords" title="数据记录数">
            <template #prefix>
              <el-icon>
                <DataBoard/>
              </el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stats-card">
          <div class="custom-stat">
            <div class="stat-title">
              <el-icon>
                <Calendar/>
              </el-icon>
              <span>数据时间范围</span>
            </div>
            <div class="stat-value">{{ stats.dateRange }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stats-card">
          <div class="custom-stat">
            <div class="stat-title">
              <el-icon>
                <Clock/>
              </el-icon>
              <span>最后更新</span>
            </div>
            <div class="stat-value">{{ stats.lastUpdate }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 功能标签页 -->
    <el-tabs v-model="activeTab" class="main-tabs">
      <!-- 数据查询 -->
      <el-tab-pane label="数据查询" name="query">
        <div class="query-panel">
          <el-form :model="queryForm" inline>
            <el-form-item label="股票代码">
              <el-select
                  v-model="queryForm.symbols"
                  allow-create
                  filterable
                  multiple
                  placeholder="请选择或输入股票代码"
                  style="width: 200px"
              >
                <el-option
                    v-for="symbol in symbolList"
                    :key="symbol"
                    :label="symbol"
                    :value="symbol"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="数据类型">
              <el-select v-model="queryForm.dataType" placeholder="选择数据类型">
                <el-option label="日线数据" value="daily"/>
                <el-option label="分钟数据" value="1min"/>
                <el-option label="Tick数据" value="tick"/>
              </el-select>
            </el-form-item>
            <el-form-item label="日期范围">
              <el-date-picker
                  v-model="queryForm.dateRange"
                  end-placeholder="结束日期"
                  range-separator="至"
                  start-placeholder="开始日期"
                  type="daterange"
                  value-format="YYYY-MM-DD"
              />
            </el-form-item>
            <el-form-item>
              <el-button :loading="loading.query" type="primary" @click="handleQuery">
                <el-icon>
                  <Search/>
                </el-icon>
                查询数据
              </el-button>
              <el-button :disabled="!queryResult.data.length" @click="handleExport">
                <el-icon>
                  <Download/>
                </el-icon>
                导出数据
              </el-button>
            </el-form-item>
          </el-form>

          <!-- 查询结果表格 -->
          <el-table
              v-if="queryResult.data.length"
              :data="queryResult.data"
              max-height="400"
              style="width: 100%; margin-top: 20px"
          >
            <el-table-column label="日期" prop="date" width="120"/>
            <el-table-column label="代码" prop="symbol" width="100"/>
            <el-table-column label="开盘价" prop="open" width="100"/>
            <el-table-column label="最高价" prop="high" width="100"/>
            <el-table-column label="最低价" prop="low" width="100"/>
            <el-table-column label="收盘价" prop="close" width="100"/>
            <el-table-column label="成交量" prop="volume"/>
            <el-table-column label="成交额" prop="turnover"/>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 数据导入 -->
      <el-tab-pane label="数据导入" name="import">
        <div class="import-panel">
          <el-form :model="importForm" label-width="100px">
            <el-form-item label="数据类型">
              <el-radio-group v-model="importForm.dataType">
                <el-radio value="daily">日线数据</el-radio>
                <el-radio value="1min">分钟数据</el-radio>
                <el-radio value="tick">Tick数据</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="数据清洗">
              <el-switch v-model="importForm.cleanData" active-text="启用" inactive-text="禁用"/>
            </el-form-item>
            <el-form-item label="CSV文件">
              <el-upload
                  ref="uploadRef"
                  :auto-upload="false"
                  :limit="1"
                  :on-change="handleFileChange"
                  accept=".csv"
                  drag
              >
                <el-icon class="el-icon--upload">
                  <UploadFilled/>
                </el-icon>
                <div class="el-upload__text">
                  将文件拖到此处，或<em>点击上传</em>
                </div>
                <template #tip>
                  <div class="el-upload__tip">只能上传 CSV 文件</div>
                </template>
              </el-upload>
            </el-form-item>
            <el-form-item>
              <el-button
                  :disabled="!importForm.file"
                  :loading="loading.import"
                  type="primary"
                  @click="handleImport"
              >
                <el-icon>
                  <Upload/>
                </el-icon>
                开始导入
              </el-button>
            </el-form-item>
          </el-form>

          <!-- 导入结果 -->
          <el-alert
              v-if="importResult.show"
              :description="importResult.description"
              :title="importResult.title"
              :type="importResult.type"
              closable
              show-icon
              @close="importResult.show = false"
          />
        </div>
      </el-tab-pane>

      <!-- 技术指标 -->
      <el-tab-pane label="技术指标" name="indicators">
        <div class="indicators-panel">
          <el-form :model="indicatorForm" inline>
            <el-form-item label="股票代码">
              <el-select
                  v-model="indicatorForm.symbol"
                  filterable
                  placeholder="请选择股票代码"
                  style="width: 150px"
              >
                <el-option
                    v-for="symbol in symbolList"
                    :key="symbol"
                    :label="symbol"
                    :value="symbol"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="日期范围">
              <el-date-picker
                  v-model="indicatorForm.dateRange"
                  end-placeholder="结束日期"
                  range-separator="至"
                  start-placeholder="开始日期"
                  type="daterange"
                  value-format="YYYY-MM-DD"
              />
            </el-form-item>
            <el-form-item label="技术指标">
              <el-checkbox-group v-model="indicatorForm.indicators">
                <el-checkbox value="SMA">简单移动平均</el-checkbox>
                <el-checkbox value="EMA">指数移动平均</el-checkbox>
                <el-checkbox value="RSI">相对强弱指标</el-checkbox>
                <el-checkbox value="MACD">MACD</el-checkbox>
                <el-checkbox value="BBANDS">布林带</el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            <el-form-item>
              <el-button :loading="loading.indicators" type="primary" @click="handleCalculateIndicators">
                <el-icon>
                  <TrendCharts/>
                </el-icon>
                计算指标
              </el-button>
            </el-form-item>
          </el-form>

          <!-- 指标结果图表 -->
          <div v-if="indicatorResult.data.length" class="chart-container">
            <div ref="chartRef" style="width: 100%; height: 400px;"></div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import {nextTick, onMounted, reactive, ref} from 'vue'
import {ElMessage} from 'element-plus'
import * as echarts from 'echarts'
import {
  calculateIndicators,
  exportData,
  getDataStatistics,
  getSymbolList,
  importCsvData,
  queryMarketData
} from '@/api/data'

// 定义组件名称
defineOptions({
  name: 'DataManagement'
})

// 组件数据
const activeTab = ref('query')
const chartRef = ref(null)
const uploadRef = ref(null)
const chart = ref(null)

// 统计数据
const stats = reactive({
  totalSymbols: 0,
  totalRecords: 0,
  dateRange: '-',
  lastUpdate: '-'
})

// 股票代码列表
const symbolList = ref([])

// 加载状态
const loading = reactive({
  query: false,
  import: false,
  indicators: false
})

// 查询表单
const queryForm = reactive({
  symbols: [],
  dataType: 'daily',
  dateRange: []
})

// 查询结果
const queryResult = reactive({
  count: 0,
  data: []
})

// 导入表单
const importForm = reactive({
  dataType: 'daily',
  cleanData: true,
  file: null
})

// 导入结果
const importResult = reactive({
  show: false,
  type: 'success',
  title: '',
  description: ''
})

// 技术指标表单
const indicatorForm = reactive({
  symbol: '',
  dateRange: [],
  indicators: ['SMA', 'EMA', 'RSI']
})

// 指标结果
const indicatorResult = reactive({
  data: []
})

// 加载数据统计
const loadStatistics = async () => {
  try {
    const res = await getDataStatistics()
    if (res.data) {
      stats.totalSymbols = res.data.total_symbols || 0
      stats.totalRecords = res.data.total_records || 0

      if (res.data.date_range) {
        const {start, end} = res.data.date_range
        stats.dateRange = start && end ? `${start} ~ ${end}` : '-'
      }

      if (res.data.last_update) {
        stats.lastUpdate = new Date(res.data.last_update).toLocaleString()
      }
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

// 加载股票代码列表
const loadSymbolList = async () => {
  try {
    const res = await getSymbolList()
    if (res.data && res.data.symbols) {
      symbolList.value = res.data.symbols
    }
  } catch (error) {
    console.error('加载股票列表失败:', error)
  }
}

// 处理查询
const handleQuery = async () => {
  if (!queryForm.symbols.length) {
    ElMessage.warning('请选择股票代码')
    return
  }

  if (!queryForm.dateRange || queryForm.dateRange.length !== 2) {
    ElMessage.warning('请选择日期范围')
    return
  }

  loading.query = true
  try {
    const res = await queryMarketData({
      symbols: queryForm.symbols,
      start_date: queryForm.dateRange[0],
      end_date: queryForm.dateRange[1],
      data_type: queryForm.dataType
    })

    if (res.data) {
      queryResult.count = res.data.count || 0
      queryResult.data = res.data.data || []
      ElMessage.success(`查询成功，共 ${queryResult.count} 条数据`)
    }
  } catch (error) {
    ElMessage.error('查询失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.query = false
  }
}

// 处理导出
const handleExport = async () => {
  try {
    const res = await exportData(queryForm.dataType, {
      symbols: queryForm.symbols,
      start_date: queryForm.dateRange[0],
      end_date: queryForm.dateRange[1],
      format: 'csv'
    })

    // 创建下载链接
    const blob = new Blob([res.data], {type: 'text/csv'})
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `market_data_${new Date().toISOString().split('T')[0]}.csv`
    link.click()
    window.URL.revokeObjectURL(url)

    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败: ' + (error.response?.data?.detail || error.message))
  }
}

// 处理文件变化
const handleFileChange = (file) => {
  importForm.file = file.raw
}

// 处理导入
const handleImport = async () => {
  if (!importForm.file) {
    ElMessage.warning('请选择要导入的文件')
    return
  }

  loading.import = true
  try {
    const res = await importCsvData(
        importForm.file,
        importForm.dataType,
        importForm.cleanData
    )

    if (res.data) {
      importResult.show = true
      importResult.type = 'success'
      importResult.title = '导入成功'
      importResult.description = res.data.message || `成功导入 ${res.data.count} 条数据`

      // 清空文件
      uploadRef.value?.clearFiles()
      importForm.file = null

      // 刷新统计数据
      await loadStatistics()
      await loadSymbolList()
    }
  } catch (error) {
    importResult.show = true
    importResult.type = 'error'
    importResult.title = '导入失败'
    importResult.description = error.response?.data?.detail || error.message
  } finally {
    loading.import = false
  }
}

// 处理技术指标计算
const handleCalculateIndicators = async () => {
  if (!indicatorForm.symbol) {
    ElMessage.warning('请选择股票代码')
    return
  }

  if (!indicatorForm.dateRange || indicatorForm.dateRange.length !== 2) {
    ElMessage.warning('请选择日期范围')
    return
  }

  if (!indicatorForm.indicators.length) {
    ElMessage.warning('请选择技术指标')
    return
  }

  loading.indicators = true
  try {
    const res = await calculateIndicators({
      symbol: indicatorForm.symbol,
      start_date: indicatorForm.dateRange[0],
      end_date: indicatorForm.dateRange[1],
      indicators: indicatorForm.indicators
    })

    if (res.data) {
      indicatorResult.data = res.data.data || []
      ElMessage.success('指标计算成功')

      // 绘制图表
      await nextTick()
      drawIndicatorChart()
    }
  } catch (error) {
    ElMessage.error('计算失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.indicators = false
  }
}

// 绘制指标图表
const drawIndicatorChart = () => {
  if (!chartRef.value || !indicatorResult.data.length) return

  if (!chart.value) {
    chart.value = echarts.init(chartRef.value)
  }

  const dates = indicatorResult.data.map(item => item.date)
  const prices = indicatorResult.data.map(item => item.close)

  const series = [
    {
      name: '收盘价',
      type: 'line',
      data: prices,
      yAxisIndex: 0
    }
  ]

  // 添加指标系列
  if (indicatorForm.indicators.includes('SMA')) {
    series.push({
      name: 'SMA',
      type: 'line',
      data: indicatorResult.data.map(item => item.SMA),
      yAxisIndex: 0
    })
  }

  if (indicatorForm.indicators.includes('EMA')) {
    series.push({
      name: 'EMA',
      type: 'line',
      data: indicatorResult.data.map(item => item.EMA),
      yAxisIndex: 0
    })
  }

  if (indicatorForm.indicators.includes('RSI')) {
    series.push({
      name: 'RSI',
      type: 'line',
      data: indicatorResult.data.map(item => item.RSI),
      yAxisIndex: 1
    })
  }

  const option = {
    title: {
      text: `${indicatorForm.symbol} 技术指标图`,
      left: 'center'
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      }
    },
    legend: {
      data: series.map(s => s.name),
      top: 30
    },
    grid: [
      {
        left: '10%',
        right: '10%',
        height: '50%'
      },
      {
        left: '10%',
        right: '10%',
        top: '70%',
        height: '20%'
      }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        gridIndex: 0
      },
      {
        type: 'category',
        data: dates,
        gridIndex: 1
      }
    ],
    yAxis: [
      {
        type: 'value',
        name: '价格',
        gridIndex: 0
      },
      {
        type: 'value',
        name: 'RSI',
        min: 0,
        max: 100,
        gridIndex: 1
      }
    ],
    series
  }

  chart.value.setOption(option)
}

// 组件挂载
onMounted(() => {
  loadStatistics()
  loadSymbolList()

  // 监听窗口大小变化
  window.addEventListener('resize', () => {
    if (chart.value) {
      chart.value.resize()
    }
  })
})
</script>

<style lang="scss" scoped>
.data-management {
  padding: 20px;

  .page-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 20px;
    font-weight: 500;

    .el-icon {
      font-size: 24px;
    }
  }

  .stats-row {
    margin: 20px 0;

    .stats-card {
      transition: all 0.3s ease;

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
      }

      :deep(.el-statistic__head) {
        color: var(--el-text-color-secondary);
      }

      :deep(.el-statistic__content) {
        display: flex;
        align-items: center;
        gap: 8px;

        .el-icon {
          font-size: 20px;
          color: var(--el-color-primary);
        }
      }

      .custom-stat {
        .stat-title {
          display: flex;
          align-items: center;
          gap: 8px;
          color: var(--el-text-color-secondary);
          font-size: 14px;
          margin-bottom: 8px;

          .el-icon {
            font-size: 20px;
            color: var(--el-color-primary);
          }
        }

        .stat-value {
          font-size: 20px;
          font-weight: 500;
          color: var(--el-text-color-primary);
        }
      }
    }
  }

  .main-tabs {
    background: var(--el-bg-color);
    padding: 20px;
    border-radius: 4px;

    .query-panel,
    .import-panel,
    .indicators-panel {
      padding: 20px 0;
    }

    .el-table {
      font-size: 13px;
    }

    .chart-container {
      margin-top: 20px;
      background: var(--el-fill-color-light);
      border-radius: 4px;
      padding: 10px;
    }
  }
}
</style>