// @ts-nocheck
import React, {useMemo} from 'react'
import {Alert, Button} from 'antd'
import {PageContainer, ProCard} from '@ant-design/pro-components'
import {useNavigate} from 'react-router-dom'
import {LineChartOutlined} from '@ant-design/icons'

// Import Market Components
import {useMarketData} from '../market/hooks/useMarketData'
import MarketHeader from '../market/components/MarketHeader'
import StrengthTable from '../market/components/StrengthTable'
import BoardOverviewTable from '../market/components/BoardOverviewTable'

const Dashboard: React.FC = () => {
    const navigate = useNavigate()
    // Reuse the market data hook
  const {
      phase,
      isStale,
      globalAsOf,
      retrievedAt,
      dataSource,
      activeDataSource,
      adapterOptions,
      cacheInfo,
      realtimeSource,
      autoRefresh,
      canAutoRefresh,
    loading,
      refreshing,
      fetchError,

      // Data Items
      strengthItems,
      boardItems,

      // State & Handlers
      strength,
      boardOverview,
      moduleSources,
      moduleSourceOptions,
      selectedWindow,
      boardType,

      handleSwitchDataSource,
      handleAutoRefreshChange,
      fetchAll,
      setSelectedWindow,
      setBoardType,
      handleModuleSourceChange,
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

  return (
      <PageContainer
          header={{
              title: '实时总览',
              subTitle: 'Real-time Market Dashboard',
              extra: [
                  <Button
                      key="market-view"
                      type="primary"
                      icon={<LineChartOutlined/>}
                      onClick={() => navigate('/market')}
                  >
                      完整行情视图
                  </Button>
              ]
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

              {/* Core Market Data: Strength & Boards */}
              <ProCard
                  colSpan={24}
                  bordered
                  boxShadow
                  title="资金脉冲 (Real-time Flow)"
                  headStyle={{fontWeight: 'bold'}}
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
                  headStyle={{fontWeight: 'bold'}}
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
                  />
        </ProCard>
      </ProCard>
      </PageContainer>
  )
}

export default Dashboard
