import type { DataCapability, DataSourceType } from '../types'

export type SlowLoadTrigger = 'elapsed_timeout' | 'provider_reason'

export type SlowLoadReasonCode =
    | 'PROVIDER_TIMEOUT'
    | 'PROVIDER_UNAVAILABLE'
    | 'PROVIDER_ERROR'
    | 'UNKNOWN'

export interface SlowLoadSwitchEvent {
    id: string
    pageKey: string
    pageName: string
    moduleKey: string
    moduleName: string
    capability: DataCapability
    currentSource?: DataSourceType
    preferredSource?: DataSourceType
    elapsedMs?: number
    trigger: SlowLoadTrigger
    reasonCode?: SlowLoadReasonCode
    reasonDetail?: string
    candidateSources: DataSourceType[]
    onSwitchSource?: (target: DataSourceType) => void | Promise<void>
    createdAt: number
}
