import {defineStore} from 'pinia'
import {getSystemStatus} from '@/api/system'
import {getDatabaseStatus} from '@/api/database'
import {getCacheStatus} from '@/api/cache'
import backendStatus from '@/utils/backendStatus'

// 调试日志工具
const debugLog = (stage, message, data = null) => {
    const timestamp = new Date().toISOString()
    const logEntry = `[system.store ${timestamp}] ${stage}: ${message}`
    console.log('%c' + logEntry, 'color: #f56c6c; font-weight: bold;', data)
}

export const useSystemStore = defineStore('system', {
    state: () => ({
        status: {
            timestamp: null,
            engine: {
                running: false,
                uptime: 0,
                event_count: 0,
                queue_size: 0
            },
            monitor: {
                running: false,
                api_running: false
            },
            components: {}
        },
        components: [], // 组件状态列表
        // 数据库状态
        database: {
            main: {
                connected: false,
                status: 'unknown',
                connectionStatus: 'disconnected',
                config: {},
                timescaledbEnabled: false,
                lastHealthCheck: null,
                disconnectReason: null
            },
            cache: {
                connected: false,
                status: 'unknown',
                connectionStatus: 'disconnected',
                config: {},
                connectionInfo: {},
                lastHealthCheck: null,
                disconnectReason: null,
                health: null
            }
        },
        loading: false,
        error: null
    }),

    getters: {
        isRunning: (state) => state.status.engine?.running || false,
        uptime: (state) => state.status.engine?.uptime || 0,
        queueSize: (state) => state.status.engine?.queue_size || 0,
        // 数据库状态 getters
        isDatabaseConnected: (state) => state.database.main.connected,
        isCacheConnected: (state) => state.database.cache.connected,
        databaseStatus: (state) => state.database.main,
        cacheStatus: (state) => state.database.cache,
        // 检查是否有数据库连接问题
        hasDatabaseIssue: (state) => {
            // 从 components 检查数据库组件状态
            const dbComponent = state.components.find(c => c.name === 'database')
            if (dbComponent && dbComponent.config?.enabled !== false) {
                return !state.database.main.connected
            }
            return false
        },
        // 检查是否有缓存连接问题
        hasCacheIssue: (state) => {
            const cacheComponent = state.components.find(c => c.name === 'cache')
            if (cacheComponent && cacheComponent.config?.enabled !== false) {
                return !state.database.cache.connected
            }
            return false
        }
    },

    actions: {
        async fetchStatus(retryCount = 0) {
            debugLog('FETCH_STATUS', '开始获取系统状态', {retryCount})

            // 首先检查后端是否可用
            if (!backendStatus.isAvailable) {
                debugLog('BACKEND_CHECK', '后端不可用，跳过状态获取')
                this.error = '后端服务不可用'
                return
            }

            const startTime = Date.now()
            const maxRetries = 2
            
            try {
                this.loading = true
                this.error = null

                debugLog('API_CALL', '调用getSystemStatus')
                const data = await getSystemStatus()
                debugLog('API_CALL', 'getSystemStatus返回成功', {data})
                
                this.status = data

                // 并行获取数据库和缓存状态，避免串行等待
                debugLog('API_CALL', '并行获取数据库和缓存状态')
                const startTimeDb = Date.now()
                const [dbResult, cacheResult] = await Promise.allSettled([
                    this.fetchDatabaseStatus(),
                    this.fetchCacheStatus()
                ])
                const dbDuration = Date.now() - startTimeDb
                debugLog('API_CALL', `数据库和缓存状态获取完成，耗时: ${dbDuration}ms`)

                // 记录失败的状态获取
                if (dbResult.status === 'rejected') {
                    debugLog('API_ERROR', '数据库状态获取失败', {
                        error: dbResult.reason?.message || dbResult.reason,
                        code: dbResult.reason?.code,
                        response: dbResult.reason?.response
                    })
                }
                if (cacheResult.status === 'rejected') {
                    debugLog('API_ERROR', '缓存状态获取失败', {
                        error: cacheResult.reason?.message || cacheResult.reason,
                        code: cacheResult.reason?.code,
                        response: cacheResult.reason?.response
                    })
                }

                const duration = Date.now() - startTime
                debugLog('FETCH_STATUS', '系统状态获取完成', {
                    duration: `${duration}ms`,
                    status: this.status,
                    database: this.database
                })
                
            } catch (error) {
                const duration = Date.now() - startTime
                this.error = error.message

                debugLog('FETCH_STATUS_ERROR', '获取系统状态失败', {
                    duration: `${duration}ms`,
                    error: error.message,
                    stack: error.stack,
                    response: error.response?.data,
                    retryCount
                })

                // 如果是网络错误且还有重试次数，尝试重试
                if (retryCount < maxRetries && (
                    error.code === 'ECONNABORTED' ||
                    error.message.includes('Network Error') ||
                    error.message.includes('timeout')
                )) {
                    debugLog('RETRY', `第${retryCount + 1}次重试获取系统状态`)
                    await new Promise(resolve => setTimeout(resolve, 1000 * (retryCount + 1))) // 递增延迟
                    return this.fetchStatus(retryCount + 1)
                }
                
                console.error('获取系统状态失败:', error)
                throw error // 重新抛出错误，让调用方处理
            } finally {
                this.loading = false
                debugLog('FETCH_STATUS', '状态加载完成', {loading: false})
            }
        },

        // 更新组件状态
        updateComponents(components) {
            this.components = components
            // 从组件状态更新数据库连接状态
            this.updateDatabaseStatusFromComponents()

            // 从组件信息中更新缓存状态
            const cacheComponent = components.find(c => c.name === 'cache')
            if (cacheComponent) {
                // 合并组件状态和详细信息
                const info = cacheComponent.info || {}

                // 如果组件正在运行，清除错误信息
                const isRunning = cacheComponent.status === 'running'
                
                this.database.cache = {
                    connected: info.connected || false,
                    status: cacheComponent.status || 'unknown',
                    connectionStatus: info.connection_status || 'disconnected',
                    config: info.config || {},
                    connectionInfo: info.connection_info || {},
                    lastHealthCheck: info.last_health_check,
                    // 运行状态下清除断开原因
                    disconnectReason: isRunning ? null : (info.disconnect_reason || info.error_message || cacheComponent.error_message),
                    health: info.health || null,
                    // 保存原始错误信息
                    errorMessage: isRunning ? null : cacheComponent.error_message
                }

                // 如果组件状态是错误但没有断开原因，使用错误信息
                if (cacheComponent.status === 'error' && !this.database.cache.disconnectReason && cacheComponent.error_message) {
                    this.database.cache.disconnectReason = cacheComponent.error_message
                }
            }
        },

        // 获取数据库状态
        async fetchDatabaseStatus() {
            // 检查后端是否可用
            if (!backendStatus.isAvailable) {
                debugLog('DATABASE_CHECK', '后端不可用，跳过数据库状态获取')
                return null
            }

            const startTime = Date.now()
            try {
                debugLog('API_CALL', '调用getDatabaseStatus')
                const status = await getDatabaseStatus()
                const duration = Date.now() - startTime
                debugLog('API_CALL', `getDatabaseStatus返回成功，耗时: ${duration}ms`, {status})

                // 更新主数据库状态
                this.database.main = {
                    connected: status.connected || false,
                    status: status.status || 'unknown',
                    connectionStatus: status.connection_status || 'disconnected',
                    config: status.config || {},
                    timescaledbEnabled: status.timescaledb_enabled || false,
                    lastHealthCheck: status.last_health_check,
                    disconnectReason: status.disconnect_reason
                }

                // 如果有缓存状态，也更新
                if (status.cache) {
                    this.database.cache = {
                        connected: status.cache.connected || false,
                        status: status.cache.status || 'unknown',
                        config: status.cache.config || {}
                    }
                }

                return status
            } catch (error) {
                debugLog('DATABASE_ERROR', '获取数据库状态失败', {error: error.message})

                // 设置默认的错误状态，避免undefined
                this.database.main = {
                    connected: false,
                    status: 'error',
                    connectionStatus: 'error',
                    config: {},
                    timescaledbEnabled: false,
                    lastHealthCheck: null,
                    disconnectReason: error.message || '无法连接到数据库API'
                }
                
                // 失败时从组件状态推断
                this.updateDatabaseStatusFromComponents()

                // 不抛出错误，允许系统继续运行
                return null
            }
        },

        // 从组件状态更新数据库状态
        updateDatabaseStatusFromComponents() {
            const dbComponent = this.components.find(c => c.name === 'database')
            if (dbComponent) {
                const isConnected = dbComponent.status === 'running' &&
                    dbComponent.info?.connection_status === 'connected'

                this.database.main.connected = isConnected
                this.database.main.status = dbComponent.status || 'unknown'
                this.database.main.connectionStatus = dbComponent.info?.connection_status || 'disconnected'

                // 保留其他详细信息
                if (dbComponent.info) {
                    this.database.main.timescaledbEnabled = dbComponent.info.timescaledb_enabled || false
                    this.database.main.disconnectReason = dbComponent.info.disconnect_reason
                }
            }

            // 缓存状态通过单独的 API 调用更新，不从组件状态推断
        },

        // 更新数据库连接状态
        updateDatabaseConnection(connected, reason = null) {
            this.database.main.connected = connected
            this.database.main.connectionStatus = connected ? 'connected' : 'disconnected'
            if (!connected && reason) {
                this.database.main.disconnectReason = reason
            }
        },

        // 获取缓存状态
        async fetchCacheStatus() {
            // 检查后端是否可用
            if (!backendStatus.isAvailable) {
                debugLog('CACHE_CHECK', '后端不可用，跳过缓存状态获取')
                return null
            }
            
            try {
                const status = await getCacheStatus()

                // 更新缓存状态
                this.database.cache = {
                    connected: status.connected || false,
                    status: status.status || 'unknown',
                    connectionStatus: status.connection_status || 'disconnected',
                    config: status.config || {},
                    connectionInfo: status.connection_info || {},
                    lastHealthCheck: status.last_health_check,
                    disconnectReason: status.disconnect_reason,
                    health: status.health || null
                }

                return status
            } catch (error) {
                debugLog('CACHE_ERROR', '获取缓存状态失败', {error: error.message})

                // 设置默认的错误状态，避免undefined
                this.database.cache = {
                    connected: false,
                    status: 'error',
                    connectionStatus: 'error',
                    config: {},
                    connectionInfo: {},
                    lastHealthCheck: null,
                    disconnectReason: error.message || '无法连接到缓存API',
                    health: null
                }

                // 不抛出错误，允许系统继续运行
                return null
            }
        },

        // 更新缓存连接状态
        updateCacheConnection(connected, reason = null) {
            this.database.cache.connected = connected
            this.database.cache.connectionStatus = connected ? 'connected' : 'disconnected'
            if (!connected && reason) {
                this.database.cache.disconnectReason = reason
            }
        }
    }
})