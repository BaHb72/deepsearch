import React from 'react'
import { Card, Empty } from 'antd'
import { GlobalOutlined } from '@ant-design/icons'

const CacheSystem = () => {
  return (
    <div>
      <h1><GlobalOutlined /> 缓存系统监控</h1>
      <Card>
        <Empty description="缓存系统监控页面开发中..." />
      </Card>
    </div>
  )
}

export default CacheSystem