import type { DataCapability, DataSourceType } from '../types'
import type { SlowLoadMonitorContext } from '../types/rich-data'
import type { SlowLoadReasonCode, SlowLoadSwitchEvent } from './types'
import { getSwitchCandidates } from '../capability-resolver'
import { useSlowLoadSwitchStore } from '@/stores/slowLoadSwitch.store'

const DEFAULT_SLOW_THRESHOLD_MS = 45_000
const ERROR_REASON_CODES = new Set(['PROVIDER_TIMEOUT', 'PROVIDER_UNAVAILABLE', 'PROVIDER_ERROR'])
const KNOWN_SOURCES = new Set<DataSourceType>([
    'miniqmt',
    'amazingdata',
    'akshare',
    'tushare',
    'eastmoney',
])

interface AttemptSnapshot {
    provider: string
    success: boolean
    reason_code?: string | null
    reason_detail?: string | null
    latency_ms?: number | null
}

interface SlowWatchState {
    watchId: string
    startedAt: number
    capability: DataCapability
    preferredSource?: DataSourceType
    monitor: SlowLoadMonitorContext
    timeoutId: ReturnType<typeof setTimeout>
    emitted: boolean
}

interface BeginSlowWatchInput {
    capability: DataCapability
    preferredSource?: DataSourceType
    monitor?: SlowLoadMonitorContext
}

let watchSeq = 0
const activeWatches = new Map<string, SlowWatchState>()

function normalizeSource(source: unknown, fallback?: DataSourceType): DataSourceType | undefined {
    if (typeof source === 'string') {
        const normalized = source.trim().toLowerCase() as DataSourceType
        if (KNOWN_SOURCES.has(normalized)) {
            return normalized
        }
    }
    return fallback
}

function normalizeReasonCode(reasonCode: unknown): SlowLoadReasonCode {
    if (typeof reasonCode !== 'string') {
        return 'UNKNOWN'
    }
    const normalized = reasonCode.trim().toUpperCase()
    if (normalized === 'PROVIDER_TIMEOUT') return 'PROVIDER_TIMEOUT'
    if (normalized === 'PROVIDER_UNAVAILABLE') return 'PROVIDER_UNAVAILABLE'
    if (normalized === 'PROVIDER_ERROR') return 'PROVIDER_ERROR'
    return 'UNKNOWN'
}

async function buildSwitchEvent(
    state: SlowWatchState,
    trigger: SlowLoadSwitchEvent['trigger'],
    extras: {
        currentSource?: DataSourceType
        elapsedMs?: number
        reasonCode?: SlowLoadReasonCode
        reasonDetail?: string
    }
): Promise<SlowLoadSwitchEvent> {
    const currentSource = extras.currentSource ?? state.preferredSource
    const candidateSources = await getSwitchCandidates({
        capability: state.capability,
        currentSource,
    })
    const now = Date.now()

    return {
        id: `slow-load-${now}-${Math.random().toString(36).slice(2, 8)}`,
        pageKey: state.monitor.pageKey,
        pageName: state.monitor.pageName,
        moduleKey: state.monitor.moduleKey,
        moduleName: state.monitor.moduleName,
        capability: state.capability,
        currentSource,
        preferredSource: state.preferredSource,
        elapsedMs: extras.elapsedMs,
        trigger,
        reasonCode: extras.reasonCode,
        reasonDetail: extras.reasonDetail,
        candidateSources,
        onSwitchSource: state.monitor.onSwitchSource,
        createdAt: now,
    }
}

async function emitElapsedTimeoutEvent(state: SlowWatchState): Promise<void> {
    if (state.emitted) {
        return
    }
    state.emitted = true
    const elapsedMs = Date.now() - state.startedAt
    const event = await buildSwitchEvent(state, 'elapsed_timeout', {
        elapsedMs,
        reasonCode: 'UNKNOWN',
    })
    useSlowLoadSwitchStore.getState().enqueue(event)
}

function selectFailedAttempt(
    attempts: AttemptSnapshot[],
    preferredSource?: DataSourceType
): AttemptSnapshot | null {
    const failures = attempts.filter((attempt) => {
        if (attempt.success) {
            return false
        }
        const reason = typeof attempt.reason_code === 'string'
            ? attempt.reason_code.trim().toUpperCase()
            : ''
        return ERROR_REASON_CODES.has(reason)
    })

    if (failures.length === 0) {
        return null
    }
    if (preferredSource) {
        const preferred = failures.find((item) => normalizeSource(item.provider) === preferredSource)
        if (preferred) {
            return preferred
        }
    }
    return failures[0]
}

export function beginSlowWatch(input: BeginSlowWatchInput): string | null {
    if (!input.monitor) {
        return null
    }

    watchSeq += 1
    const watchId = `watch-${Date.now()}-${watchSeq}`
    const thresholdMs = input.monitor.slowThresholdMs ?? DEFAULT_SLOW_THRESHOLD_MS
    const state: SlowWatchState = {
        watchId,
        startedAt: Date.now(),
        capability: input.capability,
        preferredSource: input.preferredSource,
        monitor: input.monitor,
        emitted: false,
        timeoutId: setTimeout(() => {
            const current = activeWatches.get(watchId)
            if (!current) {
                return
            }
            void emitElapsedTimeoutEvent(current)
        }, thresholdMs),
    }
    activeWatches.set(watchId, state)
    return watchId
}

export async function emitProviderReasonEvent(
    watchId: string | null,
    attempts: AttemptSnapshot[] | undefined,
    resolvedSource?: DataSourceType
): Promise<void> {
    if (!watchId || !attempts || attempts.length === 0) {
        return
    }

    const state = activeWatches.get(watchId)
    if (!state || state.emitted) {
        return
    }

    const failedAttempt = selectFailedAttempt(attempts, state.preferredSource)
    if (!failedAttempt) {
        return
    }

    state.emitted = true
    const reasonCode = normalizeReasonCode(failedAttempt.reason_code)
    const currentSource =
        normalizeSource(failedAttempt.provider, resolvedSource) ??
        state.preferredSource ??
        resolvedSource

    const event = await buildSwitchEvent(state, 'provider_reason', {
        currentSource,
        elapsedMs:
            typeof failedAttempt.latency_ms === 'number' && failedAttempt.latency_ms >= 0
                ? failedAttempt.latency_ms
                : Date.now() - state.startedAt,
        reasonCode,
        reasonDetail: failedAttempt.reason_detail || undefined,
    })
    useSlowLoadSwitchStore.getState().enqueue(event)
}

export function finishSlowWatch(watchId: string | null): void {
    if (!watchId) {
        return
    }
    const state = activeWatches.get(watchId)
    if (!state) {
        return
    }
    clearTimeout(state.timeoutId)
    activeWatches.delete(watchId)
}
