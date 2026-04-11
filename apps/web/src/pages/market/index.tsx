/**
 * Market 页面 - 使用 React Query 重构版
 * 完整市场行情视图
 */

import React, { useMemo, useState, useCallback, useEffect } from 'react'
import { Alert } from 'antd'
import { ProCard } from '@ant-design/pro-components'
import { useQueryClient } from '@tanstack/react-query'

// React Query Hooks
import {
    useConceptStrength,
    useIndexConceptPulse,
    useBoardOverview,
    useConceptFlow,
    getRefreshIntervalByPhase,
    marketQueryKeys,
} from '@/hooks/queries/useMarketQueries'

// 组件
import MarketHeader from './components/MarketHeader'
import StrengthTable from './components/StrengthTable'
import BoardOverviewTable from './components/BoardOverviewTable'
import ConceptFlowTable from './components/ConceptFlowTable'
import IndexConceptPulseChart from './components/IndexConceptPulseChart'
import ConceptPulseEventPanel from './components/ConceptPulseEventPanel'

// 工具函数
import {
    formatDataSourceLabel,
    normalizeDataSourceList,
    normalizeDataSourceValue,
} from '@/utils/dataSource'
import type { PhaseState, StrengthItem } from '@/api/marketDataLive'

// ============ 类型定义 ============

type ModuleSourceKey = 'strength' | 'board_overview' | 'concept_flow'

// ============ 常量配置 ============

const AUTO_REFRESH_DISABLED_PHASES: PhaseState[] = ['off_day']

const MarketData: React.FC = () => {
    const queryClient = useQueryClient()

    // ============ 本地状态 ============
    const [selectedWindow, setSelectedWindow] = useState<string>()
    const [boardType, setBoardType] = useState<'concept' | 'industry'>('concept')
    const [autoRefresh, setAutoRefresh] = useState<boolean>(true)
    const [phase, setPhase] = useState<PhaseState>('unknown')
    const [selectedPulseEventAt, setSelectedPulseEventAt] = useState<string | null>(null)
    const [moduleSources, setModuleSources] = useState<Record<ModuleSourceKey, string | null>>({
        strength: null,
        board_overview: null,
        concept_flow: null,
    })

    // 计算刷新间隔
    const refetchInterval = autoRefresh ? getRefreshIntervalByPhase(phase) : false

    // ============ React Query 数据获取 ============

    // 使用概念板块资金脉冲接口
    const {
        data: strength,
        isLoading: strengthLoading,
        isFetching: strengthFetching,
        error: strengthError,
    } = useConceptStrength(
        { source: moduleSources.strength, limit: 50 },
        { refetchInterval }
    )

    const {
        data: indexConceptPulse,
        isLoading: pulseLoading,
        isFetching: pulseFetching,
        error: pulseError,
    } = useIndexConceptPulse(
        {
            source: moduleSources.board_overview,
            board_limit: 6,
            event_limit: 16,
            candidate_limit: 6,
            threshold: 72,
        },
        { refetchInterval }
    )

    const {
        data: boardOverview,
        isLoading: boardLoading,
        isFetching: boardFetching,
        error: boardError,
    } = useBoardOverview(
        {
            type: boardType,
            limit: 20,
            source: moduleSources.board_overview,
        },
        { refetchInterval }
    )

    const {
        data: conceptFlow,
        isLoading: conceptFlowLoading,
        isFetching: conceptFlowFetching,
        error: conceptFlowError,
    } = useConceptFlow(
        {
            limit: 50,
            source: moduleSources.concept_flow,
        },
        { refetchInterval }
    )

    // 更新 phase 状态
    useEffect(() => {
        if (strength?.phase_state) {
            setPhase(strength.phase_state)
        }
    }, [strength?.phase_state])

    // ============ 派生状态 ============

    const loading = pulseLoading || strengthLoading || boardLoading || conceptFlowLoading
    const refreshing = pulseFetching || strengthFetching || boardFetching || conceptFlowFetching
    const fetchError =
        pulseError?.message || strengthError?.message || boardError?.message || conceptFlowError?.message || null

    const globalAsOf = indexConceptPulse?.asOf || strength?.asOf || boardOverview?.asOf || conceptFlow?.retrieved_at || null
    const retrievedAt =
        indexConceptPulse?.retrieved_at || strength?.retrieved_at || boardOverview?.retrieved_at || conceptFlow?.retrieved_at || null
    const dataSource =
        indexConceptPulse?.data_source || strength?.data_source || boardOverview?.data_source || conceptFlow?.data_source || 'amazingdata'
    const isStale =
        Boolean(indexConceptPulse?.stale) || Boolean(strength?.stale) || Boolean(boardOverview?.stale) || Boolean(conceptFlow?.stale)
    const phaseAllowsAutoRefresh = !AUTO_REFRESH_DISABLED_PHASES.includes(phase)

    const cacheInfo = useMemo(() => {
        const entries = [strength?.cache, boardOverview?.cache].filter(Boolean)
        if (!entries.length) return undefined
        const cachedAt = entries.map(e => e?.cachedAt).filter(Boolean).sort().pop()
        const expiresAt = entries.map(e => e?.expiresAt).filter(Boolean).sort().shift()
        return { cachedAt, expiresAt }
    }, [strength?.cache, boardOverview?.cache])

    // ============ 数据处理 ============

    const strengthByWindow = useMemo(() => {
        if (!strength) return {}
        const grouped: Record<string, StrengthItem[]> = {}
        strength.items.forEach((item) => {
            const key = item.window || 'unknown'
            grouped[key] = grouped[key] ? [...grouped[key], item] : [item]
        })
        return grouped
    }, [strength])

    const strengthItems = useMemo(() => {
        if (!selectedWindow) return []
        const items = strengthByWindow[selectedWindow] ?? []
        return [...items].sort((a, b) => (b.speed_per_min ?? 0) - (a.speed_per_min ?? 0))
    }, [selectedWindow, strengthByWindow])

    useEffect(() => {
        if (!strength?.windows?.length) return
        if (!selectedWindow || !strength.windows.includes(selectedWindow)) {
            setSelectedWindow(strength.windows[0])
        }
    }, [strength?.windows, selectedWindow])

    const boardItems = useMemo(() => {
        const items = boardOverview?.items ?? []
        return [...items].sort((a, b) => (b.inflow_speed ?? 0) - (a.inflow_speed ?? 0))
    }, [boardOverview])

    const conceptFlowItems = useMemo(() => {
        return conceptFlow?.items ?? []
    }, [conceptFlow])

    const selectedPulseEvent = useMemo(() => {
        const events = indexConceptPulse?.events ?? []
        if (!events.length) return null
        if (!selectedPulseEventAt) return events[events.length - 1]
        return events.find((item) => item.captured_at === selectedPulseEventAt) ?? events[events.length - 1]
    }, [indexConceptPulse?.events, selectedPulseEventAt])

    useEffect(() => {
        const events = indexConceptPulse?.events ?? []
        if (!events.length) {
            if (selectedPulseEventAt !== null) setSelectedPulseEventAt(null)
            return
        }
        const matched = selectedPulseEventAt && events.some((item) => item.captured_at === selectedPulseEventAt)
        if (!matched) {
            setSelectedPulseEventAt(events[events.length - 1].captured_at)
        }
    }, [indexConceptPulse?.events, selectedPulseEventAt])

    // ============ 数据源选项 ============

    const adapterOptions = useMemo(() => {
        const adapters = boardOverview?.detail?.adapters
            ? Object.keys(boardOverview.detail.adapters)
            : []
        const entries = [...adapters]
        if (dataSource) entries.push(dataSource)
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

    const activeDataSource = normalizeDataSourceValue(dataSource) || adapterOptions[0] || 'amazingdata'

    // ============ 事件处理 ============

    const handleRefresh = useCallback(() => {
        queryClient.invalidateQueries({ queryKey: marketQueryKeys.all })
    }, [queryClient])

    const handleAutoRefreshChange = useCallback((checked: boolean) => {
        setAutoRefresh(checked)
    }, [])

    const handleSwitchDataSource = useCallback(async (_target: string) => {
        // 后续可接入 useSwitchDataSource mutation
    }, [])

    const handleModuleSourceChange = useCallback((moduleKey: string, value: string) => {
        const normalized = normalizeDataSourceValue(value) ?? null
        setModuleSources((prev) => {
            if (prev[moduleKey as ModuleSourceKey] === normalized) return prev
            return { ...prev, [moduleKey]: normalized }
        })
    }, [])

    const getFallbackLabel = useCallback((detail?: unknown): string | null => {
        if (!detail || typeof detail !== 'object') return null
        const fallback = (detail as Record<string, unknown>).fallback
        if (!fallback || typeof fallback !== 'object') return null
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

    const strengthFallbackLabel = useMemo(() => getFallbackLabel(strength?.detail), [strength, getFallbackLabel])
    const boardFallbackLabel = useMemo(() => getFallbackLabel(boardOverview?.detail), [boardOverview, getFallbackLabel])
    const conceptFlowFallbackLabel = useMemo(() => getFallbackLabel(conceptFlow?.detail), [conceptFlow, getFallbackLabel])

    // ============ 渲染 ============

    return (
        <ProCard ghost gutter={[24, 24]} wrap style={{ padding: 24 }}>
            {fetchError && (
                <ProCard colSpan={24} ghost>
                    <Alert
                        type="error"
                        showIcon
                        message="市场行情数据拉取失败"
                        description={fetchError}
                        closable
                    />
                </ProCard>
            )}

            {/* Header Area */}
            <ProCard colSpan={24} bordered boxShadow>
                <MarketHeader
                    phase={phase}
                    isStale={isStale}
                    globalAsOf={globalAsOf}
                    retrievedAt={retrievedAt}
                    dataSource={dataSource}
                    activeDataSource={activeDataSource}
                    adapterOptions={adapterOptions}
                    cacheInfo={cacheInfo}
                    realtimeSource={null}
                    autoRefresh={autoRefresh}
                    canAutoRefresh={phaseAllowsAutoRefresh}
                    loading={loading}
                    refreshing={refreshing}
                    onSwitchDataSource={handleSwitchDataSource}
                    onAutoRefreshChange={handleAutoRefreshChange}
                    onRefresh={handleRefresh}
                />
            </ProCard>

            {/* Row 1: Index Pulse */}
            <ProCard colSpan={24} bordered boxShadow title="上证指数与概念启动" headStyle={{ fontWeight: 'bold' }}>
                <IndexConceptPulseChart
                    indexPoints={indexConceptPulse?.index.points ?? []}
                    events={indexConceptPulse?.events ?? []}
                    selectedEventAt={selectedPulseEventAt}
                    loading={pulseLoading || pulseFetching}
                    onSelectEvent={setSelectedPulseEventAt}
                />
            </ProCard>

            {/* Row 2: Pulse Detail & Concept Flow */}
            <ProCard
                colSpan={{ xs: 24, xl: 15 }}
                bordered
                boxShadow
                title="启动概念与高质量个股"
                headStyle={{ fontWeight: 'bold' }}
            >
                <ConceptPulseEventPanel
                    event={selectedPulseEvent}
                    loading={pulseLoading || pulseFetching}
                />
            </ProCard>
            <ProCard colSpan={{ xs: 24, xl: 9 }} bordered boxShadow title="概念资金流 (Concept Flow)" headStyle={{ fontWeight: 'bold' }}>
                <ConceptFlowTable
                    items={conceptFlowItems}
                    loading={loading}
                    refreshing={refreshing}
                    isStale={isStale}
                    moduleSource={moduleSources.concept_flow}
                    moduleSourceOptions={moduleSourceOptions}
                    fallbackLabel={conceptFlowFallbackLabel}
                    onModuleSourceChange={handleModuleSourceChange}
                />
            </ProCard>

            {/* Row 3: Board Overview */}
            <ProCard colSpan={24} bordered boxShadow title="板块概览 (Board Overview)" headStyle={{ fontWeight: 'bold' }}>
                <BoardOverviewTable
                    items={boardItems}
                    loading={loading}
                    refreshing={refreshing}
                    isStale={isStale}
                    boardType={boardType}
                    onBoardTypeChange={setBoardType}
                    moduleSource={moduleSources.board_overview}
                    moduleSourceOptions={moduleSourceOptions}
                    fallbackLabel={boardFallbackLabel}
                    onModuleSourceChange={handleModuleSourceChange}
                />
            </ProCard>

            {/* Row 4: Strength */}
            <ProCard colSpan={24} bordered boxShadow title="资金脉冲 (Real-time Flow)" headStyle={{ fontWeight: 'bold' }}>
                <StrengthTable
                    items={strengthItems}
                    loading={loading}
                    refreshing={refreshing}
                    isStale={isStale}
                    windows={strength?.windows ?? []}
                    selectedWindow={selectedWindow}
                    onWindowChange={setSelectedWindow}
                    moduleSource={moduleSources.strength}
                    moduleSourceOptions={moduleSourceOptions}
                    fallbackLabel={strengthFallbackLabel}
                    onModuleSourceChange={handleModuleSourceChange}
                />
            </ProCard>
        </ProCard>
    )
}

export default MarketData
