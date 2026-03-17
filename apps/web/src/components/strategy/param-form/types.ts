export type UnifiedParamType = 'int' | 'float' | 'bool' | 'str' | 'list' | 'select';

export type UnifiedParamPrimitive = boolean | number | string;

export type UnifiedParamValue = UnifiedParamPrimitive | string[];

export type UnifiedParamPayloadValue = UnifiedParamPrimitive;

export type UnifiedParamMap = Record<string, UnifiedParamValue>;

export type UnifiedParamPayloadMap = Record<string, UnifiedParamPayloadValue>;

export interface UnifiedParamChoice {
    label: string;
    value: UnifiedParamPrimitive;
}

export interface UnifiedParamDef {
    type: UnifiedParamType;
    default?: unknown;
    min?: number;
    max?: number;
    step?: number;
    label?: string;
    description?: string;
    choices?: UnifiedParamChoice[];
}
