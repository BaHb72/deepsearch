/**
 * 监控列表抽屉组件
 * 
 * 右侧抽屉，包含股票搜索、添加、列表管理功能
 */
import React, { useState } from 'react';
import { Drawer, Button, List, Space, Typography, Popconfirm, Tag, message } from 'antd';
import { MenuOutlined, DeleteOutlined, ThunderboltOutlined, PlusOutlined } from '@ant-design/icons';
import UniversalStockSearch from '../common/UniversalStockSearch';

const { Text } = Typography;

interface WatchlistStock {
    symbol: string;
    name: string;
    price?: number;
    change?: number;
}

interface WatchlistDrawerProps {
    /** 监控列表 */
    watchlist: WatchlistStock[];
    /** 选中的股票代码 */
    selectedSymbol: string;
    /** 添加股票回调 */
    onAdd: (symbol: string, name: string) => void;
    /** 删除股票回调 */
    onRemove: (symbol: string) => void;
    /** 分析股票回调 */
    onAnalyze: (symbol: string) => void;
    /** 抽屉是否打开 (受控模式) */
    open?: boolean;
    /** 打开/关闭回调 (受控模式) */
    onOpenChange?: (open: boolean) => void;
}

const WatchlistDrawer: React.FC<WatchlistDrawerProps> = ({
    watchlist,
    selectedSymbol,
    onAdd,
    onRemove,
    onAnalyze,
    open: controlledOpen,
    onOpenChange,
}) => {
    const [internalOpen, setInternalOpen] = useState(false);
    const [searchValue, setSearchValue] = useState('');

    // 支持受控和非受控模式
    const isControlled = controlledOpen !== undefined;
    const open = isControlled ? controlledOpen : internalOpen;
    const setOpen = isControlled ? (onOpenChange || (() => { })) : setInternalOpen;

    const handleAdd = () => {
        if (!searchValue) {
            message.warning('请先搜索并选择股票');
            return;
        }
        // searchValue 格式: "代码 名称"
        const parts = searchValue.split(' ');
        if (parts.length >= 2) {
            const symbol = parts[0];
            const name = parts.slice(1).join(' ');

            if (watchlist.some(s => s.symbol === symbol)) {
                message.warning('股票已在监控列表中');
                return;
            }

            onAdd(symbol, name);
            setSearchValue('');
            message.success(`已添加 ${name}`);
        }
    };

    return (
        <Drawer
            title="股票监控列表"
            placement="right"
            width={360}
            onClose={() => setOpen(false)}
            open={open}
            extra={
                <Text type="secondary">{watchlist.length} 只股票</Text>
            }
        >
            {/* 搜索添加区域 */}
            <div style={{ marginBottom: 16 }}>
                <Space.Compact style={{ width: '100%' }}>
                    <UniversalStockSearch
                        value={searchValue}
                        onChange={setSearchValue}
                        placeholder="搜索股票代码/名称"
                        style={{ flex: 1 }}
                    />
                    <Button
                        type="primary"
                        icon={<PlusOutlined />}
                        onClick={handleAdd}
                    >
                        添加
                    </Button>
                </Space.Compact>
            </div>

            {/* 股票列表 */}
            <List
                dataSource={watchlist}
                renderItem={(stock) => (
                    <List.Item
                        style={{
                            background: stock.symbol === selectedSymbol ? '#e6f7ff' : undefined,
                            borderRadius: 4,
                            marginBottom: 4,
                            padding: '8px 12px',
                        }}
                        actions={[
                            <Button
                                key="analyze"
                                type="link"
                                size="small"
                                icon={<ThunderboltOutlined />}
                                onClick={() => {
                                    onAnalyze(stock.symbol);
                                    setOpen(false); // 分析后关闭抽屉
                                }}
                            >
                                分析
                            </Button>,
                            <Popconfirm
                                key="delete"
                                title="确定删除?"
                                onConfirm={() => onRemove(stock.symbol)}
                                okText="是"
                                cancelText="否"
                            >
                                <Button
                                    type="link"
                                    size="small"
                                    danger
                                    icon={<DeleteOutlined />}
                                />
                            </Popconfirm>,
                        ]}
                    >
                        <List.Item.Meta
                            title={
                                <Space>
                                    <Text strong>{stock.name}</Text>
                                    {stock.symbol === selectedSymbol && (
                                        <Tag color="blue">当前</Tag>
                                    )}
                                </Space>
                            }
                            description={
                                <Space>
                                    <Text type="secondary">{stock.symbol}</Text>
                                    {stock.price && (
                                        <Text
                                            style={{
                                                color: (stock.change || 0) >= 0 ? '#cf1322' : '#3f8600'
                                            }}
                                        >
                                            ¥{stock.price.toFixed(2)}
                                            {stock.change !== undefined && (
                                                <span> ({stock.change >= 0 ? '+' : ''}{stock.change.toFixed(2)}%)</span>
                                            )}
                                        </Text>
                                    )}
                                </Space>
                            }
                        />
                    </List.Item>
                )}
                locale={{ emptyText: '暂无监控股票，请添加' }}
            />
        </Drawer>
    );
};

export default WatchlistDrawer;
