<template>
  <div class="dashboard">
    <!-- 系统待办事项 -->
    <SystemAlerts/>

    <!-- 状态卡片 -->
    <el-row :gutter="24" class="status-cards">
      <el-col :md="6" :sm="12" :xs="24">
        <StatusCard
            :icon="DataAnalysis"
            :progress="getEventProgress()"
            :status="getTrendStatus(dashboardData.trends?.events_change)"
            :status-type="getTrendStatusType(dashboardData.trends?.events_change)"
            :subtitle="dashboardData.trends?.events_change !== undefined ? '较上次统计' : '累计处理'"
            :value="dashboardData.current?.total_events || 0"
            progress-status=""
            title="事件处理"
            type="primary"
            unit="个"
        />
      </el-col>

      <el-col :md="6" :sm="12" :xs="24">
        <StatusCard
            :icon="CircleCheck"
            :progress="getHealthScore()"
            :progress-status="getHealthProgressStatus()"
            :pulse="dashboardData.current?.health_status === 'good'"
            :status="getHealthText(dashboardData.current?.health_status)"
            :status-dot="true"
            :status-type="getHealthType(dashboardData.current?.health_status)"
            :type="getHealthCardType(dashboardData.current?.health_status)"
            :value="getHealthScore()"
            subtitle="所有组件运行状态"
            title="系统健康"
            unit="%"
        />
      </el-col>

      <el-col :md="6" :sm="12" :xs="24">
        <StatusCard
            :icon="List"
            :progress="getQueueProgress(dashboardData.current?.queue_size)"
            :progress-status="getQueueProgressStatus(dashboardData.current?.queue_size)"
            :status="getQueueStatus(dashboardData.current?.queue_size)"
            :status-type="getQueueStatusType(dashboardData.current?.queue_size)"
            :subtitle="dashboardData.trends?.queue_size_change !== undefined ? '队列压力' : '当前积压'"
            :value="dashboardData.current?.queue_size || 0"
            title="事件队列"
            type="warning"
            unit="个"
        />
      </el-col>

      <el-col :md="6" :sm="12" :xs="24">
        <StatusCard
            :icon="Warning"
            :progress="getAlertProgress()"
            :progress-status="getAlertProgressStatus()"
            :pulse="dashboardData.current?.active_alerts > 0"
            :status="getAlertStatus(dashboardData.current?.active_alerts)"
            :status-type="getAlertStatusType(dashboardData.current?.active_alerts)"
            :type="dashboardData.current?.active_alerts > 0 ? 'danger' : 'success'"
            :value="dashboardData.current?.active_alerts || 0"
            clickable
            subtitle="需要关注的问题"
            title="活跃告警"
            unit="个"
            @click="navigateToAlerts"
        />
      </el-col>
    </el-row>

    <!-- 系统组件管理 -->
    <el-card class="components-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>
            <el-icon><Setting/></el-icon>
            系统组件管理
          </span>
          <el-button :loading="componentLoading" size="small" @click="refreshComponents">
            <el-icon>
              <Refresh/>
            </el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-table v-loading="componentLoading" :data="components" style="width: 100%">
        <el-table-column label="组件名称" prop="display_name" width="180"/>
        <el-table-column label="描述" min-width="200" prop="description"/>
        <el-table-column label="类型" prop="type" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.type === 'infrastructure' ? 'primary' : 'success'" size="small">
              {{ scope.row.type === 'infrastructure' ? '基础设施' : '业务组件' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="180" prop="status">
          <template #default="scope">
            <div class="status-cell">
              <el-tooltip
                  v-if="getComponentErrorMessage(scope.row)"
                  :content="getComponentErrorMessage(scope.row)"
                  placement="top"
              >
                <el-tag :type="getComponentStatusType(scope.row.status)" size="small">
                  {{ getComponentStatusText(scope.row.status) }}
                </el-tag>
              </el-tooltip>
              <el-tag
                  v-else
                  :type="getComponentStatusType(scope.row.status)"
                  size="small"
              >
                {{ getComponentStatusText(scope.row.status) }}
              </el-tag>
              <span v-if="getComponentErrorMessage(scope.row)" class="error-hint">
                ({{ getShortErrorMessage(getComponentErrorMessage(scope.row)) }})
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column fixed="right" label="操作" width="180">
          <template #default="scope">
            <el-button
                v-if="scope.row.status !== 'running'"
                :disabled="!canStartComponent(scope.row)"
                size="small"
                type="primary"
                @click="handleStartComponent(scope.row)"
            >
              <el-icon>
                <VideoPlay/>
              </el-icon>
              启动
            </el-button>
            <el-button
                v-else
                :disabled="!canStopComponent(scope.row)"
                size="small"
                type="danger"
                @click="handleStopComponent(scope.row)"
            >
              <el-icon>
                <VideoPause/>
              </el-icon>
              停止
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-alert
          :closable="false"
          show-icon
          style="margin-top: 20px"
          type="info"
      >
        <template #title>
          温馨提示：基础设施组件已自动启动，业务组件需要手动启动。停止组件时，依赖该组件的其他组件也会被停止。
        </template>
      </el-alert>
    </el-card>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="chart-area">
      <el-col :md="16" :xs="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>事件处理趋势</span>
              <el-button-group size="small">
                <el-button :type="chartPeriod === '5m' ? 'primary' : ''" @click="changeChartPeriod('5m')">5分钟
                </el-button>
                <el-button :type="chartPeriod === '1h' ? 'primary' : ''" @click="changeChartPeriod('1h')">1小时
                </el-button>
                <el-button :type="chartPeriod === '24h' ? 'primary' : ''" @click="changeChartPeriod('24h')">24小时
                </el-button>
              </el-button-group>
            </div>
          </template>
          <div ref="trendChart" class="chart-container"></div>
        </el-card>
      </el-col>

      <el-col :md="8" :xs="24">
        <el-card>
          <template #header>
            <span>事件类型分布</span>
          </template>
          <div ref="pieChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 告警列表 -->
    <el-card v-if="dashboardData.alerts?.length > 0" class="alerts-card">
      <template #header>
        <span>系统告警</span>
      </template>
      <el-timeline>
        <el-timeline-item
            v-for="(alert, index) in dashboardData.alerts"
            :key="index"
            :timestamp="formatTime(alert.timestamp)"
            :type="getTimelineType(alert.level)"
            placement="top"
        >
          <el-alert
              :closable="false"
              :title="alert.message"
              :type="getAlertType(alert.level)"
              show-icon
          />
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <!-- WebSocket 连接状态 -->
    <div class="ws-status">
      <el-tag :type="wsConnected ? 'success' : 'info'" size="small">
        <el-icon>
          <Link/>
        </el-icon>
        {{ wsConnected ? '实时连接' : '连接断开' }}
      </el-tag>
    </div>
  </div>
</template>

<script setup>
import {nextTick, onMounted, onUnmounted, ref, watch} from 'vue'
import {ElLoading, ElMessage, ElMessageBox} from 'element-plus'
import {useRouter} from 'vue-router'
import {
  CircleCheck,
  DataAnalysis,
  Link,
  List,
  Refresh,
  Setting,
  VideoPause,
  VideoPlay,
  Warning
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import {getDashboard, getRealtimeMetrics} from '@/api/monitor'
import {getAllComponents, startComponent, stopComponent} from '@/api/system'
import {wsManager} from '@/utils/websocket'
import {useSystemStore} from '@/stores/system'
import SystemAlerts from '@/components/SystemAlerts.vue'
import StatusCard from '@/components/StatusCard.vue'

// 定义组件名称
defineOptions({
  name: 'Dashboard'
})

// 路由
const router = useRouter()
// 系统状态
const systemStore = useSystemStore()

// 响应式数据
const dashboardData = ref({
  current: null,
  trends: null,
  alerts: []
})
const chartPeriod = ref('1h')
const wsConnected = ref(false)

// 组件管理相关
const components = ref([])
const componentLoading = ref(false)

// 图表实例
let trendChartInstance = null
let pieChartInstance = null

// 图表容器引用
const trendChart = ref(null)
const pieChart = ref(null)

// WebSocket 连接管理
const setupWebSocket = () => {
  // 监听连接状态变化
  const updateConnectionStatus = () => {
    const status = wsManager.getStatus()
    wsConnected.value = status.isConnected
  }

  // 设置事件处理器
  wsManager.on('open', () => {
    updateConnectionStatus()
    console.log('监控面板: WebSocket 已连接')
  })

  wsManager.on('message', (data) => {
    if (data.type === 'monitor_update') {
      dashboardData.value = data.data
      updateCharts()
    }
  })

  wsManager.on('close', () => {
    updateConnectionStatus()
  })

  wsManager.on('error', (error) => {
    // 静默处理错误，避免日志噪音
    updateConnectionStatus()
  })

  // 连接 WebSocket
  wsManager.connect()
}

// 初始化图表
const initCharts = () => {
  // 趋势图
  if (trendChart.value) {
    trendChartInstance = echarts.init(trendChart.value)
    trendChartInstance.setOption({
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross'
        }
      },
      legend: {
        data: ['处理数', '成功率']
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: []
      },
      yAxis: [
        {
          type: 'value',
          name: '处理数',
          position: 'left'
        },
        {
          type: 'value',
          name: '成功率 (%)',
          position: 'right',
          max: 100,
          min: 0
        }
      ],
      series: [
        {
          name: '处理数',
          type: 'line',
          data: [],
          smooth: true,
          itemStyle: {
            color: '#409eff'
          }
        },
        {
          name: '成功率',
          type: 'line',
          yAxisIndex: 1,
          data: [],
          smooth: true,
          itemStyle: {
            color: '#67c23a'
          }
        }
      ]
    })
  }

  // 饼图
  if (pieChart.value) {
    pieChartInstance = echarts.init(pieChart.value)
    pieChartInstance.setOption({
      tooltip: {
        trigger: 'item'
      },
      legend: {
        orient: 'vertical',
        left: 'left'
      },
      series: [
        {
          type: 'pie',
          radius: '50%',
          data: [],
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }
      ]
    })
  }
}

// 更新图表数据
const updateCharts = async () => {
  try {
    const metrics = await getRealtimeMetrics()

    // 检查图表实例是否存在且未被销毁
    if (trendChartInstance && !trendChartInstance.isDisposed() && metrics.series) {
      const timestamps = metrics.timestamps?.map(t => dayjs(t).format('HH:mm:ss')) || []
      const series = []

      // 聚合所有事件类型的数据
      let totalCounts = []
      let avgSuccessRates = []

      Object.values(metrics.series).forEach(data => {
        if (data.count) {
          totalCounts = data.count
          avgSuccessRates = data.success_rate
        }
      })

      trendChartInstance.setOption({
        xAxis: {
          data: timestamps
        },
        series: [
          {
            name: '处理数',
            data: totalCounts
          },
          {
            name: '成功率',
            data: avgSuccessRates
          }
        ]
      })
    }

    // 更新饼图
    if (pieChartInstance && !pieChartInstance.isDisposed() && metrics.series) {
      const pieData = Object.entries(metrics.series).map(([name, data]) => ({
        name,
        value: data.count?.reduce((sum, val) => sum + val, 0) || 0
      }))

      pieChartInstance.setOption({
        series: [{
          data: pieData
        }]
      })
    }
  } catch (error) {
    console.error('更新图表失败:', error)
  }
}

// 格式化数字
const formatNumber = (num) => {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toString()
}

// 格式化时间
const formatTime = (timestamp) => {
  return dayjs(timestamp).format('HH:mm:ss')
}

// 获取健康状态类型
const getHealthType = (status) => {
  const types = {
    'healthy': 'success',
    'degraded': 'warning',
    'unhealthy': 'danger'
  }
  return types[status] || 'info'
}

// 获取健康状态文本
const getHealthText = (status) => {
  const texts = {
    'healthy': '健康',
    'degraded': '降级',
    'unhealthy': '异常'
  }
  return texts[status] || '未知'
}

// 获取告警类型（用于 ElAlert）
const getAlertType = (level) => {
  const types = {
    'error': 'error',
    'warning': 'warning',
    'info': 'info'
  }
  return types[level] || 'info'
}

// 获取时间线项类型（用于 ElTimelineItem）
const getTimelineType = (level) => {
  // ElTimelineItem 接受: primary, success, warning, danger, info
  const types = {
    'error': 'danger',  // ElTimelineItem 使用 'danger' 而不是 'error'
    'warning': 'warning',
    'info': 'info'
  }
  return types[level] || 'info'
}

// 获取趋势类
const getTrendClass = (value, inverse = false) => {
  if (inverse) {
    return value > 0 ? 'trend-down' : 'trend-up'
  }
  return value > 0 ? 'trend-up' : 'trend-down'
}

// 获取趋势状态文字
const getTrendStatus = (change) => {
  if (change === undefined || change === null) return '持平'
  if (change === 0) return '持平'
  const absChange = Math.abs(change)
  const prefix = change > 0 ? '↑' : '↓'
  return `${prefix} ${absChange}%`
}

// 获取趋势状态类型
const getTrendStatusType = (change) => {
  if (change === undefined || change === null || change === 0) return 'info'
  return change > 0 ? 'success' : 'danger'
}

// 获取事件进度
const getEventProgress = () => {
  const total = dashboardData.value.current?.total_events || 0
  if (total === 0) return 0
  // 假设每天目标处理 10000 个事件
  const progress = Math.min(100, (total / 10000) * 100)
  return Math.round(progress) // 确保返回整数
}

// 获取健康卡片类型
const getHealthCardType = (status) => {
  const typeMap = {
    good: 'success',
    warning: 'warning',
    error: 'danger'
  }
  return typeMap[status] || 'info'
}

// 获取队列状态
const getQueueStatus = (size) => {
  if (size === 0) return '空闲'
  if (size < 100) return '正常'
  if (size < 500) return '繁忙'
  return '拥堵'
}

// 获取队列状态类型
const getQueueStatusType = (size) => {
  if (size === 0) return 'info'
  if (size < 100) return 'success'
  if (size < 500) return 'warning'
  return 'danger'
}

// 获取队列进度
const getQueueProgress = (size) => {
  if (!size || size === 0) return 0
  // 假设队列最大容量 1000
  const progress = Math.min(100, (size / 1000) * 100)
  return Math.round(progress) // 确保返回整数
}

// 获取队列进度状态
const getQueueProgressStatus = (size) => {
  if (size < 100) return 'success'
  if (size < 500) return 'warning'
  return 'exception'
}

// 获取告警状态
const getAlertStatus = (count) => {
  if (count === 0) return '无告警'
  if (count < 5) return '有告警'
  return '告警过多'
}

// 获取告警状态类型
const getAlertStatusType = (count) => {
  if (count === 0) return 'success'
  if (count < 5) return 'warning'
  return 'danger'
}

// 导航到告警页面
const navigateToAlerts = () => {
  router.push('/logs')
}

// 获取健康分数
const getHealthScore = () => {
  const status = dashboardData.value.current?.health_status
  const scoreMap = {
    'healthy': 100,
    'good': 100,
    'degraded': 75,
    'warning': 50,
    'unhealthy': 25,
    'error': 0
  }
  return scoreMap[status] || 0
}

// 获取健康进度状态
const getHealthProgressStatus = () => {
  const score = getHealthScore()
  if (score >= 90) return 'success'
  if (score >= 70) return 'warning'
  return 'exception'
}

// 获取告警进度
const getAlertProgress = () => {
  const count = dashboardData.value.current?.active_alerts || 0
  if (count === 0) return 0
  // 假设最多10个告警为100%
  const progress = Math.min(100, (count / 10) * 100)
  return Math.round(progress) // 确保返回整数
}

// 获取告警进度状态
const getAlertProgressStatus = () => {
  const count = dashboardData.value.current?.active_alerts || 0
  if (count === 0) return 'success'
  if (count < 5) return 'warning'
  return 'exception'
}

// 获取初始数据
const fetchInitialData = async () => {
  try {
    dashboardData.value = await getDashboard(chartPeriod.value)
    await updateCharts()
    await refreshComponents()
    // 缓存状态已经通过 refreshComponents 更新到 store 中
  } catch (error) {
    ElMessage.error('获取仪表板数据失败')
  }
}

// 切换图表时间段
const changeChartPeriod = async (period) => {
  chartPeriod.value = period
  try {
    const loading = ElLoading.service({
      lock: true,
      text: '加载数据中...',
      background: 'rgba(0, 0, 0, 0.3)'
    })

    dashboardData.value = await getDashboard(period)
    await updateCharts()

    loading.close()
  } catch (error) {
    ElMessage.error('更新图表数据失败')
  }
}

// 刷新组件列表
const refreshComponents = async () => {
  componentLoading.value = true
  try {
    const res = await getAllComponents()
    // 转换成数组格式，并过滤掉 webui 组件
    components.value = Object.entries(res.components || {})
        .filter(([name]) => name !== 'webui')  // 过滤掉 webui 组件
        .map(([name, info]) => ({
          name,
          ...info
        }))
    // 更新到 systemStore
    systemStore.updateComponents(components.value)
  } catch (error) {
    console.error('获取组件列表失败:', error)
    // 如果后端未启动，显示默认数据
    components.value = []
    systemStore.updateComponents([])
  } finally {
    componentLoading.value = false
  }
}

// 获取组件状态类型
const getComponentStatusType = (status) => {
  const types = {
    'running': 'success',
    'stopped': 'info',
    'initialized': 'warning',
    'uninitialized': '',
    'error': 'danger',
    'starting': 'warning',
    'stopping': 'warning'
  }
  return types[status] || ''
}

// 获取组件状态文本
const getComponentStatusText = (status) => {
  const texts = {
    'running': '运行中',
    'stopped': '已停止',
    'initialized': '已初始化',
    'uninitialized': '未初始化',
    'error': '错误',
    'starting': '正在启动',
    'stopping': '正在停止'
  }
  return texts[status] || status
}

// 获取组件错误信息
const getComponentErrorMessage = (component) => {
  // 对于缓存组件，完全使用 systemStore 中的状态
  if (component.name === 'cache') {
    // 如果组件正在运行，不显示错误信息
    if (component.status === 'running') {
      return null
    }
    
    const cacheStatus = systemStore.cacheStatus
    // 优先显示断开原因
    if (cacheStatus.disconnectReason) {
      return cacheStatus.disconnectReason
    }
    // 如果有健康检查错误
    if (cacheStatus.health?.error) {
      return cacheStatus.health.error
    }
    // 如果状态是错误但没有具体信息
    if (component.status === 'error' && component.error_message) {
      return component.error_message
    }
    // 未连接但没有具体原因
    if (!cacheStatus.connected && component.status !== 'running') {
      return "Redis 服务未连接"
    }
    return null
  }

  // 对于其他组件，使用原始错误信息
  return component.status === 'error' ? component.error_message : null
}

// 获取简短的错误信息
const getShortErrorMessage = (errorMessage) => {
  if (!errorMessage) return ''

  // 针对常见错误提供简短描述
  if (errorMessage.includes('Redis 服务未连接')) {
    return 'Redis未连接'
  }
  if (errorMessage.includes('认证失败')) {
    return '认证失败'
  }
  if (errorMessage.includes('连接超时')) {
    return '连接超时'
  }
  if (errorMessage.includes('健康检查异常')) {
    // 提取更多信息
    const match = errorMessage.match(/健康检查异常:\s*(.+)/)
    if (match && match[1]) {
      // 如果是 coroutine 相关错误，显示更清晰的信息
      if (match[1].includes('coroutine')) {
        return '异步错误'
      }
      // 保留更多原始信息，但限制长度
      return match[1].substring(0, 30) + (match[1].length > 30 ? '...' : '')
    }
    return '健康检查异常'
  }
  if (errorMessage.includes('Redis 服务异常')) {
    // 提取具体错误
    const match = errorMessage.match(/Redis 服务异常:\s*(.+)/)
    if (match && match[1]) {
      // 保留更多信息
      return 'Redis异常: ' + match[1].substring(0, 25) + (match[1].length > 25 ? '...' : '')
    }
    return 'Redis服务异常'
  }

  // 如果错误信息太长，保留更多内容
  if (errorMessage.length > 35) {
    return errorMessage.substring(0, 35) + '...'
  }

  return errorMessage
}

// 判断是否可以启动组件
const canStartComponent = (component) => {
  // 检查依赖的组件是否都已启动
  if (component.dependencies && component.dependencies.length > 0) {
    for (const dep of component.dependencies) {
      const depComponent = components.value.find(c => c.name === dep)
      if (!depComponent || depComponent.status !== 'running') {
        return false
      }
    }
  }
  return true
}

// 判断是否可以停止组件
const canStopComponent = (component) => {
  // 基础设施组件通常不允许停止
  // 但我们允许停止，只是需要检查是否有其他组件依赖它
  const dependentComponents = components.value.filter(c =>
      c.dependencies && c.dependencies.includes(component.name) && c.status === 'running'
  )
  return dependentComponents.length === 0
}

// 启动组件
const handleStartComponent = async (component) => {
  let loading = null
  try {
    await ElMessageBox.confirm(
        `确定要启动组件 "${component.display_name}" 吗？`,
        '启动组件',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'info'
        }
    )

    loading = ElLoading.service({
      lock: true,
      text: `正在启动 ${component.display_name}...`,
      background: 'rgba(0, 0, 0, 0.7)'
    })

    await startComponent(component.name)
    ElMessage.success(`组件 "${component.display_name}" 启动成功`)
    await refreshComponents()

  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '启动组件失败')
    }
  } finally {
    // 确保loading一定会被关闭
    if (loading) {
      loading.close()
    }
  }
}

// 停止组件
const handleStopComponent = async (component) => {
  let loading = null
  try {
    await ElMessageBox.confirm(
        `确定要停止组件 "${component.display_name}" 吗？`,
        '停止组件',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        }
    )

    loading = ElLoading.service({
      lock: true,
      text: `正在停止 ${component.display_name}...`,
      background: 'rgba(0, 0, 0, 0.7)'
    })

    await stopComponent(component.name)
    ElMessage.success(`组件 "${component.display_name}" 停止成功`)
    await refreshComponents()

  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '停止组件失败')
    }
  } finally {
    // 确保loading一定会被关闭
    if (loading) {
      loading.close()
    }
  }
}

// 处理窗口大小变化
const handleResize = () => {
  if (trendChartInstance && !trendChartInstance.isDisposed()) {
    trendChartInstance.resize()
  }
  if (pieChartInstance && !pieChartInstance.isDisposed()) {
    pieChartInstance.resize()
  }
}

// 监听系统状态变化
watch(() => systemStore.isRunning, (isRunning) => {
  if (isRunning) {
    // 引擎启动时，连接 WebSocket
    wsManager.shouldReconnect = true
    wsManager.connect()
  } else {
    // 引擎停止时，断开 WebSocket
    wsManager.shouldReconnect = false
    wsManager.disconnect()
    wsConnected.value = false
  }
})

// 定时刷新相关
let refreshTimer = null

onMounted(async () => {
  await fetchInitialData()
  await nextTick()
  initCharts()

  // 只有在引擎运行时才连接 WebSocket
  if (systemStore.isRunning) {
    setupWebSocket()
  }
  
  window.addEventListener('resize', handleResize)

  // 设置定时刷新（每30秒刷新一次组件状态）
  refreshTimer = setInterval(async () => {
    try {
      await refreshComponents()
      // 同时刷新系统状态，包括缓存状态
      await systemStore.fetchStatus()
    } catch (error) {
      console.error('定时刷新失败:', error)
    }
  }, 30000)
})

onUnmounted(() => {
  // 组件卸载时断开 WebSocket
  wsManager.shouldReconnect = false
  wsManager.disconnect()

  // 清除定时器
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  
  trendChartInstance?.dispose()
  pieChartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style lang="scss" scoped>
@use '@/assets/styles/design-tokens.scss' as tokens;

.dashboard {
  padding: tokens.$spacing-5;
  background: var(--bg-color);
  min-height: 100vh;

  .status-cards {
    margin-bottom: tokens.$spacing-6;

    .el-col {
      margin-bottom: tokens.$spacing-5;
    }
  }

  .chart-area {
    margin-bottom: tokens.$spacing-6;

    .el-card {
      border-radius: tokens.$radius-lg;
      overflow: hidden;

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;

        span {
          font-size: tokens.$font-size-lg;
          font-weight: tokens.$font-weight-semibold;
          color: var(--text-primary);
        }

        .el-button-group {
          .el-button {
            padding: tokens.$spacing-1 tokens.$spacing-3;
            font-size: tokens.$font-size-sm;
          }
        }
      }
    }

    .chart-container {
      height: 380px;
      padding: tokens.$spacing-3 0;
    }
  }

  .components-card {
    margin-bottom: tokens.$spacing-6;
    border-radius: tokens.$radius-lg;
    overflow: hidden;

    .el-card__header {
      background: linear-gradient(135deg, var(--card-bg) 0%, rgba(tokens.$brand-primary, 0.05) 100%);
      border-bottom: tokens.$border-width solid var(--border-lighter);

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;

        span {
          display: flex;
          align-items: center;
          gap: tokens.$spacing-2;
          font-size: tokens.$font-size-lg;
          font-weight: tokens.$font-weight-semibold;
          color: var(--text-primary);

          .el-icon {
            font-size: 20px;
          }
        }
      }
    }

    .el-table {
      font-size: tokens.$font-size-sm;

      .el-table__row {
        transition: all tokens.$duration-base;

        &:hover {
          background-color: rgba(tokens.$brand-primary, 0.02);
        }
      }

      .component-status {
        display: flex;
        align-items: center;
        gap: tokens.$spacing-2;

        .el-tag {
          font-weight: tokens.$font-weight-medium;
          border-radius: tokens.$radius-full;
        }
      }
    }
  }

  .alerts-card {
    margin-bottom: tokens.$spacing-6;
    border-radius: tokens.$radius-lg;
    overflow: hidden;

    .el-timeline {
      padding: tokens.$spacing-4 0;

      .el-timeline-item {
        padding-bottom: tokens.$spacing-6;

        &:last-child {
          padding-bottom: 0;
        }
      }
    }
  }

  .ws-status {
    position: fixed;
    bottom: tokens.$spacing-6;
    right: tokens.$spacing-6;
    z-index: tokens.$z-index-sticky;

    .el-tag {
      padding: tokens.$spacing-2 tokens.$spacing-4;
      font-weight: tokens.$font-weight-medium;
      box-shadow: tokens.$shadow-lg;
      border-radius: tokens.$radius-full;
      backdrop-filter: blur(10px);
    }
  }
}

// 状态指示器
.status-indicator {
  display: inline-block;
  margin-right: tokens.$spacing-1;

  &.breathing {
    @include tokens.breathing-animation;
  }
}

// 暗色主题适配
.dark {
  .dashboard {
    .components-card {
      .el-card__header {
        background: linear-gradient(135deg, var(--card-bg) 0%, rgba(tokens.$brand-primary, 0.1) 100%);
      }
    }

    .ws-status {
      .el-tag {
        @include tokens.dark-glassmorphism(0.8, 10px);
      }
    }
  }
}

// 响应式
@media (max-width: tokens.$breakpoint-md) {
  .dashboard {
    padding: tokens.$spacing-3;

    .chart-container {
      height: 300px;
    }

    .ws-status {
      bottom: tokens.$spacing-4;
      right: tokens.$spacing-4;
    }
  }
}

// 状态单元格样式
.status-cell {
  display: flex;
  align-items: center;
  gap: tokens.$spacing-1;

  .error-hint {
    font-size: tokens.$font-size-xs;
    color: var(--text-secondary);
    @include tokens.truncate;
    max-width: 200px;
  }
}
</style>