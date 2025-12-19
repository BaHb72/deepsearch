import { create } from 'zustand'
import { devtools } from 'zustand/middleware'

export interface MarketData {
  indices: any[]
  stocks: any[]
  sectors: any[]
  hotStocks: any[]
  ztPool: any[]
  anomalies: any[]
}

export interface WatchStock {
  code: string
  [key: string]: any
}

export interface MarketRealtimeEntry {
  lastUpdate?: number
  [key: string]: any
}

interface MarketState {
  marketData: MarketData
  selectedStock: WatchStock | null
  watchList: WatchStock[]
  realTimeData: Record<string, MarketRealtimeEntry>
  loading: boolean
  error: string | null
  setMarketData: (data: Partial<MarketData>) => void
  selectStock: (stock: WatchStock | null) => void
  addToWatchList: (stock: WatchStock) => void
  removeFromWatchList: (stockCode: string) => void
  updateRealTimeData: (stockCode: string, data: Partial<MarketRealtimeEntry>) => void
  clearRealTimeData: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

const buildDefaultMarketData = (): MarketData => ({
  indices: [],
  stocks: [],
  sectors: [],
  hotStocks: [],
  ztPool: [],
  anomalies: [],
})

export const useMarketStore = create<MarketState>()(
  devtools(
    (set) => ({
      marketData: buildDefaultMarketData(),
      selectedStock: null,
      watchList: [],
      realTimeData: {},
      loading: false,
      error: null,

      setMarketData: (data) =>
        set((state) => ({
          marketData: {
            ...state.marketData,
            ...data,
          },
        })),

      selectStock: (stock) => set({ selectedStock: stock }),

      addToWatchList: (stock) =>
        set((state) => {
          if (!stock || typeof stock.code !== 'string') {
            return {}
          }
          if (state.watchList.some((item) => item.code === stock.code)) {
            return {}
          }
          return { watchList: [...state.watchList, stock] }
        }),

      removeFromWatchList: (stockCode) =>
        set((state) => ({
          watchList: state.watchList.filter((item) => item.code !== stockCode),
        })),

      updateRealTimeData: (stockCode, data) =>
        set((state) => {
          if (!stockCode) {
            return {}
          }
          const previous = state.realTimeData[stockCode] ?? {}
          return {
            realTimeData: {
              ...state.realTimeData,
              [stockCode]: {
                ...previous,
                ...data,
                lastUpdate: Date.now(),
              },
            },
          }
        }),

      clearRealTimeData: () => set({ realTimeData: {} }),

      setLoading: (loading) => set({ loading }),

      setError: (error) => set({ error }),

      reset: () =>
        set({
          marketData: buildDefaultMarketData(),
          selectedStock: null,
          watchList: [],
          realTimeData: {},
          loading: false,
          error: null,
        }),
    }),
    { name: 'market-store' }
  )
)

