/**
 * FieldMapper - 字段映射器
 * 将原始数据转换为 RichDataResponse 格式
 */
import type { DataSourceType, DataCapability } from './types'
import type {
    RichDataResponse,
    RichDataMeta,
    FieldMapping,
    CoreData,
} from './types/rich-data'
import { CAPABILITY_MAPPINGS } from './field-mappings'

/**
 * 字段映射器类
 */
export class FieldMapper {
    private mappings: FieldMapping[]

    constructor(mappings: FieldMapping[]) {
        this.mappings = mappings
    }

    /**
     * 从单条原始数据中提取核心字段
     */
    extractCore<TCore extends CoreData>(
        rawItem: Record<string, unknown>,
        source: DataSourceType
    ): TCore {
        const core: Record<string, unknown> = {}

        for (const mapping of this.mappings) {
            const sourceFields = mapping.sources[source]
            if (!sourceFields) continue

            // 支持单个字段名或多个候选字段名
            const fieldNames = Array.isArray(sourceFields) ? sourceFields : [sourceFields]

            // 按优先级尝试每个候选字段
            for (const fieldName of fieldNames) {
                if (rawItem[fieldName] !== undefined) {
                    const value = rawItem[fieldName]
                    core[mapping.core] = mapping.transform
                        ? mapping.transform(value, source)
                        : value
                    break
                }
            }
        }

        return core as TCore
    }

    /**
     * 从单条原始数据中提取扩展字段 (未映射的字段)
     */
    extractExtended(
        rawItem: Record<string, unknown>,
        source: DataSourceType
    ): Record<string, unknown> {
        const extended: Record<string, unknown> = {}

        // 收集所有已映射的字段名
        const mappedFields = new Set<string>()
        for (const mapping of this.mappings) {
            const sourceFields = mapping.sources[source]
            if (sourceFields) {
                const fieldNames = Array.isArray(sourceFields) ? sourceFields : [sourceFields]
                fieldNames.forEach(f => mappedFields.add(f))
            }
        }

        // 未映射的字段放入 extended
        for (const [key, value] of Object.entries(rawItem)) {
            if (!mappedFields.has(key) && !key.startsWith('_')) {
                extended[key] = value
            }
        }

        return extended
    }

    /**
     * 转换原始数据数组为 RichDataResponse
     */
    transform<TCore extends CoreData, TRaw = Record<string, unknown>>(
        rawData: TRaw[],
        source: DataSourceType,
        capability: DataCapability,
        latency: number,
        options: { preserveRaw?: boolean } = {}
    ): RichDataResponse<TCore, TRaw> {
        const { preserveRaw = false } = options

        const meta: RichDataMeta = {
            source,
            capability,
            timestamp: Date.now(),
            latency,
            cached: false,
        }

        if (!rawData || rawData.length === 0) {
            return {
                success: true,
                _meta: meta,
                core: [],
                extended: [],
                count: 0,
                _raw: preserveRaw ? [] : undefined,
            }
        }

        const core: TCore[] = []
        const extended: Record<string, unknown>[] = []

        for (const item of rawData) {
            const rawItem = item as Record<string, unknown>
            core.push(this.extractCore<TCore>(rawItem, source))
            extended.push(this.extractExtended(rawItem, source))
        }

        return {
            success: true,
            _meta: meta,
            core,
            extended,
            count: core.length,
            _raw: preserveRaw ? rawData : undefined,
        }
    }
}

/**
 * 获取指定能力的字段映射器
 */
export function getFieldMapper(capability: DataCapability): FieldMapper {
    const mappings = CAPABILITY_MAPPINGS[capability] || []
    return new FieldMapper(mappings)
}

/**
 * 快捷转换函数
 */
export function transformToRichData<TCore extends CoreData, TRaw = Record<string, unknown>>(
    rawData: TRaw[],
    source: DataSourceType,
    capability: DataCapability,
    latency: number,
    options?: { preserveRaw?: boolean }
): RichDataResponse<TCore, TRaw> {
    const mapper = getFieldMapper(capability)
    return mapper.transform<TCore, TRaw>(rawData, source, capability, latency, options)
}
