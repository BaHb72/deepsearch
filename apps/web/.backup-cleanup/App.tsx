import React from 'react'
import { RouterProvider } from 'react-router-dom'
import { ConfigProvider, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { AppProvider } from '@/contexts/AppContext'
import ErrorBoundary from '@/components/common/ErrorBoundary'
import router from '@/router'
import 'dayjs/locale/zh-cn'
import './styles/index.scss'

const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AppProvider>
          <ConfigProvider locale={zhCN}>
            <AntApp>
              <RouterProvider router={router} />
            </AntApp>
          </ConfigProvider>
        </AppProvider>
      </ThemeProvider>
    </ErrorBoundary>
  )
}

export default App
