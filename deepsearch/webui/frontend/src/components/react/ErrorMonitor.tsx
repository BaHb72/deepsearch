import React, { useState, useEffect } from 'react'
import { Alert, Badge, Drawer, List, Typography, Button, Space, Tag } from 'antd'
import { CloseOutlined, BugOutlined, WarningOutlined, InfoCircleOutlined } from '@ant-design/icons'

const { Text, Paragraph } = Typography

const ErrorMonitor = () => {
  const [errors, setErrors] = useState([])
  const [visible, setVisible] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    // 监听全局错误
    const handleError = (event) => {
      const error = {
        id: Date.now(),
        type: 'error',
        message: event.message,
        source: `${event.filename}:${event.lineno}:${event.colno}`,
        stack: event.error?.stack,
        timestamp: new Date().toISOString(),
        read: false
      }
      
      setErrors(prev => [error, ...prev].slice(0, 50)) // 最多保留50条
      setUnreadCount(prev => prev + 1)
    }

    // 监听未处理的 Promise rejection
    const handleUnhandledRejection = (event) => {
      const error = {
        id: Date.now(),
        type: 'promise',
        message: event.reason?.message || String(event.reason),
        stack: event.reason?.stack,
        timestamp: new Date().toISOString(),
        read: false
      }
      
      setErrors(prev => [error, ...prev].slice(0, 50))
      setUnreadCount(prev => prev + 1)
    }

    window.addEventListener('error', handleError)
    window.addEventListener('unhandledrejection', handleUnhandledRejection)

    return () => {
      window.removeEventListener('error', handleError)
      window.removeEventListener('unhandledrejection', handleUnhandledRejection)
    }
  }, [])

  const handleOpen = () => {
    setVisible(true)
    // 标记所有错误为已读
    setErrors(prev => prev.map(e => ({ ...e, read: true })))
    setUnreadCount(0)
  }

  const handleClose = () => {
    setVisible(false)
  }

  const clearErrors = () => {
    setErrors([])
    setUnreadCount(0)
  }

  const getErrorIcon = (type) => {
    switch (type) {
      case 'error':
        return <BugOutlined style={{ color: '#ff4d4f' }} />
      case 'promise':
        return <WarningOutlined style={{ color: '#faad14' }} />
      default:
        return <InfoCircleOutlined style={{ color: '#1890ff' }} />
    }
  }

  const getErrorTag = (type) => {
    switch (type) {
      case 'error':
        return <Tag color="error">运行错误</Tag>
      case 'promise':
        return <Tag color="warning">Promise错误</Tag>
      default:
        return <Tag color="default">未知错误</Tag>
    }
  }

  if (errors.length === 0) {
    return null
  }

  return (
    <>
      {/* 浮动错误提示按钮 */}
      <div 
        style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          zIndex: 1000
        }}
      >
        <Badge count={unreadCount} offset={[-5, 5]}>
          <Button
            type="primary"
            danger
            shape="circle"
            size="large"
            icon={<BugOutlined />}
            onClick={handleOpen}
            style={{
              boxShadow: '0 4px 12px rgba(255, 77, 79, 0.3)'
            }}
          />
        </Badge>
      </div>

      {/* 错误详情抽屉 */}
      <Drawer
        title="错误监控"
        placement="right"
        width={500}
        onClose={handleClose}
        open={visible}
        extra={
          <Space>
            <Button size="small" onClick={clearErrors}>
              清空所有
            </Button>
            <Button 
              size="small" 
              type="text" 
              icon={<CloseOutlined />} 
              onClick={handleClose}
            />
          </Space>
        }
      >
        {errors.length === 0 ? (
          <Alert
            message="没有错误"
            description="当前没有捕获到任何错误"
            type="success"
            showIcon
          />
        ) : (
          <List
            dataSource={errors}
            renderItem={(error) => (
              <List.Item
                style={{
                  background: error.read ? 'transparent' : '#fff7e6',
                  padding: '12px',
                  marginBottom: '8px',
                  borderRadius: '4px',
                  border: '1px solid #f0f0f0'
                }}
              >
                <List.Item.Meta
                  avatar={getErrorIcon(error.type)}
                  title={
                    <Space>
                      {getErrorTag(error.type)}
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        {new Date(error.timestamp).toLocaleTimeString()}
                      </Text>
                    </Space>
                  }
                  description={
                    <div>
                      <Paragraph 
                        ellipsis={{ rows: 2, expandable: true }} 
                        style={{ marginBottom: 4 }}
                      >
                        {error.message}
                      </Paragraph>
                      {error.source && (
                        <Text type="secondary" style={{ fontSize: '12px' }}>
                          位置: {error.source}
                        </Text>
                      )}
                      {error.stack && (
                        <details style={{ marginTop: '8px' }}>
                          <summary style={{ cursor: 'pointer', color: '#1890ff' }}>
                            查看堆栈信息
                          </summary>
                          <pre style={{
                            fontSize: '12px',
                            background: '#f5f5f5',
                            padding: '8px',
                            borderRadius: '4px',
                            overflow: 'auto',
                            marginTop: '8px'
                          }}>
                            {error.stack}
                          </pre>
                        </details>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Drawer>
    </>
  )
}

export default ErrorMonitor