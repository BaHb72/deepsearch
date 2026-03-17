import axios from 'axios'

import { loadStockOptions } from '../stock-search'

jest.mock('axios')

const mockedAxios = axios as jest.Mocked<typeof axios>
type AxiosGetResolved = Awaited<ReturnType<typeof axios.get>>

function asAxiosResponse(status: number, data: unknown): AxiosGetResolved {
    return { status, data } as AxiosGetResolved
}

describe('loadStockOptions', () => {
    beforeEach(() => {
        mockedAxios.get.mockReset()
    })

    test('MiniQMT 返回 refreshing 时应回退 chart 数据而不是空列表', async () => {
        mockedAxios.get
            .mockResolvedValueOnce(
                asAxiosResponse(200, {
                    refreshing: true,
                    data: [],
                })
            )
            .mockResolvedValueOnce(
                asAxiosResponse(200, {
                    items: [{ code: '000001.SZ', name: '平安银行' }],
                })
            )

        const result = await loadStockOptions()

        expect(result.source).toBe('chart')
        expect(result.refreshing).toBe(false)
        expect(result.options).toHaveLength(1)
        expect(result.options[0]).toMatchObject({
            symbol: '000001.SZ',
            name: '平安银行',
        })
    })

    test('chart 接口使用 items 字段时可以被正确解析', async () => {
        mockedAxios.get
            .mockRejectedValueOnce(new Error('miniqmt unavailable'))
            .mockResolvedValueOnce(
                asAxiosResponse(200, {
                    items: [{ value: '600519.SH', name: '贵州茅台' }],
                })
            )

        const result = await loadStockOptions()

        expect(result.source).toBe('chart')
        expect(result.options).toHaveLength(1)
        expect(result.options[0]).toMatchObject({
            symbol: '600519.SH',
            name: '贵州茅台',
        })
    })

    test('MiniQMT 刷新且 chart 不可用时应返回空列表，不给终端用户预设假数据', async () => {
        mockedAxios.get
            .mockResolvedValueOnce(
                asAxiosResponse(200, {
                    refreshing: true,
                    data: [],
                })
            )
            .mockResolvedValueOnce(asAxiosResponse(503, {}))

        const result = await loadStockOptions()

        expect(result.source).toBe('none')
        expect(result.refreshing).toBe(false)
        expect(result.options).toHaveLength(0)
    })
})
