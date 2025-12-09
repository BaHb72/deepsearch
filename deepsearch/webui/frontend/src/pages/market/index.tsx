import React, { useMemo } from 'react'
import { Alert } from 'antd'
import { ProCard } from '@ant-design/pro-components'

import { useMarketData } from './hooks/useMarketData'
import MarketHeader from './components/MarketHeader'
import StrengthTable from './components/StrengthTable'
import BoardOverviewTable from './components/BoardOverviewTable'
import OrderImbalanceTable from './components/OrderImbalanceTable'
import AuctionQualityTable from './components/AuctionQualityTable'

const MarketData: React.FC = () => {
    const {
        strength,
        boardOverview,
        orderImbalance,
        auctionQuality,
        moduleSources,
        selectedWindow,
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
        setBoardType,
        getFallbackLabel,
    } = useMarketData()

    const strengthFallbackLabel = useMemo(
        () => getFallbackLabel(strength?.detail),
        [strength, getFallbackLabel]
    )
    const boardFallbackLabel = useMemo(
        () => getFallbackLabel(boardOverview?.detail),
        [boardOverview, getFallbackLabel]
    )
    const orderFallbackLabel = useMemo(
        () => getFallbackLabel(orderImbalance?.detail),
        [orderImbalance, getFallbackLabel]
    )
    const auctionFallbackLabel = useMemo(
        () => getFallbackLabel(auctionQuality?.detail),
        [auctionQuality, getFallbackLabel]
    )

    return (
        <ProCard direction="column" ghost gutter={[0, 16]} style={{ padding: 24 }}>
            {fetchError && (
                <Alert
                    type="error"
                    showIcon
                    message="市场行情数据拉取失败"
                    description={fetchError}
                    closable
                    style={{ marginBottom: 16 }}
                />
            )}

            <ProCard>
                <MarketHeader
                    phase={phase}
                    isStale={isStale}
                    globalAsOf={globalAsOf}
                    retrievedAt={retrievedAt}
                    dataSource={dataSource}
                    activeDataSource={activeDataSource}
                    adapterOptions={adapterOptions}
                    cacheInfo={cacheInfo}
                    realtimeSource={realtimeSource}
                    autoRefresh={autoRefresh}
                    canAutoRefresh={canAutoRefresh}
                    loading={loading}
                    refreshing={refreshing}
                    onSwitchDataSource={handleSwitchDataSource}
                    onAutoRefreshChange={handleAutoRefreshChange}
                    onRefresh={() => fetchAll()}
                />
            </ProCard>

            <ProCard ghost gutter={16}>
                <ProCard colSpan={24} ghost>
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

            <ProCard ghost gutter={16}>
                <ProCard colSpan={14} ghost>
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
                <ProCard colSpan={10} ghost>
                    <OrderImbalanceTable
                        items={orderItems}
                        loading={loading}
                        refreshing={refreshing}
                        isStale={isStale}
                        moduleSource={moduleSources.order_imbalance}
                        moduleSourceOptions={moduleSourceOptions}
                        fallbackLabel={orderFallbackLabel}
                        onModuleSourceChange={handleModuleSourceChange}
                    />
                </ProCard>
            </ProCard>

            <ProCard ghost>
                <AuctionQualityTable
                    items={auctionItems}
                    loading={loading}
                    refreshing={refreshing}
                    isStale={isStale}
                    moduleSource={moduleSources.auction_quality}
                    moduleSourceOptions={moduleSourceOptions}
                    fallbackLabel={auctionFallbackLabel}
                    onModuleSourceChange={handleModuleSourceChange}
                />
            </ProCard>
        </ProCard>
    )
}

export default MarketData
