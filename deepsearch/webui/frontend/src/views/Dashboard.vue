<template>
  <div class="dashboard">
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
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="chart-area">
      <el-col :md="16" :xs="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>事件处理趋势</span>
              <el-button-group size="small">
                <el-button :type="chartPeriod === '5m' ? 'primary' : ''" @click="chartPeriod = '5m'">5分钟</el-button>
                <el-button :type="chartPeriod === '1h' ? 'primary' : ''" @click="chartPeriod = '1h'">1小时</el-button>
                <el-button :type="chartPeriod === '24h' ? 'primary' : ''" @click="chartPeriod = '24h'">24小时
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
            :type="getAlertType(alert.level)"
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
import {ref, onMounted, onUnmounted, nextTick} from 'vue'
import {ElMessage} from 'element-plus'
import {DataLine, CircleCheck, Clock, Warning, Top, Bottom, Link} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import {getDashboard, getRealtimeMetrics} from '@/api/monitor'
import {wsManager} from '@/utils/websocket'

// 响应式数据
const dashboardData = ref({
  current: null,
  trends: null,
  alerts: []
})
const chartPeriod = ref('1h')
const wsConnected = ref(false)

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
    console.warn('监控面板: WebSocket 连接错误（后端可能未启动）')
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
        data: ['处理数', '成功率', '平均耗时']
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

    if (trendChartInstance && metrics.series) {
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
    if (pieChartInstance && metrics.series) {
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

// 获取告警类型
const getAlertType = (level) => {
  const types = {
    'error': 'error',
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
    dashboardData.value = await getDashboard()
    await updateCharts()
  } catch (error) {
    ElMessage.error('获取仪表板数据失败')
  }
}

// 处理窗口大小变化
const handleResize = () => {
  trendChartInstance?.resize()
  pieChartInstance?.resize()
}

onMounted(async () => {
  await fetchInitialData()
  await nextTick()
  initCharts()
  setupWebSocket()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  // wsManager 会自动管理连接，这里不需要手动关闭
  trendChartInstance?.dispose()
  pieChartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style lang="scss" scoped>
.dashboard {
  .status-cards {
    margin-bottom: 20px;

    .status-card {
      .card-header {
        display: flex;
        align-items: center;
        margin-bottom: 10px;
        color: #909399;
        font-size: 14px;

        .card-icon {
          font-size: 24px;
          margin-right: 8px;
        }
      }

      .card-value {
        font-size: 28px;
        font-weight: 600;
        color: #303133;
        margin-bottom: 8px;
      }

      .card-trend {
        display: flex;
        align-items: center;
        font-size: 14px;

        .trend-up {
          color: #67c23a;
        }

        .trend-down {
          color: #f56c6c;
        }
      }
    }
  }

  .chart-area {
    margin-bottom: 20px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .chart-container {
      height: 350px;
    }
  }

  .alerts-card {
    margin-bottom: 20px;
  }

  .ws-status {
    position: fixed;
    bottom: 20px;
    right: 20px;
  }
}

// 暗色主题适配
.dark {
  .status-card {
    .card-value {
      color: #fff;
    }
  }
}
</style>