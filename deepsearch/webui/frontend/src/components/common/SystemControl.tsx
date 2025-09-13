import React from 'react'
import { Badge, Tooltip } from 'antd'
import { SyncOutlined } from '@ant-design/icons'

const SystemControl = ({ status, loading }) => {
  const getStatusColor = () => {
    if (!status) return 'default'
    return status.status === 'running' ? 'success' : 'error'
  }

  return (
    <Tooltip title="系统状态">
      <Badge 
        status={getStatusColor()} 
        text={status?.status || 'unknown'}
        icon={loading && <SyncOutlined spin />}
      />
    </Tooltip>
  )
}

export default SystemControl