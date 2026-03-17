import type { StrategyParameter } from '../../../api/strategy';
import type { StrategyParamDef } from '../../../api/strategy-center';
import type {
    UnifiedParamChoice,
    UnifiedParamDef,
    UnifiedParamMap,
    UnifiedParamPayloadMap,
    UnifiedParamPrimitive,
    UnifiedParamValue,
} from './types';

const clamp = (value: number, min?: number, max?: number): number => {
    if (typeof min === 'number' && value < min) {
        return min;
    }
    if (typeof max === 'number' && value > max) {
        return max;
    }
    return value;
};

const toPrimitive = (value: unknown): UnifiedParamPrimitive | undefined => {
    if (typeof value === 'boolean' || typeof value === 'string') {
        return value;
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value;
    }
    return undefined;
};

const toChoice = (item: unknown): UnifiedParamChoice | null => {
    if (
        typeof item === 'object' &&
        item !== null &&
        'label' in item &&
        'value' in item
    ) {
        const raw = item as { label: unknown; value: unknown };
        const primitive = toPrimitive(raw.value);
        if (primitive === undefined) {
            return null;
        }
        return {
            label: String(raw.label ?? raw.value),
            value: primitive,
        };
    }

    const primitive = toPrimitive(item);
    if (primitive === undefined) {
        return null;
    }
    return {
        label: String(primitive),
        value: primitive,
    };
};

const normalizeChoices = (choices?: unknown[]): UnifiedParamChoice[] | undefined => {
    if (!Array.isArray(choices) || !choices.length) {
        return undefined;
    }
    const normalized = choices
        .map((item) => toChoice(item))
        .filter((item): item is UnifiedParamChoice => item !== null);
    return normalized.length ? normalized : undefined;
};

const normalizeListValue = (value: unknown): string[] | undefined => {
    if (Array.isArray(value)) {
        const normalized = value.map((item) => String(item).trim()).filter(Boolean);
        return normalized.length ? normalized : [];
    }
    if (typeof value === 'string') {
        const normalized = value.split(',').map((item) => item.trim()).filter(Boolean);
        return normalized.length ? normalized : [];
    }
    return undefined;
};

export const fromStrategyCenterParams = (
    params: Record<string, StrategyParamDef>,
): Record<string, UnifiedParamDef> => {
    const definitions: Record<string, UnifiedParamDef> = {};

    Object.entries(params || {}).forEach(([key, def]) => {
        definitions[key] = {
            type: def.type === 'list' ? 'list' : def.type,
            default: def.default,
            min: def.min,
            max: def.max,
            step: def.step,
            label: def.label || key,
            description: def.description,
            choices: normalizeChoices(def.choices),
        };
    });

    return definitions;
};

export const fromGeneratorStrategyParams = (
    params: Record<string, StrategyParameter>,
): Record<string, UnifiedParamDef> => {
    const definitions: Record<string, UnifiedParamDef> = {};

    Object.entries(params || {}).forEach(([key, def]) => {
        const mappedType = (() => {
            if (def.type === 'string') {
                return 'str';
            }
            if (def.type === 'boolean') {
                return 'bool';
            }
            if (def.type === 'select') {
                return 'select';
            }
            return def.type;
        })();

        definitions[key] = {
            type: mappedType,
            default: def.default,
            min: def.min,
            max: def.max,
            label: key,
            description: def.description,
            choices: normalizeChoices(def.options),
        };
    });

    return definitions;
};

export const buildDefaultParamValues = (
    definitions: Record<string, UnifiedParamDef>,
): UnifiedParamMap => {
    const defaults: UnifiedParamMap = {};

    Object.entries(definitions).forEach(([key, def]) => {
        if (def.default === undefined || def.default === null) {
            return;
        }

        if (def.type === 'bool') {
            defaults[key] = Boolean(def.default);
            return;
        }

        if (def.type === 'int') {
            const numeric = Number(def.default);
            if (Number.isFinite(numeric)) {
                defaults[key] = Math.trunc(clamp(numeric, def.min, def.max));
            }
            return;
        }

        if (def.type === 'float') {
            const numeric = Number(def.default);
            if (Number.isFinite(numeric)) {
                defaults[key] = clamp(numeric, def.min, def.max);
            }
            return;
        }

        if (def.type === 'list') {
            const normalized = normalizeListValue(def.default);
            if (normalized !== undefined) {
                defaults[key] = normalized;
            }
            return;
        }

        const primitive = toPrimitive(def.default);
        if (primitive !== undefined) {
            defaults[key] = primitive;
            return;
        }

        defaults[key] = String(def.default);
    });

    return defaults;
};

export const toPayloadParamMap = (
    definitions: Record<string, UnifiedParamDef>,
    values: UnifiedParamMap,
): UnifiedParamPayloadMap => {
    const payload: UnifiedParamPayloadMap = {};

    Object.entries(definitions).forEach(([key, def]) => {
        const rawValue = values[key];
        if (rawValue === undefined || rawValue === null) {
            return;
        }

        if (def.type === 'bool') {
            payload[key] = Boolean(rawValue);
            return;
        }

        if (def.type === 'int') {
            const numeric = Number(rawValue);
            if (Number.isFinite(numeric)) {
                payload[key] = Math.trunc(clamp(numeric, def.min, def.max));
            }
            return;
        }

        if (def.type === 'float') {
            const numeric = Number(rawValue);
            if (Number.isFinite(numeric)) {
                payload[key] = clamp(numeric, def.min, def.max);
            }
            return;
        }

        if (def.type === 'list') {
            const normalized = normalizeListValue(rawValue);
            if (normalized !== undefined) {
                payload[key] = normalized.join(',');
            }
            return;
        }

        if (Array.isArray(rawValue)) {
            payload[key] = rawValue.map((item) => String(item)).join(',');
            return;
        }

        const primitive = toPrimitive(rawValue);
        if (primitive !== undefined) {
            payload[key] = primitive;
            return;
        }

        payload[key] = String(rawValue);
    });

    return payload;
};

export const upsertParamValue = (
    prev: UnifiedParamMap,
    key: string,
    value: UnifiedParamValue | undefined,
): UnifiedParamMap => {
    const next = { ...prev };
    if (value === undefined) {
        delete next[key];
        return next;
    }
    next[key] = value;
    return next;
};
