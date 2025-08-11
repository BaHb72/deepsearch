/**
 * Cloudflare Worker - AkShare API 代理
 *
 * 通过 Worker 运行 Python AkShare 代码，避免本地 IP 限制
 * 注意：这需要使用 Cloudflare Workers Python Runtime 或通过 API 网关调用
 */

export default {
    async fetch(request, env, ctx) {
        const url = new URL(request.url);

        // CORS 处理
        if (request.method === 'OPTIONS') {
            return new Response(null, {
                headers: {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, X-API-Key'
                }
            });
        }

        // 健康检查
        if (url.pathname === '/health') {
            return new Response(JSON.stringify({
                status: 'healthy',
                timestamp: new Date().toISOString(),
                type: 'akshare-proxy',
                version: '2.0.0'
            }), {
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                }
            });
        }

        // AkShare API 路由
        if (url.pathname.startsWith('/api/akshare/')) {
            return handleAkShareRequest(request, url, env, ctx);
        }

        return new Response('Not Found', {status: 404});
    }
};

/**
 * 处理 AkShare API 请求
 *
 * 由于 Workers 不能直接运行 Python，我们有几个方案：
 * 1. 调用部署在其他地方的 AkShare API 服务
 * 2. 使用 Workers 直接实现爬虫逻辑（复制 AkShare 的实现）
 * 3. 通过 Workers AI/Python Runtime（如果支持）
 */
async function handleAkShareRequest(request, url, env, ctx) {
    const pathParts = url.pathname.split('/').filter(p => p);
    const endpoint = pathParts[2]; // /api/akshare/{endpoint}

    // 获取查询参数
    const params = Object.fromEntries(url.searchParams);

    try {
        // 方案1：代理到远程 AkShare API 服务
        if (env.AKSHARE_API_URL) {
            return proxyToAkShareAPI(endpoint, params, env);
        }

        // 方案2：直接实现数据获取逻辑
        switch (endpoint) {
            case 'stock_zh_a_spot_em':
                return await getStockRealtimeEM(params);

            case 'stock_zh_a_hist':
                return await getStockHistoryEM(params);

            case 'stock_individual_info_em':
                return await getStockInfoEM(params);

            case 'stock_zh_a_minute':
                return await getStockMinuteEM(params);

            default:
                return new Response(JSON.stringify({
                    error: 'Unsupported endpoint',
                    available: [
                        'stock_zh_a_spot_em',
                        'stock_zh_a_hist',
                        'stock_individual_info_em',
                        'stock_zh_a_minute'
                    ]
                }), {
                    status: 400,
                    headers: {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    }
                });
        }
    } catch (error) {
        console.error('AkShare request failed:', error);
        return new Response(JSON.stringify({
            error: 'Request failed',
            message: error.message
        }), {
            status: 500,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        });
    }
}

/**
 * 方案1：代理到远程 AkShare API 服务
 */
async function proxyToAkShareAPI(endpoint, params, env) {
    const apiUrl = `${env.AKSHARE_API_URL}/api/${endpoint}`;
    const queryString = new URLSearchParams(params).toString();
    const targetUrl = queryString ? `${apiUrl}?${queryString}` : apiUrl;

    const response = await fetch(targetUrl, {
        headers: {
            'X-API-Key': env.AKSHARE_API_KEY || '',
            'User-Agent': 'Cloudflare-Worker/1.0'
        }
    });

    const data = await response.text();

    return new Response(data, {
        status: response.status,
        headers: {
            'Content-Type': response.headers.get('Content-Type') || 'application/json',
            'Access-Control-Allow-Origin': '*',
            'X-Cache': 'MISS',
            'X-Proxy': 'akshare-api'
        }
    });
}

/**
 * 方案2：直接实现东方财富实时行情获取
 * 复制 AkShare 的 stock_zh_a_spot_em 实现
 */
async function getStockRealtimeEM(params) {
    // 东方财富实时行情接口
    const url = 'http://82.push2.eastmoney.com/api/qt/clist/get';

    // 构建请求参数（参考 AkShare 源码）
    const queryParams = {
        pn: params.page || '1',
        pz: params.size || '20',
        po: '1',
        np: '1',
        ut: 'bd1d9ddb04089700cf9c27f6f7426281',
        fltt: '2',
        invt: '2',
        fid: 'f3',
        fs: 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048',
        fields: 'f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152',
        _: Date.now()
    };

    const targetUrl = `${url}?${new URLSearchParams(queryParams).toString()}`;

    try {
        const response = await fetch(targetUrl, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'http://quote.eastmoney.com/',
                'Accept': '*/*'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        // 转换数据格式
        const result = {
            success: true,
            data: data.data?.diff || [],
            total: data.data?.total || 0,
            timestamp: new Date().toISOString()
        };

        // 添加缓存
        const cacheResponse = new Response(JSON.stringify(result), {
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'public, max-age=5',
                'X-Data-Source': 'eastmoney'
            }
        });

        // 缓存5秒
        ctx.waitUntil(
            caches.default.put(request, cacheResponse.clone())
        );

        return cacheResponse;

    } catch (error) {
        console.error('Failed to fetch from EastMoney:', error);
        throw error;
    }
}

/**
 * 获取历史K线数据
 * 复制 AkShare 的 stock_zh_a_hist 实现
 */
async function getStockHistoryEM(params) {
    const {symbol, period = 'daily', start_date, end_date, adjust = 'qfq'} = params;

    if (!symbol) {
        return new Response(JSON.stringify({
            error: 'Missing required parameter: symbol'
        }), {
            status: 400,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        });
    }

    // 转换周期参数
    const periodMap = {
        'daily': '101',   // 日K
        'weekly': '102',  // 周K
        'monthly': '103'  // 月K
    };

    const klt = periodMap[period] || '101';

    // 构建东方财富K线接口URL
    const secid = symbol.startsWith('6') ? `1.${symbol}` : `0.${symbol}`;

    const url = 'http://push2his.eastmoney.com/api/qt/stock/kline/get';
    const queryParams = {
        secid: secid,
        ut: 'fa5fd1943c7b386f172d6893dbfba10b',
        fields1: 'f1,f2,f3,f4,f5,f6',
        fields2: 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        klt: klt,
        fqt: adjust === 'qfq' ? '1' : adjust === 'hfq' ? '2' : '0',
        beg: start_date?.replace(/-/g, '') || '0',
        end: end_date?.replace(/-/g, '') || '20500101',
        _: Date.now()
    };

    const targetUrl = `${url}?${new URLSearchParams(queryParams).toString()}`;

    try {
        const response = await fetch(targetUrl, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'http://quote.eastmoney.com/'
            }
        });

        const data = await response.json();

        // 解析K线数据
        const klines = data.data?.klines || [];
        const parsedData = klines.map(line => {
            const parts = line.split(',');
            return {
                date: parts[0],
                open: parseFloat(parts[1]),
                close: parseFloat(parts[2]),
                high: parseFloat(parts[3]),
                low: parseFloat(parts[4]),
                volume: parseFloat(parts[5]),
                amount: parseFloat(parts[6]),
                amplitude: parseFloat(parts[7]),
                change_pct: parseFloat(parts[8]),
                change_amt: parseFloat(parts[9]),
                turnover: parseFloat(parts[10])
            };
        });

        return new Response(JSON.stringify({
            success: true,
            symbol: symbol,
            period: period,
            data: parsedData,
            total: parsedData.length,
            timestamp: new Date().toISOString()
        }), {
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'public, max-age=60'
            }
        });

    } catch (error) {
        console.error('Failed to fetch history:', error);
        throw error;
    }
}

/**
 * 获取个股信息
 */
async function getStockInfoEM(params) {
    const {symbol} = params;

    if (!symbol) {
        return new Response(JSON.stringify({
            error: 'Missing required parameter: symbol'
        }), {
            status: 400,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        });
    }

    // 实现个股信息获取逻辑
    // ...

    return new Response(JSON.stringify({
        success: true,
        symbol: symbol,
        data: {
            // 返回个股信息
        }
    }), {
        headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        }
    });
}

/**
 * 获取分钟K线数据
 */
async function getStockMinuteEM(params) {
    const {symbol, period = '1'} = params;

    if (!symbol) {
        return new Response(JSON.stringify({
            error: 'Missing required parameter: symbol'
        }), {
            status: 400,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        });
    }

    // 实现分钟K线获取逻辑
    // ...

    return new Response(JSON.stringify({
        success: true,
        symbol: symbol,
        period: period,
        data: []
    }), {
        headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        }
    });
}