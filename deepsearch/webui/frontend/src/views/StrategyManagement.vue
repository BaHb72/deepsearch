<template>
  <div class="strategy-management">
    <el-card class="header-card">
      <div class="header">
        <h2>策略管理</h2>
        <div class="header-actions">
          <el-button type="primary" @click="showAddDialog = true">
            <el-icon>
              <Plus/>
            </el-icon>
            添加策略
          </el-button>
          <el-button @click="refreshStrategies">
            <el-icon>
              <Refresh/>
            </el-icon>
            刷新
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 策略列表 -->
    <el-card class="strategy-list-card">
      <el-table v-loading="loading" :data="strategies" style="width: 100%">
        <el-table-column label="策略ID" prop="id" width="200"/>
        <el-table-column label="策略类型" prop="class" width="150"/>
        <el-table-column label="状态" prop="status" width="100">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">
              {{ scope.row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="性能指标">
          <template #default="scope">
            <div v-if="scope.row.metrics">
              <span>总交易: {{ scope.row.metrics.total_trades || 0 }}</span> |
              <span>胜率: {{ (scope.row.metrics.win_rate * 100).toFixed(1) }}%</span> |
              <span>PnL: {{ scope.row.metrics.total_pnl?.toFixed(2) || 0 }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" prop="created_at" width="180">
          <template #default="scope">
            {{ formatTime(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column fixed="right" label="操作" width="250">
          <template #default="scope">
            <el-button-group>
              <el-button
                  v-if="scope.row.status === 'STOPPED'"
                  size="small"
                  type="success"
                  @click="startStrategy(scope.row.id)">
                启动
              </el-button>
              <el-button
                  v-if="scope.row.status === 'RUNNING'"
                  size="small"
                  type="warning"
                  @click="pauseStrategy(scope.row.id)">
                暂停
              </el-button>
              <el-button
                  v-if="scope.row.status === 'PAUSED'"
                  size="small"
                  type="success"
                  @click="resumeStrategy(scope.row.id)">
                恢复
              </el-button>
              <el-button
                  v-if="scope.row.status === 'RUNNING' || scope.row.status === 'PAUSED'"
                  size="small"
                  type="danger"
                  @click="stopStrategy(scope.row.id)">
                停止
              </el-button>
              <el-button
                  size="small"
                  @click="showMetrics(scope.row)">
                详情
              </el-button>
              <el-button
                  size="small"
                  type="danger"
                  @click="removeStrategy(scope.row.id)">
                删除
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 回测区域 -->
    <el-card class="backtest-card">
      <template #header>
        <div class="card-header">
          <span>策略回测</span>
          <el-button size="small" type="primary" @click="showBacktestDialog = true">
            运行回测
          </el-button>
        </div>
      </template>

      <div v-if="backtestResult" class="backtest-result">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-descriptions :column="2" title="回测结果">
              <el-descriptions-item label="策略">{{ backtestResult.strategy_name }}</el-descriptions-item>
              <el-descriptions-item label="时间范围">
                {{ backtestResult.start_date }} 至 {{ backtestResult.end_date }}
              </el-descriptions-item>
              <el-descriptions-item label="初始资金">{{ backtestResult.initial_capital }}</el-descriptions-item>
              <el-descriptions-item label="最终价值">{{ backtestResult.final_value?.toFixed(2) }}</el-descriptions-item>
              <el-descriptions-item label="总收益率">
                <span :class="backtestResult.total_return > 0 ? 'profit' : 'loss'">
                  {{ (backtestResult.total_return * 100).toFixed(2) }}%
                </span>
              </el-descriptions-item>
              <el-descriptions-item label="年化收益">{{
                  (backtestResult.annual_return * 100).toFixed(2)
                }}%
              </el-descriptions-item>
              <el-descriptions-item label="夏普比率">{{
                  backtestResult.sharpe_ratio?.toFixed(2)
                }}
              </el-descriptions-item>
              <el-descriptions-item label="最大回撤">{{
                  (backtestResult.max_drawdown * 100).toFixed(2)
                }}%
              </el-descriptions-item>
              <el-descriptions-item label="总交易数">{{ backtestResult.total_trades }}</el-descriptions-item>
              <el-descriptions-item label="胜率">{{
                  (backtestResult.win_rate * 100).toFixed(1)
                }}%
              </el-descriptions-item>
            </el-descriptions>
          </el-col>
          <el-col :span="12">
            <div v-if="backtestResult.plot_base64" class="backtest-chart">
              <img :src="backtestResult.plot_base64" alt="Backtest Chart" style="width: 100%;"/>
            </div>
          </el-col>
        </el-row>
      </div>
      <el-empty v-else description="暂无回测结果"/>
    </el-card>

    <!-- 添加策略对话框 -->
    <el-dialog v-model="showAddDialog" title="添加策略" width="500px">
      <el-form :model="newStrategy" label-width="100px">
        <el-form-item label="策略类型">
          <el-select v-model="newStrategy.strategy_type" placeholder="选择策略类型">
            <el-option label="移动平均" value="MA"/>
            <el-option label="均值回归" value="MeanReversion"/>
            <el-option label="动量策略" value="Momentum"/>
          </el-select>
        </el-form-item>

        <!-- 动态参数表单 -->
        <div v-if="newStrategy.strategy_type">
          <h4>策略参数</h4>
          <el-form-item
              v-for="(param, key) in getStrategyParams(newStrategy.strategy_type)"
              :key="key"
              :label="param.description">
            <el-input-number
                v-model="newStrategy.params[key]"
                :placeholder="String(param.default)"
                :step="param.type === 'float' ? 0.01 : 1"
                style="width: 100%"/>
          </el-form-item>
        </div>

        <el-form-item label="自动启动">
          <el-switch v-model="newStrategy.auto_start"/>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="addStrategy">确定</el-button>
      </template>
    </el-dialog>

    <!-- 回测对话框 -->
    <el-dialog v-model="showBacktestDialog" title="运行回测" width="600px">
      <el-form :model="backtestParams" label-width="120px">
        <el-form-item label="策略类型">
          <el-select v-model="backtestParams.strategy_type" placeholder="选择策略">
            <el-option label="移动平均" value="MA"/>
            <el-option label="均值回归" value="MeanReversion"/>
            <el-option label="动量策略" value="Momentum"/>
          </el-select>
        </el-form-item>

        <el-form-item label="股票代码">
          <el-select v-model="backtestParams.symbols" multiple placeholder="选择股票">
            <el-option label="平安银行" value="000001"/>
            <el-option label="浦发银行" value="600000"/>
            <el-option label="万科A" value="000002"/>
            <el-option label="贵州茅台" value="600519"/>
          </el-select>
        </el-form-item>

        <el-form-item label="时间范围">
          <el-date-picker
              v-model="backtestParams.dateRange"
              end-placeholder="结束日期"
              format="YYYY-MM-DD"
              range-separator="至"
              start-placeholder="开始日期"
              type="daterange"
              value-format="YYYY-MM-DD"
          />
        </el-form-item>

        <el-form-item label="初始资金">
          <el-input-number v-model="backtestParams.initial_capital" :min="10000" :step="10000"/>
        </el-form-item>

        <el-form-item label="手续费率">
          <el-input-number v-model="backtestParams.commission" :max="0.01" :min="0" :step="0.0001"/>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBacktestDialog = false">取消</el-button>
        <el-button :loading="backtestLoading" type="primary" @click="runBacktest">
          运行回测
        </el-button>
      </template>
    </el-dialog>

    <!-- 策略详情对话框 -->
    <el-dialog v-model="showMetricsDialog" title="策略详情" width="600px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="策略ID">{{ currentStrategy?.id }}</el-descriptions-item>
        <el-descriptions-item label="策略类型">{{ currentStrategy?.class }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentStrategy?.status)">
            {{ currentStrategy?.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(currentStrategy?.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="启动时间">{{ formatTime(currentStrategy?.started_at) }}</el-descriptions-item>
        <el-descriptions-item label="总交易数">{{ currentStrategy?.metrics?.total_trades || 0 }}</el-descriptions-item>
        <el-descriptions-item label="胜率">
          {{ ((currentStrategy?.metrics?.win_rate || 0) * 100).toFixed(1) }}%
        </el-descriptions-item>
        <el-descriptions-item label="总PnL">{{
            currentStrategy?.metrics?.total_pnl?.toFixed(2) || 0
          }}
        </el-descriptions-item>
        <el-descriptions-item label="最大回撤">
          {{ ((currentStrategy?.metrics?.max_drawdown || 0) * 100).toFixed(2) }}%
        </el-descriptions-item>
        <el-descriptions-item label="夏普比率">{{
            currentStrategy?.metrics?.sharpe_ratio?.toFixed(2) || 0
          }}
        </el-descriptions-item>
      </el-descriptions>

      <h4 style="margin-top: 20px;">策略参数</h4>
      <el-table :data="paramsTableData" style="width: 100%">
        <el-table-column label="参数名" prop="key"/>
        <el-table-column label="参数值" prop="value"/>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import {computed, onMounted, ref} from 'vue'
import {ElMessage} from 'element-plus'
import {Plus, Refresh} from '@element-plus/icons-vue'
import axios from 'axios'

// 响应式数据
const strategies = ref([])
const strategyTypes = ref([])
const loading = ref(false)
const showAddDialog = ref(false)
const showBacktestDialog = ref(false)
const showMetricsDialog = ref(false)
const backtestLoading = ref(false)
const backtestResult = ref(null)
const currentStrategy = ref(null)

// 新策略表单
const newStrategy = ref({
  strategy_type: '',
  params: {},
  auto_start: false
})

// 回测参数
const backtestParams = ref({
  strategy_type: 'MA',
  symbols: ['000001'],
  dateRange: ['2024-01-01', '2024-12-31'],
  initial_capital: 100000,
  commission: 0.001
})

// API基础URL
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// 获取策略类型参数配置
const strategyParamsConfig = {
  MA: {
    short_period: {type: 'int', default: 10, description: '短期均线'},
    long_period: {type: 'int', default: 30, description: '长期均线'},
    position_size: {type: 'int', default: 100, description: '仓位大小'},
    max_positions: {type: 'int', default: 5, description: '最大持仓数'}
  },
  MeanReversion: {
    lookback_period: {type: 'int', default: 20, description: '回看周期'},
    std_multiplier: {type: 'float', default: 2.0, description: '标准差倍数'},
    rsi_period: {type: 'int', default: 14, description: 'RSI周期'},
    rsi_oversold: {type: 'int', default: 30, description: 'RSI超卖'},
    rsi_overbought: {type: 'int', default: 70, description: 'RSI超买'}
  },
  Momentum: {
    momentum_period: {type: 'int', default: 20, description: '动量周期'},
    volume_period: {type: 'int', default: 20, description: '成交量周期'},
    breakout_period: {type: 'int', default: 50, description: '突破周期'},
    momentum_threshold: {type: 'float', default: 0.05, description: '动量阈值'},
    stop_loss_pct: {type: 'float', default: 0.02, description: '止损百分比'}
  }
}

// 计算属性
const paramsTableData = computed(() => {
  if (!currentStrategy.value?.params) return []
  return Object.entries(currentStrategy.value.params).map(([key, value]) => ({
    key,
    value: String(value)
  }))
})

// 方法
const getStatusType = (status) => {
  const types = {
    'RUNNING': 'success',
    'STOPPED': 'info',
    'PAUSED': 'warning',
    'ERROR': 'danger'
  }
  return types[status] || 'info'
}

const formatTime = (timeStr) => {
  if (!timeStr) return '-'
  return new Date(timeStr).toLocaleString('zh-CN')
}

const getStrategyParams = (type) => {
  return strategyParamsConfig[type] || {}
}

// API调用方法
const refreshStrategies = async () => {
  loading.value = true
  try {
    const response = await axios.get(`${API_BASE}/api/strategy/list`)
    strategies.value = response.data.strategies
  } catch (error) {
    ElMessage.error('获取策略列表失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

const addStrategy = async () => {
  try {
    // 设置默认参数值
    const params = getStrategyParams(newStrategy.value.strategy_type)
    for (const [key, config] of Object.entries(params)) {
      if (!(key in newStrategy.value.params)) {
        newStrategy.value.params[key] = config.default
      }
    }

    await axios.post(`${API_BASE}/api/strategy/add`, newStrategy.value)
    ElMessage.success('策略添加成功')
    showAddDialog.value = false
    refreshStrategies()

    // 重置表单
    newStrategy.value = {
      strategy_type: '',
      params: {},
      auto_start: false
    }
  } catch (error) {
    ElMessage.error('添加策略失败: ' + error.message)
  }
}

const startStrategy = async (id) => {
  try {
    await axios.post(`${API_BASE}/api/strategy/start/${id}`)
    ElMessage.success('策略启动成功')
    refreshStrategies()
  } catch (error) {
    ElMessage.error('启动策略失败: ' + error.message)
  }
}

const stopStrategy = async (id) => {
  try {
    await axios.post(`${API_BASE}/api/strategy/stop/${id}`)
    ElMessage.success('策略停止成功')
    refreshStrategies()
  } catch (error) {
    ElMessage.error('停止策略失败: ' + error.message)
  }
}

const pauseStrategy = async (id) => {
  try {
    await axios.post(`${API_BASE}/api/strategy/pause/${id}`)
    ElMessage.success('策略暂停成功')
    refreshStrategies()
  } catch (error) {
    ElMessage.error('暂停策略失败: ' + error.message)
  }
}

const resumeStrategy = async (id) => {
  try {
    await axios.post(`${API_BASE}/api/strategy/resume/${id}`)
    ElMessage.success('策略恢复成功')
    refreshStrategies()
  } catch (error) {
    ElMessage.error('恢复策略失败: ' + error.message)
  }
}

const removeStrategy = async (id) => {
  try {
    await axios.delete(`${API_BASE}/api/strategy/remove/${id}?force=true`)
    ElMessage.success('策略删除成功')
    refreshStrategies()
  } catch (error) {
    ElMessage.error('删除策略失败: ' + error.message)
  }
}

const showMetrics = (strategy) => {
  currentStrategy.value = strategy
  showMetricsDialog.value = true
}

const runBacktest = async () => {
  backtestLoading.value = true
  try {
    const params = {
      strategy_type: backtestParams.value.strategy_type,
      symbols: backtestParams.value.symbols,
      start_date: backtestParams.value.dateRange[0],
      end_date: backtestParams.value.dateRange[1],
      initial_capital: backtestParams.value.initial_capital,
      commission: backtestParams.value.commission,
      strategy_params: {}
    }

    const response = await axios.post(`${API_BASE}/api/strategy/backtest`, params)
    backtestResult.value = response.data
    showBacktestDialog.value = false
    ElMessage.success('回测完成')
  } catch (error) {
    ElMessage.error('回测失败: ' + error.message)
  } finally {
    backtestLoading.value = false
  }
}

// 生命周期
onMounted(() => {
  refreshStrategies()
})
</script>

<style scoped>
.strategy-management {
  padding: 20px;
}

.header-card {
  margin-bottom: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header h2 {
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.strategy-list-card,
.backtest-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.backtest-result {
  padding: 20px 0;
}

.backtest-chart {
  max-height: 400px;
  overflow: auto;
}

.profit {
  color: #67c23a;
  font-weight: bold;
}

.loss {
  color: #f56c6c;
  font-weight: bold;
}
</style>