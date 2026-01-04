import React, { Component, ErrorInfo, ReactNode } from 'react'
import { Result, Button, Typography, Collapse, Space, Card } from 'antd'
import {
  ReloadOutlined,
  HomeOutlined,
  BugOutlined,
  CopyOutlined,
  QuestionCircleOutlined
} from '@ant-design/icons'
import { copyToClipboard } from '@/utils/clipboard'
import './index.scss'

// 扩展 Window 接口
declare global {
  interface Window {
    errorReporter?: {
      report: (data: unknown) => void
    }
  }
}

const { Paragraph, Text } = Typography
const { Panel } = Collapse

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
  showDetails?: boolean
  enableReport?: boolean
  resetKeys?: Array<string | number>
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  errorCount: number
  errorHistory: Array<{
    error: Error
    errorInfo: ErrorInfo
    timestamp: Date
  }>
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0,
      errorHistory: [],
    }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    const { onError, enableReport } = this.props

    // 记录错误历史
    this.setState(prevState => ({
      errorInfo,
      errorCount: prevState.errorCount + 1,
      errorHistory: [
        ...prevState.errorHistory,
        { error, errorInfo, timestamp: new Date() }
      ].slice(-5), // 只保留最近5条错误
    }))

    // 回调处理
    onError?.(error, errorInfo)

    // 错误上报
    if (enableReport) {
      this.reportError(error, errorInfo)
    }

    // 开发环境打印详细错误
    if (import.meta.env.DEV) {
      console.group('🚨 ErrorBoundary Caught Error')
      console.error('Error:', error)
      console.error('Error Info:', errorInfo)
      console.error('Component Stack:', errorInfo.componentStack)
      console.groupEnd()
    }
  }

  componentDidUpdate(prevProps: Props) {
    const { resetKeys } = this.props
    const { hasError } = this.state

    // 通过 resetKeys 的变化来重置错误状态
    if (hasError && prevProps.resetKeys !== resetKeys) {
      const hasResetKeyChanged = resetKeys?.some(
        (key, index) => key !== prevProps.resetKeys?.[index]
      )

      if (hasResetKeyChanged) {
        this.resetError()
      }
    }
  }

  // 错误上报
  reportError = async (error: Error, errorInfo: ErrorInfo) => {
    try {
      // 这里可以接入错误监控服务
      const errorData = {
        message: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
        url: window.location.href,
      }

      // 示例：发送到错误收集服务
      if (window.errorReporter) {
        window.errorReporter.report(errorData)
      }

      // 或者发送到后端
      // await fetch('/api/errors', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify(errorData),
      // })
    } catch (reportError) {
      console.error('Failed to report error:', reportError)
    }
  }

  // 重置错误状态
  resetError = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    })
  }

  // 刷新页面
  handleRefresh = () => {
    window.location.reload()
  }

  // 返回首页
  handleGoHome = () => {
    window.location.href = '/'
  }

  // 复制错误信息
  handleCopyError = () => {
    const { error, errorInfo } = this.state
    const errorText = `
Error: ${error?.message}
Stack: ${error?.stack}
Component Stack: ${errorInfo?.componentStack}
Time: ${new Date().toISOString()}
URL: ${window.location.href}
    `.trim()

    copyToClipboard(errorText)
  }

  // 渲染错误详情
  renderErrorDetails = () => {
    const { error, errorInfo, errorCount, errorHistory } = this.state
    const { showDetails = true } = this.props

    if (!showDetails) return null

    return (
      <Collapse
        ghost
        className="error-details-collapse"
        defaultActiveKey={import.meta.env.DEV ? ['1'] : []}
      >
        <Panel
          header="错误详情"
          key="1"
          extra={
            <Button
              size="small"
              icon={<CopyOutlined />}
              onClick={(e) => {
                e.stopPropagation()
                this.handleCopyError()
              }}
            >
              复制错误
            </Button>
          }
        >
          <Space direction="vertical" style={{ width: '100%' }}>
            <Card size="small" title="错误信息">
              <Paragraph>
                <Text strong>消息：</Text>
                <Text code>{error?.message}</Text>
              </Paragraph>
              <Paragraph>
                <Text strong>发生次数：</Text>
                <Text type="danger">{errorCount} 次</Text>
              </Paragraph>
              <Paragraph>
                <Text strong>时间：</Text>
                <Text>{new Date().toLocaleString()}</Text>
              </Paragraph>
            </Card>

            {error?.stack && (
              <Card size="small" title="错误堆栈">
                <Paragraph>
                  <pre className="error-stack">{error.stack}</pre>
                </Paragraph>
              </Card>
            )}

            {errorInfo?.componentStack && (
              <Card size="small" title="组件堆栈">
                <Paragraph>
                  <pre className="component-stack">{errorInfo.componentStack}</pre>
                </Paragraph>
              </Card>
            )}

            {errorHistory.length > 1 && (
              <Card size="small" title="错误历史">
                {errorHistory.map((item, index) => (
                  <Paragraph key={index}>
                    <Text type="secondary">
                      [{item.timestamp.toLocaleTimeString()}]
                    </Text>{' '}
                    <Text>{item.error.message}</Text>
                  </Paragraph>
                ))}
              </Card>
            )}
          </Space>
        </Panel>
      </Collapse>
    )
  }

  render() {
    const { hasError, error } = this.state
    const { children, fallback } = this.props

    if (hasError) {
      // 自定义降级UI
      if (fallback) {
        return <>{fallback}</>
      }

      // 默认错误UI
      return (
        <div className="error-boundary-container">
          <Result
            status="error"
            icon={<BugOutlined />}
            title="页面出现错误"
            subTitle={
              <Space direction="vertical">
                <Text>抱歉，页面遇到了一些问题。</Text>
                <Text type="secondary">{error?.message}</Text>
              </Space>
            }
            extra={[
              <Button
                type="primary"
                key="refresh"
                icon={<ReloadOutlined />}
                onClick={this.handleRefresh}
              >
                刷新页面
              </Button>,
              <Button
                key="home"
                icon={<HomeOutlined />}
                onClick={this.handleGoHome}
              >
                返回首页
              </Button>,
              <Button
                key="retry"
                onClick={this.resetError}
              >
                重试
              </Button>,
            ]}
          >
            {this.renderErrorDetails()}
          </Result>

          {/* 帮助信息 */}
          <Card className="help-card">
            <Space>
              <QuestionCircleOutlined />
              <Text>如果问题持续出现，请联系技术支持或查看</Text>
              <a href="/help" target="_blank" rel="noopener noreferrer">
                帮助文档
              </a>
            </Space>
          </Card>
        </div>
      )
    }

    return children
  }
}

// 创建带错误边界的高阶组件
export const withErrorBoundary = <P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Props
) => {
  const WrappedComponent = (props: P) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  )

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`

  return WrappedComponent
}

// 错误恢复 Hook
export const useErrorHandler = () => {
  return (error: Error, errorInfo?: ErrorInfo) => {
    console.error('useErrorHandler:', error, errorInfo)

    // 可以在这里进行错误处理
    // 例如：显示通知、上报错误等
    if (window.errorReporter) {
      window.errorReporter.report({
        error,
        errorInfo,
        timestamp: new Date().toISOString(),
      })
    }
  }
}

export default ErrorBoundary
