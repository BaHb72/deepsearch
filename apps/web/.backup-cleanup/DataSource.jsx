import React from 'react'
import { Card, Empty } from 'antd'
import { DatabaseOutlined } from '@ant-design/icons'

const DataSource = () => {
  return (
    <div>
      <h1><DatabaseOutlined /> 数据源管理</h1>
      <Card>
        <Empty description="数据源管理页面正在开发中..." />
      </Card>
    </div>
  )
}

export default DataSource
