<template>
  <div class="amazingdata-example">
    <h2>AmazingData API 示例</h2>

    <!-- 基础数据示例 -->
    <div class="section">
      <h3>基础数据</h3>
      <el-row :gutter="20">
        <el-col :span="12">
          <el-input
            v-model="stockCode"
            placeholder="输入股票代码（如600000）"
            @keyup.enter="fetchStockInfo"
          >
            <template #append>
              <el-button @click="fetchStockInfo">查询</el-button>
            </template>
          </el-input>
        </el-col>
        <el-col :span="12">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />
        </el-col>
      </el-row>
    </div>

    <!-- K线数据示例 -->
    <div class="section">
      <h3>历史K线</h3>
      <el-button @click="fetchKLineData" :loading="loading.kline">
        获取K线数据
      </el-button>
      <div v-if="klineData.length > 0" class="data-preview">
        <el-table :data="klineData.slice(0, 10)" stripe>
          <el-table-column prop="date" label="日期" width="120" />
          <el-table-column prop="open" label="开盘价" width="100" />
          <el-table-column prop="high" label="最高价" width="100" />
          <el-table-column prop="low" label="最低价" width="100" />
          <el-table-column prop="close" label="收盘价" width="100" />
          <el-table-column prop="volume" label="成交量" />
        </el-table>
      </div>
    </div>

    <!-- 实时行情订阅示例 -->
    <div class="section">
      <h3>实时行情</h3>
      <el-button @click="subscribeRealtime" :loading="loading.realtime">
        {{ isSubscribed ? '取消订阅' : '订阅实时行情' }}
      </el-button>
      <div v-if="realtimeData" class="realtime-data">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="股票代码">
            {{ realtimeData.code }}
          </el-descriptions-item>
          <el-descriptions-item label="股票名称">
            {{ realtimeData.name }}
          </el-descriptions-item>
          <el-descriptions-item label="最新价">
            <span :class="getPriceClass(realtimeData.change)">
              {{ realtimeData.price }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="涨跌额">
            <span :class="getPriceClass(realtimeData.change)">
              {{ realtimeData.change }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="涨跌幅">
            <span :class="getPriceClass(realtimeData.change)">
              {{ realtimeData.changePercent }}%
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="成交量">
            {{ formatVolume(realtimeData.volume) }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </div>

    <!-- 融资融券数据示例 -->
    <div class="section">
      <h3>融资融券</h3>
      <el-button @click="fetchMarginData" :loading="loading.margin">
        获取融资融券数据
      </el-button>
      <div v-if="marginData" class="data-preview">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="融资余额">
            {{ formatAmount(marginData.financeBalance) }}
          </el-descriptions-item>
          <el-descriptions-item label="融券余额">
            {{ formatAmount(marginData.securitiesBalance) }}
          </el-descriptions-item>
          <el-descriptions-item label="融资买入额">
            {{ formatAmount(marginData.financeBuy) }}
          </el-descriptions-item>
          <el-descriptions-item label="融券卖出量">
            {{ formatVolume(marginData.securitiesSell) }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </div>

    <!-- 龙虎榜数据示例 -->
    <div class="section">
      <h3>龙虎榜</h3>
      <el-button @click="fetchLongHuBangData" :loading="loading.longHuBang">
        获取今日龙虎榜
      </el-button>
      <div v-if="longHuBangData.length > 0" class="data-preview">
        <el-table :data="longHuBangData" stripe>
          <el-table-column prop="code" label="代码" width="100" />
          <el-table-column prop="name" label="名称" width="100" />
          <el-table-column prop="changePercent" label="涨跌幅" width="100">
            <template #default="{ row }">
              <span :class="getPriceClass(row.changePercent)">
                {{ row.changePercent }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="上榜原因" />
          <el-table-column prop="buyAmount" label="买入金额" width="120">
            <template #default="{ row }">
              {{ formatAmount(row.buyAmount) }}
            </template>
          </el-table-column>
          <el-table-column prop="sellAmount" label="卖出金额" width="120">
            <template #default="{ row }">
              {{ formatAmount(row.sellAmount) }}
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import amazingDataAPI from '@/api/amazingdata'

export default {
  name: 'AmazingDataExample',

  setup() {
    // 响应式数据
    const stockCode = ref('600000')
    const dateRange = ref([])
    const klineData = ref([])
    const realtimeData = ref(null)
    const marginData = ref(null)
    const longHuBangData = ref([])
    const isSubscribed = ref(false)
    const ws = ref(null)

    const loading = ref({
      kline: false,
      realtime: false,
      margin: false,
      longHuBang: false
    })

    // 获取K线数据
    const fetchKLineData = async () => {
      loading.value.kline = true
      try {
        const code = amazingDataAPI.formatCode(stockCode.value)
        const params = {
          code,
          period: 'daily',
          adjust: 'qfq'
        }

        if (dateRange.value && dateRange.value.length === 2) {
          params.start_date = dateRange.value[0]
          params.end_date = dateRange.value[1]
        }

        const res = await amazingDataAPI.history.queryKLine(params)
        klineData.value = res.data || []
        ElMessage.success('K线数据获取成功')
      } catch (error) {
        ElMessage.error('获取K线数据失败: ' + error.message)
      } finally {
        loading.value.kline = false
      }
    }

    // 订阅实时行情
    const subscribeRealtime = async () => {
      if (isSubscribed.value) {
        // 取消订阅
        if (ws.value) {
          ws.value.close()
          ws.value = null
        }
        await amazingDataAPI.realtime.unsubscribe()
        isSubscribed.value = false
        realtimeData.value = null
        ElMessage.success('已取消订阅')
        return
      }

      loading.value.realtime = true
      try {
        const code = amazingDataAPI.formatCode(stockCode.value)

        // 订阅股票
        await amazingDataAPI.realtime.subscribeStock({ codes: [code] })

        // 创建WebSocket连接
        ws.value = amazingDataAPI.createWebSocket(
          (data) => {
            // 处理实时数据
            if (data.type === 'snapshot' && data.code === code) {
              realtimeData.value = data
            }
          },
          (error) => {
            ElMessage.error('WebSocket连接错误')
          }
        )

        isSubscribed.value = true
        ElMessage.success('订阅成功，等待数据推送...')
      } catch (error) {
        ElMessage.error('订阅失败: ' + error.message)
      } finally {
        loading.value.realtime = false
      }
    }

    // 获取融资融券数据
    const fetchMarginData = async () => {
      loading.value.margin = true
      try {
        const code = amazingDataAPI.formatCode(stockCode.value)
        const res = await amazingDataAPI.margin.getMarginDetail({ code })
        marginData.value = res.data && res.data[0] || null
        ElMessage.success('融资融券数据获取成功')
      } catch (error) {
        ElMessage.error('获取融资融券数据失败: ' + error.message)
      } finally {
        loading.value.margin = false
      }
    }

    // 获取龙虎榜数据
    const fetchLongHuBangData = async () => {
      loading.value.longHuBang = true
      try {
        const res = await amazingDataAPI.margin.getLongHuBang({ limit: 20 })
        longHuBangData.value = res.data || []
        ElMessage.success('龙虎榜数据获取成功')
      } catch (error) {
        ElMessage.error('获取龙虎榜数据失败: ' + error.message)
      } finally {
        loading.value.longHuBang = false
      }
    }

    // 获取股票信息
    const fetchStockInfo = async () => {
      try {
        const code = amazingDataAPI.formatCode(stockCode.value)
        const res = await amazingDataAPI.basic.getStockBasic({ code })
        ElMessage.success('股票信息获取成功')
        console.log('股票信息:', res.data)
      } catch (error) {
        ElMessage.error('获取股票信息失败: ' + error.message)
      }
    }

    // 工具方法
    const getPriceClass = (value) => {
      if (value > 0) return 'price-up'
      if (value < 0) return 'price-down'
      return 'price-flat'
    }

    const formatAmount = (value) => {
      if (!value) return '-'
      return (value / 100000000).toFixed(2) + '亿'
    }

    const formatVolume = (value) => {
      if (!value) return '-'
      if (value > 100000000) return (value / 100000000).toFixed(2) + '亿'
      if (value > 10000) return (value / 10000).toFixed(2) + '万'
      return value
    }

    // 清理
    onUnmounted(() => {
      if (ws.value) {
        ws.value.close()
      }
    })

    return {
      stockCode,
      dateRange,
      klineData,
      realtimeData,
      marginData,
      longHuBangData,
      isSubscribed,
      loading,
      fetchKLineData,
      subscribeRealtime,
      fetchMarginData,
      fetchLongHuBangData,
      fetchStockInfo,
      getPriceClass,
      formatAmount,
      formatVolume
    }
  }
}
</script>

<style lang="scss" scoped>
.amazingdata-example {
  padding: 20px;

  .section {
    margin-bottom: 30px;
    padding: 20px;
    background: #fff;
    border-radius: 4px;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);

    h3 {
      margin-bottom: 20px;
      font-size: 16px;
      font-weight: 600;
    }
  }

  .data-preview {
    margin-top: 20px;
  }

  .realtime-data {
    margin-top: 20px;
  }

  .price-up {
    color: #f56c6c;
  }

  .price-down {
    color: #67c23a;
  }

  .price-flat {
    color: #909399;
  }
}
</style>