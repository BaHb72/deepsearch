import React from 'react'
import { Card, Empty } from 'antd'
import { MonitorOutlined } from '@ant-design/icons'

const Events = () => {
  return (
    <div>
      <h1><MonitorOutlined /> 事件管理</h1>
      <Card>
        <Empty description="事件管理页面正在开发中..." />
      </Card>
    </div>
  )
}

export default Events
