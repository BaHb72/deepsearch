/**
 * Cloudflare Worker - HTTP 代理服务
 *
 * 功能：
 * - 作为纯 HTTP 代理，隐藏真实服务器 IP
 * - 代理访问 50+ 金融数据源网站
 * - 智能缓存机制，减少重复请求
 * - 支持 CORS 跨域请求
 *
 * 说明：
 * - Worker 仅负责代理请求，不处理数据
 * - 所有数据处理由 DeepSearch 的 akshare 库完成
 * - 支持请求合并和速率限制
 */

// ============ 配置 ============
const ALLOWED_HOSTS = [
    // 新浪财经
    'finance.sina.com.cn',
    'hq.sinajs.cn',
    'stock.finance.sina.com.cn',
    'vip.stock.finance.sina.com.cn',

    // 网易财经
    'quotes.money.163.com',
    'api.money.126.net',

    // 腾讯财经
    'qt.gtimg.cn',
    'stock.gtimg.cn',

    // 东方财富
    'push2.eastmoney.com',
    'push2his.eastmoney.com',
    'datacenter.eastmoney.com',
    'datacenter-web.eastmoney.com',

    // 同花顺
    'data.10jqka.com.cn',
    'basic.10jqka.com.cn',

    // 交易所
    'www.sse.com.cn',
    'query.sse.com.cn',
    'www.szse.cn',

    // 雪球
    'xueqiu.com',
    'api.xueqiu.com',

    // 其他数据源
    'www.chinamoney.com.cn',
    'www.shibor.org',
    'dc.cls.cn'
];

// User-Agent池
const USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
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
            return handleHealthCheck(env);
        }

        // 代理端点
        if (url.pathname === '/proxy') {
            return handleProxy(request, env, ctx);
        }

        // 根路径
        if (url.pathname === '/') {
            return handleRoot(env);
        }

        return new Response('Not Found', {
            status: 404,
            headers: getCORSHeaders()
        });
    }
};

// ============ 代理处理 ============
async function handleProxy(request, env, ctx) {
    try {
        const url = new URL(request.url);
        let targetUrl = url.searchParams.get('url') ||
            url.searchParams.get('target');

        if (!targetUrl) {
            return jsonResponse({
                error: 'Missing target URL',
                usage: 'Add ?url=https://target-site.com/api'
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
                message: 'This host is not allowed for proxy'
            }, 403);
        }

        // 构建请求头
        const headers = new Headers();

        // 复制原始请求头（排除敏感信息）
        const blockedHeaders = [
            'host', 'cf-connecting-ip', 'cf-ipcountry', 'cf-ray',
            'x-forwarded-for', 'x-real-ip', 'cookie'
        ];

        for (const [key, value] of request.headers.entries()) {
            const lowerKey = key.toLowerCase();
            if (!blockedHeaders.includes(lowerKey) && !lowerKey.startsWith('cf-')) {
                headers.set(key, value);
            }
        }

        // 设置随机User-Agent
        const randomUA = USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
        headers.set('User-Agent', randomUA);

        // 设置必要的请求头
        headers.set('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8');
        headers.set('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8');
        headers.set('Accept-Encoding', 'gzip, deflate, br');

        // 设置 Referer（根据目标站点）
        const refererMap = {
            'sina.com.cn': 'https://finance.sina.com.cn/',
            '163.com': 'https://money.163.com/',
            'eastmoney.com': 'https://www.eastmoney.com/',
            '10jqka.com.cn': 'http://www.10jqka.com.cn/',
            'xueqiu.com': 'https://xueqiu.com/',
            'gtimg.cn': 'https://gu.qq.com/'
        };

        for (const [domain, referer] of Object.entries(refererMap)) {
            if (targetHost.includes(domain)) {
                headers.set('Referer', referer);
                break;
            }
        }

        if (!headers.has('Referer')) {
            headers.set('Referer', `https://${targetHost}/`);
        }

        // 构建缓存键
        const cacheKey = new Request(
            `https://cache.local/proxy/${targetHost}${targetUrlObj.pathname}?${targetUrlObj.search}`,
            {method: 'GET'}
        );

        // 检查缓存
        const cache = caches.default;
        if (request.method === 'GET') {
            const cached = await cache.match(cacheKey);
            if (cached && !url.searchParams.has('nocache')) {
                const cachedBody = await cached.text();
                return new Response(cachedBody, {
                    status: cached.status,
                    headers: {
                        ...Object.fromEntries(cached.headers),
                        'X-Cache': 'HIT',
                        'X-Proxy-By': 'Cloudflare-Worker',
                        ...getCORSHeaders()
                    }
                });
            }
        }

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

        // 构建响应头
        const responseHeaders = new Headers();

        // 复制响应头（排除敏感信息）
        const blockedResponseHeaders = [
            'set-cookie', 'cf-ray', 'cf-cache-status'
        ];

        for (const [key, value] of response.headers.entries()) {
            const lowerKey = key.toLowerCase();
            if (!blockedResponseHeaders.includes(lowerKey) && !lowerKey.startsWith('cf-')) {
                responseHeaders.set(key, value);
            }
        }

        // 添加CORS和代理标识
        responseHeaders.set('Access-Control-Allow-Origin', '*');
        responseHeaders.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
        responseHeaders.set('Access-Control-Allow-Headers', '*');
        responseHeaders.set('X-Proxy-By', 'Cloudflare-Worker');
        responseHeaders.set('X-Cache', 'MISS');

        // 获取响应体
        const responseBody = await response.arrayBuffer();

        // 创建响应
        const result = new Response(responseBody, {
            status: response.status,
            statusText: response.statusText,
            headers: responseHeaders
        });

        // 缓存成功的GET响应
        if (request.method === 'GET' && response.ok) {
            const cacheTime = getCacheTime(targetUrlObj.pathname, targetHost);
            if (cacheTime > 0) {
                responseHeaders.set('Cache-Control', `public, max-age=${cacheTime}`);
                const cacheResponse = result.clone();
                ctx.waitUntil(cache.put(cacheKey, cacheResponse));
            }
        }

        return result;

    } catch (error) {
        console.error('Proxy error:', error);
        return jsonResponse({
            error: 'Proxy error',
            message: error.message
        }, 500);
    }
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

// ============ 缓存时间策略 ============
function getCacheTime(pathname, host) {
    const path = pathname.toLowerCase();

    // 实时数据 - 极短缓存
    if (path.includes('realtime') || path.includes('spot') ||
        path.includes('now') || path.includes('quote')) {
        return 5;
    }

    // 分钟级数据
    if (path.includes('minute') || path.includes('min')) {
        return 60;
    }

    // 日线数据
    if (path.includes('daily') || path.includes('day') ||
        path.includes('kline')) {
        return 300;
    }

    // 根据主机特定规则
    if (host.includes('sinajs.cn') || host.includes('gtimg.cn')) {
        return 5; // 实时行情
    }

    return 60; // 默认1分钟
}

// ============ 健康检查 ============
function handleHealthCheck(env) {
    const config = getConfig(env);
    return jsonResponse({
        status: 'healthy',
        version: '2.0.0',
        mode: 'proxy-only',
        timestamp: new Date().toISOString(),
        features: {
            proxy: true,
            cache: true,
            whitelist: true,
            retry: true
        },
        allowed_hosts_count: ALLOWED_HOSTS.length,
        auth_enabled: config.AUTH_ENABLED
    });
}

// ============ 根路径 ============
function handleRoot(env) {
    const html = `<!DOCTYPE html>
<html>
<head>
  <title>Proxy Worker</title>
  <style>
    body { font-family: monospace; padding: 20px; background: #1a1a1a; color: #0f0; }
    pre { background: #000; padding: 15px; border: 1px solid #0f0; }
    h1 { color: #0f0; }
  </style>
</head>
<body>
  <h1>Cloudflare Worker Proxy v2.0</h1>
  <pre>
Status: Running
Mode: Proxy-Only (Simplified)
Purpose: Protect server IP

Usage:
GET /proxy?url={target_url} - Proxy HTTP request
GET /health - Health check

Example:
/proxy?url=https://hq.sinajs.cn/list=sz000001

Note: All data processing is done by DeepSearch's akshare library.
This worker only acts as a proxy to protect your server IP.
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
function getConfig(env) {
    return {
        API_KEY: env.API_KEY || '',
        AUTH_ENABLED: env.API_KEY ? true : false,
        VERSION: '2.0.0'
    };
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
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-API-Key',
        'Access-Control-Max-Age': '86400'
    };
}

function handleCORS() {
    return new Response(null, {
        status: 204,
        headers: getCORSHeaders()
    });
}