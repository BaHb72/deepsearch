"""
股票列表缓存服务

提供股票列表的缓存管理，支持：
- 从 xtdata 获取完整股票列表
- 生成拼音首字母用于搜索
- 缓存到 Redis/内存，减少实时查询延迟
"""

import asyncio
from typing import Any, Dict, List, Optional

from loguru import logger

from deepsearch.webui.api.cache.unified import get_cache

# 缓存键和过期时间
STOCK_LIST_CACHE_KEY = "stock_list"
STOCK_LIST_TTL = 86400  # 24小时


def _get_pinyin_initials(name: str) -> str:
    """获取中文名称的拼音首字母"""
    try:
        from pypinyin import lazy_pinyin
        initials = ''.join([p[0] for p in lazy_pinyin(name) if p])
        return initials.lower()
    except ImportError:
        return ""
    except Exception:
        return ""


def _fetch_stock_list_sync(sector: str = "沪深A股") -> List[Dict[str, str]]:
    """同步获取股票列表（在后台线程中执行）"""
    try:
        from xtquant import xtdata
        
        logger.info(f"[StockCache] 开始获取板块 {sector} 的股票列表...")
        
        # 获取股票代码列表
        stock_codes = xtdata.get_stock_list_in_sector(sector)
        if not stock_codes:
            logger.warning(f"[StockCache] 板块 {sector} 未获取到股票列表")
            return []
        
        logger.info(f"[StockCache] 获取到 {len(stock_codes)} 个股票代码")
        
        result = []
        success_count = 0
        fail_count = 0
        
        for i, code in enumerate(stock_codes):
            try:
                detail = xtdata.get_instrument_detail(code)
                if detail and detail.get("InstrumentName"):
                    name = detail["InstrumentName"]
                    # 尝试修复编码问题
                    try:
                        if isinstance(name, bytes):
                            name = name.decode('gbk', errors='ignore')
                    except Exception:
                        pass
                    
                    pinyin = _get_pinyin_initials(name)
                    result.append({
                        "symbol": code,
                        "name": name,
                        "pinyin": pinyin,
                    })
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
                if fail_count < 5:
                    logger.warning(f"[StockCache] 获取 {code} 详情失败: {e}")
            
            # 每 500 个打印进度
            if (i + 1) % 500 == 0:
                logger.info(f"[StockCache] 进度: {i + 1}/{len(stock_codes)} (成功: {success_count})")
        
        logger.info(
            f"[StockCache] 完成! 总计: {len(stock_codes)}, 成功: {success_count}, 失败: {fail_count}"
        )
        return result
        
    except ImportError:
        logger.warning("[StockCache] xtquant 未安装，无法获取股票列表")
        return []
    except Exception as e:
        logger.error(f"[StockCache] 获取股票列表失败: {e}")
        return []


async def refresh_stock_cache(sector: str = "沪深A股") -> bool:
    """
    刷新股票列表缓存
    
    Args:
        sector: 板块名称
        
    Returns:
        是否成功刷新
    """
    try:
        logger.info(f"[StockCache] 开始刷新 {sector} 股票列表缓存...")
        
        # 在后台线程中执行同步操作
        loop = asyncio.get_event_loop()
        stock_list = await loop.run_in_executor(None, _fetch_stock_list_sync, sector)
        
        if not stock_list:
            logger.warning("[StockCache] 刷新失败，股票列表为空")
            return False
        
        # 存入缓存
        cache = get_cache()
        cache_key = f"{STOCK_LIST_CACHE_KEY}:{sector}"
        cache.set(cache_key, stock_list, ttl=STOCK_LIST_TTL)
        
        logger.info(
            f"[StockCache] 缓存刷新成功! {sector} 共 {len(stock_list)} 只股票, TTL={STOCK_LIST_TTL}秒"
        )
        return True
        
    except Exception as e:
        logger.error(f"[StockCache] 刷新缓存失败: {e}")
        return False


def get_stock_list_from_cache(
    sector: str = "沪深A股",
    limit: int = 0,
) -> Optional[List[Dict[str, str]]]:
    """
    从缓存获取股票列表
    
    Args:
        sector: 板块名称
        limit: 返回数量限制，0表示全部
        
    Returns:
        股票列表，缓存不存在返回 None
    """
    try:
        cache = get_cache()
        cache_key = f"{STOCK_LIST_CACHE_KEY}:{sector}"
        result = cache.get(cache_key)
        
        if result is None:
            return None
        
        if limit > 0:
            return result[:limit]
        return result
        
    except Exception as e:
        logger.error(f"[StockCache] 从缓存读取失败: {e}")
        return None


async def ensure_stock_cache(sector: str = "沪深A股") -> List[Dict[str, str]]:
    """
    确保股票列表缓存存在，不存在则刷新
    
    Args:
        sector: 板块名称
        
    Returns:
        股票列表
    """
    # 先尝试从缓存读取
    cached = get_stock_list_from_cache(sector)
    if cached is not None:
        logger.debug(f"[StockCache] 命中缓存: {sector} ({len(cached)} 只股票)")
        return cached
    
    # 缓存不存在，刷新
    logger.info(f"[StockCache] 缓存不存在，开始刷新: {sector}")
    await refresh_stock_cache(sector)
    
    # 再次尝试读取
    cached = get_stock_list_from_cache(sector)
    return cached or []


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息"""
    cache = get_cache()
    stats = cache.get_stats()
    
    # 检查股票列表缓存状态
    for sector in ["沪深A股"]:
        cache_key = f"{STOCK_LIST_CACHE_KEY}:{sector}"
        cached = cache.get(cache_key)
        stats[f"stock_list_{sector}"] = len(cached) if cached else 0
    
    return stats
