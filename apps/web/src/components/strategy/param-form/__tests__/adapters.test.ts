import {
    buildDefaultParamValues,
    fromGeneratorStrategyParams,
    fromStrategyCenterParams,
    toPayloadParamMap,
} from '../adapters';

describe('strategy param adapters', () => {
    it('converts strategy-center param definitions', () => {
        const defs = fromStrategyCenterParams({
            short_period: {
                type: 'int',
                default: 10,
                min: 2,
                max: 30,
                label: '短期均线',
                description: '短周期窗口',
            },
            symbols: {
                type: 'list',
                default: ['000001.SZ', '600519.SH'],
                choices: ['000001.SZ', '600519.SH'],
            },
        });

        expect(defs.short_period.type).toBe('int');
        expect(defs.short_period.label).toBe('短期均线');
        expect(defs.symbols.type).toBe('list');
        expect(defs.symbols.choices).toEqual([
            { label: '000001.SZ', value: '000001.SZ' },
            { label: '600519.SH', value: '600519.SH' },
        ]);
    });

    it('converts generator strategy params and keeps select options', () => {
        const defs = fromGeneratorStrategyParams({
            enabled: {
                type: 'boolean',
                default: true,
                description: '是否启用',
            },
            mode: {
                type: 'select',
                default: 'fast',
                options: [
                    { label: '快速', value: 'fast' },
                    { label: '稳健', value: 'steady' },
                ],
            },
        });

        expect(defs.enabled.type).toBe('bool');
        expect(defs.mode.type).toBe('select');
        expect(defs.mode.choices).toEqual([
            { label: '快速', value: 'fast' },
            { label: '稳健', value: 'steady' },
        ]);
    });

    it('builds defaults and payload with normalized value types', () => {
        const definitions = fromStrategyCenterParams({
            short_period: {
                type: 'int',
                default: 5,
                min: 2,
                max: 20,
            },
            deviation: {
                type: 'float',
                default: 0.6,
                min: 0,
                max: 1,
            },
            symbols: {
                type: 'list',
                default: '000001.SZ, 600519.SH',
            },
            enabled: {
                type: 'bool',
                default: false,
            },
            note: {
                type: 'str',
                default: 'intraday',
            },
        });

        const defaults = buildDefaultParamValues(definitions);
        expect(defaults).toEqual({
            short_period: 5,
            deviation: 0.6,
            symbols: ['000001.SZ', '600519.SH'],
            enabled: false,
            note: 'intraday',
        });

        const payload = toPayloadParamMap(definitions, {
            ...defaults,
            short_period: 100,
            symbols: ['000001.SZ', '600036.SH'],
        });
        expect(payload).toEqual({
            short_period: 20,
            deviation: 0.6,
            symbols: '000001.SZ,600036.SH',
            enabled: false,
            note: 'intraday',
        });
    });
});
