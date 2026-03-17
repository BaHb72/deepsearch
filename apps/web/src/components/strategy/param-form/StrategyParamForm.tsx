import React, { useCallback } from 'react';
import { Input, InputNumber, Select, Space, Switch, Tooltip, Typography } from 'antd';
import type { UnifiedParamDef, UnifiedParamMap, UnifiedParamValue } from './types';
import { upsertParamValue } from './adapters';

const { Text } = Typography;

export interface StrategyParamFormProps {
    definitions: Record<string, UnifiedParamDef>;
    value: UnifiedParamMap;
    onChange: (next: UnifiedParamMap) => void;
    disabled?: boolean;
    emptyText?: string;
}

const toNumber = (value: UnifiedParamValue | undefined): number | undefined => {
    if (typeof value === 'number') {
        return value;
    }
    if (typeof value === 'string' && value !== '') {
        const parsed = Number(value);
        if (Number.isFinite(parsed)) {
            return parsed;
        }
    }
    return undefined;
};

const StrategyParamForm: React.FC<StrategyParamFormProps> = ({
    definitions,
    value,
    onChange,
    disabled = false,
    emptyText = '当前策略未声明可配置参数。',
}) => {
    const updateField = useCallback(
        (key: string, nextValue: UnifiedParamValue | undefined) => {
            onChange(upsertParamValue(value, key, nextValue));
        },
        [onChange, value],
    );

    const entries = Object.entries(definitions);
    if (!entries.length) {
        return <Text type="secondary">{emptyText}</Text>;
    }

    return (
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
            {entries.map(([key, def]) => {
                const currentValue = value[key];
                const renderLabel = (
                    <Space direction="vertical" size={0}>
                        <Text strong>{def.label || key}</Text>
                        <Text type="secondary">{`${key} · ${def.type}`}</Text>
                    </Space>
                );

                const withTooltip = (node: React.ReactNode) => {
                    if (!def.description) {
                        return node;
                    }
                    return <Tooltip title={def.description}>{node}</Tooltip>;
                };

                return (
                    <div
                        key={key}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: 12,
                        }}
                    >
                        {renderLabel}

                        {def.type === 'bool' &&
                            withTooltip(
                                <Switch
                                    disabled={disabled}
                                    checked={Boolean(currentValue)}
                                    onChange={(checked) => updateField(key, checked)}
                                />,
                            )}

                        {(def.type === 'int' || def.type === 'float') &&
                            withTooltip(
                                <InputNumber
                                    disabled={disabled}
                                    min={def.min}
                                    max={def.max}
                                    step={def.step || (def.type === 'int' ? 1 : 0.01)}
                                    value={toNumber(currentValue)}
                                    onChange={(next) => {
                                        if (next === null || next === undefined) {
                                            updateField(key, undefined);
                                            return;
                                        }
                                        updateField(key, Number(next));
                                    }}
                                />,
                            )}

                        {def.type === 'str' &&
                            withTooltip(
                                <Input
                                    disabled={disabled}
                                    style={{ maxWidth: 280 }}
                                    value={
                                        typeof currentValue === 'string'
                                            ? currentValue
                                            : currentValue === undefined
                                                ? ''
                                                : String(currentValue)
                                    }
                                    onChange={(event) =>
                                        updateField(key, event.target.value)
                                    }
                                />,
                            )}

                        {def.type === 'list' &&
                            withTooltip(
                                <Select
                                    disabled={disabled}
                                    mode="tags"
                                    tokenSeparators={[',']}
                                    style={{ minWidth: 220, maxWidth: 320 }}
                                    value={
                                        Array.isArray(currentValue)
                                            ? currentValue.map((item) => String(item))
                                            : typeof currentValue === 'string' && currentValue !== ''
                                                ? currentValue
                                                    .split(',')
                                                    .map((item) => item.trim())
                                                    .filter(Boolean)
                                                : []
                                    }
                                    onChange={(next) => {
                                        updateField(
                                            key,
                                            next.map((item) => String(item).trim()).filter(Boolean),
                                        );
                                    }}
                                />,
                            )}

                        {def.type === 'select' &&
                            withTooltip(
                                <Select
                                    disabled={disabled}
                                    allowClear
                                    style={{ minWidth: 220, maxWidth: 320 }}
                                    options={(def.choices || []).map((choice) => ({
                                        label: choice.label,
                                        value: choice.value,
                                    }))}
                                    value={currentValue as string | number | boolean | undefined}
                                    onChange={(nextValue) => {
                                        if (
                                            typeof nextValue === 'string' ||
                                            typeof nextValue === 'number' ||
                                            typeof nextValue === 'boolean'
                                        ) {
                                            updateField(key, nextValue);
                                            return;
                                        }
                                        updateField(key, undefined);
                                    }}
                                />,
                            )}
                    </div>
                );
            })}
        </Space>
    );
};

export default StrategyParamForm;
