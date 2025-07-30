<template>
  <div class="dashboard">
    <!-- 系统待办事项 -->
    <SystemAlerts/>

    <!-- 状态卡片 -->
    <el-row :gutter="20" class="status-cards">
      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="status-card" shadow="hover">
          <div class="card-header">
            <el-icon class="card-icon" color="#409eff">
              <DataLine/>
            </el-icon>
            <span>处理事件</span>
          </div>
          <div class="card-value">{{ formatNumber(dashboardData.current?.total_events || 0) }}</div>
          <div v-if="dashboardData.trends?.events_change !== undefined" class="card-trend">
            <el-icon v-if="dashboardData.trends.events_change > 0" color="#67c23a">
              <Top/>
            </el-icon>
            <el-icon v-else-if="dashboardData.trends.events_change < 0" color="#f56c6c">
              <Bottom/>
            </el-icon>
            <span :class="getTrendClass(dashboardData.trends.events_change)">
              {{ Math.abs(dashboardData.trends.events_change) }}
            </span>
          </div>
        </el-card>
      </el-col>

      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="status-card" shadow="hover">
          <div class="card-header">
            <el-icon class="card-icon" color="#67c23a">
              <CircleCheck/>
            </el-icon>
            <span>健康状态</span>
          </div>
          <div class="card-value">
            <el-tag :type="getHealthType(dashboardData.current?.health_status)" size="large">
              {{ getHealthText(dashboardData.current?.health_status) }}
            </el-tag>
          </div>
          <div class="card-trend">
            <!-- 占位元素，保持卡片高度一致 -->
            <span style="visibility: hidden;">占位</span>
          </div>
        </el-card>
      </el-col>

      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="status-card" shadow="hover">
          <div class="card-header">
            <el-icon class="card-icon" color="#e6a23c">
              <Clock/>
            </el-icon>
            <span>队列大小</span>
          </div>
          <div class="card-value">{{ dashboardData.current?.queue_size || 0 }}</div>
          <div v-if="dashboardData.trends?.queue_size_change !== undefined" class="card-trend">
            <el-icon v-if="dashboardData.trends.queue_size_change > 0" color="#f56c6c">
              <Top/>
            </el-icon>
            <el-icon v-else-if="dashboardData.trends.queue_size_change < 0" color="#67c23a">
              <Bottom/>
            </el-icon>
            <span :class="getTrendClass(dashboardData.trends.queue_size_change, true)">
              {{ Math.abs(dashboardData.trends.queue_size_change) }}
            </span>
          </div>
        </el-card>
      </el-col>

      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="status-card" shadow="hover">
          <div class="card-header">
            <el-icon class="card-icon" color="#f56c6c">
              <Warning/>
            </el-icon>
            <span>活跃告警</span>
          </div>
          <div class="card-value">{{ dashboardData.current?.active_alerts || 0 }}</div>
          <div class="card-trend">
            <!-- 占位元素，保持卡片高度一致 -->
            <span style="visibility: hidden;">占位</span>
          </div>
        </el-card>
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
        <el-table-column label="状态" prop="status" width="120">
          <template #default="scope">
            <el-tag :type="getComponentStatusType(scope.row.status)" size="small">
              {{ getComponentStatusText(scope.row.status) }}
            </el-tag>
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
import {
  Bottom,
  CircleCheck,
  Clock,
  DataLine,
  Link,
  Refresh,
  Setting,
  Top,
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

// 定义组件名称
defineOptions({
  name: 'Dashboard'
})

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

// 获取初始数据
const fetchInitialData = async () => {
  try {
    dashboardData.value = await getDashboard(chartPeriod.value)
    await updateCharts()
    await refreshComponents()
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
    // 转换成数组格式
    components.value = Object.entries(res.components || {}).map(([name, info]) => ({
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

onMounted(async () => {
  await fetchInitialData()
  await nextTick()
  initCharts()

  // 只有在引擎运行时才连接 WebSocket
  if (systemStore.isRunning) {
    setupWebSocket()
  }
  
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  // 组件卸载时断开 WebSocket
  wsManager.shouldReconnect = false
  wsManager.disconnect()
  
  trendChartInstance?.dispose()
  pieChartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style lang="scss" scoped>
.dashboard {
  padding: 20px;
  background: var(--bg-color);
  min-height: 100vh;

  .status-cards {
    margin-bottom: 24px;

    .status-card {
      transition: all 0.3s ease;
      border-radius: 12px;
      overflow: hidden;
      position: relative;
      min-height: 160px; // 设置最小高度确保卡片大小一致

      // 确保内容垂直分布均匀
      :deep(.el-card__body) {
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
      }

      &::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, var(--primary-color), var(--success-color));
        opacity: 0;
        transition: opacity 0.3s;
      }

      &:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);

        &::before {
          opacity: 1;
        }
      }

      .card-header {
        display: flex;
        align-items: center;
        margin-bottom: 16px;
        color: var(--text-secondary);
        font-size: 14px;
        font-weight: 500;

        .card-icon {
          font-size: 32px;
          margin-right: 12px;
          opacity: 0.9;
        }
      }

      .card-value {
        font-size: 32px;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 12px;
        letter-spacing: -1px;
      }

      .card-trend {
        display: flex;
        align-items: center;
        font-size: 14px;
        font-weight: 500;

        .el-icon {
          margin-right: 4px;
        }

        .trend-up {
          color: var(--success-color);
        }

        .trend-down {
          color: var(--danger-color);
        }
      }
    }
  }

  .chart-area {
    margin-bottom: 24px;

    .el-card {
      border-radius: 12px;

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;

        h3 {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
          color: var(--text-primary);
        }
      }
    }

    .chart-container {
      height: 380px;
      padding: 12px 0;
    }
  }

  .components-card {
    margin-bottom: 24px;
    border-radius: 12px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      span {
        display: flex;
        align-items: center;
        font-size: 18px;
        font-weight: 600;
        color: var(--text-primary);

        .el-icon {
          margin-right: 8px;
          font-size: 20px;
        }
      }
    }

    .el-table {
      font-size: 14px;

      .el-table__row {
        transition: all 0.3s;

        &:hover {
          background-color: var(--bg-color);
        }
      }

      .component-status {
        display: flex;
        align-items: center;
        gap: 8px;

        .el-tag {
          font-weight: 500;
        }
      }
    }
  }

  .alerts-card {
    margin-bottom: 24px;
    border-radius: 12px;

    .el-timeline {
      padding: 16px 0;

      .el-timeline-item {
        padding-bottom: 24px;

        &:last-child {
          padding-bottom: 0;
        }
      }
    }
  }

  .ws-status {
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 999;

    .el-tag {
      padding: 8px 16px;
      font-weight: 500;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
  }
}

// 呼吸动画
@keyframes breathing {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.6;
    transform: scale(1.2);
  }
}

.status-indicator {
  display: inline-block;
  margin-right: 4px;

  &.breathing {
    animation: breathing 2s ease-in-out infinite;
  }
}

// 暗色主题适配
.dark {
  .dashboard {
    background: var(--bg-color);

    .status-card {
      background: var(--card-bg);

      .card-value {
        color: var(--text-primary);
      }

      &:hover {
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
      }
    }

    .el-card {
      background: var(--card-bg);
    }
  }
}

// 响应式
@media (max-width: 768px) {
  .dashboard {
    padding: 12px;

    .status-card {
      .card-header {
        .card-icon {
          font-size: 24px;
        }
      }

      .card-value {
        font-size: 24px;
      }
    }

    .chart-container {
      height: 300px;
    }
  }
}
</style>