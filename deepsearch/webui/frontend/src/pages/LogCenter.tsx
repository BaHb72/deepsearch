import React from 'react'
import { Card, Empty } from 'antd'
import { FileTextOutlined } from '@ant-design/icons'

const LogCenter = () => {
  return (
    <div>
      <h1><FileTextOutlined /> 日志中心</h1>
      <Card>
        <Empty description="日志中心页面开发中..." />
      </Card>
    </div>
  )
}

export default LogCenter