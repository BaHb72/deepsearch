import { createLogger, defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

const proxyLogger = createLogger('info', { prefix: '[proxy]' })

export default defineConfig({
    plugins: [
        react()  // React支持
    ],
    // 优化配置
    optimizeDeps: {
        force: false,
        include: ['react', 'react-dom', 'antd'],
        esbuildOptions: {
            loader: {
                '.js': 'jsx',   // 允许在 .js 文件中使用 JSX
                '.jsx': 'jsx',  // JSX 文件
                '.ts': 'tsx',   // 允许在 .ts 文件中使用 TSX
                '.tsx': 'tsx'   // TSX 文件
            },
        },
    },

    // ESBuild 配置 - 支持 TypeScript
    esbuild: {
        loader: 'tsx',  // 默认使用 tsx loader
        include: /src\/.*\.[tj]sx?$/,  // 包含所有 ts/tsx/js/jsx 文件
        exclude: [],
    },

    // 解析配置
    resolve: {
        extensions: ['.tsx', '.ts', '.jsx', '.js', '.json'],  // 文件扩展名解析顺序
        alias: {
            '@': fileURLToPath(new URL('./src', import.meta.url)),
            '@components': fileURLToPath(new URL('./src/components', import.meta.url)),
            '@pages': fileURLToPath(new URL('./src/pages', import.meta.url)),
            '@hooks': fileURLToPath(new URL('./src/hooks', import.meta.url)),
            '@utils': fileURLToPath(new URL('./src/utils', import.meta.url)),
            '@api': fileURLToPath(new URL('./src/api', import.meta.url)),
            '@types': fileURLToPath(new URL('./src/types', import.meta.url))
        }
    },
    server: {
        host: '127.0.0.1',
        port: 3000,
        proxy: {
            // 代理日志WebSocket
            '/api/logs/ws': {
                target: 'ws://127.0.0.1:8000',
                ws: true,
                changeOrigin: true
            },
            '/api/system/logs/ws': {
                target: 'ws://127.0.0.1:8000',
                ws: true,
                changeOrigin: true
            },

            // 数据源日志 WebSocket
            '/api/data-source/logs': {
                target: 'ws://127.0.0.1:8000',
                ws: true,
                changeOrigin: true
            },
            // 代理 API 请求到后端
            '/api': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
                timeout: 30000,
                proxyTimeout: 30000,
                configure: (proxy) => {
                    proxy.on('error', (err, req) => {
                        proxyLogger.error(`[PROXY_ERROR] ${req?.url ?? 'unknown'}`, err)
                    });
                    proxy.on('proxyReq', (_proxyReq, req) => {
                        proxyLogger.info(`[PROXY_REQUEST] ${req?.url ?? 'unknown'}`)
                    });
                }
            },
            // 代理监控WebSocket
            '/ws': {
                target: 'ws://127.0.0.1:8000',
                ws: true,
                changeOrigin: true
            }
        }
    },
    css: {
        preprocessorOptions: {
            scss: {
                api: 'modern-compiler'  // 使用现代编译器 API，避免弃用警告
            }
        }
    },
    build: {
        outDir: '../static',
        emptyOutDir: true
    }
})
