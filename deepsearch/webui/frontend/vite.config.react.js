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
    port: 3001, // 使用不同端口避免与 Vue 冲突
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
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'router': ['react-router-dom'],
          'state': ['zustand', 'immer'],
          'ui': ['antd', '@ant-design/icons'],
          'utils': ['axios', 'dayjs', 'lodash-es']
        }
      }
    }
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom', 'zustand', 'antd']
  }
})
