import React from 'react'
import { Card, Empty } from 'antd'
import { StockOutlined } from '@ant-design/icons'

const Trading = () => {
  return (
    <div>
      <h1><StockOutlined /> 交易管理</h1>
      <Card>
        <Empty description="交易管理页面正在开发中..." />
      </Card>
    </div>
  )
}

export default Trading
