import { createLogger, defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

const proxyLogger = createLogger('info', { prefix: '[proxy]' })
const API_PROXY_TARGET = (process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000').trim()
const WS_PROXY_TARGET = (process.env.VITE_WS_PROXY_TARGET || API_PROXY_TARGET.replace(/^http/i, 'ws')).trim()
const BACKEND_GUARD_API_BYPASS_PREFIXES = [
    '/api/system/status',
    '/api/system/config',
    '/api/log/',
    '/api/notification/',
    '/api/market/live/',
]

const shouldBypassBackendGuard = (requestUrl: string): boolean =>
    BACKEND_GUARD_API_BYPASS_PREFIXES.some((prefix) => requestUrl.startsWith(prefix))

const extractSystemStatus = (payload: unknown): { ready?: unknown } | null => {
    if (!payload || typeof payload !== 'object') {
        return null
    }
    const envelope = payload as { data?: unknown; ready?: unknown }
    if (envelope.data && typeof envelope.data === 'object') {
        return envelope.data as { ready?: unknown }
    }
    return envelope
}

const createBackendGuardPlugin = (): Plugin => {
    let backendAvailable: boolean | null = null
    let lastProbeAt = 0
    let probing: Promise<void> | null = null
    const probeIntervalMs = 1500
    const probeTimeoutMs = 1200
    const healthUrl = new URL('/api/system/status', API_PROXY_TARGET).toString()

    const probeOnce = async (): Promise<void> => {
        if (probing) {
            await probing
            return
        }
        probing = (async () => {
            const controller = new AbortController()
            const timer = setTimeout(() => controller.abort(), probeTimeoutMs)
            let nextAvailable = false
            try {
                const response = await fetch(healthUrl, {
                    method: 'GET',
                    signal: controller.signal,
                    headers: { Accept: 'application/json' },
                })
                if (response.ok) {
                    const payload = await response.json().catch(() => null)
                    const statusPayload = extractSystemStatus(payload)
                    nextAvailable = Boolean(
                        statusPayload &&
                        statusPayload.ready === true
                    )
                } else {
                    nextAvailable = false
                }
            } catch {
                nextAvailable = false
            } finally {
                clearTimeout(timer)
            }

            if (backendAvailable !== nextAvailable) {
                backendAvailable = nextAvailable
                if (nextAvailable) {
                    proxyLogger.info(`[BACKEND_READY] ${API_PROXY_TARGET}`)
                } else {
                    proxyLogger.warn(`[BACKEND_UNAVAILABLE] ${API_PROXY_TARGET}`)
                }
            }
        })().finally(() => {
            probing = null
        })
        await probing
    }

    return {
        name: 'backend-availability-guard',
        configureServer(server) {
            server.middlewares.use(async (req, res, next) => {
                try {
                    const requestUrl = req.url || ''
                    const isApiReq = requestUrl.startsWith('/api/')
                    const isWsReq = requestUrl.startsWith('/ws')
                    if (!isApiReq && !isWsReq) {
                        next()
                        return
                    }

                    if (isApiReq && shouldBypassBackendGuard(requestUrl)) {
                        next()
                        return
                    }

                    const now = Date.now()
                    if (now - lastProbeAt >= probeIntervalMs || backendAvailable === null) {
                        lastProbeAt = now
                        await probeOnce()
                    }

                    if (backendAvailable === false) {
                        if (isWsReq) {
                            res.statusCode = 503
                            res.end('backend unavailable')
                            return
                        }

                        res.statusCode = 503
                        res.setHeader('Content-Type', 'application/json; charset=utf-8')
                        res.end(
                            JSON.stringify({
                                code: 'BACKEND_UNAVAILABLE_DEV_PROXY',
                                detail: '后端服务未就绪，请先启动后端',
                                proxy_target: API_PROXY_TARGET,
                            })
                        )
                        return
                    }

                    next()
                } catch (error) {
                    proxyLogger.error('[BACKEND_GUARD_ERROR]', error)
                    next()
                }
            })
        },
    }
}

export default defineConfig({
    plugins: [
        createBackendGuardPlugin(),
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
                target: WS_PROXY_TARGET,
                ws: true,
                changeOrigin: true
            },
            '/api/system/logs/ws': {
                target: WS_PROXY_TARGET,
                ws: true,
                changeOrigin: true
            },

            // 数据源日志 WebSocket
            '/api/data-source/logs': {
                target: WS_PROXY_TARGET,
                ws: true,
                changeOrigin: true
            },
            // 代理 API 请求到后端
            '/api': {
                target: API_PROXY_TARGET,
                changeOrigin: true,
                timeout: 30000,
                proxyTimeout: 30000,
                configure: (proxy) => {
                    proxy.on('error', (err, req) => {
                        proxyLogger.error(`[PROXY_ERROR] ${req?.url ?? 'unknown'}`, err)
                    });
                }
            },
            // 代理监控WebSocket
            '/ws': {
                target: WS_PROXY_TARGET,
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
