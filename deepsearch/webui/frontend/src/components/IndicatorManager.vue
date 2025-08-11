<template>
  <el-dialog
      v-model="dialogVisible"
      title="指标管理器"
      width="800px"
      @close="handleClose"
  >
    <div class="indicator-manager">
      <el-row :gutter="20">
        <!-- 左侧：可用指标列表 -->
        <el-col :span="12">
          <div class="panel">
            <div class="panel-header">
              <span>可用指标</span>
              <el-input
                  v-model="searchKeyword"
                  clearable
                  placeholder="搜索指标"
                  size="small"
                  style="width: 150px"
              >
                <template #prefix>
                  <el-icon>
                    <Search/>
                  </el-icon>
                </template>
              </el-input>
            </div>

            <div class="indicator-list">
              <el-collapse v-model="activeCategories">
                <!-- 主图指标 -->
                <el-collapse-item name="main" title="主图指标">
                  <div
                      v-for="indicator in filteredMainIndicators"
                      :key="indicator.name"
                      class="indicator-item"
                      @click="addIndicator(indicator)"
                  >
                    <span class="name">{{ indicator.label }}</span>
                    <el-icon class="add-icon">
                      <Plus/>
                    </el-icon>
                  </div>
                </el-collapse-item>

                <!-- 副图指标 -->
                <el-collapse-item name="sub" title="副图指标">
                  <div
                      v-for="indicator in filteredSubIndicators"
                      :key="indicator.name"
                      class="indicator-item"
                      @click="addIndicator(indicator)"
                  >
                    <span class="name">{{ indicator.label }}</span>
                    <el-icon class="add-icon">
                      <Plus/>
                    </el-icon>
                  </div>
                </el-collapse-item>

                <!-- 成交量指标 -->
                <el-collapse-item name="volume" title="成交量指标">
                  <div
                      v-for="indicator in filteredVolumeIndicators"
                      :key="indicator.name"
                      class="indicator-item"
                      @click="addIndicator(indicator)"
                  >
                    <span class="name">{{ indicator.label }}</span>
                    <el-icon class="add-icon">
                      <Plus/>
                    </el-icon>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>
          </div>
        </el-col>

        <!-- 右侧：已选指标列表 -->
        <el-col :span="12">
          <div class="panel">
            <div class="panel-header">
              <span>已选指标</span>
              <el-button size="small" text @click="clearAll">清空</el-button>
            </div>

            <div class="selected-list">
              <el-empty v-if="localSelectedIndicators.length === 0" description="暂未选择指标"/>

              <draggable
                  v-else
                  v-model="localSelectedIndicators"
                  animation="200"
                  handle=".drag-handle"
                  item-key="id"
              >
                <template #item="{ element, index }">
                  <div class="selected-item">
                    <el-icon class="drag-handle">
                      <Rank/>
                    </el-icon>

                    <div class="item-info">
                      <span class="name">{{ element.label || element.name }}</span>
                      <el-tag :type="getPaneTagType(element.pane)" size="small">
                        {{ getPaneLabel(element.pane) }}
                      </el-tag>
                    </div>

                    <div class="item-actions">
                      <el-button
                          size="small"
                          text
                          @click="editParams(index)"
                      >
                        参数
                      </el-button>
                      <el-button
                          size="small"
                          text
                          type="danger"
                          @click="removeIndicator(index)"
                      >
                        删除
                      </el-button>
                    </div>
                  </div>
                </template>
              </draggable>
            </div>

            <!-- 参数编辑区 -->
            <div v-if="editingIndex !== null" class="params-editor">
              <el-divider>参数设置</el-divider>
              <div v-for="(param, key) in editingParams" :key="key" class="param-item">
                <span class="param-label">{{ key }}</span>
                <el-input-number
                    v-if="param.type === 'number'"
                    v-model="param.value"
                    :max="param.max"
                    :min="param.min"
                    size="small"
                />
                <el-switch
                    v-else-if="param.type === 'boolean'"
                    v-model="param.value"
                    size="small"
                />
                <el-input
                    v-else-if="param.type === 'array'"
                    v-model="param.value"
                    placeholder="用逗号分隔"
                    size="small"
                />
                <el-input
                    v-else
                    v-model="param.value"
                    size="small"
                />
              </div>
              <div class="param-actions">
                <el-button size="small" @click="saveParams">保存</el-button>
                <el-button size="small" @click="cancelEdit">取消</el-button>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" @click="handleApply">应用</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script>
import {computed, onMounted, ref, watch} from 'vue'
import {ElMessage} from 'element-plus'
import {Plus, Rank, Search} from '@element-plus/icons-vue'
import draggable from 'vuedraggable'
import {getIndicatorList} from '@/api/chart'

export default {
  name: 'IndicatorManager',
  components: {
    draggable,
    Search,
    Plus,
    Rank
  },
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    selectedIndicators: {
      type: Array,
      default: () => []
    }
  },
  emits: ['close', 'apply'],
  setup(props, {emit}) {
    // 对话框显示状态
    const dialogVisible = ref(props.visible)

    // 指标列表
    const availableIndicators = ref([])
    const localSelectedIndicators = ref([])

    // 搜索和过滤
    const searchKeyword = ref('')
    const activeCategories = ref(['main', 'sub', 'volume'])

    // 参数编辑
    const editingIndex = ref(null)
    const editingParams = ref({})

    // 监听属性变化
    watch(() => props.visible, (val) => {
      dialogVisible.value = val
      if (val) {
        // 复制已选指标
        localSelectedIndicators.value = props.selectedIndicators.map((ind, idx) => ({
          ...ind,
          id: `${ind.name}_${idx}_${Date.now()}`
        }))
      }
    })

    // 过滤后的指标
    const filteredMainIndicators = computed(() => {
      return availableIndicators.value.filter(ind => {
        return ind.pane === 'main' &&
            (!searchKeyword.value || ind.label.includes(searchKeyword.value))
      })
    })

    const filteredSubIndicators = computed(() => {
      return availableIndicators.value.filter(ind => {
        return ind.pane === 'sub' &&
            (!searchKeyword.value || ind.label.includes(searchKeyword.value))
      })
    })

    const filteredVolumeIndicators = computed(() => {
      return availableIndicators.value.filter(ind => {
        return ind.category === 'volume' &&
            (!searchKeyword.value || ind.label.includes(searchKeyword.value))
      })
    })

    // 加载可用指标列表
    const loadIndicators = async () => {
      try {
        const list = await getIndicatorList()
        availableIndicators.value = list
      } catch (error) {
        console.error('加载指标列表失败:', error)
        // 使用默认列表
        availableIndicators.value = getDefaultIndicators()
      }
    }

    // 默认指标列表
    const getDefaultIndicators = () => {
      return [
        // 主图指标
        {name: 'MA', label: '移动平均线', pane: 'main', category: 'trend'},
        {name: 'EMA', label: '指数移动平均', pane: 'main', category: 'trend'},
        {name: 'BOLL', label: '布林带', pane: 'main', category: 'volatility'},
        {name: 'SAR', label: '抛物线SAR', pane: 'main', category: 'trend'},
        {name: 'VWAP', label: '成交量加权价', pane: 'main', category: 'volume'},

        // 副图指标
        {name: 'MACD', label: 'MACD', pane: 'sub', category: 'momentum'},
        {name: 'RSI', label: 'RSI', pane: 'sub', category: 'momentum'},
        {name: 'KDJ', label: 'KDJ', pane: 'sub', category: 'momentum'},
        {name: 'CCI', label: 'CCI', pane: 'sub', category: 'momentum'},
        {name: 'ATR', label: 'ATR', pane: 'sub', category: 'volatility'},
        {name: 'ADX', label: 'ADX', pane: 'sub', category: 'trend'},
        {name: 'BIAS', label: '乖离率', pane: 'sub', category: 'momentum'},

        // 成交量指标
        {name: 'Volume', label: '成交量', pane: 'sub', category: 'volume'},
        {name: 'OBV', label: 'OBV', pane: 'sub', category: 'volume'},
        {name: 'MFI', label: 'MFI', pane: 'sub', category: 'volume'},
        {name: 'VR', label: '量比', pane: 'sub', category: 'volume'}
      ]
    }

    // 添加指标
    const addIndicator = (indicator) => {
      // 检查是否已存在
      const exists = localSelectedIndicators.value.some(ind => ind.name === indicator.name)
      if (exists) {
        ElMessage.warning('该指标已添加')
        return
      }

      // 限制副图指标数量
      const subCount = localSelectedIndicators.value.filter(ind => ind.pane === 'sub').length
      if (indicator.pane === 'sub' && subCount >= 3) {
        ElMessage.warning('最多添加3个副图指标')
        return
      }

      // 添加指标
      localSelectedIndicators.value.push({
        ...indicator,
        id: `${indicator.name}_${Date.now()}`,
        params: getDefaultParams(indicator.name)
      })

      ElMessage.success('已添加指标')
    }

    // 移除指标
    const removeIndicator = (index) => {
      localSelectedIndicators.value.splice(index, 1)
      if (editingIndex.value === index) {
        editingIndex.value = null
        editingParams.value = {}
      }
    }

    // 清空所有
    const clearAll = () => {
      localSelectedIndicators.value = []
      editingIndex.value = null
      editingParams.value = {}
    }

    // 编辑参数
    const editParams = (index) => {
      editingIndex.value = index
      const indicator = localSelectedIndicators.value[index]

      // 准备参数编辑器
      const params = {}
      const defaultParams = getDefaultParams(indicator.name)

      Object.entries(defaultParams).forEach(([key, value]) => {
        params[key] = {
          value: indicator.params?.[key] || value,
          type: typeof value === 'number' ? 'number' :
              typeof value === 'boolean' ? 'boolean' :
                  Array.isArray(value) ? 'array' : 'string'
        }

        // 设置范围
        if (params[key].type === 'number') {
          params[key].min = 1
          params[key].max = 250
        }
      })

      editingParams.value = params
    }

    // 保存参数
    const saveParams = () => {
      if (editingIndex.value === null) return

      const params = {}
      Object.entries(editingParams.value).forEach(([key, param]) => {
        if (param.type === 'array') {
          params[key] = param.value.split(',').map(v => Number(v.trim()))
        } else {
          params[key] = param.value
        }
      })

      localSelectedIndicators.value[editingIndex.value].params = params

      editingIndex.value = null
      editingParams.value = {}

      ElMessage.success('参数已保存')
    }

    // 取消编辑
    const cancelEdit = () => {
      editingIndex.value = null
      editingParams.value = {}
    }

    // 获取默认参数
    const getDefaultParams = (name) => {
      const defaults = {
        MA: {periods: [5, 10, 20]},
        EMA: {periods: [12, 26]},
        BOLL: {period: 20, std: 2},
        MACD: {fast: 12, slow: 26, signal: 9},
        RSI: {period: 14},
        KDJ: {n: 9, m1: 3, m2: 3},
        CCI: {period: 14},
        ATR: {period: 14},
        ADX: {period: 14},
        MFI: {period: 14},
        SAR: {acceleration: 0.02, maximum: 0.2},
        BIAS: {period: 6},
        VR: {period: 5},
        VWAP: {sessionReset: true},
        Volume: {},
        OBV: {}
      }

      return defaults[name] || {}
    }

    // 获取面板标签
    const getPaneLabel = (pane) => {
      const labels = {
        main: '主图',
        sub: '副图',
        sub1: '副图1',
        sub2: '副图2',
        sub3: '副图3'
      }
      return labels[pane] || pane
    }

    // 获取面板标签类型
    const getPaneTagType = (pane) => {
      return pane === 'main' ? 'primary' : 'success'
    }

    // 处理关闭
    const handleClose = () => {
      dialogVisible.value = false
      emit('close')
    }

    // 处理应用
    const handleApply = () => {
      // 准备输出数据
      const indicators = localSelectedIndicators.value.map((ind, idx) => {
        // 分配副图位置
        let pane = ind.pane
        if (pane === 'sub') {
          const subIndex = localSelectedIndicators.value
              .slice(0, idx)
              .filter(i => i.pane === 'sub').length
          pane = `sub${subIndex + 1}`
        }

        return {
          name: ind.name,
          params: ind.params || {},
          pane: pane
        }
      })

      emit('apply', indicators)
      handleClose()
    }

    // 生命周期
    onMounted(() => {
      loadIndicators()
    })

    return {
      dialogVisible,
      availableIndicators,
      localSelectedIndicators,
      searchKeyword,
      activeCategories,
      editingIndex,
      editingParams,

      filteredMainIndicators,
      filteredSubIndicators,
      filteredVolumeIndicators,

      addIndicator,
      removeIndicator,
      clearAll,
      editParams,
      saveParams,
      cancelEdit,
      getPaneLabel,
      getPaneTagType,
      handleClose,
      handleApply
    }
  }
}
</script>

<style scoped>
.indicator-manager {
  height: 500px;
}

.panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.indicator-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.indicator-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  margin-bottom: 5px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.3s;
}

.indicator-item:hover {
  background: #f5f7fa;
}

.indicator-item .name {
  font-size: 14px;
}

.indicator-item .add-icon {
  color: #409eff;
  opacity: 0;
  transition: opacity 0.3s;
}

.indicator-item:hover .add-icon {
  opacity: 1;
}

.selected-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.selected-item {
  display: flex;
  align-items: center;
  padding: 10px;
  margin-bottom: 8px;
  background: #f5f7fa;
  border-radius: 4px;
}

.selected-item .drag-handle {
  cursor: move;
  margin-right: 10px;
  color: #909399;
}

.selected-item .item-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}

.selected-item .item-info .name {
  font-size: 14px;
  font-weight: 500;
}

.selected-item .item-actions {
  display: flex;
  gap: 5px;
}

/* 参数编辑器 */
.params-editor {
  padding: 15px;
  background: #fafafa;
  border-top: 1px solid #e4e7ed;
}

.param-item {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.param-label {
  width: 80px;
  font-size: 14px;
  color: #606266;
}

.param-actions {
  margin-top: 10px;
  text-align: right;
}

/* 对话框footer */
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>