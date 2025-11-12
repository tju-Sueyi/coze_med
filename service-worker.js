/**
 * 医疗AI平台 - Service Worker
 * 提供离线支持、资源缓存和性能优化
 */

const CACHE_NAME = 'medical-ai-v1';
const STATIC_CACHE = 'medical-ai-static-v1';
const API_CACHE = 'medical-ai-api-v1';

// 需要缓存的静态资源
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/styles.css',
    '/script.js',
    '/ai-medical.js',
    '/pre_consultation.js',
    '/README.md',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.min.js',
    'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+SC:wght@300;400;500;600;700;800&display=swap'
];

/**
 * Service Worker 安装阶段
 * 缓存静态资源
 */
self.addEventListener('install', (event) => {
    console.log('📦 Service Worker 正在安装...');
    
    event.waitUntil(
        Promise.all([
            caches.open(STATIC_CACHE).then((cache) => {
                console.log('📥 正在缓存静态资源...');
                return cache.addAll(STATIC_ASSETS).catch((err) => {
                    console.warn('⚠️ 部分资源缓存失败:', err);
                });
            }),
            caches.open(API_CACHE),
            caches.open(CACHE_NAME)
        ])
    );
    
    self.skipWaiting();
});

/**
 * Service Worker 激活阶段
 * 清理旧版本缓存
 */
self.addEventListener('activate', (event) => {
    console.log('🚀 Service Worker 正在激活...');
    
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    // 保留当前版本的缓存，删除旧版本
                    if (cacheName !== STATIC_CACHE && 
                        cacheName !== API_CACHE && 
                        cacheName !== CACHE_NAME) {
                        console.log('🗑️ 删除旧缓存:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    
    self.clients.claim();
});

/**
 * Service Worker 拦截请求阶段
 * 实现缓存策略
 */
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // 仅处理HTTP和HTTPS请求
    if (!url.protocol.startsWith('http')) {
        return;
    }

    // API 请求：网络优先，失败时返回缓存
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(request)
                .then((response) => {
                    // 只缓存成功的响应
                    if (response.status === 200) {
                        const cache = caches.open(API_CACHE);
                        cache.then((c) => c.put(request, response.clone()));
                    }
                    return response;
                })
                .catch(() => {
                    // 网络失败，返回缓存的响应
                    return caches.match(request).then((response) => {
                        if (response) {
                            console.log('📱 离线模式: 从缓存返回API响应');
                            return response;
                        }
                        // 缓存中也没有，返回离线页面
                        return new Response(
                            JSON.stringify({ 
                                error: true, 
                                message: '当前网络不可用，请检查连接' 
                            }),
                            { 
                                status: 503,
                                headers: { 'Content-Type': 'application/json' }
                            }
                        );
                    });
                })
        );
        return;
    }

    // 静态资源：缓存优先，网络备份
    if (
        request.destination === 'style' ||
        request.destination === 'script' ||
        request.destination === 'image' ||
        request.destination === 'font' ||
        url.pathname.endsWith('.html') ||
        url.pathname.endsWith('.css') ||
        url.pathname.endsWith('.js')
    ) {
        event.respondWith(
            caches.match(request)
                .then((response) => {
                    if (response) {
                        console.log('⚡ 从缓存提供静态资源:', url.pathname);
                        return response;
                    }
                    
                    // 缓存中没有，从网络获取
                    return fetch(request).then((response) => {
                        // 缓存成功的响应
                        if (response.status === 200) {
                            const cacheName = request.destination === 'image' ? 
                                API_CACHE : STATIC_CACHE;
                            const cache = caches.open(cacheName);
                            cache.then((c) => c.put(request, response.clone()));
                        }
                        return response;
                    }).catch(() => {
                        // 网络和缓存都失败
                        console.warn('⚠️ 无法加载资源:', url.pathname);
                        
                        if (request.destination === 'image') {
                            return new Response(
                                '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect fill="#f0f0f0" width="100" height="100"/><text x="50" y="50" text-anchor="middle" dy=".3em" fill="#999">图片</text></svg>',
                                { 
                                    headers: { 'Content-Type': 'image/svg+xml' },
                                    status: 200
                                }
                            );
                        }
                        
                        return new Response('资源暂时不可用', { status: 503 });
                    });
                })
        );
        return;
    }

    // 其他请求：网络优先
    event.respondWith(
        fetch(request)
            .then((response) => response)
            .catch(() => {
                return caches.match(request).then((response) => {
                    return response || new Response('离线模式', { status: 503 });
                });
            })
    );
});

/**
 * 处理消息
 * 允许前端控制缓存
 */
self.addEventListener('message', (event) => {
    const { type, data } = event.data;

    switch (type) {
        case 'SKIP_WAITING':
            self.skipWaiting();
            break;
            
        case 'CLEAR_CACHE':
            caches.delete(data.cacheName).then(() => {
                console.log('✅ 缓存已清空:', data.cacheName);
                event.ports[0].postMessage({ success: true });
            });
            break;
            
        case 'GET_CACHE_SIZE':
            caches.open(API_CACHE).then((cache) => {
                cache.keys().then((requests) => {
                    event.ports[0].postMessage({ 
                        size: requests.length,
                        urls: requests.map(r => r.url)
                    });
                });
            });
            break;
    }
});

console.log('✅ Service Worker 已加载 - 离线支持已启用');
