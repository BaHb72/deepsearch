/**
 * Cloudflare Worker - Ultimate Akshare Proxy Service
 * 支持50+财经网站代理，防IP封锁
 */

// ============ 配置 ============
const ALLOWED_HOSTS = [
    // 新浪财经
    'finance.sina.com.cn',
    'hq.sinajs.cn',
    'stock.finance.sina.com.cn',
    'vip.stock.finance.sina.com.cn',
    'money.finance.sina.com.cn',
    'push2.sinajs.cn',
    'suggest3.sinajs.cn',

    // 网易财经
    'quotes.money.163.com',
    'api.money.126.net',
    'money.163.com',
    'stock.163.com',

    // 腾讯财经
    'qt.gtimg.cn',
    'stock.gtimg.cn',
    'data.gtimg.cn',
    'web.ifzq.gtimg.cn',

    // 东方财富
    'push2.eastmoney.com',
    'push2his.eastmoney.com',
    'datacenter.eastmoney.com',
    'datacenter-web.eastmoney.com',
    'data.eastmoney.com',
    'finance.eastmoney.com',
    'dcfm.eastmoney.com',
    'fund.eastmoney.com',
    'fundf10.eastmoney.com',
    'reportapi.eastmoney.com',
    'emweb.eastmoney.com',
    'mapi.eastmoney.com',

    // 同花顺
    'data.10jqka.com.cn',
    'basic.10jqka.com.cn',
    'd.10jqka.com.cn',
    'news.10jqka.com.cn',
    'ai.10jqka.com.cn',

    // 交易所
    'www.sse.com.cn',
    'query.sse.com.cn',
    'yunhq.sse.com.cn',
    'www.szse.cn',
    'www.bse.cn',

    // 期货交易所
    'www.shfe.com.cn',
    'www.dce.com.cn',
    'www.czce.com.cn',
    'www.cffex.com.cn',
    'www.ine.cn',
    'www.gfex.com.cn',

    // 雪球
    'xueqiu.com',
    'api.xueqiu.com',
    'stock.xueqiu.com',

    // 其他数据源
    'www.chinamoney.com.cn',
    'www.shibor.org',
    'dc.cls.cn',
    'www.cls.cn',
    'webapi.cninfo.com.cn',
    'www.cninfo.com.cn',

    // 国际数据
    'query1.finance.yahoo.com',
    'query2.finance.yahoo.com',
    'finance.yahoo.com',
    'api.worldbank.org',
    'fred.stlouisfed.org',
    'api.stlouisfed.org',
    'www.investing.com',
    'api.investing.com',
    'cn.investing.com',
    'sbcharts.investing.com',
    'tvc4.investing.com',

    // 其他财经网站
    'www.178448.com',
    'api.anniu.com.cn',
    'www.100ppi.com',
    'index.100ppi.com',
    'www.jinshi365.com',
    'finance.ifeng.com',
    'api.finance.ifeng.com',
    'hq.finance.ifeng.com'
];

// User-Agent池
const USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0'
];

// 需要移除的请求头
const BLOCKED_REQUEST_HEADERS = [
    'cf-connecting-ip',
    'cf-ipcountry',
    'cf-ray',
    'cf-visitor',
    'x-forwarded-for',
    'x-forwarded-proto',
    'x-real-ip',
    'cf-worker',
    'cf-ew-via',
    'cf-worker-version',
    'true-client-ip'
];

// 需要移除的响应头
const BLOCKED_RESPONSE_HEADERS = [
    'cf-ray',
    'cf-cache-status',
    'cf-request-id',
    'cf-apo-via',
    'report-to',
    'nel',
    'x-powered-by'
];

// ============ 主处理器 ============
export default {
    async fetch(request, env, ctx) {
        const url = new URL(request.url);

        // CORS预检请求
        if (request.method === 'OPTIONS') {
            return handleCORS();
        }

        // 健康检查
        if (url.pathname === '/health') {
            return handleHealthCheck(request, env);
        }

        // 通用代理端点
        if (url.pathname === '/proxy' || url.searchParams.has('url')) {
            return handleUniversalProxy(request, env, ctx);
        }

        // 直接AkShare函数路径
        const pathName = url.pathname.slice(1);
        const aksharePatterns = [
            'stock_', 'fund_', 'bond_', 'index_', 'futures_',
            'option_', 'commodity_', 'forex_', 'crypto_', 'macro_',
            'news_', 'energy_', 'air_', 'tool_', 'covid_'
        ];

        const isAkshareFunction = aksharePatterns.some(pattern =>
            pathName.startsWith(pattern) && pathName.includes('_')
        );

        if (isAkshareFunction && !url.pathname.startsWith('/api/')) {
            return handleDirectAkShareFunction(pathName, request, env, ctx);
        }

        // AkShare API路由
        if (url.pathname.startsWith('/api/akshare/')) {
            return handleAkShareRequest(request, url, env, ctx);
        }

        // 直接eastmoney路由
        if (url.pathname.startsWith('/eastmoney/')) {
            return handleDirectEastMoneyRequest(request, url, env, ctx);
        }

        // 原始API路由
        if (url.pathname.startsWith('/api/')) {
            return handleStockAPIRequest(request, url, env, ctx);
        }

        // 根路径
        if (url.pathname === '/') {
            return handleRootRequest(env);
        }

        return new Response('Not Found', {
            status: 404,
            headers: getCORSHeaders()
        });
    }
};

// ============ 通用代理处理器 ============
async function handleUniversalProxy(request, env, ctx) {
    try {
        const url = new URL(request.url);
        let targetUrl = url.searchParams.get('url') ||
            url.searchParams.get('target') ||
            url.searchParams.get('q');

        if (!targetUrl) {
            return jsonResponse({
                error: 'Missing target URL',
                usage: 'Add ?url=https://target-site.com/api',
                supported_hosts: ALLOWED_HOSTS.slice(0, 20)
            }, 400);
        }

        // 解码并规范化URL
        targetUrl = decodeURIComponent(targetUrl);
        if (!targetUrl.match(/^https?:\/\//i)) {
            targetUrl = 'https://' + targetUrl;
        }

        const targetUrlObj = new URL(targetUrl);
        const targetHost = targetUrlObj.hostname;

        // 检查白名单
        const isAllowed = ALLOWED_HOSTS.some(host => {
            return targetHost === host ||
                targetHost.endsWith('.' + host) ||
                host.endsWith('.' + targetHost);
        });

        if (!isAllowed) {
            return jsonResponse({
                error: 'Host not in whitelist',
                host: targetHost,
                supported_hosts: ALLOWED_HOSTS.slice(0, 20)
            }, 403);
        }

        // 构建缓存键
        const cacheKey = new Request(
            `https://cache.local/proxy/${targetHost}${targetUrlObj.pathname}?${targetUrlObj.search}`,
            {method: 'GET'}
        );

        // 检查缓存
        const cache = caches.default;
        const cached = await cache.match(cacheKey);
        if (cached && !url.searchParams.has('nocache')) {
            const cachedBody = await cached.text();
            return new Response(cachedBody, {
                status: cached.status,
                headers: {
                    ...Object.fromEntries(cached.headers),
                    'X-Cache': 'HIT',
                    ...getCORSHeaders()
                }
            });
        }

        // 构建请求头（防封机制）
        const headers = buildAntiBlockHeaders(request, targetHost);

        // 准备请求选项
        const requestOptions = {
            method: request.method,
            headers: headers,
            redirect: 'follow',
            signal: AbortSignal.timeout(30000)
        };

        // 处理请求体
        if (request.method !== 'GET' && request.method !== 'HEAD') {
            requestOptions.body = await request.arrayBuffer();
        }

        // 执行请求（带重试）
        const response = await fetchWithRetry(targetUrl, requestOptions);

        if (!response) {
            return jsonResponse({
                error: 'Failed to fetch after retries',
                target: targetUrl
            }, 502);
        }

        // 构建响应
        const responseHeaders = buildResponseHeaders(response);

        // 缓存响应
        const cacheTime = getIntelligentCacheTime(targetUrlObj.pathname, targetHost);
        const result = new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers: responseHeaders
        });

        if (response.ok && cacheTime > 0) {
            const cacheResponse = result.clone();
            ctx.waitUntil(cache.put(cacheKey, cacheResponse));
        }

        return result;

    } catch (error) {
        console.error('Universal proxy error:', error);
        return jsonResponse({
            error: 'Proxy error',
            message: error.message
        }, 500);
    }
}

// ============ 防封请求头构建 ============
function buildAntiBlockHeaders(request, targetHost) {
    const headers = new Headers();

    // 复制允许的原始请求头
    for (const [key, value] of request.headers.entries()) {
        const lowerKey = key.toLowerCase();
        if (!BLOCKED_REQUEST_HEADERS.includes(lowerKey) &&
            !lowerKey.startsWith('cf-') &&
            lowerKey !== 'host' &&
            lowerKey !== 'cookie') {
            headers.set(key, value);
        }
    }

    // 设置随机User-Agent
    const randomUA = USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
    headers.set('User-Agent', randomUA);

    // 设置必要的请求头
    headers.set('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8');
    headers.set('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7');
    headers.set('Accept-Encoding', 'gzip, deflate, br');
    headers.set('Cache-Control', 'no-cache');
    headers.set('Pragma', 'no-cache');

    // 根据不同网站设置特定的Referer
    const refererMap = {
        'sina.com.cn': 'https://finance.sina.com.cn/',
        'sinajs.cn': 'https://finance.sina.com.cn/',
        '163.com': 'https://money.163.com/',
        '126.net': 'https://money.163.com/',
        'eastmoney.com': 'https://www.eastmoney.com/',
        '10jqka.com.cn': 'http://www.10jqka.com.cn/',
        'xueqiu.com': 'https://xueqiu.com/',
        'investing.com': 'https://cn.investing.com/',
        'gtimg.cn': 'https://gu.qq.com/',
        'sse.com.cn': 'http://www.sse.com.cn/',
        'szse.cn': 'http://www.szse.cn/'
    };

    // 查找匹配的Referer
    for (const [domain, referer] of Object.entries(refererMap)) {
        if (targetHost.includes(domain)) {
            headers.set('Referer', referer);
            break;
        }
    }

    // 如果没有找到特定的，使用通用的
    if (!headers.has('Referer')) {
        headers.set('Referer', `https://${targetHost}/`);
    }

    return headers;
}

// ============ 响应头处理 ============
function buildResponseHeaders(response) {
    const headers = new Headers();

    // 复制允许的响应头
    for (const [key, value] of response.headers.entries()) {
        const lowerKey = key.toLowerCase();
        if (!BLOCKED_RESPONSE_HEADERS.includes(lowerKey) &&
            !lowerKey.startsWith('cf-') &&
            !lowerKey.startsWith('x-amz-') &&
            lowerKey !== 'set-cookie') {
            headers.set(key, value);
        }
    }

    // 设置CORS头
    headers.set('Access-Control-Allow-Origin', '*');
    headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS, HEAD');
    headers.set('Access-Control-Allow-Headers', '*');
    headers.set('Access-Control-Expose-Headers', '*');
    headers.set('X-Proxy-By', 'Cloudflare-Worker');

    // 确保Content-Type正确
    const contentType = response.headers.get('content-type');
    if (contentType) {
        if ((contentType.includes('text/') || contentType.includes('application/json')) &&
            !contentType.includes('charset')) {
            headers.set('Content-Type', contentType + '; charset=utf-8');
        }
    }

    return headers;
}

// ============ 重试机制 ============
async function fetchWithRetry(url, options, maxRetries = 3) {
    let lastError;
    const retryDelays = [1000, 2000, 3000];

    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            const response = await fetch(url, options);

            // 如果是429或503，继续重试
            if ((response.status === 429 || response.status === 503) && attempt < maxRetries - 1) {
                await new Promise(resolve => setTimeout(resolve, retryDelays[attempt]));
                continue;
            }

            return response;
        } catch (error) {
            lastError = error;
            if (attempt < maxRetries - 1) {
                await new Promise(resolve => setTimeout(resolve, retryDelays[attempt]));
            }
        }
    }

    console.error('All retry attempts failed:', lastError);
    return null;
}

// ============ 智能缓存时间 ============
function getIntelligentCacheTime(pathname, host) {
    const path = pathname.toLowerCase();

    // 实时数据 - 极短缓存
    if (path.includes('realtime') || path.includes('spot') ||
        path.includes('now') || path.includes('quote')) {
        return 5;
    }

    // 分钟级数据
    if (path.includes('minute') || path.includes('min') ||
        path.includes('intraday')) {
        return 60;
    }

    // 日线数据
    if (path.includes('daily') || path.includes('day') ||
        path.includes('kline') || path.includes('hist')) {
        return 300;
    }

    // 基本面数据
    if (path.includes('info') || path.includes('fundamental') ||
        path.includes('financial') || path.includes('report')) {
        return 3600;
    }

    // 指数和宏观数据
    if (path.includes('index') || path.includes('macro')) {
        return 1800;
    }

    // 根据主机特定规则
    if (host.includes('sinajs.cn') || host.includes('gtimg.cn')) {
        return 5; // 实时行情
    }

    if (host.includes('eastmoney.com')) {
        return 30; // 东方财富默认
    }

    return 60; // 默认1分钟
}

// ============ AkShare函数处理 ============
async function handleDirectAkShareFunction(functionName, request, env, ctx) {
    const config = getConfig(env);
    const url = new URL(request.url);

    // 检查认证
    if (config.AUTH_ENABLED) {
        const apiKey = request.headers.get('X-API-Key');
        if (apiKey !== config.API_KEY) {
            return jsonResponse({
                error: 'Unauthorized',
                message: 'Invalid or missing API key'
            }, 401);
        }
    }

    // 解析参数
    let params = {};
    if (request.method === 'GET') {
        for (const [key, value] of url.searchParams) {
            if (value === '') {
                params[key] = '';
            } else if (!isNaN(Number(value)) && value !== '') {
                params[key] = value.includes('.') ? parseFloat(value) : parseInt(value);
            } else {
                params[key] = value;
            }
        }
    } else if (request.method === 'POST') {
        try {
            const body = await request.text();
            params = body ? JSON.parse(body) : {};
        } catch (e) {
            params = {};
        }
    }

    try {
        const data = await proxyAkShareData(functionName, params, env, ctx);

        if (!data) {
            return jsonResponse({
                error: 'No backend configured',
                message: 'AKSHARE_BASE_URL environment variable not set'
            }, 501);
        }

        return jsonResponse({
            success: true,
            data: data,
            source: 'proxy',
            cached: false,
            function: functionName,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        console.error(`AkShare direct handler error for ${functionName}:`, error);
        return jsonResponse({
            error: 'Internal Server Error',
            message: error.message,
            function: functionName
        }, 500);
    }
}

// ============ 代理AkShare数据 ============
async function proxyAkShareData(functionName, params, env, ctx) {
    const config = getConfig(env);

    if (!config.AKSHARE_BASE_URL) {
        return null;
    }

    try {
        const cacheKey = new Request(
            `https://cache.local/akshare/${functionName}?${JSON.stringify(params)}`,
            {method: 'GET'}
        );

        const cache = caches.default;
        const cached = await cache.match(cacheKey);
        if (cached) {
            console.log(`Cache HIT for ${functionName}`);
            return await cached.json();
        }

        const targetUrl = `${config.AKSHARE_BASE_URL}/api/akshare/${functionName}`;
        console.log(`Proxying to: ${targetUrl}`);

        const response = await fetch(targetUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'User-Agent': 'CloudflareWorker/3.0'
            },
            body: JSON.stringify(params || {}),
            signal: AbortSignal.timeout(30000)
        });

        if (!response.ok) {
            throw new Error(`Backend returned ${response.status}`);
        }

        const result = await response.json();
        const data = result.success && result.data ? result.data : result;

        // 智能缓存
        const cacheTime = getCacheTimeForFunction(functionName);
        const cacheResponse = new Response(JSON.stringify(data), {
            headers: {
                'Content-Type': 'application/json',
                'Cache-Control': `public, max-age=${cacheTime}`
            }
        });

        ctx.waitUntil(cache.put(cacheKey, cacheResponse));
        console.log(`Cached ${functionName} for ${cacheTime}s`);

        return data;

    } catch (error) {
        console.error(`Failed to proxy ${functionName}: ${error.message}`);
        throw error;
    }
}

// ============ 配置管理 ============
function getConfig(env) {
    return {
        API_KEY: env.API_KEY || '',
        CACHE_TTL: parseInt(env.CACHE_TTL || '300'),
        AKSHARE_BASE_URL: env.AKSHARE_BASE_URL || '',
        VERSION: '3.0.0',
        AUTH_ENABLED: env.API_KEY ? true : false
    };
}

// ============ 健康检查 ============
async function handleHealthCheck(request, env) {
    const config = getConfig(env);
    const apiKey = request.headers.get('X-API-Key') || '';
    const requiresAuth = config.AUTH_ENABLED;
    const isAuthenticated = !requiresAuth || (apiKey === config.API_KEY);

    const response = {
        status: 'healthy',
        version: config.VERSION,
        timestamp: new Date().toISOString(),
        requires_auth: requiresAuth,
        authenticated: isAuthenticated,
        features: {
            universal_proxy: true,
            stock_proxy: true,
            akshare_api: true,
            direct_akshare_paths: true,
            cache_enabled: true,
            anti_blocking: true,
            retry_mechanism: true,
            cache_ttl: config.CACHE_TTL
        },
        supported_hosts_count: ALLOWED_HOSTS.length,
        user_agents_count: USER_AGENTS.length,
        akshare_backend: config.AKSHARE_BASE_URL ? 'configured' : 'not-configured'
    };

    return jsonResponse(response);
}

// ============ 原有处理器 ============
async function handleDirectEastMoneyRequest(request, url, env, ctx) {
    const pathParts = url.pathname.split('/').filter(p => p);
    const endpoint = pathParts[1];

    if (endpoint === 'test') {
        const symbol = url.searchParams.get('symbol') || '000001';
        return jsonResponse({
            status: 'ok',
            endpoint: 'test',
            symbol: symbol,
            message: 'Test endpoint working',
            timestamp: new Date().toISOString()
        });
    }

    const params = Object.fromEntries(url.searchParams);
    return handleEastMoneyEndpoint(request, endpoint, params, env, ctx);
}

async function handleEastMoneyEndpoint(request, endpoint, params, env, ctx) {
    const dataSource = DATA_SOURCES.eastmoney;
    const endpointConfig = dataSource.endpoints[endpoint];

    if (!endpointConfig) {
        return jsonResponse({
            error: 'Invalid endpoint',
            available: Object.keys(dataSource.endpoints)
        }, 400);
    }

    const cacheKey = new Request(
        `https://cache.local/eastmoney/${endpoint}?${JSON.stringify(params)}`,
        {method: 'GET'}
    );

    const cache = caches.default;
    let response = await cache.match(cacheKey);
    if (response) {
        const cachedBody = await response.text();
        return new Response(cachedBody, {
            status: response.status,
            headers: {
                ...Object.fromEntries(response.headers),
                'X-Cache': 'HIT',
                ...getCORSHeaders()
            }
        });
    }

    let targetUrl = endpointConfig.url;
    if (endpointConfig.params) {
        const targetParams = endpointConfig.params(params.symbol, params.period);
        const searchParams = new URLSearchParams();
        for (const [key, value] of Object.entries(targetParams)) {
            if (value !== undefined && value !== null) {
                searchParams.append(key, String(value));
            }
        }
        targetUrl += '?' + searchParams.toString();
    }

    try {
        const targetResponse = await fetchWithRetry(targetUrl, {
            headers: buildAntiBlockHeaders(request, 'eastmoney.com')
        });

        if (!targetResponse || !targetResponse.ok) {
            return jsonResponse({
                rc: 102,
                rt: 1,
                data: null,
                message: 'Upstream temporarily unavailable'
            }, 200);
        }

        const data = await targetResponse.json();
        response = jsonResponse(data, 200);

        const cacheTime = getCacheTime(endpoint);
        response.headers.set('Cache-Control', `public, max-age=${cacheTime}`);

        ctx.waitUntil(cache.put(cacheKey, response.clone()));
        return response;

    } catch (error) {
        console.error('EastMoney request failed:', error);
        return jsonResponse({
            rc: 102,
            rt: 1,
            data: null,
            error: error.message
        }, 200);
    }
}

async function handleAkShareRequest(request, url, env, ctx) {
    const config = getConfig(env);

    if (config.AUTH_ENABLED) {
        const apiKey = request.headers.get('X-API-Key');
        if (apiKey !== config.API_KEY) {
            return jsonResponse({
                error: 'Unauthorized',
                message: 'Invalid or missing API key'
            }, 401);
        }
    }

    const pathParts = url.pathname.split('/').filter(p => p);
    const functionName = pathParts[pathParts.length - 1];

    let params = {};
    try {
        if (request.method === 'POST') {
            const body = await request.text();
            params = body ? JSON.parse(body) : {};
        } else if (request.method === 'GET') {
            for (const [key, value] of url.searchParams) {
                params[key] = value;
            }
        }
    } catch (e) {
        return jsonResponse({
            error: 'Invalid Request',
            message: 'Invalid JSON in request body'
        }, 400);
    }

    try {
        const data = await proxyAkShareData(functionName, params, env, ctx);

        if (!data) {
            return jsonResponse({
                error: 'No backend configured',
                message: 'AKSHARE_BASE_URL environment variable not set'
            }, 501);
        }

        return jsonResponse({
            success: true,
            data: data,
            source: 'proxy',
            cached: false,
            function: functionName,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        console.error('AkShare handler error:', error);
        return jsonResponse({
            error: 'Internal Server Error',
            message: error.message,
            function: functionName
        }, 500);
    }
}

async function handleStockAPIRequest(request, url, env, ctx) {
    const pathParts = url.pathname.split('/').filter(p => p);
    if (pathParts.length < 3) {
        return jsonResponse({
            error: 'Invalid API path, expected /api/{source}/{endpoint}'
        }, 400);
    }

    const source = pathParts[1];
    const endpoint = pathParts[2];

    if (source === 'akshare') {
        return handleAkShareRequest(request, url, env, ctx);
    }

    if (source === 'eastmoney') {
        const params = Object.fromEntries(url.searchParams);
        return handleEastMoneyEndpoint(request, endpoint, params, env, ctx);
    }

    const dataSource = DATA_SOURCES[source];
    if (!dataSource) {
        return jsonResponse({
            error: 'Invalid data source',
            available: Object.keys(DATA_SOURCES)
        }, 400);
    }

    if (endpoint !== 'realtime') {
        return jsonResponse({
            error: 'Invalid endpoint for this source',
            endpoint,
            supported: Object.keys(dataSource.endpoints)
        }, 400);
    }

    const symbol = url.searchParams.get('symbol') || '';
    if (!symbol) {
        return jsonResponse({
            error: 'Missing required parameter: symbol'
        }, 400);
    }

    const cacheKey = new Request(
        `https://cache.local/${source}/${endpoint}?symbol=${encodeURIComponent(symbol)}`,
        {method: 'GET'}
    );
    const cache = caches.default;
    const cached = await cache.match(cacheKey);
    if (cached) {
        const cachedBody = await cached.text();
        return new Response(cachedBody, {
            status: cached.status,
            headers: {
                ...Object.fromEntries(cached.headers),
                'X-Cache': 'HIT',
                ...getCORSHeaders()
            }
        });
    }

    const cfg = dataSource.endpoints[endpoint];
    if (!cfg) {
        return jsonResponse({
            error: 'Endpoint not configured for source'
        }, 400);
    }

    const targetUrl = cfg.buildUrl ? cfg.buildUrl(symbol) : cfg.url;
    try {
        const resp = await fetchWithRetry(targetUrl, {
            headers: buildAntiBlockHeaders(request, source)
        });
        if (!resp || !resp.ok) {
            return jsonResponse({
                error: 'Upstream error',
                status: resp ? resp.status : 0
            }, 502);
        }
        const txt = await resp.text();
        const parsed = cfg.parseResponse ? cfg.parseResponse(txt) : {raw: txt};
        const result = jsonResponse({
            source,
            endpoint,
            symbol: normalizeTicker(symbol),
            data: parsed
        }, 200);

        const cacheTime = getCacheTime(endpoint);
        result.headers.set('Cache-Control', `public, max-age=${cacheTime}`);
        ctx.waitUntil(cache.put(cacheKey, result.clone()));

        return result;
    } catch (e) {
        console.error(`${source} request failed:`, e);
        return jsonResponse({
            error: 'Fetch failed',
            message: e.message
        }, 500);
    }
}

// ============ 根路径处理 ============
function handleRootRequest(env) {
    const config = getConfig(env);
    const html = `<!DOCTYPE html>
<html>
<head><title>API</title></head>
<body>
<pre>
Stock Data Proxy Service v${config.VERSION}
Status: Running
Supported hosts: ${ALLOWED_HOSTS.length}
User agents: ${USER_AGENTS.length}
Backend: ${config.AKSHARE_BASE_URL || 'Not configured'}

Endpoints:
GET /proxy?url={target_url} - Universal proxy
GET /{akshare_function}?params - Direct AkShare functions
GET /health - Health check
POST /api/akshare/{function} - AkShare API
GET /api/{source}/realtime?symbol={code} - Stock data

Examples:
/proxy?url=https://hq.sinajs.cn/list=sz000001
/stock_zh_a_hist?symbol=000001&period=daily
/api/eastmoney/realtime?symbol=000001
</pre>
</body>
</html>`;

    return new Response(html, {
        status: 200,
        headers: {
            'Content-Type': 'text/html; charset=utf-8',
            ...getCORSHeaders()
        }
    });
}

// ============ 工具函数 ============
function getCacheTime(endpoint) {
    const cacheConfig = {
        realtime: 5,
        spot: 5,
        kline: 60,
        daily: 300,
        flow: 30,
        test: 0,
        default: 10
    };
    return cacheConfig[endpoint] || cacheConfig.default;
}

function getCacheTimeForFunction(functionName) {
    const lowerName = functionName.toLowerCase();

    if (lowerName.includes('spot') || lowerName.includes('realtime')) return 5;
    if (lowerName.includes('minute') || lowerName.includes('min')) return 60;
    if (lowerName.includes('hist') || lowerName.includes('daily')) return 300;
    if (lowerName.includes('info') || lowerName.includes('fundamental')) return 3600;
    if (lowerName.includes('index')) return 60;
    if (lowerName.includes('macro')) return 1800;

    return 60;
}

function jsonResponse(data, status = 200) {
    return new Response(JSON.stringify(data, null, 2), {
        status: status,
        headers: {
            'Content-Type': 'application/json; charset=utf-8',
            ...getCORSHeaders()
        }
    });
}

function getCORSHeaders() {
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS, HEAD',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-API-Key, X-Timestamp, X-Signature',
        'Access-Control-Max-Age': '86400'
    };
}

function handleCORS() {
    return new Response(null, {
        status: 204,
        headers: getCORSHeaders()
    });
}

function normalizeTicker(symbol) {
    if (!symbol) return '';
    const s = symbol.toLowerCase();
    if (s.startsWith('sh') || s.startsWith('sz')) return s;
    if (/^\d+$/.test(s)) {
        if (s.startsWith('6')) return 'sh' + s;
        if (s.startsWith('0') || s.startsWith('3')) return 'sz' + s;
    }
    return s;
}

function toSecId(symbol) {
    if (!symbol) return '';
    const s = symbol.toLowerCase();
    const pure = s.replace(/^sh|^sz/, '');
    const code = /^\d+$/.test(pure) ? pure : s;
    if (s.startsWith('sh') || code.startsWith('6')) return '1.' + code.slice(-6);
    if (s.startsWith('sz') || code.startsWith('0') || code.startsWith('3')) return '0.' + code.slice(-6);
    return code;
}

// ============ 数据源配置 ============
const DATA_SOURCES = {
    eastmoney: {
        name: 'East Money',
        endpoints: {
            realtime: {
                url: 'https://push2.eastmoney.com/api/qt/stock/get',
                params: (symbol) => ({
                    secid: toSecId(symbol),
                    fields: 'f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f60,f61,f62,f63,f64'
                })
            },
            kline: {
                url: 'https://push2his.eastmoney.com/api/qt/stock/kline/get',
                params: (symbol, period) => ({
                    secid: toSecId(symbol),
                    klt: period || '101',
                    fqt: '1',
                    fields1: 'f1,f2,f3,f4,f5',
                    fields2: 'f51,f52,f53,f54,f55,f56,f57,f58'
                })
            },
            flow: {
                url: 'https://push2.eastmoney.com/api/qt/stock/fflow/daykline/get',
                params: (symbol) => ({
                    secid: toSecId(symbol),
                    fields1: 'f1,f2,f3,f7',
                    fields2: 'f51,f52,f53,f54,f55,f56,f57'
                })
            }
        },
        headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://quote.eastmoney.com/'
        }
    },

    sina: {
        name: 'Sina Finance',
        endpoints: {
            realtime: {
                buildUrl: (symbol) => `https://hq.sinajs.cn/list=${normalizeTicker(symbol)}`,
                parseResponse: (text) => {
                    const match = text.match(/="(.+)"/);
                    if (!match) return null;
                    const parts = match[1].split(',');
                    const safeNum = (v) => (v === '' || v == null ? null : Number(v));
                    return {
                        name: parts[0] || '',
                        open: safeNum(parts[1]),
                        close: safeNum(parts[2]),
                        current: safeNum(parts[3]),
                        high: safeNum(parts[4]),
                        low: safeNum(parts[5]),
                        volume: safeNum(parts[8]),
                        amount: safeNum(parts[9])
                    };
                }
            }
        },
        headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn'
        }
    },

    tencent: {
        name: 'Tencent Finance',
        endpoints: {
            realtime: {
                buildUrl: (symbol) => `https://qt.gtimg.cn/q=${normalizeTicker(symbol)}`,
                parseResponse: (text) => {
                    const match = text.match(/="(.+)"/);
                    if (!match) return null;
                    const parts = match[1].split('~');
                    const safeNum = (v) => (v === '' || v == null ? null : Number(v));
                    return {
                        name: parts[1] || '',
                        code: parts[2] || '',
                        current: safeNum(parts[3]),
                        prev_close: safeNum(parts[4]),
                        open: safeNum(parts[5]),
                        volume: safeNum(parts[6]),
                        amount: safeNum(parts[37])
                    };
                }
            }
        },
        headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://gu.qq.com'
        }
    }
};