import {
    shouldBlockByBackendAvailability,
    shouldBypassBackendStatusCheck,
} from '../backendGate'
import request from '../request'
import backendStatus from '@/utils/backendStatus'

describe('request backend gate', () => {
    test('market live endpoints should bypass backend availability precheck', () => {
        expect(shouldBypassBackendStatusCheck('/market/live/strength')).toBe(true)
        expect(shouldBypassBackendStatusCheck('/market/live/board-overview')).toBe(true)
    })

    test('non live endpoints should not bypass backend availability precheck', () => {
        expect(shouldBypassBackendStatusCheck('/system/status')).toBe(false)
        expect(shouldBypassBackendStatusCheck('/strategy/list')).toBe(false)
    })

    test('market live endpoints should not be blocked when backend status is unavailable', () => {
        expect(shouldBlockByBackendAvailability({
            url: '/market/live/strength',
            backendAvailable: false,
        })).toBe(false)
    })

    test('non live endpoints should still be blocked when backend status is unavailable', () => {
        expect(shouldBlockByBackendAvailability({
            url: '/strategy/list',
            backendAvailable: false,
        })).toBe(true)
    })

    test('unknown backend state should not block requests', () => {
        expect(shouldBlockByBackendAvailability({
            url: '/strategy/list',
            backendAvailable: 'unknown',
        })).toBe(false)
    })
})

describe('backend availability runtime behavior', () => {
    const status = backendStatus as {
        availabilityState: 'unknown' | 'available' | 'unavailable'
        isAvailable: boolean | null
        lastStatus: Record<string, unknown> | null
        consecutiveFailures: number
        maxConsecutiveFailures: number
        recordSuccess?: () => void
        stopRecoveryProcess?: () => void
        setAvailable?: (available: boolean, reason?: string) => void
        startRecoveryProcess?: () => void
        getAvailabilityState?: () => string
        getLastStatus?: () => Record<string, unknown> | null
    }

    const resetState = () => {
        status.stopRecoveryProcess?.()
        status.availabilityState = 'unknown'
        status.isAvailable = null
        status.lastStatus = null
        status.consecutiveFailures = 0
    }

    beforeEach(() => {
        resetState()
    })

    afterEach(() => {
        resetState()
        jest.restoreAllMocks()
    })

    test('should start recovery when unavailable state receives repeated failures', () => {
        status.availabilityState = 'unavailable'
        status.isAvailable = false
        status.consecutiveFailures = status.maxConsecutiveFailures

        const startRecoverySpy = jest
            .spyOn(status, 'startRecoveryProcess')
            .mockImplementation(() => undefined)

        status.setAvailable?.(false, 'still_unavailable')

        expect(startRecoverySpy).toHaveBeenCalled()
    })

    test('request interceptor should not block when state is available but snapshot is stale', async () => {
        status.availabilityState = 'available'
        status.isAvailable = true
        status.lastStatus = { ready: false }

        const fulfilled = (request as unknown as {
            interceptors: {
                request: {
                    handlers: Array<{
                        fulfilled: (config: Record<string, unknown>) => Promise<Record<string, unknown>>
                    }>
                }
            }
        }).interceptors.request.handlers[0].fulfilled

        expect(
            fulfilled({
                url: '/strategy/list',
                method: 'get',
                headers: {},
            })
        ).toMatchObject({
            url: '/strategy/list',
        })
    })

    test('response interceptor should ignore market live success for availability recovery', async () => {
        const recordSuccessSpy = jest
            .spyOn(status, 'recordSuccess')
            .mockImplementation(() => undefined)

        const fulfilled = (request as unknown as {
            interceptors: {
                response: {
                    handlers: Array<{
                        fulfilled: (response: Record<string, unknown>) => unknown
                    }>
                }
            }
        }).interceptors.response.handlers[0].fulfilled

        fulfilled({
            config: { url: '/market/live/strength' },
            data: { ok: true },
            status: 200,
            statusText: 'OK',
            headers: {},
        })

        expect(recordSuccessSpy).not.toHaveBeenCalled()
    })

    test('response interceptor should keep counting non-bypass success signals', async () => {
        const recordSuccessSpy = jest
            .spyOn(status, 'recordSuccess')
            .mockImplementation(() => undefined)

        const fulfilled = (request as unknown as {
            interceptors: {
                response: {
                    handlers: Array<{
                        fulfilled: (response: Record<string, unknown>) => unknown
                    }>
                }
            }
        }).interceptors.response.handlers[0].fulfilled

        fulfilled({
            config: { url: '/strategy/list' },
            data: { ok: true },
            status: 200,
            statusText: 'OK',
            headers: {},
        })

        expect(recordSuccessSpy).toHaveBeenCalledTimes(1)
    })
})
