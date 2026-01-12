import React from 'react'
import { Card, Empty } from 'antd'
import { FileTextOutlined } from '@ant-design/icons'

const Logs = () => {
  return (
    <div>
      <h1><FileTextOutlined /> 系统日志</h1>
      <Card>
        <Empty description="日志页面正在开发中..." />
      </Card>
    </div>
  )
}

export default Logs
