import React, { useState, useCallback, useMemo, useRef } from 'react'
import {
  Table,
  Card,
  Space,
  Button,
  Input,
  Dropdown,
  Checkbox,
  Tooltip,
  message
} from 'antd'
import {
  ReloadOutlined,
  SettingOutlined,
  DownloadOutlined,
  FullscreenOutlined,
  FullscreenExitOutlined,
  ColumnHeightOutlined,
  PushpinOutlined,
} from '@ant-design/icons'
import { useFullscreen } from 'ahooks'
import { exportToExcel, exportToCSV } from '@/utils/export'
import './index.scss'

const { Search } = Input

/**
 * 增强型数据表格组件
 */
const DataTable = ({
  // 数据相关
  columns: propColumns = [],
  dataSource = [],
  loading = false,
  rowKey = 'id',

  // 分页相关
  pagination = false,

  // 选择相关
  rowSelection = null,

  // 功能开关
  showSearch = true,
  showRefresh = true,
  showColumnSetting = true,
  showExport = true,
  showSizeChanger = true,
  showFullscreen = true,

  // 样式相关
  title,
  extra,
  bordered = false,
  size: propSize = 'middle',
  scroll,
  sticky = false,

  // 事件处理
  onRefresh,
  onChange,
  onRow,

  // 其他配置
  ...restProps
}) => {
  const tableRef = useRef(null)
  const [searchText, setSearchText] = useState('')
  const [selectedColumns, setSelectedColumns] = useState(() =>
    propColumns.map(col => col.dataIndex || col.key)
  )
  const [pinnedColumns, setPinnedColumns] = useState(new Set())
  const [tableSize, setTableSize] = useState(propSize)
  const [isFullscreen, { toggleFullscreen }] = useFullscreen(tableRef)

  // 处理列配置
  const processedColumns = useMemo(() => {
    let cols = propColumns
      .filter(col => selectedColumns.includes(col.dataIndex || col.key))
      .map(col => {
        // 添加固定列功能
        if (pinnedColumns.has(col.dataIndex || col.key)) {
          return { ...col, fixed: 'left' }
        }
        return col
      })

    // 添加搜索高亮
    if (searchText) {
      cols = cols.map(col => ({
        ...col,
        render: (text, record, index) => {
          const originalRender = col.render || ((t) => t)
          const rendered = originalRender(text, record, index)

          if (typeof rendered === 'string' && rendered.includes(searchText)) {
            const parts = rendered.split(new RegExp(`(${searchText})`, 'gi'))
            return (
              <span>
                {parts.map((part, i) =>
                  part.toLowerCase() === searchText.toLowerCase() ? (
                    <mark key={i} className="search-highlight">{part}</mark>
                  ) : (
                    part
                  )
                )}
              </span>
            )
          }

          return rendered
        },
      }))
    }

    return cols
  }, [propColumns, selectedColumns, pinnedColumns, searchText])

  // 过滤数据
  const filteredData = useMemo(() => {
    if (!searchText) return dataSource

    return dataSource.filter(record => {
      return Object.values(record).some(value =>
        String(value).toLowerCase().includes(searchText.toLowerCase())
      )
    })
  }, [dataSource, searchText])

  // 列设置菜单
  const columnSettingMenu = useMemo(() => ({
    items: propColumns.map(col => ({
      key: col.dataIndex || col.key,
      label: (
        <Space>
          <Checkbox
            checked={selectedColumns.includes(col.dataIndex || col.key)}
            onChange={(e) => {
              const key = col.dataIndex || col.key
              if (e.target.checked) {
                setSelectedColumns(prev => [...prev, key])
              } else {
                setSelectedColumns(prev => prev.filter(k => k !== key))
              }
            }}
          />
          <span>{col.title}</span>
          <Tooltip title={pinnedColumns.has(col.dataIndex || col.key) ? '取消固定' : '固定列'}>
            <PushpinOutlined
              className={pinnedColumns.has(col.dataIndex || col.key) ? 'pinned' : ''}
              onClick={(e) => {
                e.stopPropagation()
                const key = col.dataIndex || col.key
                setPinnedColumns(prev => {
                  const next = new Set(prev)
                  if (next.has(key)) {
                    next.delete(key)
                  } else {
                    next.add(key)
                  }
                  return next
                })
              }}
            />
          </Tooltip>
        </Space>
      ),
    })),
  }), [propColumns, selectedColumns, pinnedColumns])

  // 导出菜单
  const exportMenu = useMemo(() => ({
    items: [
      {
        key: 'excel',
        label: 'Excel',
        icon: <DownloadOutlined />,
        onClick: () => handleExport('excel'),
      },
      {
        key: 'csv',
        label: 'CSV',
        icon: <DownloadOutlined />,
        onClick: () => handleExport('csv'),
      },
    ],
  }), [])

  // 表格尺寸菜单
  const sizeMenu = useMemo(() => ({
    items: [
      { key: 'large', label: '宽松' },
      { key: 'middle', label: '中等' },
      { key: 'small', label: '紧凑' },
    ],
    onClick: ({ key }) => setTableSize(key),
  }), [])

  // 处理导出
  const handleExport = useCallback((type) => {
    const exportData = filteredData.map(record => {
      const row = {}
      processedColumns.forEach(col => {
        const value = record[col.dataIndex || col.key]
        row[col.title] = col.render ? col.render(value, record) : value
      })
      return row
    })

    const fileName = `数据导出_${new Date().getTime()}`

    if (type === 'excel') {
      exportToExcel(exportData, fileName)
    } else {
      exportToCSV(exportData, fileName)
    }

    message.success('导出成功')
  }, [filteredData, processedColumns])

  // 处理刷新
  const handleRefresh = useCallback(() => {
    setSearchText('')
    onRefresh?.()
  }, [onRefresh])

  // 渲染工具栏
  const renderToolbar = () => (
    <Space className="table-toolbar">
      {showSearch && (
        <Search
          placeholder="搜索..."
          allowClear
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ width: 200 }}
        />
      )}

      {showRefresh && (
        <Tooltip title="刷新">
          <Button
            icon={<ReloadOutlined spin={loading} />}
            onClick={handleRefresh}
          />
        </Tooltip>
      )}

      {showColumnSetting && (
        <Dropdown menu={columnSettingMenu} trigger={['click']}>
          <Tooltip title="列设置">
            <Button icon={<SettingOutlined />} />
          </Tooltip>
        </Dropdown>
      )}

      {showSizeChanger && (
        <Dropdown menu={sizeMenu} trigger={['click']}>
          <Tooltip title="密度">
            <Button icon={<ColumnHeightOutlined />} />
          </Tooltip>
        </Dropdown>
      )}

      {showExport && (
        <Dropdown menu={exportMenu} trigger={['click']}>
          <Tooltip title="导出">
            <Button icon={<DownloadOutlined />} />
          </Tooltip>
        </Dropdown>
      )}

      {showFullscreen && (
        <Tooltip title={isFullscreen ? '退出全屏' : '全屏'}>
          <Button
            icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
            onClick={toggleFullscreen}
          />
        </Tooltip>
      )}

      {extra}
    </Space>
  )

  return (
    <div ref={tableRef} className={`data-table-wrapper ${isFullscreen ? 'fullscreen' : ''}`}>
      <Card
        variant={bordered ? 'outlined' : 'borderless'}
        title={title}
        extra={renderToolbar()}
        styles={{ body: { padding: 0 } }}
      >
        <Table
          columns={processedColumns}
          dataSource={filteredData}
          loading={loading}
          rowKey={rowKey}
          pagination={pagination}
          rowSelection={rowSelection}
          size={tableSize}
          scroll={scroll}
          sticky={sticky}
          onChange={onChange}
          onRow={onRow}
          {...restProps}
        />
      </Card>
    </div>
  )
}

export default React.memo(DataTable)
