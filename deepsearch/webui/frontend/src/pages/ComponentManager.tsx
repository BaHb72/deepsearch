import React from 'react'
import { Card, Empty } from 'antd'
import { MonitorOutlined } from '@ant-design/icons'

const ComponentManager = () => {
  return (
    <div>
      <h1><MonitorOutlined /> 组件管理</h1>
      <Card>
        <Empty description="组件管理页面开发中..." />
      </Card>
    </div>
  )
}

export default ComponentManager