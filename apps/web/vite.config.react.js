import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'

// 自定义插件：使用 React HTML 文件
const createReactHtmlPlugin = () => ({
  name: 'use-react-html',
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      if (req.url === '/' || req.url === '/index.html') {
        req.url = '/index-react.html'
      }
      next()
    })
  },
  transformIndexHtml: {
    order: 'pre',
    handler(html, ctx) {
      if (ctx.filename.endsWith('index.html') && !ctx.filename.endsWith('index-react.html')) {
        // 读取 React HTML 文件
        const reactHtmlPath = path.resolve(__dirname, 'index-react.html')
        if (fs.existsSync(reactHtmlPath)) {
          return fs.readFileSync(reactHtmlPath, 'utf-8')
        }
      }
      return html
    }
  }
})

const resolveVendorChunk = id => {
  const normalizedId = id.replace(/\\/g, '/')
  const nodeModuleIndex = normalizedId.lastIndexOf('/node_modules/')
  if (nodeModuleIndex === -1) {
    return undefined
  }

  const packageId = normalizedId.slice(nodeModuleIndex + '/node_modules/'.length)
  if (packageId.startsWith('react/') || packageId.startsWith('react-dom/')) {
    return 'react-vendor'
  }
  if (packageId.startsWith('react-router-dom/')) {
    return 'router-vendor'
  }
  if (packageId.startsWith('zustand/') || packageId.startsWith('immer/')) {
    return 'state-vendor'
  }
  if (packageId.startsWith('@tanstack/react-query/')) {
    return 'query-vendor'
  }
  if (
    packageId.startsWith('@ant-design/charts/') ||
    packageId.startsWith('@antv/') ||
    packageId.startsWith('echarts/') ||
    packageId.startsWith('echarts-for-react/') ||
    packageId.startsWith('lightweight-charts/')
  ) {
    return 'charts-vendor'
  }
  if (
    packageId.startsWith('antd/') ||
    packageId.startsWith('@ant-design/') ||
    packageId.startsWith('@rc-component/') ||
    packageId.startsWith('rc-')
  ) {
    return 'antd-vendor'
  }
  if (
    packageId.startsWith('axios/') ||
    packageId.startsWith('dayjs/') ||
    packageId.startsWith('lodash-es/')
  ) {
    return 'utils-vendor'
  }
  return undefined
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    createReactHtmlPlugin(),
    react({
      // 启用 Fast Refresh
      fastRefresh: true,
      // 支持自动导入 React
      jsxImportSource: 'react'
    })
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@views': path.resolve(__dirname, './src/views'),
      '@stores': path.resolve(__dirname, './src/stores'),
      '@utils': path.resolve(__dirname, './src/utils'),
      '@api': path.resolve(__dirname, './src/api'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@styles': path.resolve(__dirname, './src/styles')
    },
    extensions: ['.js', '.jsx', '.ts', '.tsx', '.json']
  },
  server: {
    port: parseInt(process.env.VITE_PORT || '3000'), // dev: 3000, prod: 3001
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    },
    // 配置开发服务器使用的 HTML 文件
    fs: {
      strict: false
    }
  },
  build: {
    outDir: 'dist-react',
    sourcemap: true,
    rollupOptions: {
      input: path.resolve(__dirname, 'index-react.html'),
      output: {
        manualChunks: resolveVendorChunk
      }
    }
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom', 'zustand', 'antd']
  }
})
