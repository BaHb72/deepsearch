import React from 'react'
import { Card, Empty } from 'antd'
import { LineChartOutlined } from '@ant-design/icons'

const Market = () => {
  return (
    <div>
      <h1><LineChartOutlined /> 市场数据</h1>
      <Card>
        <Empty description="市场数据页面正在开发中..." />
      </Card>
    </div>
  )
}

export default Market
