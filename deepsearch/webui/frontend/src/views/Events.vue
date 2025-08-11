<template>
  <div class="events-view">
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">
          <el-icon class="title-icon">
            <List/>
          </el-icon>
          事件监控
        </h1>
        <p class="page-subtitle">实时监控系统事件流，跟踪所有交易活动</p>
      </div>
      <div class="header-actions">
        <el-button :disabled="events.length === 0" @click="clearEvents">
          <el-icon>
            <Delete/>
          </el-icon>
          清除所有
        </el-button>
        <el-button type="primary" @click="exportEvents">
          <el-icon>
            <Download/>
          </el-icon>
          导出日志
        </el-button>
      </div>
    </div>

    <el-card class="filter-card">
      <div class="filters">
        <el-input
            v-model="searchText"
            class="search-input"
            clearable
            placeholder="搜索事件内容..."
        >
          <template #prefix>
            <el-icon>
              <Search/>
            </el-icon>
          </template>
        </el-input>

        <el-select
            v-model="selectedType"
            class="type-select"
            clearable
            placeholder="选择事件类型"
        >
          <el-option
              v-for="type in eventTypes"
              :key="type"
              :value="type"
          >
            <span class="option-label">
              <el-icon :color="getTypeColor(type)"><Lightning/></el-icon>
              {{ type }}
            </span>
          </el-option>
        </el-select>

        <div class="filter-stats">
          <el-tag type="info">
            <el-icon>
              <DataAnalysis/>
            </el-icon>
            总计: {{ events.length }} 条
          </el-tag>
          <el-tag v-if="filteredEvents.length !== events.length" type="primary">
            <el-icon>
              <Filter/>
            </el-icon>
            筛选: {{ filteredEvents.length }} 条
          </el-tag>
        </div>
      </div>
    </el-card>

    <el-card class="events-card">
      <template v-if="filteredEvents.length > 0">
        <el-table
            :data="filteredEvents"
            class="events-table"
            max-height="600"
            stripe
        >
          <el-table-column
              fixed="left"
              label="时间"
              prop="timestamp"
              width="200"
          >
            <template #default="scope">
              <div class="time-cell">
                <el-icon class="time-icon">
                  <Clock/>
                </el-icon>
                <span class="time-text">{{ formatTime(scope.row) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column
              label="类型"
              prop="type"
              width="180"
          >
            <template #default="scope">
              <el-tag
                  :type="getTagType(scope.row.type)"
                  class="type-tag"
                  effect="dark"
              >
                <el-icon>
                  <Lightning/>
                </el-icon>
                {{ scope.row.type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
              label="数据内容"
              min-width="300"
              prop="data"
          >
            <template #default="scope">
              <div class="data-cell">
                <pre class="data-content">{{ formatDataPretty(scope.row.data) }}</pre>
              </div>
            </template>
          </el-table-column>
          <el-table-column
              fixed="right"
              label="操作"
              width="120"
          >
            <template #default="scope">
              <el-button
                  link
                  size="small"
                  type="primary"
                  @click="viewEventDetail(scope.row)"
              >
                <el-icon>
                  <View/>
                </el-icon>
                详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <template v-else>
        <el-empty description="暂无事件数据">
          <el-button type="primary" @click="mockEvents">
            生成模拟数据
          </el-button>
        </el-empty>
      </template>
    </el-card>
  </div>
</template>

<script setup>
import {computed, onMounted, onUnmounted, ref} from 'vue'
import {Clock, DataAnalysis, Delete, Download, Filter, Lightning, List, Search, View} from '@element-plus/icons-vue'
import {ElMessage, ElMessageBox} from 'element-plus'
import {useSystemStore} from '@/stores/system'

// 定义组件名称
defineOptions({
  name: 'Events'
})

const store = useSystemStore()
const events = ref([])
const searchText = ref('')
const selectedType = ref('')
const eventTypes = ref([])

// 模拟事件数据
const mockEvents = () => {
  const types = ['EVENT_TICK', 'EVENT_ORDER', 'EVENT_TRADE', 'EVENT_LOG', 'EVENT_ERROR']
  const event = {
    id: Date.now(),
    timestamp: new Date(),
    type: types[Math.floor(Math.random() * types.length)],
    data: {
      symbol: 'AAPL',
      price: 150 + Math.random() * 10,
      volume: Math.floor(Math.random() * 1000)
    }
  }
  events.value.unshift(event)
  if (events.value.length > 100) {
    events.value.pop()
  }
  updateEventTypes()
}

const updateEventTypes = () => {
  const types = new Set(events.value.map(e => e.type))
  eventTypes.value = Array.from(types)
}

const filteredEvents = computed(() => {
  return events.value.filter(event => {
    const matchesSearch = !searchText.value ||
        JSON.stringify(event).toLowerCase().includes(searchText.value.toLowerCase())
    const matchesType = !selectedType.value || event.type === selectedType.value
    return matchesSearch && matchesType
  })
})

const formatTime = (row) => {
  return new Date(row.timestamp).toLocaleString('zh-CN')
}

const formatData = (row) => {
  return JSON.stringify(row.data)
}

const formatDataPretty = (data) => {
  return JSON.stringify(data, null, 2)
}

const getTypeColor = (type) => {
  const colors = {
    'EVENT_TICK': '#409eff',
    'EVENT_ORDER': '#e6a23c',
    'EVENT_TRADE': '#67c23a',
    'EVENT_LOG': '#909399',
    'EVENT_ERROR': '#f56c6c'
  }
  return colors[type] || '#909399'
}

const viewEventDetail = (event) => {
  ElMessageBox.alert(
      `<pre>${JSON.stringify(event, null, 2)}</pre>`,
      '事件详情',
      {
        dangerouslyUseHTMLString: true,
        customClass: 'event-detail-dialog'
      }
  )
}

const getTagType = (type) => {
  if (type.includes('ERROR')) return 'danger'
  if (type.includes('TRADE')) return 'success'
  if (type.includes('ORDER')) return 'warning'
  return 'info'
}

const clearEvents = () => {
  events.value = []
  ElMessage.success('事件已清除')
}

const exportEvents = () => {
  const data = JSON.stringify(events.value, null, 2)
  const blob = new Blob([data], {type: 'application/json'})
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `events_${new Date().getTime()}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

let timer = null

onMounted(() => {
  // 模拟实时事件
  timer = setInterval(mockEvents, 2000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

<style lang="scss" scoped>
@use '@/assets/styles/design-tokens.scss' as tokens;

.events-view {
  padding: tokens.$spacing-6;
  background: var(--bg-color);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: tokens.$spacing-6;
  padding: tokens.$spacing-6;
  background: var(--card-bg);
  border-radius: tokens.$radius-xl;
  box-shadow: tokens.$shadow-sm;

  .header-content {
    .page-title {
      margin: 0 0 tokens.$spacing-2 0;
      font-size: tokens.$font-size-3xl;
      font-weight: tokens.$font-weight-bold;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: tokens.$spacing-3;

      .title-icon {
        font-size: 36px;
        @include tokens.gradient-text(tokens.$brand-primary, tokens.$brand-secondary);
      }
    }

    .page-subtitle {
      margin: 0;
      font-size: tokens.$font-size-base;
      color: var(--text-secondary);
      padding-left: 48px;
    }
  }

  .header-actions {
    display: flex;
    gap: tokens.$spacing-3;

    .el-button {
      padding: tokens.$spacing-2 tokens.$spacing-4;
      height: 40px;

      .el-icon {
        margin-right: tokens.$spacing-1;
      }
    }
  }
}

.filter-card {
  margin-bottom: tokens.$spacing-5;
  border-radius: tokens.$radius-lg;
  box-shadow: tokens.$shadow-sm;

  .filters {
    display: flex;
    align-items: center;
    gap: tokens.$spacing-4;
    flex-wrap: wrap;

    .search-input {
      flex: 1;
      min-width: 300px;

      :deep(.el-input__wrapper) {
        border-radius: tokens.$radius-base;
        transition: all tokens.$duration-fast;

        &:hover {
          box-shadow: tokens.$shadow-sm;
        }
      }
    }

    .type-select {
      width: 240px;

      .option-label {
        display: flex;
        align-items: center;
        gap: tokens.$spacing-2;

        .el-icon {
          font-size: 16px;
        }
      }
    }

    .filter-stats {
      display: flex;
      gap: tokens.$spacing-2;
      margin-left: auto;

      .el-tag {
        border-radius: tokens.$radius-full;
        padding: tokens.$spacing-1 tokens.$spacing-3;
        font-weight: tokens.$font-weight-medium;

        .el-icon {
          margin-right: tokens.$spacing-1;
        }
      }
    }
  }
}

.events-card {
  border-radius: tokens.$radius-lg;
  box-shadow: tokens.$shadow-sm;
  overflow: hidden;

  .events-table {
    :deep(.el-table__header) {
      th {
        background: var(--bg-color);
        font-weight: tokens.$font-weight-semibold;
        color: var(--text-primary);
      }
    }

    :deep(.el-table__row) {
      transition: all tokens.$duration-base;

      &:hover {
        background: rgba(tokens.$brand-primary, 0.02);
      }
    }

    .time-cell {
      display: flex;
      align-items: center;
      gap: tokens.$spacing-2;

      .time-icon {
        color: var(--text-secondary);
        font-size: 16px;
      }

      .time-text {
        font-family: tokens.$font-mono;
        font-size: tokens.$font-size-sm;
        color: var(--text-regular);
      }
    }

    .type-tag {
      border-radius: tokens.$radius-full;
      padding: tokens.$spacing-1 tokens.$spacing-3;
      font-weight: tokens.$font-weight-medium;

      .el-icon {
        margin-right: tokens.$spacing-1;
      }
    }

    .data-cell {
      .data-content {
        margin: 0;
        padding: tokens.$spacing-2;
        background: var(--bg-color);
        border-radius: tokens.$radius-base;
        font-family: tokens.$font-mono;
        font-size: tokens.$font-size-xs;
        color: var(--text-regular);
        max-height: 100px;
        overflow-y: auto;
        @include tokens.custom-scrollbar(6px, var(--bg-color), var(--border-color));
      }
    }
  }
}

/* 响应式 */
@media (max-width: tokens.$breakpoint-md) {
  .events-view {
    padding: tokens.$spacing-4;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: tokens.$spacing-4;

    .header-content {
      .page-title {
        font-size: tokens.$font-size-2xl;
      }
    }
  }

  .filter-card {
    .filters {
      .search-input {
        min-width: 100%;
      }

      .filter-stats {
        width: 100%;
        justify-content: center;
      }
    }
  }
}

/* 暗色主题 */
.dark {
  .filter-card,
  .events-card {
    @include tokens.dark-glassmorphism(0.95, 5px);
  }

  .events-table {
    .data-cell {
      .data-content {
        background: tokens.$dark-bg-tertiary;
      }
    }
  }
}

/* 事件详情弹窗样式 */
:global(.event-detail-dialog) {
  .el-message-box__content {
    pre {
      font-family: tokens.$font-mono;
      font-size: tokens.$font-size-sm;
      background: var(--bg-color);
      padding: tokens.$spacing-4;
      border-radius: tokens.$radius-base;
      overflow: auto;
      max-height: 60vh;
      @include tokens.custom-scrollbar(8px, var(--bg-color), var(--border-color));
    }
  }
}
</style>