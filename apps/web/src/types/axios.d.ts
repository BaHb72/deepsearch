import type {RequestMetadata} from '@/api/core/types'

declare module 'axios' {
    interface AxiosRequestConfig<D = any> {
        metadata?: RequestMetadata
    }

    interface InternalAxiosRequestConfig<D = any> {
        metadata?: RequestMetadata
    }
}
