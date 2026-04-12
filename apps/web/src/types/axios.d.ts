import type {RequestMetadata} from '@/api/core/types'

declare module 'axios' {
    interface AxiosRequestConfig<_D = any> {
        metadata?: RequestMetadata
    }

    interface InternalAxiosRequestConfig<_D = any> {
        metadata?: RequestMetadata
    }
}
