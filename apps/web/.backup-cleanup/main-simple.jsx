// 简化版React入口，用于开发测试
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, createBrowserRouter, RouterProvider } from 'react-router-dom'
import AppSimple from './AppSimple.jsx'

// 导入样式
import './styles/variables.css'
import 'antd/dist/reset.css'

// 创建带有future flags的路由器
const router = createBrowserRouter(
  [
    {
      path: "*",
      element: <AppSimple />
    }
  ],
  {
    future: {
      v7_startTransition: true,
      v7_relativeSplatPath: true,
    }
  }
)

// 创建React根节点
const root = ReactDOM.createRoot(document.getElementById('app'))

root.render(
    <React.StrictMode>
        <RouterProvider router={router} />
    </React.StrictMode>
)

console.log('React应用已启动')
