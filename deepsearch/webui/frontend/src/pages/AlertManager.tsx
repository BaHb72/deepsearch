import React from 'react'
import { Card, Empty } from 'antd'
import { BellOutlined } from '@ant-design/icons'

const AlertManager = () => {
  return (
    <div>
      <h1><BellOutlined /> 告警管理</h1>
      <Card>
        <Empty description="告警管理页面开发中..." />
      </Card>
    </div>
  )
}

export default AlertManager