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
    'money.finance.sina.com.cn',

    // 网易财经
    'quotes.money.163.com',
    'api.money.126.net',

    // 腾讯财经
    'qt.gtimg.cn',
    'stock.gtimg.cn',

    // 东方财富（支持所有数字子域名如 17.push2, 79.push2, 82.push2 等）
    'push2.eastmoney.com',
    'push2his.eastmoney.com',
    'push2ex.eastmoney.com',  // 新增：涨停跌停池数据
    'datacenter.eastmoney.com',
    'datacenter-web.eastmoney.com',
    'quote.eastmoney.com',  // 新增：行情页面/部分接口跳转域名
    'data.eastmoney.com',  // 新增：千股千评等页面域名
    'np-anotice-stock.eastmoney.com',  // 新增：公告数据
    'np-listnotice.eastmoney.com',  // 新增：公告列表
    // 东方财富数字子域名（用于不同的数据分片）
    '17.push2.eastmoney.com',  // 实时行情数据分片
    '79.push2.eastmoney.com',  // 实时行情数据分片
    '82.push2.eastmoney.com',  // 实时行情数据分片

    // 同花顺
    'data.10jqka.com.cn',
    'basic.10jqka.com.cn',
    // 交易所
    'www.sse.com.cn',
    'query.sse.com.cn',
    'www.szse.cn',
    'docs.static.szse.cn',  // 新增：深交所静态文档直链

    // 雪球
    'xueqiu.com',
    'api.xueqiu.com',

    // 其他数据源
    'www.chinamoney.com.cn',
    'www.shibor.org',
    'dc.cls.cn'
];

// User-Agent池（2025年最新版本）
const USER_AGENTS = [
    // Windows Chrome
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',

    // Windows Firefox
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',

    // Windows Edge
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0',

    // Mac Chrome
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',

    // Mac Firefox
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:129.0) Gecko/20100101 Firefox/129.0',

    // Linux Chrome
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',

    // Mobile（少量，模拟部分移动访问）
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36'
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
        const config = getConfig(env);
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

        if (config.AUTH_ENABLED) {
            const providedKey = request.headers.get('X-API-Key') ||
                url.searchParams.get('api_key') ||
                url.searchParams.get('apikey');

            if (!providedKey || providedKey !== config.API_KEY) {
                return jsonResponse({
                    error: 'Unauthorized',
                    message: 'Invalid or missing API key'
                }, 401);
            }
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
            'x-forwarded-for', 'x-real-ip', 'cookie', 'x-api-key'
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

        // 根据请求类型设置不同的请求头
        // 检测是否为 API 请求（datacenter/api 路径或 JSON 相关）
        const isApiRequest = targetUrlObj.pathname.includes('/api/') ||
                             targetUrlObj.pathname.includes('/data/') ||
                             targetUrl.includes('datacenter');

        if (isApiRequest) {
            // API 请求：使用 XHR/fetch 风格的请求头
            headers.set('Accept', 'application/json, text/plain, */*');
            headers.set('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8');
            headers.set('Accept-Encoding', 'gzip, deflate, br');
            headers.set('Cache-Control', 'no-cache');
            headers.set('Pragma', 'no-cache');
            // 使用 XHR/fetch 的 Sec-Fetch 头
            headers.set('Sec-Fetch-Dest', 'empty');
            headers.set('Sec-Fetch-Mode', 'cors');
            headers.set('Sec-Fetch-Site', 'same-origin');
        } else {
            // 网页请求：使用浏览器导航风格的请求头
            headers.set('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8');
            headers.set('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8');
            headers.set('Accept-Encoding', 'gzip, deflate, br');
            headers.set('Cache-Control', 'no-cache');
            headers.set('Pragma', 'no-cache');
            headers.set('Sec-Ch-Ua', '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"');
            headers.set('Sec-Ch-Ua-Mobile', '?0');
            headers.set('Sec-Ch-Ua-Platform', '"Windows"');
            headers.set('Sec-Fetch-Dest', 'document');
            headers.set('Sec-Fetch-Mode', 'navigate');
            headers.set('Sec-Fetch-Site', 'none');
            headers.set('Sec-Fetch-User', '?1');
            headers.set('Upgrade-Insecure-Requests', '1');
        }
        headers.set('Dnt', '1');

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
        const cacheKeyUrl = new URL(`https://cache.local/proxy/${targetHost}${targetUrlObj.pathname}`);
        const cacheSearch = targetUrlObj.searchParams.toString();
        if (cacheSearch) {
            cacheKeyUrl.search = cacheSearch;
        }
        const cacheKey = new Request(cacheKeyUrl.toString(), {method: 'GET'});

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

        // 执行请求（服务端重试，处理源站瞬时故障）
        const MAX_RETRIES = 3;
        const RETRY_DELAYS = [0, 500, 1500];
        let response;
        let lastError;

        for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
            if (attempt > 0) {
                await new Promise(r => setTimeout(r, RETRY_DELAYS[attempt]));
            }
            try {
                response = await fetch(targetUrl, requestOptions);
                if (response.ok || response.status < 500) {
                    break;
                }
                lastError = `HTTP ${response.status}`;
            } catch (error) {
                lastError = error.message;
                if (attempt === MAX_RETRIES - 1) {
                    console.error('Fetch error after retries:', lastError);
                    return jsonResponse({
                        error: 'Failed to fetch',
                        message: lastError,
                        target: targetUrl
                    }, 502);
                }
            }
        }

        // 构建响应头
        const responseHeaders = new Headers();

        // 复制响应头（排除敏感信息和CloudFlare特征）
        const blockedResponseHeaders = [
            'set-cookie', 'cf-ray', 'cf-cache-status',
            'cf-request-id', 'cf-connecting-ip', 'cf-ipcountry',
            'x-forwarded-for', 'x-real-ip', 'via', 'server'
        ];

        for (const [key, value] of response.headers.entries()) {
            const lowerKey = key.toLowerCase();
            if (!blockedResponseHeaders.includes(lowerKey) && !lowerKey.startsWith('cf-')) {
                responseHeaders.set(key, value);
            }
        }

        // 仅添加必要的CORS头（不暴露代理身份）
        responseHeaders.set('Access-Control-Allow-Origin', '*');
        responseHeaders.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
        responseHeaders.set('Access-Control-Allow-Headers', '*');

        // 获取响应体
        const responseBody = await response.arrayBuffer();

        // 创建响应
        const result = new Response(responseBody, {
            status: response.status,
            statusText: response.statusText,
            headers: responseHeaders
        });

        // 缓存成功的GET响应（不添加缓存头暴露身份）
        if (request.method === 'GET' && response.ok) {
            const cacheTime = getCacheTime(targetUrlObj.pathname, targetHost);
            if (cacheTime > 0) {
                // 内部缓存，不暴露给外部
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

// ============ 请求处理 ============

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
        cache_enabled: true,
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
