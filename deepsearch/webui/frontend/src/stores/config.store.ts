import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

export interface NotificationSettings {
  enabled: boolean
  sound: boolean
  desktop: boolean
}

export interface DisplaySettings {
  compactMode: boolean
  showGridLines: boolean
  animationsEnabled: boolean
}

export interface TradingSettings {
  defaultLeverage: number
  riskLevel: string
  autoStopLoss: boolean
  stopLossPercentage: number
}

interface ConfigState {
  theme: 'light' | 'dark' | string
  language: string
  autoRefresh: boolean
  refreshInterval: number
  notifications: NotificationSettings
  display: DisplaySettings
  trading: TradingSettings
  setTheme: (theme: ConfigState['theme']) => void
  setLanguage: (language: string) => void
  setAutoRefresh: (enabled: boolean) => void
  setRefreshInterval: (interval: number) => void
  updateNotifications: (settings: Partial<NotificationSettings>) => void
  updateDisplay: (settings: Partial<DisplaySettings>) => void
  updateTrading: (settings: Partial<TradingSettings>) => void
  resetToDefaults: () => void
  reset: () => void
}

const buildDefaultNotifications = (): NotificationSettings => ({
  enabled: true,
  sound: false,
  desktop: true,
})

const buildDefaultDisplay = (): DisplaySettings => ({
  compactMode: false,
  showGridLines: true,
  animationsEnabled: true,
})

const buildDefaultTrading = (): TradingSettings => ({
  defaultLeverage: 1,
  riskLevel: 'medium',
  autoStopLoss: true,
  stopLossPercentage: 5,
})

const buildDefaultConfig = () => ({
  theme: 'light' as ConfigState['theme'],
  language: 'zh-CN',
  autoRefresh: true,
  refreshInterval: 5000,
  notifications: buildDefaultNotifications(),
  display: buildDefaultDisplay(),
  trading: buildDefaultTrading(),
})

export const useConfigStore = create<ConfigState>()(
  devtools(
    persist(
      (set) => ({
        ...buildDefaultConfig(),

        setTheme: (theme) => set({ theme }),
        setLanguage: (language) => set({ language }),
        setAutoRefresh: (enabled) => set({ autoRefresh: enabled }),
        setRefreshInterval: (interval) => set({ refreshInterval: interval }),

        updateNotifications: (settings) =>
          set((state) => ({
            notifications: { ...state.notifications, ...settings },
          })),

        updateDisplay: (settings) =>
          set((state) => ({
            display: { ...state.display, ...settings },
          })),

        updateTrading: (settings) =>
          set((state) => ({
            trading: { ...state.trading, ...settings },
          })),

        resetToDefaults: () => set(buildDefaultConfig()),
        reset: () => set(buildDefaultConfig()),
      }),
      {
        name: 'deepsearch-config',
        version: 1,
      }
    ),
    { name: 'config-store' }
  )
)

