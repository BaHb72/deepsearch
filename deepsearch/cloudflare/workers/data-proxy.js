/**
 * Cloudflare Worker - 数据代理服务
 * 用于规避 IP 封锁，提供全球分布式数据获取
 */

// 配置
const CONFIG = {
    // 支持的数据源
    dataSources: {
        'eastmoney': {
            baseUrl: 'http://push2.eastmoney.com',
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'http://quote.eastmoney.com'
            }
        },
        'sina': {
            baseUrl: 'https://hq.sinajs.cn',
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://finance.sina.com.cn'
            }
        },
        'tencent': {
            baseUrl: 'https://qt.gtimg.cn',
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://gu.qq.com'
            }
        }
    },

    // 缓存配置
    cache: {
        'realtime': 5,      // 实时数据缓存5秒
        'minute': 60,       // 分钟数据缓存60秒
        'daily': 3600,      // 日线数据缓存1小时
        'history': 86400    // 历史数据缓存24小时
    },

    // Worker 节点信息
    workers: [
        {id: 'us-east', region: 'US East', weight: 1},
        {id: 'us-west', region: 'US West', weight: 1},
        {id: 'eu-west', region: 'EU West', weight: 1},
        {id: 'asia-ne', region: 'Asia NE', weight: 2}
    ]
};

export default {
    async fetch(request, env, ctx) {
        const url = new URL(request.url);

        // 健康检查
        if (url.pathname === '/health') {
            return new Response(JSON.stringify({
                status: 'healthy',
                worker_id: env.WORKER_ID || 'unknown',
                region: env.REGION || 'unknown',
                timestamp: new Date().toISOString()
            }), {
                headers: {'Content-Type': 'application/json'}
            });
        }

        // 验证请求来源
        if (!isAuthorized(request, env)) {
            return new Response('Unauthorized', {status: 401});
        }

        // 解析请求参数
        const params = parseRequest(url);

        // 获取或创建缓存键
        const cacheKey = getCacheKey(params);
        const cache = caches.default;

        // 尝试从缓存获取
        let response = await cache.match(cacheKey);
        if (response) {
            // 添加缓存命中标记
            const headers = new Headers(response.headers);
            headers.set('X-Cache', 'HIT');
            return new Response(response.body, {
                status: response.status,
                headers: headers
            });
        }

        // 选择数据源和构建请求
        const targetRequest = buildTargetRequest(params);

        // 执行请求（带重试）
        response = await fetchWithRetry(targetRequest, 3);

        // 处理响应
        if (response.ok) {
            // 添加缓存
            const ttl = getCacheTTL(params.type);
            const cachedResponse = new Response(response.body, {
                headers: {
                    ...Object.fromEntries(response.headers),
                    'Cache-Control': `public, max-age=${ttl}`,
                    'X-Worker-Id': env.WORKER_ID || 'unknown',
                    'X-Cache': 'MISS'
                }
            });

            ctx.waitUntil(cache.put(cacheKey, cachedResponse.clone()));
            return addCorsHeaders(cachedResponse);
        }

        return new Response('Data fetch failed', {status: 502});
    }
};

// 授权验证
function isAuthorized(request, env) {
    const apiKey = request.headers.get('X-API-Key');
    const signature = request.headers.get('X-Signature');
    const timestamp = request.headers.get('X-Timestamp');

    if (!apiKey || !signature || !timestamp) {
        return false;
    }

    // 验证时间戳（5分钟内有效）
    const now = Date.now();
    const reqTime = parseInt(timestamp);
    if (Math.abs(now - reqTime) > 300000) {
        return false;
    }

    // 验证签名
    const expectedSignature = generateSignature(apiKey + timestamp, env.SECRET_KEY || 'default-secret');
    return signature === expectedSignature;
}

// 生成签名（简化版）
function generateSignature(data, secret) {
    // 在实际环境中应使用 crypto.subtle
    // 这里使用简化版本作为示例
    return btoa(data + secret);
}

// 解析请求参数
function parseRequest(url) {
    const pathParts = url.pathname.split('/').filter(p => p);
    const searchParams = url.searchParams;

    return {
        source: pathParts[0] || 'eastmoney',
        type: pathParts[1] || 'realtime',
        symbol: searchParams.get('symbol'),
        period: searchParams.get('period') || 'daily',
        start: searchParams.get('start'),
        end: searchParams.get('end')
    };
}

// 构建目标请求
function buildTargetRequest(params) {
    const source = CONFIG.dataSources[params.source];
    if (!source) {
        throw new Error('Invalid data source');
    }

    let targetUrl = source.baseUrl;

    // 根据不同数据源构建 URL
    switch (params.source) {
        case 'eastmoney':
            if (params.type === 'realtime') {
                targetUrl += `/api/qt/stock/get?secid=${params.symbol}&fields=f43,f44,f45,f46,f47,f48,f49,f50,f51,f52`;
            } else if (params.type === 'kline') {
                targetUrl += `/api/qt/stock/kline/get?secid=${params.symbol}&klt=${params.period === 'daily' ? '101' : '1'}`;
            }
            break;

        case 'sina':
            targetUrl += `/list=${params.symbol}`;
            break;

        case 'tencent':
            targetUrl += `/q=${params.symbol}`;
            break;
    }

    return new Request(targetUrl, {
        headers: source.headers
    });
}

// 带重试的请求
async function fetchWithRetry(request, maxRetries) {
    let lastError;

    for (let i = 0; i < maxRetries; i++) {
        try {
            const response = await fetch(request.clone());
            if (response.ok) {
                return response;
            }
            lastError = new Error(`HTTP ${response.status}`);
        } catch (error) {
            lastError = error;
            // 等待后重试
            await new Promise(resolve => setTimeout(resolve, Math.pow(2, i) * 1000));
        }
    }

    throw lastError;
}

// 获取缓存 TTL
function getCacheTTL(type) {
    return CONFIG.cache[type] || 60;
}

// 获取缓存键
function getCacheKey(params) {
    const key = `${params.source}:${params.type}:${params.symbol}:${params.period}`;
    return new Request(new URL(key, 'https://cache.local').toString());
}

// 添加 CORS 头
function addCorsHeaders(response) {
    const headers = new Headers(response.headers);
    headers.set('Access-Control-Allow-Origin', '*');
    headers.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    headers.set('Access-Control-Allow-Headers', 'Content-Type, X-API-Key, X-Signature, X-Timestamp');

    return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: headers
    });
}