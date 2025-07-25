import {defineStore} from 'pinia'
import {getSystemStatus} from '@/api/system'

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
        loading: false,
        error: null
    }),

    getters: {
        isRunning: (state) => state.status.engine?.running || false,
        uptime: (state) => state.status.engine?.uptime || 0,
        queueSize: (state) => state.status.engine?.queue_size || 0
    },

    actions: {
        async fetchStatus() {
            try {
                this.loading = true
                this.error = null
                const data = await getSystemStatus()
                this.status = data
            } catch (error) {
                this.error = error.message
                console.error('获取系统状态失败:', error)
            } finally {
                this.loading = false
            }
        }
    }
})