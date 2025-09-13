import React, { createContext, useContext } from 'react'
import { useSystemStore } from './systemStore'
import { useMarketStore } from './marketStore'
import { useConfigStore } from './configStore'

const StoreContext = createContext(null)

export const StoreProvider = ({ children }) => {
  const stores = {
    system: useSystemStore(),
    market: useMarketStore(),
    config: useConfigStore()
  }

  return (
    <StoreContext.Provider value={stores}>
      {children}
    </StoreContext.Provider>
  )
}

export const useStores = () => {
  const context = useContext(StoreContext)
  if (!context) {
    throw new Error('useStores must be used within StoreProvider')
  }
  return context
}