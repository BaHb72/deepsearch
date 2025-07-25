<template>
  <div class="trading-view">
    <div class="page-header">
      <h1>交易管理</h1>
    </div>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>持仓信息</span>
              <el-button type="text" @click="refreshPositions">刷新</el-button>
            </div>
          </template>

          <el-table :data="positions" style="width: 100%">
            <el-table-column label="代码" prop="symbol" width="80"/>
            <el-table-column label="名称" prop="name" width="100"/>
            <el-table-column label="数量" prop="quantity" width="80"/>
            <el-table-column label="成本价" prop="avgPrice" width="80"/>
            <el-table-column label="现价" prop="currentPrice" width="80"/>
            <el-table-column label="盈亏" width="100">
              <template #default="scope">
                <span :class="scope.row.pnl >= 0 ? 'profit' : 'loss'">
                  {{ scope.row.pnl.toFixed(2) }} ({{ scope.row.pnlPercent.toFixed(2) }}%)
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>委托订单</span>
              <el-button type="text" @click="refreshOrders">刷新</el-button>
            </div>
          </template>

          <el-table :data="orders" style="width: 100%">
            <el-table-column label="订单号" prop="orderId" width="100"/>
            <el-table-column label="代码" prop="symbol" width="80"/>
            <el-table-column label="方向" prop="side" width="60">
              <template #default="scope">
                <el-tag :type="scope.row.side === 'BUY' ? 'success' : 'danger'" size="small">
                  {{ scope.row.side === 'BUY' ? '买入' : '卖出' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="价格" prop="price" width="80"/>
            <el-table-column label="数量" prop="quantity" width="80"/>
            <el-table-column label="状态" prop="status" width="80">
              <template #default="scope">
                <el-tag :type="getOrderStatusType(scope.row.status)" size="small">
                  {{ scope.row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="scope">
                <el-button
                    v-if="scope.row.status === 'PENDING'"
                    size="small"
                    type="text"
                    @click="cancelOrder(scope.row.orderId)"
                >
                  撤单
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>成交记录</span>
          </template>

          <el-table :data="trades" style="width: 100%">
            <el-table-column label="成交号" prop="tradeId" width="100"/>
            <el-table-column label="订单号" prop="orderId" width="100"/>
            <el-table-column label="代码" prop="symbol" width="80"/>
            <el-table-column label="方向" prop="side" width="60">
              <template #default="scope">
                <el-tag :type="scope.row.side === 'BUY' ? 'success' : 'danger'" size="small">
                  {{ scope.row.side === 'BUY' ? '买入' : '卖出' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="成交价" prop="price" width="80"/>
            <el-table-column label="成交量" prop="quantity" width="80"/>
            <el-table-column label="成交额" prop="amount" width="100"/>
            <el-table-column label="手续费" prop="fee" width="80"/>
            <el-table-column :formatter="formatTime" label="成交时间" prop="time" width="160"/>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>快速下单</span>
          </template>

          <el-form :model="orderForm" inline>
            <el-form-item label="代码">
              <el-input v-model="orderForm.symbol" style="width: 100px"/>
            </el-form-item>
            <el-form-item label="方向">
              <el-select v-model="orderForm.side" style="width: 80px">
                <el-option label="买入" value="BUY"/>
                <el-option label="卖出" value="SELL"/>
              </el-select>
            </el-form-item>
            <el-form-item label="价格">
              <el-input-number v-model="orderForm.price" :precision="2" :step="0.01"/>
            </el-form-item>
            <el-form-item label="数量">
              <el-input-number v-model="orderForm.quantity" :min="100" :step="100"/>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="submitOrder">提交订单</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import {ref, onMounted} from 'vue'
import {ElMessage} from 'element-plus'

const positions = ref([
  {
    symbol: 'AAPL',
    name: '苹果',
    quantity: 100,
    avgPrice: 150.50,
    currentPrice: 155.20,
    pnl: 470,
    pnlPercent: 3.12
  },
  {
    symbol: 'GOOGL',
    name: '谷歌',
    quantity: 50,
    avgPrice: 2800.00,
    currentPrice: 2750.00,
    pnl: -2500,
    pnlPercent: -1.79
  }
])

const orders = ref([
  {
    orderId: 'ORD001',
    symbol: 'MSFT',
    side: 'BUY',
    price: 300.00,
    quantity: 100,
    status: 'PENDING'
  },
  {
    orderId: 'ORD002',
    symbol: 'AAPL',
    side: 'SELL',
    price: 160.00,
    quantity: 50,
    status: 'FILLED'
  }
])

const trades = ref([
  {
    tradeId: 'TRD001',
    orderId: 'ORD002',
    symbol: 'AAPL',
    side: 'SELL',
    price: 160.00,
    quantity: 50,
    amount: 8000.00,
    fee: 8.00,
    time: new Date()
  }
])

const orderForm = ref({
  symbol: '',
  side: 'BUY',
  price: 0,
  quantity: 100
})

const getOrderStatusType = (status) => {
  const statusMap = {
    'PENDING': 'warning',
    'FILLED': 'success',
    'CANCELLED': 'info',
    'REJECTED': 'danger'
  }
  return statusMap[status] || 'info'
}

const formatTime = (row) => {
  return new Date(row.time).toLocaleString('zh-CN')
}

const refreshPositions = () => {
  ElMessage.success('持仓信息已刷新')
}

const refreshOrders = () => {
  ElMessage.success('委托订单已刷新')
}

const cancelOrder = (orderId) => {
  ElMessage.success(`订单 ${orderId} 已撤销`)
  const order = orders.value.find(o => o.orderId === orderId)
  if (order) {
    order.status = 'CANCELLED'
  }
}

const submitOrder = () => {
  if (!orderForm.value.symbol) {
    ElMessage.error('请输入股票代码')
    return
  }
  if (orderForm.value.price <= 0) {
    ElMessage.error('请输入有效价格')
    return
  }

  const newOrder = {
    orderId: `ORD${Date.now()}`,
    symbol: orderForm.value.symbol,
    side: orderForm.value.side,
    price: orderForm.value.price,
    quantity: orderForm.value.quantity,
    status: 'PENDING'
  }

  orders.value.unshift(newOrder)
  ElMessage.success('订单已提交')

  // 重置表单
  orderForm.value = {
    symbol: '',
    side: 'BUY',
    price: 0,
    quantity: 100
  }
}

onMounted(() => {
  // 可以在这里加载真实数据
})
</script>

<style scoped>
.trading-view {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.profit {
  color: #67c23a;
}

.loss {
  color: #f56c6c;
}
</style>