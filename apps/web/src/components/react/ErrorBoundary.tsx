import React from 'react'
import { Result, Button } from 'antd'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(_error) {
    return { hasError: true }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
    this.setState({
      error,
      errorInfo
    })

    // 可以在这里发送错误到日志服务
    if (window.errorTracker) {
      window.errorTracker.logError(error, errorInfo)
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <Result
          status="error"
          title="页面出现错误"
          subTitle={this.state.error?.message || '抱歉，页面出现了一些问题'}
          extra={[
            <Button type="primary" key="reload" onClick={this.handleReset}>
              重新加载
            </Button>,
            <Button key="home" onClick={() => window.location.href = '/'}>
              返回首页
            </Button>
          ]}
        >
            {import.meta.env.DEV && (
            <div className="error-details" style={{
              textAlign: 'left',
              background: '#f5f5f5',
              padding: '20px',
              borderRadius: '4px',
              marginTop: '20px'
            }}>
              <h4>错误详情（仅开发环境显示）</h4>
              <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {this.state.error && this.state.error.toString()}
                {this.state.errorInfo && this.state.errorInfo.componentStack}
              </pre>
            </div>
          )}
        </Result>
      )
    }

    return this.props.children
  }
}

export { ErrorBoundary }
