import React from 'react'
import { Result, Button, Collapse, Typography } from 'antd'
import { ReloadOutlined, BugOutlined } from '@ant-design/icons'
import { captureError } from '../utils/errorHandler'

const { Panel } = Collapse
const { Text, Paragraph } = Typography

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0
    }
  }

  static getDerivedStateFromError(_error) {
    // 更新 state 使下一次渲染能够显示降级后的 UI
    return { hasError: true }
  }

  componentDidCatch(error, errorInfo) {
    // 记录错误到错误处理器
    captureError(error, {
      componentStack: errorInfo.componentStack,
      props: this.props
    })

    // 更新错误计数
    this.setState(prevState => ({
      error,
      errorInfo,
      errorCount: prevState.errorCount + 1
    }))

    // 开发环境打印详细错误
    if (process.env.NODE_ENV === 'development') {
      console.group('🔴 React Error Boundary')
      console.error('Error:', error)
      console.error('Error Info:', errorInfo)
      console.groupEnd()
    }
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    })
    
    // 如果提供了重置回调，执行它
    if (this.props.onReset) {
      this.props.onReset()
    }
  }

  handleReload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      const { error, errorInfo, errorCount } = this.state
      const isDev = process.env.NODE_ENV === 'development'

      // 如果错误次数过多，显示更严重的错误页面
      if (errorCount > 3) {
        return (
          <Result
            status="error"
            title="系统遇到严重错误"
            subTitle="多次尝试恢复失败，请刷新页面或联系技术支持"
            extra={[
              <Button 
                type="primary" 
                key="reload" 
                icon={<ReloadOutlined />}
                onClick={this.handleReload}
              >
                刷新页面
              </Button>
            ]}
          />
        )
      }

      return (
        <div style={{ 
          padding: '50px', 
          background: '#f0f2f5', 
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <div style={{ maxWidth: 800, width: '100%' }}>
            <Result
              status="warning"
              icon={<BugOutlined style={{ color: '#faad14' }} />}
              title="页面遇到了一些问题"
              subTitle={
                <div>
                  <Paragraph>
                    系统检测到异常，已自动记录错误信息。
                    {!isDev && '请尝试重新加载或返回上一页。'}
                  </Paragraph>
                  {isDev && (
                    <Paragraph type="secondary" style={{ fontSize: 12 }}>
                      开发模式：错误详情已在下方显示
                    </Paragraph>
                  )}
                </div>
              }
              extra={[
                <Button 
                  type="primary" 
                  key="retry" 
                  onClick={this.handleReset}
                >
                  重试
                </Button>,
                <Button 
                  key="reload" 
                  icon={<ReloadOutlined />}
                  onClick={this.handleReload}
                >
                  刷新页面
                </Button>
              ]}
            >
              {/* 开发环境显示错误详情 */}
              {isDev && error && (
                <Collapse 
                  ghost 
                  style={{ marginTop: 24, textAlign: 'left' }}
                  defaultActiveKey={['1']}
                >
                  <Panel header="错误详情" key="1">
                    <div style={{ 
                      background: '#fff', 
                      padding: 16, 
                      borderRadius: 4,
                      border: '1px solid #ffd591'
                    }}>
                      <Text strong style={{ color: '#fa8c16' }}>
                        {error.toString()}
                      </Text>
                      {errorInfo && (
                        <pre style={{ 
                          marginTop: 12,
                          padding: 12,
                          background: '#f6f6f6',
                          borderRadius: 4,
                          fontSize: 12,
                          overflow: 'auto',
                          maxHeight: 300
                        }}>
                          {errorInfo.componentStack}
                        </pre>
                      )}
                    </div>
                  </Panel>
                </Collapse>
              )}
            </Result>
          </div>
        </div>
      )
    }

    // 正常渲染子组件
    return this.props.children
  }
}

// 带有后备UI的错误边界
export function withErrorBoundary(Component, fallback) {
  return function WithErrorBoundaryComponent(props) {
    return (
      <ErrorBoundary fallback={fallback}>
        <Component {...props} />
      </ErrorBoundary>
    )
  }
}

export default ErrorBoundary