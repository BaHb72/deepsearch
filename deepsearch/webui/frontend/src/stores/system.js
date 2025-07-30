import {defineStore} from 'pinia'
import {getSystemStatus} from '@/api/system'
import {getDatabaseStatus} from '@/api/database'

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
                config: {}
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
        }
    },

    actions: {
        async fetchStatus() {
            try {
                this.loading = true
                this.error = null
                const data = await getSystemStatus()
                this.status = data
                // 同时获取数据库状态
                await this.fetchDatabaseStatus()
            } catch (error) {
                this.error = error.message
                console.error('获取系统状态失败:', error)
            } finally {
                this.loading = false
            }
        },

        // 更新组件状态
        updateComponents(components) {
            this.components = components
            // 从组件状态更新数据库连接状态
            this.updateDatabaseStatusFromComponents()
        },

        // 获取数据库状态
        async fetchDatabaseStatus() {
            try {
                const status = await getDatabaseStatus()

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
                console.error('获取数据库状态失败:', error)
                // 失败时从组件状态推断
                this.updateDatabaseStatusFromComponents()
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

            // 更新缓存状态
            const cacheComponent = this.components.find(c => c.name === 'cache')
            if (cacheComponent) {
                this.database.cache.connected = cacheComponent.status === 'running'
                this.database.cache.status = cacheComponent.status || 'unknown'
            }
        },

        // 更新数据库连接状态
        updateDatabaseConnection(connected, reason = null) {
            this.database.main.connected = connected
            this.database.main.connectionStatus = connected ? 'connected' : 'disconnected'
            if (!connected && reason) {
                this.database.main.disconnectReason = reason
            }
        }
    }
})