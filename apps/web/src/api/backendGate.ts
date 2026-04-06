const BACKEND_CHECK_BYPASS_URLS = ['/notification/', '/system/config', '/log/', '/market/live/']
export type BackendAvailability = boolean | 'unknown' | 'available' | 'unavailable'

export interface BackendRequestGateInput {
    url?: string | null
    skipBackendCheck?: boolean
    backendAvailable: BackendAvailability
}

export const shouldBypassBackendStatusCheck = (url?: string | null): boolean => {
    if (!url) return false
    return BACKEND_CHECK_BYPASS_URLS.some((pattern) => url.includes(pattern))
}

export const shouldBlockByBackendAvailability = ({
    url,
    skipBackendCheck = false,
    backendAvailable,
}: BackendRequestGateInput): boolean => {
    const normalizedState =
        backendAvailable === 'available' || backendAvailable === true
            ? 'available'
            : backendAvailable === 'unavailable' || backendAvailable === false
                ? 'unavailable'
                : 'unknown'

    if (skipBackendCheck) {
        return false
    }

    if (url === '/system/status') {
        return false
    }

    if (shouldBypassBackendStatusCheck(url)) {
        return false
    }

    return normalizedState === 'unavailable'
}
