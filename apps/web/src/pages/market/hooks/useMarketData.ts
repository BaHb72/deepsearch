import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { message } from 'antd'
import {
    marketDataLiveApi,
    type AuctionQualityResponse,
    type BoardOverviewResponse,
    type OrderImbalanceResponse,
    type PhaseState,
    type StrengthItem,
    type StrengthResponse,
    type CacheInfo,
} from '@/api/marketDataLive'
import { useRealtimeSource } from '@/contexts/RealtimeSourceContext'
import {
    formatDataSourceLabel,
    normalizeDataSourceList,
    normalizeDataSourceValue,
} from '@/utils/dataSource'

export type ModuleSourceKey =
    | 'strength'
    | 'board_overview'
    | 'order_imbalance'
    | 'auction_quality'

export const PHASE_META: Record<PhaseState, { label: string; color: string }> = {
    off_day: { label: '休市', color: 'default' },
    no_trade: { label: '盘前/盘后', color: 'blue' },
    auction: { label: '集合竞价', color: 'orange' },
    continuous: { label: '连续竞价', color: 'green' },
    unknown: { label: '待同步', color: 'default' },
}

const REFRESH_INTERVAL: Record<PhaseState, number> = {
    continuous: 15_000,
    auction: 10_000,
    no_trade: 60_000,
    off_day: 0,
    unknown: 30_000,
}

const AUTO_REFRESH_DISABLED_PHASES: PhaseState[] = ['off_day']

const mergeCacheInfo = (sources: Array<CacheInfo | undefined>): CacheInfo | undefined => {
    const cacheEntries = sources.filter(Boolean) as CacheInfo[]
    if (!cacheEntries.length) {
        return undefined
    }
    const cachedAt = cacheEntries
        .map((entry) => entry.cachedAt)
        .filter((item): item is string => Boolean(item))
        .sort()
        .pop()
    const expiresAt = cacheEntries
        .map((entry) => entry.expiresAt)
        .filter((item): item is string => Boolean(item))
        .sort()
        .shift()
    return { cachedAt, expiresAt }
}

const pickLatestTimestamp = (timestamps: Array<string | undefined | null>) => {
    const valid = timestamps.filter((item): item is string => Boolean(item))
    if (!valid.length) {
        return null
    }
    return valid.reduce((latest, current) => (current > latest ? current : latest))
}

export const useMarketData = () => {
    const [strength, setStrength] = useState<StrengthResponse | null>(null)
    const [boardOverview, setBoardOverview] = useState<BoardOverviewResponse | null>(null)
    const [orderImbalance, setOrderImbalance] = useState<OrderImbalanceResponse | null>(null)
    const [auctionQuality, setAuctionQuality] = useState<AuctionQualityResponse | null>(null)
    const [moduleSources, setModuleSources] = useState<Record<ModuleSourceKey, string | null>>({
        strength: null,
        board_overview: null,
        order_imbalance: null,
        auction_quality: null,
    })

    const [selectedWindow, setSelectedWindow] = useState<string>()
    const [boardWindow, setBoardWindow] = useState<string>()
    const [boardType, setBoardType] = useState<'concept' | 'industry'>('concept')
    const [phase, setPhase] = useState<PhaseState>('unknown')
    const [autoRefresh, setAutoRefresh] = useState<boolean>(true)
    const [loading, setLoading] = useState<boolean>(false)
    const [refreshing, setRefreshing] = useState<boolean>(false)
    const [fetchError, setFetchError] = useState<string | null>(null)

    const boardWindowRef = useRef<string | undefined>(undefined)
    const requestLockRef = useRef(false)
    const manualAutoRefreshRef = useRef(false)
    const realtimeSource = useRealtimeSource()
    const skipNextSourceRefreshRef = useRef(false)
    const sourceInitializedRef = useRef(false)
    const moduleSourceInitializedRef = useRef(false)

    useEffect(() => {
        boardWindowRef.current = boardWindow
    }, [boardWindow])

    const fetchAll = useCallback(
        async (options?: { silent?: boolean; suppressToast?: boolean; window?: string }) => {
            if (requestLockRef.current) {
                return
            }

            requestLockRef.current = true
            const silent = Boolean(options?.silent)
            const suppressToast = Boolean(options?.suppressToast)
            const windowParam = options?.window ?? boardWindowRef.current

            if (silent) {
                setRefreshing(true)
            } else {
                setLoading(true)
            }

            try {
                const [strengthResp, boardResp, imbalanceResp, auctionResp] = await Promise.all([
                    marketDataLiveApi.getStrength({
                        source: moduleSources.strength ?? undefined,
                    }),
                    marketDataLiveApi.getBoardOverview({
                        type: boardType,
                        window: windowParam,
                        limit: 20,
                        source: moduleSources.board_overview ?? undefined,
                    }),
                    marketDataLiveApi.getOrderImbalance({
                        limit: 80,
                        source: moduleSources.order_imbalance ?? undefined,
                    }),
                    marketDataLiveApi.getAuctionQuality({
                        source: moduleSources.auction_quality ?? undefined,
                    }),
                ])

                setStrength(strengthResp)
                setBoardOverview(boardResp)
                setOrderImbalance(imbalanceResp)
                setAuctionQuality(auctionResp)
                setPhase(strengthResp.phase_state ?? 'unknown')

                setFetchError(null)

                setSelectedWindow((prev) => {
                    const windows = strengthResp.windows
                    if (!windows?.length) {
                        return prev
                    }
                    if (!prev) {
                        return windows[0]
                    }
                    if (!windows.includes(prev)) {
                        return windows[0]
                    }
                    return prev
                })

                if (!boardWindowRef.current && boardResp.window) {
                    boardWindowRef.current = boardResp.window
                    setBoardWindow(boardResp.window)
                }
            } catch (error) {
                const messageText = (error as Error)?.message || '拉取市场行情数据失败，请稍后重试'
                setFetchError(messageText)
                if (!suppressToast) {
                    message.error(messageText)
                }
            } finally {
                requestLockRef.current = false
                if (silent) {
                    setRefreshing(false)
                } else {
                    setLoading(false)
                }
            }
        },
        [boardType, moduleSources]
    )

    const handleSwitchDataSource = useCallback(
        async (target: string) => {
            const normalized = normalizeDataSourceValue(target)
            if (!normalized) {
                return
            }

            skipNextSourceRefreshRef.current = true
            try {
                const response = await realtimeSource.switchSource(normalized, { silent: true })
                const label = formatDataSourceLabel(response?.active ?? normalized)
                message.success(`已切换到 ${label}`)
                await fetchAll({ silent: true, suppressToast: true })
            } catch (error) {
                skipNextSourceRefreshRef.current = false
                const text = (error as Error)?.message || '切换数据源失败，请稍后重试'
                message.error(text)
            }
        },
        [fetchAll, realtimeSource]
    )

    useEffect(() => {
        fetchAll()
    }, [fetchAll])

    useEffect(() => {
        if (!moduleSourceInitializedRef.current) {
            moduleSourceInitializedRef.current = true
            return
        }
        fetchAll({ silent: true, suppressToast: true })
    }, [moduleSources, fetchAll])

    useEffect(() => {
        if (!realtimeSource.activeSource) {
            return
        }
        if (!sourceInitializedRef.current) {
            sourceInitializedRef.current = true
            return
        }
        if (skipNextSourceRefreshRef.current) {
            skipNextSourceRefreshRef.current = false
            return
        }
        fetchAll({ silent: true, suppressToast: true })
    }, [fetchAll, realtimeSource.activeSource])

    const phaseAllowsAutoRefresh = !AUTO_REFRESH_DISABLED_PHASES.includes(phase)

    useEffect(() => {
        if (!phaseAllowsAutoRefresh) {
            if (autoRefresh) {
                setAutoRefresh(false)
            }
            manualAutoRefreshRef.current = false
            return
        }

        if (!autoRefresh && !manualAutoRefreshRef.current) {
            setAutoRefresh(true)
        }
    }, [autoRefresh, phaseAllowsAutoRefresh])

    useEffect(() => {
        const intervalMs = REFRESH_INTERVAL[phase] ?? 0
        if (!autoRefresh || intervalMs <= 0) {
            return undefined
        }

        const timer = window.setInterval(() => {
            fetchAll({ silent: true, suppressToast: true })
        }, intervalMs)
        return () => window.clearInterval(timer)
    }, [autoRefresh, fetchAll, phase])

    const strengthByWindow = useMemo(() => {
        if (!strength) {
            return {}
        }
        const grouped: Record<string, StrengthItem[]> = {}
        strength.items.forEach((item) => {
            const key = item.window || 'unknown'
            grouped[key] = grouped[key] ? [...grouped[key], item] : [item]
        })
        return grouped
    }, [strength])

    const strengthItems = useMemo(() => {
        if (!selectedWindow) {
            return []
        }
        const items = strengthByWindow[selectedWindow] ?? []
        return [...items].sort((a, b) => (b.speed_per_min ?? 0) - (a.speed_per_min ?? 0))
    }, [selectedWindow, strengthByWindow])

    const boardItems = useMemo(() => {
        const items = boardOverview?.items ?? []
        return [...items].sort((a, b) => (b.inflow_speed ?? 0) - (a.inflow_speed ?? 0))
    }, [boardOverview])

    const orderItems = useMemo(() => {
        const items = orderImbalance?.items ?? []
        return [...items].sort((a, b) => Math.abs(b.obi ?? 0) - Math.abs(a.obi ?? 0))
    }, [orderImbalance])

    const auctionItems = useMemo(() => {
        const items = auctionQuality?.items ?? []
        return [...items].sort((a, b) => (b.speed_per_min ?? 0) - (a.speed_per_min ?? 0))
    }, [auctionQuality])

    const globalAsOf =
        strength?.asOf ||
        boardOverview?.asOf ||
        orderImbalance?.asOf ||
        auctionQuality?.asOf ||
        null
    const retrievedAt = pickLatestTimestamp([
        strength?.retrieved_at,
        boardOverview?.retrieved_at,
        orderImbalance?.retrieved_at,
        auctionQuality?.retrieved_at,
    ])
    const dataSource =
        strength?.data_source ||
        boardOverview?.data_source ||
        orderImbalance?.data_source ||
        auctionQuality?.data_source ||
        'amazingdata'
    const isStale =
        Boolean(strength?.stale) ||
        Boolean(boardOverview?.stale) ||
        Boolean(orderImbalance?.stale) ||
        Boolean(auctionQuality?.stale)

    const cacheInfo = mergeCacheInfo([
        strength?.cache,
        boardOverview?.cache,
        orderImbalance?.cache,
        auctionQuality?.cache,
    ])

    const adapterOptions = useMemo(() => {
        const adapters = boardOverview?.detail?.adapters
            ? Object.keys(boardOverview.detail.adapters)
            : []
        const entries = [...adapters]
        if (dataSource) {
            entries.push(dataSource)
        }
        return normalizeDataSourceList(entries)
    }, [boardOverview, dataSource])

    const moduleSourceOptions = useMemo(
        () => [
            { label: '自动', value: '' },
            ...adapterOptions.map((item) => ({
                label: formatDataSourceLabel(item),
                value: item,
            })),
        ],
        [adapterOptions]
    )

    const activeDataSource =
        normalizeDataSourceValue(dataSource) || adapterOptions[0] || 'amazingdata'

    const canAutoRefresh = phaseAllowsAutoRefresh

    const handleAutoRefreshChange = (checked: boolean) => {
        if (!checked) {
            manualAutoRefreshRef.current = true
            setAutoRefresh(false)
            return
        }
        manualAutoRefreshRef.current = false
        setAutoRefresh(true)
    }

    const handleModuleSourceChange = useCallback((moduleKey: string, value: string) => {
        const normalized = normalizeDataSourceValue(value) ?? null
        setModuleSources((prev) => {
            if (prev[moduleKey as ModuleSourceKey] === normalized) {
                return prev
            }
            return { ...prev, [moduleKey]: normalized }
        })
    }, [])

    const getFallbackLabel = useCallback((detail?: unknown): string | null => {
        if (!detail || typeof detail !== 'object') {
            return null
        }
        const fallback = (detail as Record<string, unknown>).fallback
        if (!fallback || typeof fallback !== 'object') {
            return null
        }
        const fallbackObj = fallback as Record<string, unknown>
        const sourceCandidate =
            typeof fallbackObj.writer_source === 'string' && fallbackObj.writer_source.trim().length
                ? fallbackObj.writer_source.trim()
                : typeof fallbackObj.source === 'string' && fallbackObj.source.trim().length
                    ? fallbackObj.source.trim()
                    : null
        if (sourceCandidate) {
            return `自动: ${formatDataSourceLabel(sourceCandidate)}`
        }
        const message = typeof fallbackObj.message === 'string' ? fallbackObj.message : null
        return message ?? '已进行自动降级'
    }, [])

    return {
        strength,
        boardOverview,
        orderImbalance,
        auctionQuality,
        moduleSources,
        selectedWindow,
        boardWindow,
        boardType,
        phase,
        autoRefresh,
        loading,
        refreshing,
        fetchError,
        realtimeSource,
        strengthItems,
        boardItems,
        orderItems,
        auctionItems,
        globalAsOf,
        retrievedAt,
        dataSource,
        isStale,
        cacheInfo,
        adapterOptions,
        moduleSourceOptions,
        activeDataSource,
        canAutoRefresh,
        handleAutoRefreshChange,
        handleModuleSourceChange,
        handleSwitchDataSource,
        fetchAll,
        setSelectedWindow,
        setBoardWindow,
        setBoardType,
        getFallbackLabel,
    }
}
