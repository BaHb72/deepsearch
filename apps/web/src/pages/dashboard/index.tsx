/**
 * Dashboard 页面 - 使用 React Query 重构版
 * 实时市场总览
 */

import React, { useMemo, useState, useCallback } from 'react'
import { Alert, Button } from 'antd'
import { PageContainer, ProCard } from '@ant-design/pro-components'
import { useNavigate } from 'react-router-dom'
import { LineChartOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'

// 使用新的 React Query Hooks
import {
    useMarketStrength,
    useBoardOverview,
    useBoardDrivers,
    getRefreshIntervalByPhase,
    marketQueryKeys,
} from '@/hooks/queries/useMarketQueries'

// 复用现有组件
import MarketHeader from '../market/components/MarketHeader'
import StrengthTable from '../market/components/StrengthTable'
import BoardOverviewTable from '../market/components/BoardOverviewTable'
import BoardDriversDrawer from '../market/components/BoardDriversDrawer'

// 复用工具函数
import {
    formatDataSourceLabel,
    normalizeDataSourceList,
    normalizeDataSourceValue,
} from '@/utils/dataSource'
import type { PhaseState } from '@/api/marketDataLive'

// ============ 自动刷新配置 ============

const AUTO_REFRESH_DISABLED_PHASES: PhaseState[] = ['off_day']

const Dashboard: React.FC = () => {
    const navigate = useNavigate()
    const queryClient = useQueryClient()

    // ============ 本地状态 ============
    const [selectedWindow, setSelectedWindow] = useState<string>()
    const [boardType, setBoardType] = useState<'concept' | 'industry'>('concept')
    const [autoRefresh, setAutoRefresh] = useState<boolean>(true)
    const [phase, setPhase] = useState<PhaseState>('unknown')
    const [selectedBoard, setSelectedBoard] = useState<string>()
    const [boardDrawerOpen, setBoardDrawerOpen] = useState<boolean>(false)
    const [moduleSources, setModuleSources] = useState<Record<string, string | null>>({
        strength: null,
        board_overview: null,
    })

    // 计算刷新间隔
    const refetchInterval = autoRefresh ? getRefreshIntervalByPhase(phase) : false

    // ============ React Query 数据获取 ============

    // 资金脉冲数据
    const {
        data: strength,
        isLoading: strengthLoading,
        isFetching: strengthFetching,
        error: strengthError,
    } = useMarketStrength(
        { source: moduleSources.strength },
        { refetchInterval }
    )

    // 板块概览数据
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
        data: boardDrivers,
        isLoading: boardDriversLoading,
        isFetching: boardDriversFetching,
    } = useBoardDrivers(
        {
            type: boardType,
            board: selectedBoard || '',
            window: selectedWindow,
            limit: 40,
            source: moduleSources.board_overview,
        },
        { refetchInterval, enabled: Boolean(selectedBoard && boardDrawerOpen) }
    )

    // 当获取到数据后更新 phase 状态
    React.useEffect(() => {
        if (strength?.phase_state) {
            setPhase(strength.phase_state)
        }
    }, [strength?.phase_state])

    // ============ 派生状态 ============

    const phaseAllowsAutoRefresh = !AUTO_REFRESH_DISABLED_PHASES.includes(phase)
    const loading = strengthLoading || boardLoading
    const refreshing = strengthFetching || boardFetching
    const fetchError = strengthError?.message || boardError?.message || null

    const strengthItemsCount = strength?.items?.length ?? 0
    const boardItemsCount = boardOverview?.items?.length ?? 0
    const globalAsOf = strength?.asOf || boardOverview?.asOf || null
    const retrievedAt = strength?.retrieved_at || boardOverview?.retrieved_at || null
    const dataSource = boardItemsCount > 0
        ? (boardOverview?.data_source || strength?.data_source || 'amazingdata')
        : strengthItemsCount > 0
            ? (strength?.data_source || boardOverview?.data_source || 'amazingdata')
            : (strength?.data_source || boardOverview?.data_source || 'amazingdata')
    const isStale = Boolean(strength?.stale) || Boolean(boardOverview?.stale)

    const cacheInfo = useMemo(() => {
        const entries = [strength?.cache, boardOverview?.cache].filter(Boolean)
        if (!entries.length) return undefined
        const cachedAt = entries.map(e => e?.cachedAt).filter(Boolean).sort().pop()
        const expiresAt = entries.map(e => e?.expiresAt).filter(Boolean).sort().shift()
        return { cachedAt, expiresAt }
    }, [strength?.cache, boardOverview?.cache])

    // ============ 资金脉冲数据处理 ============

    const strengthByWindow = useMemo(() => {
        if (!strength) return {}
        const grouped: Record<string, typeof strength.items> = {}
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

    // 自动选择窗口
    React.useEffect(() => {
        if (!strength?.windows?.length) return
        if (!selectedWindow || !strength.windows.includes(selectedWindow)) {
            setSelectedWindow(strength.windows[0])
        }
    }, [strength?.windows, selectedWindow])

    // ============ 板块概览数据处理 ============

    const boardItems = useMemo(() => {
        const items = boardOverview?.items ?? []
        return [...items].sort((a, b) => (b.inflow_speed ?? 0) - (a.inflow_speed ?? 0))
    }, [boardOverview])

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
        // 暂时保留，后续可以接入 useSwitchDataSource mutation
    }, [])

    const handleModuleSourceChange = useCallback((moduleKey: string, value: string) => {
        const normalized = normalizeDataSourceValue(value) ?? null
        setModuleSources((prev) => {
            if (prev[moduleKey] === normalized) return prev
            return { ...prev, [moduleKey]: normalized }
        })
    }, [])

    const handleBoardSelect = useCallback((board: string) => {
        setSelectedBoard(board)
        setBoardDrawerOpen(true)
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

    const strengthFallbackLabel = useMemo(
        () => getFallbackLabel(strength?.detail),
        [strength, getFallbackLabel]
    )
    const boardFallbackLabel = useMemo(
        () => getFallbackLabel(boardOverview?.detail),
        [boardOverview, getFallbackLabel]
    )

    const diagnostics = useMemo(() => {
        const strengthDetail = (strength?.detail || {}) as Record<string, unknown>
        const boardDetail = (boardOverview?.detail || {}) as Record<string, unknown>
        const strengthFailure = strengthItemsCount > 0
            ? null
            : (() => {
                const failure = strengthDetail.latest_failure as Record<string, unknown> | undefined
                return failure?.code ? String(failure.code) : null
            })()
        const boardFailure = boardItemsCount > 0
            ? null
            : (() => {
                const failure = boardDetail.latest_failure as Record<string, unknown> | undefined
                return failure?.code ? String(failure.code) : null
            })()
        const requestedSource = String(
            boardDetail.requested_source || strengthDetail.requested_source || 'auto'
        )
        const effectiveSource = String(
            boardItemsCount > 0
                ? (boardDetail.effective_source || boardOverview?.data_source || dataSource || '--')
                : strengthItemsCount > 0
                    ? (strengthDetail.effective_source || strength?.data_source || dataSource || '--')
                    : (boardDetail.effective_source || strengthDetail.effective_source || dataSource || '--')
        )
        const failureCode = boardFailure || strengthFailure
        const failureSummary = failureCode
            ? `资金脉冲=${strengthFailure || 'OK'}；板块概览=${boardFailure || 'OK'}`
            : null
        return {
            requestedSource,
            effectiveSource,
            failureCode,
            failureSummary,
        }
    }, [boardOverview?.detail, boardOverview?.data_source, boardItemsCount, strength?.detail, strength?.data_source, strengthItemsCount, dataSource])

    // ============ 渲染 ============

    return (
        <PageContainer
            header={{
                title: '实时总览',
                subTitle: 'Real-time Market Dashboard',
                extra: [
                    <Button
                        key="market-view"
                        type="primary"
                        icon={<LineChartOutlined />}
                        onClick={() => navigate('/market')}
                    >
                        完整行情视图
                    </Button>,
                ],
            }}
        >
            <ProCard ghost gutter={[24, 24]} wrap>
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

                {/* Header Area: Key Metrics & Controls */}
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

                <ProCard colSpan={24} bordered boxShadow>
                    <Alert
                        type={diagnostics.failureCode ? 'warning' : 'info'}
                        showIcon
                        message={`链路诊断：请求源 ${diagnostics.requestedSource} / 生效源 ${diagnostics.effectiveSource}`}
                        description={
                            diagnostics.failureCode
                                ? `最近失败码：${diagnostics.failureCode}（${diagnostics.failureSummary || '模块级诊断已记录'}，已按当前策略返回可用结果或陈旧快照）`
                                : '当前链路正常，支持盘后陈旧快照展示。'
                        }
                    />
                </ProCard>

                {/* Core Market Data: Strength & Boards */}
                <ProCard
                    colSpan={24}
                    bordered
                    boxShadow
                    title="资金脉冲 (Real-time Flow)"
                    headStyle={{ fontWeight: 'bold' }}
                >
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

                <ProCard
                    colSpan={24}
                    bordered
                    boxShadow
                    title="板块概览 (Board Overview)"
                    headStyle={{ fontWeight: 'bold' }}
                >
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
                        onBoardSelect={handleBoardSelect}
                        selectedBoard={selectedBoard}
                    />
                </ProCard>
            </ProCard>
            <BoardDriversDrawer
                open={boardDrawerOpen && Boolean(selectedBoard)}
                boardName={selectedBoard}
                loading={boardDriversLoading || boardDriversFetching}
                data={boardDrivers}
                onClose={() => setBoardDrawerOpen(false)}
            />
        </PageContainer>
    )
}

export default Dashboard
