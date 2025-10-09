import request from './request'

// 获取数据统计信息
export function getDataStatistics() {
    return request({
        url: '/data/stats',
        method: 'get'
    })
}

// 查询市场数据
export function queryMarketData(params) {
    return request({
        url: '/data/query',
        method: 'post',
        data: params
    })
}

// 导入CSV数据
export function importCsvData(file, dataType, cleanData = true) {
    const formData = new FormData()
    formData.append('file', file)

    return request({
        url: `/data/import/csv?data_type=${dataType}&clean_data=${cleanData}`,
        method: 'post',
        data: formData,
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    })
}

// 导出数据
export function exportData(dataType, params) {
    return request({
        url: `/data/export/${dataType}`,
        method: 'get',
        params,
        responseType: 'blob'
    })
}

// 计算技术指标
export function calculateIndicators(params) {
    return request({
        url: '/data/indicators',
        method: 'post',
        data: params
    })
}

// 获取股票代码列表
export function getSymbolList() {
    return request({
        url: '/data/symbols',
        method: 'get'
    })
}