import {create} from 'zustand'
import {devtools} from 'zustand/middleware'
import systemAPI, {type SystemInfo} from '@/api/system'

export interface SystemComponent {
  name?: string
  [key: string]: any
}

export interface SystemStatistics {
  total_events: number
  events_per_second: number
  active_connections: number
  memory_usage: number
  cpu_usage: number
}

export interface SystemAlert {
  id: number
  timestamp: string
  message: string
  type?: string
  severity?: string
  [key: string]: any
}

type AddAlertPayload = Omit<SystemAlert, 'id' | 'timestamp'> & {
  id?: number
  timestamp?: string
}

interface SystemState {
  status: SystemInfo | null
  components: SystemComponent[]
  alerts: SystemAlert[]
  statistics: SystemStatistics
  loading: boolean
  error: string | null
  fetchStatus: () => Promise<SystemInfo | null>
  updateComponent: (componentName: string, updates: Partial<SystemComponent>) => void
  addAlert: (alert: AddAlertPayload) => void
  removeAlert: (alertId: number) => void
  clearAlerts: () => void
  reset: () => void
}

const buildDefaultStatistics = (): SystemStatistics => ({
  total_events: 0,
  events_per_second: 0,
  active_connections: 0,
  memory_usage: 0,
  cpu_usage: 0,
})

const normalizeComponents = (raw: unknown): SystemComponent[] => {
  if (Array.isArray(raw)) {
    return raw as SystemComponent[]
  }

  if (raw && typeof raw === 'object') {
    return Object.entries(raw as Record<string, unknown>).map(([name, detail]) => ({
      name,
      ...(typeof detail === 'object' && detail !== null ? (detail as Record<string, unknown>) : { value: detail }),
    }))
  }

  return []
}

const buildStatistics = (info: any): SystemStatistics => {
  const defaults = buildDefaultStatistics()
  const statsSource = info?.statistics ?? {}
  return {
    total_events: Number(statsSource?.total_events ?? statsSource?.totalEvents ?? info?.total_events ?? defaults.total_events) || 0,
    events_per_second: Number(statsSource?.events_per_second ?? statsSource?.eventsPerSecond ?? defaults.events_per_second) || 0,
    active_connections: Number(statsSource?.active_connections ?? statsSource?.activeConnections ?? defaults.active_connections) || 0,
    memory_usage: Number(statsSource?.memory_usage ?? statsSource?.memoryUsage ?? info?.memory_usage ?? defaults.memory_usage) || 0,
    cpu_usage: Number(statsSource?.cpu_usage ?? statsSource?.cpuUsage ?? info?.cpu_usage ?? defaults.cpu_usage) || 0,
  }
}

export const useSystemStore = create<SystemState>()(
  devtools(
    (set) => ({
      status: null,
      components: [],
      alerts: [],
      statistics: buildDefaultStatistics(),
      loading: false,
      error: null,

      fetchStatus: async () => {
        set({ loading: true, error: null })
        try {
          const info = await systemAPI.getSystemStatus()
          set({
            status: info,
            components: normalizeComponents(info?.components),
            statistics: buildStatistics(info),
            loading: false,
            error: null,
          })
          return info
        } catch (error) {
          const message = error instanceof Error ? error.message : '获取系统状态失败'
          set({ loading: false, error: message })
          throw error
        }
      },

      updateComponent: (componentName, updates) => {
        if (!componentName) {
          return
        }
        set((state) => ({
          components: state.components.map((component) =>
            (component.name ?? '') === componentName
              ? { ...component, ...updates }
              : component
          ),
        }))
      },

      addAlert: (alert) => {
        const { id, timestamp, message, ...rest } = alert
        const messageText =
          typeof message === 'string' && message.trim().length > 0
            ? message
            : '系统通知'
        const nextAlert: SystemAlert = {
          id: id ?? Date.now(),
          timestamp: timestamp ?? new Date().toISOString(),
          message: messageText,
          ...rest,
        }
        set((state) => ({
          alerts: [...state.alerts, nextAlert],
        }))
      },

      removeAlert: (alertId) => {
        set((state) => ({
          alerts: state.alerts.filter((alertItem) => alertItem.id !== alertId),
        }))
      },

      clearAlerts: () => {
        set({ alerts: [] })
      },

      reset: () => {
        set({
          status: null,
          components: [],
          alerts: [],
          statistics: buildDefaultStatistics(),
          loading: false,
          error: null,
        })
      },
    }),
    { name: 'system-store' }
  )
)


