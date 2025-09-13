import React from 'react'
import { Card, Empty } from 'antd'
import { BarChartOutlined } from '@ant-design/icons'

const PerformanceAnalytics = () => {
  return (
    <div>
      <h1><BarChartOutlined /> 性能分析</h1>
      <Card>
        <Empty description="性能分析页面开发中..." />
      </Card>
    </div>
  )
}

export default PerformanceAnalytics