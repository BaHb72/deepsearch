// @ts-nocheck
import React, {useCallback, useEffect, useState} from 'react'
import {
    Alert,
    App as AntApp,
    Button,
    Card,
    Col,
    Empty,
    Input,
    Row,
    Select,
    Space,
    Spin,
    Tag,
    Tooltip,
    Typography,
} from 'antd'
import {ReloadOutlined, SaveOutlined, SearchOutlined, UndoOutlined,} from '@ant-design/icons'

const {Title, Text} = Typography
const {Option} = Select

interface ModuleConfig {
    name: string
    label: string
    description: string
    category: string
    currentConfig: {
        primary: string | null
        fallback: string[]
    }
    defaultConfig: {
        primary: string
        fallback: string[]
    }
    availableSources: string[]
}

interface CategoryInfo {
    key: string
    label: string
    description: string
}

interface ModuleListResponse {
    modules: ModuleConfig[]
    categories: CategoryInfo[]
}

interface PendingChange {
    primary?: string
    fallback?: string[]
}

const DATA_SOURCE_LABELS: Record<string, string> = {
    amazingdata: 'AmazingData',
    akshare: 'AkShare',
    cloudflare: 'Cloudflare',
    tushare: 'TuShare',
}

const DATA_SOURCE_COLORS: Record<string, string> = {
    amazingdata: '#1890ff',
    akshare: '#52c41a',
    cloudflare: '#722ed1',
    tushare: '#fa8c16',
}

/**
 * 模块数据源配置组件
 */
const ModuleSourceConfig: React.FC = () => {
    const {message} = AntApp.useApp()
    const [loading, setLoading] = useState(false)
    const [saving, setSaving] = useState(false)
    const [modules, setModules] = useState<ModuleConfig[]>([])
    const [categories, setCategories] = useState<CategoryInfo[]>([])
    const [searchText, setSearchText] = useState('')
    const [selectedCategory, setSelectedCategory] = useState<string>('all')
    const [pendingChanges, setPendingChanges] = useState<Record<string, PendingChange>>({})

    // 加载模块列表
    const loadModules = useCallback(async () => {
        setLoading(true)
        try {
            const response = await fetch('/api/module-sources')
            if (!response.ok) {
                throw new Error('加载失败')
            }
            const data: ModuleListResponse = await response.json()
            setModules(data.modules)
            setCategories(data.categories)
        } catch (error) {
            message.error('加载模块配置失败')
            console.error(error)
        } finally {
            setLoading(false)
        }
    }, [message])

    useEffect(() => {
        loadModules()
    }, [loadModules])

    // 更新模块配置
    const handlePrimaryChange = (moduleName: string, value: string) => {
        setPendingChanges(prev => ({
            ...prev,
            [moduleName]: {
                ...prev[moduleName],
                primary: value,
            },
        }))
    }

    const handleFallbackChange = (moduleName: string, values: string[]) => {
        setPendingChanges(prev => ({
            ...prev,
            [moduleName]: {
                ...prev[moduleName],
                fallback: values,
            },
        }))
    }

    // 重置单个模块
    const handleResetModule = (moduleName: string, defaultConfig: ModuleConfig['defaultConfig']) => {
        setPendingChanges(prev => ({
            ...prev,
            [moduleName]: {
                primary: defaultConfig.primary,
                fallback: defaultConfig.fallback,
            },
        }))
    }

    // 保存所有更改
    const handleSaveAll = async () => {
        if (Object.keys(pendingChanges).length === 0) {
            message.info('没有需要保存的更改')
            return
        }

        setSaving(true)
        try {
            for (const [moduleName, changes] of Object.entries(pendingChanges)) {
                const response = await fetch(`/api/module-sources/${moduleName}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(changes),
                })
                if (!response.ok) {
                    throw new Error(`保存 ${moduleName} 失败`)
                }
            }
            message.success('配置已保存')
            setPendingChanges({})
            await loadModules()
        } catch (error) {
            message.error('保存失败')
            console.error(error)
        } finally {
            setSaving(false)
        }
    }

    // 重新加载配置
    const handleReload = async () => {
        try {
            await fetch('/api/module-sources/reload', {method: 'POST'})
            message.success('配置已重新加载')
            await loadModules()
            setPendingChanges({})
        } catch (error) {
            message.error('重新加载失败')
        }
    }

    // 过滤模块
    const filteredModules = modules.filter(m => {
        const matchCategory = selectedCategory === 'all' || m.category === selectedCategory
        const matchSearch = !searchText ||
            m.label.toLowerCase().includes(searchText.toLowerCase()) ||
            m.name.toLowerCase().includes(searchText.toLowerCase())
        return matchCategory && matchSearch
    })

    // 按分类分组
    const groupedModules = filteredModules.reduce((acc, module) => {
        const cat = module.category
        if (!acc[cat]) acc[cat] = []
        acc[cat].push(module)
        return acc
    }, {} as Record<string, ModuleConfig[]>)

    const getCategoryLabel = (key: string) => {
        const cat = categories.find(c => c.key === key)
        return cat?.label || key
    }

    const hasChanges = Object.keys(pendingChanges).length > 0

    const getEffectiveConfig = (module: ModuleConfig): ModuleConfig['currentConfig'] => {
        const pending = pendingChanges[module.name]
        if (!pending) return module.currentConfig
        return {
            primary: pending.primary ?? module.currentConfig.primary,
            fallback: pending.fallback ?? module.currentConfig.fallback,
        }
    }

    if (loading && modules.length === 0) {
        return (
            <div style={{textAlign: 'center', padding: '50px'}}>
                <Spin size="large"/>
                <div style={{marginTop: 16}}>加载中...</div>
            </div>
        )
    }

    return (
        <div style={{padding: '16px 0'}}>
            {/* 工具栏 */}
            <Row gutter={16} style={{marginBottom: 16}} align="middle">
                <Col flex="auto">
                    <Space>
                        <Input
                            placeholder="搜索模块..."
                            prefix={<SearchOutlined/>}
                            value={searchText}
                            onChange={e => setSearchText(e.target.value)}
                            style={{width: 200}}
                            allowClear
                        />
                        <Select
                            value={selectedCategory}
                            onChange={setSelectedCategory}
                            style={{width: 150}}
                        >
                            <Option value="all">全部分类</Option>
                            {categories.map(cat => (
                                <Option key={cat.key} value={cat.key}>{cat.label}</Option>
                            ))}
                        </Select>
                    </Space>
                </Col>
                <Col>
                    <Space>
                        <Button
                            icon={<ReloadOutlined/>}
                            onClick={handleReload}
                        >
                            重载配置
                        </Button>
                        <Button
                            type="primary"
                            icon={<SaveOutlined/>}
                            onClick={handleSaveAll}
                            loading={saving}
                            disabled={!hasChanges}
                        >
                            保存更改 {hasChanges && `(${Object.keys(pendingChanges).length})`}
                        </Button>
                    </Space>
                </Col>
            </Row>

            {hasChanges && (
                <Alert
                    message="有未保存的更改"
                    description={'点击"保存更改"按钮保存所有修改到配置文件。'}
                    type="warning"
                    showIcon
                    style={{marginBottom: 16}}
                />
            )}

            {/* 模块列表 */}
            {filteredModules.length === 0 ? (
                <Empty description="没有找到模块"/>
            ) : (
                Object.entries(groupedModules).map(([category, categoryModules]) => (
                    <Card
                        key={category}
                        title={getCategoryLabel(category)}
                        size="small"
                        style={{marginBottom: 16}}
                        headStyle={{background: '#fafafa'}}
                    >
                        {categoryModules.map(module => {
                            const effectiveConfig = getEffectiveConfig(module)
                            const isModified = !!pendingChanges[module.name]

                            return (
                                <div
                                    key={module.name}
                                    style={{
                                        padding: '12px 0',
                                        borderBottom: '1px solid #f0f0f0',
                                    }}
                                >
                                    <Row gutter={16} align="middle">
                                        <Col span={6}>
                                            <Space direction="vertical" size={0}>
                                                <Text strong>
                                                    {module.label}
                                                    {isModified && (
                                                        <Tag color="orange" style={{marginLeft: 8}}>
                                                            已修改
                                                        </Tag>
                                                    )}
                                                </Text>
                                                <Text type="secondary" style={{fontSize: 12}}>
                                                    {module.description || module.name}
                                                </Text>
                                            </Space>
                                        </Col>
                                        <Col span={6}>
                                            <Space direction="vertical" size={4} style={{width: '100%'}}>
                                                <Text type="secondary" style={{fontSize: 12}}>主数据源</Text>
                                                <Select
                                                    value={effectiveConfig.primary || undefined}
                                                    onChange={v => handlePrimaryChange(module.name, v)}
                                                    style={{width: '100%'}}
                                                    placeholder="选择主数据源"
                                                >
                                                    {module.availableSources.map(source => (
                                                        <Option key={source} value={source}>
                                                            <Tag color={DATA_SOURCE_COLORS[source] || 'default'}>
                                                                {DATA_SOURCE_LABELS[source] || source}
                                                            </Tag>
                                                        </Option>
                                                    ))}
                                                </Select>
                                            </Space>
                                        </Col>
                                        <Col span={8}>
                                            <Space direction="vertical" size={4} style={{width: '100%'}}>
                                                <Text type="secondary" style={{fontSize: 12}}>回退数据源</Text>
                                                <Select
                                                    mode="multiple"
                                                    value={effectiveConfig.fallback}
                                                    onChange={v => handleFallbackChange(module.name, v)}
                                                    style={{width: '100%'}}
                                                    placeholder="选择回退数据源"
                                                    maxTagCount={2}
                                                >
                                                    {module.availableSources
                                                        .filter(s => s !== effectiveConfig.primary)
                                                        .map(source => (
                                                            <Option key={source} value={source}>
                                                                <Tag color={DATA_SOURCE_COLORS[source] || 'default'}>
                                                                    {DATA_SOURCE_LABELS[source] || source}
                                                                </Tag>
                                                            </Option>
                                                        ))}
                                                </Select>
                                            </Space>
                                        </Col>
                                        <Col span={4} style={{textAlign: 'right'}}>
                                            <Tooltip title="重置为默认配置">
                                                <Button
                                                    size="small"
                                                    icon={<UndoOutlined/>}
                                                    onClick={() => handleResetModule(module.name, module.defaultConfig)}
                                                >
                                                    重置
                                                </Button>
                                            </Tooltip>
                                        </Col>
                                    </Row>
                                </div>
                            )
                        })}
                    </Card>
                ))
            )}
        </div>
    )
}

export default ModuleSourceConfig
