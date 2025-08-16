<template>
  <div class="market-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>市场数据</h2>
      <div class="header-actions">
        <el-button :loading="loading.overview" @click="refreshAll">
          <el-icon>
            <Refresh/>
          </el-icon>
          刷新
        </el-button>
        <span v-if="lastUpdateTime" class="update-time">
          最后更新: {{ formatTime(lastUpdateTime) }}
        </span>
      </div>
    </div>

    <!-- 指数卡片 -->
    <div class="indices-section">
      <el-row :gutter="20">
        <el-col v-for="index in indices" :key="index.code" :span="6">
          <el-card class="index-card" shadow="hover">
            <div class="index-header">
              <span class="index-name">{{ index.name }}</span>
              <span class="index-code">{{ index.code }}</span>
            </div>
            <div class="index-price">
              {{ formatNumber(index.price) }}
            </div>
            <div :class="getChangeClass(index.change_pct)" class="index-change">
              <span class="change-value">{{ index.change > 0 ? '+' : '' }}{{ formatNumber(index.change) }}</span>
              <span class="change-pct">{{ index.change_pct > 0 ? '+' : '' }}{{ index.change_pct.toFixed(2) }}%</span>
            </div>
            <div class="index-volume">
              成交额: {{ formatAmount(index.amount) }}
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 市场宽度 -->
    <div class="breadth-section">
      <el-card>
        <template #header>
          <div class="breadth-header">
            <span>市场宽度</span>
            <span class="breadth-total">总计: {{ breadth.total || 0 }} 只</span>
          </div>
        </template>
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="breadth-item">
              <div class="breadth-label">涨跌分布</div>
              <el-progress
                  :color="customColors"
                  :percentage="getAdvanceDeclineRatio()"
                  :show-text="false"
                  :stroke-width="20"
              />
              <div class="breadth-stats">
                <span class="stat-item rise">上涨 {{ breadth.advancers || 0 }}</span>
                <span class="stat-item flat">平盘 {{ breadth.unchanged || 0 }}</span>
                <span class="stat-item fall">下跌 {{ breadth.decliners || 0 }}</span>
              </div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="breadth-item">
              <div class="breadth-label">涨停跌停</div>
              <div class="limit-stats">
                <div class="limit-item">
                  <span class="limit-label">涨停</span>
                  <span class="limit-value rise">{{ breadth.limit_up || 0 }}</span>
                </div>
                <div class="limit-item">
                  <span class="limit-label">跌停</span>
                  <span class="limit-value fall">{{ breadth.limit_down || 0 }}</span>
                </div>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-card>
    </div>

    <!-- 板块排行 -->
    <div class="sectors-section">
      <el-row :gutter="20">
        <!-- 行业板块 -->
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="sector-header">
                <span>行业板块</span>
                <el-button-group size="small">
                  <el-button
                      v-for="sort in sortOptions"
                      :key="sort.value"
                      :type="industrySortBy === sort.value ? 'primary' : ''"
                      @click="changeSectorSort('industry', sort.value)"
                  >
                    {{ sort.label }}
                  </el-button>
                </el-button-group>
              </div>
            </template>
            <div v-loading="loading.sectors" class="sector-list">
              <div
                  v-for="(sector, index) in industrySectors"
                  :key="sector.code"
                  class="sector-item"
              >
                <span class="sector-rank">{{ index + 1 }}</span>
                <span class="sector-name">{{ sector.name }}</span>
                <span :class="getChangeClass(sector.change_pct)" class="sector-change">
                  {{ sector.change_pct > 0 ? '+' : '' }}{{ sector.change_pct.toFixed(2) }}%
                </span>
                <span v-if="sector.leader" class="sector-leader">
                  {{ sector.leader.name }}
                </span>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 概念板块 -->
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="sector-header">
                <span>概念板块</span>
                <el-button-group size="small">
                  <el-button
                      v-for="sort in sortOptions"
                      :key="sort.value"
                      :type="conceptSortBy === sort.value ? 'primary' : ''"
                      @click="changeSectorSort('concept', sort.value)"
                  >
                    {{ sort.label }}
                  </el-button>
                </el-button-group>
              </div>
            </template>
            <div v-loading="loading.sectors" class="sector-list">
              <div
                  v-for="(sector, index) in conceptSectors"
                  :key="sector.code"
                  class="sector-item"
              >
                <span class="sector-rank">{{ index + 1 }}</span>
                <span class="sector-name">{{ sector.name }}</span>
                <span :class="getChangeClass(sector.change_pct)" class="sector-change">
                  {{ sector.change_pct > 0 ? '+' : '' }}{{ sector.change_pct.toFixed(2) }}%
                </span>
                <span v-if="sector.leader" class="sector-leader">
                  {{ sector.leader.name }}
                </span>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 异动监控 -->
    <div class="anomalies-section">
      <el-card>
        <template #header>
          <div class="anomalies-header">
            <span>异动监控</span>
            <el-radio-group v-model="anomalyType" size="small" @change="fetchAnomalies">
              <el-radio-button label="all">全部</el-radio-button>
              <el-radio-button label="limit_up">涨停</el-radio-button>
              <el-radio-button label="limit_down">跌停</el-radio-button>
              <el-radio-button label="price_surge">急拉</el-radio-button>
              <el-radio-button label="volume_spike">放量</el-radio-button>
            </el-radio-group>
          </div>
        </template>
        <el-table
            v-loading="loading.anomalies"
            :data="anomalies"
            height="400"
            stripe
        >
          <el-table-column label="代码" prop="symbol" width="80"/>
          <el-table-column label="名称" prop="name" width="100"/>
          <el-table-column label="现价" prop="price" width="80">
            <template #default="scope">
              {{ formatNumber(scope.row.price) }}
            </template>
          </el-table-column>
          <el-table-column label="涨跌幅" prop="change_pct" width="100">
            <template #default="scope">
              <span :class="getChangeClass(scope.row.change_pct)">
                {{ scope.row.change_pct > 0 ? '+' : '' }}{{ scope.row.change_pct.toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="成交额" prop="amount" width="120">
            <template #default="scope">
              {{ formatAmount(scope.row.amount) }}
            </template>
          </el-table-column>
          <el-table-column label="异动原因" prop="reason" width="100">
            <template #default="scope">
              <el-tag :type="getAnomalyTagType(scope.row.reason)" size="small">
                {{ scope.row.reason }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="时间" prop="timestamp">
            <template #default="scope">
              {{ formatTime(scope.row.timestamp) }}
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script>
import {Refresh} from '@element-plus/icons-vue'
import {getAnomalies, getMarketOverview, getSectors, refreshMarketData} from '@/api/market'

export default {
  name: 'Market',
  components: {
    Refresh
  },
  data() {
    return {
      // 加载状态
      loading: {
        overview: false,
        sectors: false,
        anomalies: false
      },

      // 数据
      indices: [],
      breadth: {},
      capital: {},
      industrySectors: [],
      conceptSectors: [],
      anomalies: [],

      // 配置
      industrySortBy: 'change_pct',
      conceptSortBy: 'change_pct',
      anomalyType: 'all',
      lastUpdateTime: null,

      // 排序选项
      sortOptions: [
        {label: '涨幅', value: 'change_pct'},
        {label: '成交额', value: 'amount'}
      ],

      // 进度条颜色
      customColors: [
        {color: '#f56c6c', percentage: 30},
        {color: '#e6a23c', percentage: 50},
        {color: '#5cb87a', percentage: 100}
      ],

      // 定时器
      refreshTimer: null
    }
  },
  mounted() {
    this.init()
    // 设置自动刷新
    this.startAutoRefresh()

    // 监听页面可见性变化
    document.addEventListener('visibilitychange', this.handleVisibilityChange)
  },
  beforeDestroy() {
    this.stopAutoRefresh()
    document.removeEventListener('visibilitychange', this.handleVisibilityChange)
  },
  methods: {
    async init() {
      await Promise.all([
        this.fetchOverview(),
        this.fetchSectors(),
        this.fetchAnomalies()
      ])
    },

    async fetchOverview() {
      this.loading.overview = true
      try {
        const res = await getMarketOverview()
        this.indices = res.indices || []
        this.breadth = res.breadth || {}
        this.capital = res.capital || {}
        this.lastUpdateTime = res.timestamp

        if (res.stale) {
          this.$message.warning('数据为缓存副本，正在恢复实时连接')
        }
      } catch (error) {
        console.error('获取市场概览失败:', error)
        this.$message.error('获取市场概览失败')
      } finally {
        this.loading.overview = false
      }
    },

    async fetchSectors() {
      this.loading.sectors = true
      try {
        // 并行获取行业和概念板块
        const [industryRes, conceptRes] = await Promise.all([
          getSectors({type: 'industry', sort: this.industrySortBy}),
          getSectors({type: 'concept', sort: this.conceptSortBy})
        ])

        this.industrySectors = industryRes || []
        this.conceptSectors = conceptRes || []
      } catch (error) {
        console.error('获取板块数据失败:', error)
        this.$message.error('获取板块数据失败')
      } finally {
        this.loading.sectors = false
      }
    },

    async fetchAnomalies() {
      this.loading.anomalies = true
      try {
        const res = await getAnomalies({kind: this.anomalyType})
        this.anomalies = res || []
      } catch (error) {
        console.error('获取异动数据失败:', error)
        this.$message.error('获取异动数据失败')
      } finally {
        this.loading.anomalies = false
      }
    },

    async changeSectorSort(type, sortBy) {
      if (type === 'industry') {
        this.industrySortBy = sortBy
      } else {
        this.conceptSortBy = sortBy
      }
      await this.fetchSectors()
    },

    async refreshAll() {
      try {
        await refreshMarketData('all')
        this.$message.success('市场数据已刷新')
        await this.init()
      } catch (error) {
        console.error('刷新失败:', error)
        this.$message.error('刷新失败')
      }
    },

    startAutoRefresh() {
      // 每5秒刷新概览，每30秒刷新板块，每15秒刷新异动
      this.refreshTimer = setInterval(() => {
        this.fetchOverview()

        // 每6次刷新板块（30秒）
        if (this.refreshCount % 6 === 0) {
          this.fetchSectors()
        }

        // 每3次刷新异动（15秒）
        if (this.refreshCount % 3 === 0) {
          this.fetchAnomalies()
        }

        this.refreshCount = (this.refreshCount || 0) + 1
      }, 5000)
    },

    stopAutoRefresh() {
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer)
        this.refreshTimer = null
      }
    },

    handleVisibilityChange() {
      if (document.hidden) {
        // 页面隐藏时停止刷新
        this.stopAutoRefresh()
      } else {
        // 页面显示时恢复刷新
        this.startAutoRefresh()
        this.init()
      }
    },

    getAdvanceDeclineRatio() {
      const total = this.breadth.advancers + this.breadth.decliners + this.breadth.unchanged
      if (total === 0) return 50
      return Math.round((this.breadth.advancers / total) * 100)
    },

    getChangeClass(value) {
      if (value > 0) return 'rise'
      if (value < 0) return 'fall'
      return 'flat'
    },

    getAnomalyTagType(reason) {
      const typeMap = {
        '涨停': 'danger',
        '跌停': 'success',
        '急速拉升': 'warning',
        '大单买入': 'primary',
        '放量突破': 'info'
      }
      return typeMap[reason] || 'info'
    },

    formatNumber(value) {
      if (!value) return '0.00'
      return Number(value).toFixed(2)
    },

    formatAmount(value) {
      if (!value) return '0'
      if (value >= 100000000) {
        return (value / 100000000).toFixed(2) + '亿'
      } else if (value >= 10000) {
        return (value / 10000).toFixed(2) + '万'
      }
      return value.toString()
    },

    formatTime(timestamp) {
      if (!timestamp) return ''
      const date = new Date(timestamp)
      return date.toLocaleTimeString('zh-CN')
    }
  }
}
</script>

<style scoped>
.market-container {
  padding: 20px;
  background: #0a0e1a;
  min-height: calc(100vh - 60px);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  color: #c9d1d9;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 15px;
}

.update-time {
  color: #8b949e;
  font-size: 14px;
}

/* 指数卡片 */
.indices-section {
  margin-bottom: 20px;
}

.index-card {
  background: #161b22 !important;
  border: 1px solid #30363d !important;
  transition: transform 0.3s;
}

.index-card:hover {
  transform: translateY(-5px);
  background: #1c2128 !important;
}

.index-card :deep(.el-card__body) {
  background: transparent;
  color: #c9d1d9;
}

.index-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.index-name {
  font-weight: bold;
  color: #c9d1d9;
}

.index-code {
  color: #8b949e;
  font-size: 12px;
}

.index-price {
  font-size: 28px;
  font-weight: bold;
  color: #c9d1d9;
  margin-bottom: 8px;
}

.index-change {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}

.index-volume {
  font-size: 12px;
  color: #8b949e;
}

/* 市场宽度 */
.breadth-section {
  margin-bottom: 20px;
}

.breadth-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.breadth-total {
  color: #8b949e;
  font-size: 14px;
}

.breadth-item {
  padding: 10px;
}

.breadth-label {
  font-size: 14px;
  color: #8b949e;
  margin-bottom: 15px;
}

.breadth-stats {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  font-size: 14px;
}

.stat-item {
  padding: 2px 8px;
  border-radius: 3px;
}

.limit-stats {
  display: flex;
  justify-content: space-around;
  margin-top: 20px;
}

.limit-item {
  text-align: center;
}

.limit-label {
  display: block;
  color: #8b949e;
  font-size: 14px;
  margin-bottom: 8px;
}

.limit-value {
  font-size: 24px;
  font-weight: bold;
}

/* 板块排行 */
.sectors-section {
  margin-bottom: 20px;
}

.sector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sector-list {
  max-height: 400px;
  overflow-y: auto;
}

.sector-item {
  display: flex;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid #30363d;
  transition: background 0.3s;
}

.sector-item:hover {
  background: #1c2128;
}

.sector-rank {
  width: 30px;
  text-align: center;
  color: #8b949e;
  font-size: 14px;
}

.sector-name {
  flex: 1;
  margin-left: 10px;
  color: #c9d1d9;
}

.sector-change {
  width: 80px;
  text-align: right;
  font-weight: bold;
}

.sector-leader {
  width: 100px;
  margin-left: 10px;
  color: #8b949e;
  font-size: 12px;
  text-align: right;
}

/* 异动监控 */
.anomalies-section {
  margin-bottom: 20px;
}

.anomalies-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 涨跌样式 */
.rise {
  color: #f56c6c;
}

.fall {
  color: #67c23a;
}

.flat {
  color: #909399;
}

/* 响应式 */
@media (max-width: 1200px) {
  .el-col-12 {
    width: 100%;
    margin-bottom: 20px;
  }
}

/* 全局卡片深色主题 */
.market-container :deep(.el-card) {
  background: #161b22 !important;
  border: 1px solid #30363d !important;
  color: #c9d1d9;
}

.market-container :deep(.el-card__header) {
  background: #0d1117;
  border-bottom: 1px solid #30363d;
  color: #c9d1d9;
}

.market-container :deep(.el-card__body) {
  background: transparent;
  color: #c9d1d9;
}

/* 表格深色主题 */
.market-container :deep(.el-table) {
  background: transparent;
  color: #c9d1d9;
}

.market-container :deep(.el-table th),
.market-container :deep(.el-table tr) {
  background: #161b22;
  color: #c9d1d9;
}

.market-container :deep(.el-table td),
.market-container :deep(.el-table th.is-leaf) {
  border-bottom: 1px solid #30363d;
}

.market-container :deep(.el-table--enable-row-hover .el-table__body tr:hover > td) {
  background: #1c2128;
}

/* 按钮深色主题 */
.market-container :deep(.el-button) {
  background: #21262d;
  border: 1px solid #30363d;
  color: #c9d1d9;
}

.market-container :deep(.el-button:hover) {
  background: #30363d;
  border-color: #484f58;
  color: #ffffff;
}

/* 按钮组深色主题 */
.market-container :deep(.el-button-group .el-button) {
  background: #21262d;
  border-color: #30363d;
  color: #8b949e;
}

.market-container :deep(.el-button-group .el-button.is-active) {
  background: #1f6feb;
  border-color: #1f6feb;
  color: #ffffff;
}

/* 标签深色主题 */
.market-container :deep(.el-tag) {
  background: #21262d;
  border: 1px solid #30363d;
  color: #c9d1d9;
}

/* 进度条深色主题 */
.market-container :deep(.el-progress__text) {
  color: #c9d1d9;
}

/* 修改涨跌颜色为更鲜明的红绿 */
.rise {
  color: #f85149 !important; /* 更鲜明的红色 */
  background: rgba(248, 81, 73, 0.1);
}

.fall {
  color: #3fb950 !important; /* 更鲜明的绿色 */
  background: rgba(63, 185, 80, 0.1);
}

.flat {
  color: #8b949e !important;
  background: rgba(139, 148, 158, 0.1);
}
</style>