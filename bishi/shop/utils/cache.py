from django.core.cache import caches
from django.conf import settings
import logging

logger = logging.getLogger(__name__)
product_cache = caches['products']


def cache_product(product):
    """缓存商品信息（带异常处理）"""
    try:
        key = f"product:{product.id}"
        product_cache.set(key, {
            'id': product.id,
            'name': product.name,
            'price': float(product.price),
            'stock': product.stock,
            'is_active': product.is_active
        }, timeout=300)
    except Exception as e:
        logger.error(f"Failed to cache product {product.id}: {str(e)}")


def invalidate_product(product_id):
    """使商品缓存失效（带异常处理）"""
    try:
        product_cache.delete(f"product:{product_id}")
        # 异步失效搜索缓存（实际生产中应使用消息队列）
        # from .tasks import async_invalidate_search_cache
        # async_invalidate_search_cache.delay()
    except Exception as e:
        logger.error(f"Failed to invalidate cache for product {product_id}: {str(e)}")


def get_cached_product(product_id):
    """获取缓存商品（带降级处理）"""
    try:
        return product_cache.get(f"product:{product_id}")
    except Exception as e:
        logger.error(f"Cache read failed for product {product_id}: {str(e)}")
        return None
