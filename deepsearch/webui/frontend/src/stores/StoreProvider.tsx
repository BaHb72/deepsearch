import { createContext, useContext, type ReactNode } from 'react'
import { useSystemStore } from './system.store'
import { useMarketStore } from './market.store'
import { useConfigStore } from './config.store'

type StoreContextValue = {
  system: ReturnType<typeof useSystemStore>
  market: ReturnType<typeof useMarketStore>
  config: ReturnType<typeof useConfigStore>
}

const StoreContext = createContext<StoreContextValue | null>(null)

interface StoreProviderProps {
  children: ReactNode
}

export const StoreProvider = ({ children }: StoreProviderProps) => {
  const stores: StoreContextValue = {
    system: useSystemStore(),
    market: useMarketStore(),
    config: useConfigStore(),
  }

  return (
    <StoreContext.Provider value={stores}>
      {children}
    </StoreContext.Provider>
  )
}

export const useStores = (): StoreContextValue => {
  const context = useContext(StoreContext)
  if (!context) {
    throw new Error('useStores must be used within StoreProvider')
  }
  return context
}
