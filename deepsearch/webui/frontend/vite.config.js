import {defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import {ElementPlusResolver} from 'unplugin-vue-components/resolvers'
import path from 'path'

export default defineConfig({
    plugins: [
        vue(),
        // 自动导入 Vue 和 Element Plus 相关函数
        AutoImport({
            imports: ['vue', 'vue-router', 'pinia'],
            resolvers: [ElementPlusResolver()],
            dts: 'src/auto-imports.d.ts'
        }),
        // 自动导入 Element Plus 组件
        Components({
            resolvers: [ElementPlusResolver()],
            dts: 'src/components.d.ts'
        })
    ],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, 'src')
        }
    },
    server: {
        port: 3000,
        proxy: {
            // 代理日志WebSocket
            '/api/logs/ws': {
                target: 'ws://localhost:8000',
                ws: true,
                changeOrigin: true
            },
            // 代理 API 请求到后端
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true
            },
            // 代理监控WebSocket
            '/ws': {
                target: 'ws://localhost:8000',
                ws: true,
                changeOrigin: true
            }
        }
    },
    build: {
        outDir: '../static',
        emptyOutDir: true
    }
})