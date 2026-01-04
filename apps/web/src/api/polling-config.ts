/**
 * 轮询配置 API 客户端
 */

/**
 * 阶段行为配置
 */
export interface PhaseBehavior {
    interval_seconds: number
    timeout_seconds: number
    skip_polling?: boolean
}

/**
 * 交易阶段判断配置
 */
export interface SessionGuard {
    enabled: boolean
    calendar_source: 'amazingdata' | 'miniqmt' | 'auto'
    market: string  // SH, SZ, BJ, HK, SHF, CFE 等
}

/**
 * 轮询配置
 */
export interface PollingConfig {
    calendar_ttl_minutes: number
    session_guard: SessionGuard
    defaults: {
        continuous?: PhaseBehavior
        auction?: PhaseBehavior
        no_trade?: PhaseBehavior
        off_day?: PhaseBehavior
    }
    markets?: Record<string, unknown>
}

/**
 * 阶段行为更新
 */
export interface PhaseBehaviorUpdate {
    interval_seconds?: number
    timeout_seconds?: number
    skip_polling?: boolean
}

/**
 * 交易阶段判断配置更新
 */
export interface SessionGuardUpdate {
    enabled?: boolean
    calendar_source?: 'amazingdata' | 'miniqmt' | 'auto'
    market?: string
}

/**
 * 轮询配置更新
 */
export interface PollingConfigUpdate {
    calendar_ttl_minutes?: number
    session_guard?: SessionGuardUpdate
    defaults?: {
        continuous?: PhaseBehaviorUpdate
        auction?: PhaseBehaviorUpdate
        no_trade?: PhaseBehaviorUpdate
        off_day?: PhaseBehaviorUpdate
    }
}

/**
 * API 响应
 */
export interface PollingConfigResponse {
    success: boolean
    config: PollingConfig
    message?: string
}

const API_BASE = '/api/system/config'

/**
 * 获取当前轮询配置
 */
export async function getPollingConfig(): Promise<PollingConfigResponse> {
    const response = await fetch(`${API_BASE}/polling`)
    if (!response.ok) {
        throw new Error(`获取轮询配置失败: ${response.statusText}`)
    }
    return response.json()
}

/**
 * 更新轮询配置
 */
export async function updatePollingConfig(
    config: PollingConfigUpdate
): Promise<PollingConfigResponse> {
    const response = await fetch(`${API_BASE}/polling`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(config),
    })
    if (!response.ok) {
        throw new Error(`更新轮询配置失败: ${response.statusText}`)
    }
    return response.json()
}
