import logging

from django.db import models
from django.db import transaction, DatabaseError
from .models import Product, Order, OrderItem
from .utils.lock import acquire_lock, release_lock
from .utils.cache import get_cached_product, cache_product, invalidate_product, product_cache
from .exceptions import InsufficientStockException, ConcurrentUpdateException

logger = logging.getLogger(__name__)


class OrderService:
    @staticmethod
    def process_bulk_order(order_data):
        """
        处理批量订单
        :param order_data: [{"product_id": int, "quantity": int}]
        :return: (order_id, [{"product_id": int, "status": str, "message": str}])
        """
        order = Order.objects.create(total_amount=0, status='pending')
        results = []

        # 按商品ID排序处理避免死锁
        sorted_items = sorted(order_data, key=lambda x: x['product_id'])

        for item in sorted_items:
            product_id = item['product_id']
            quantity = item['quantity']
            lock_key = f"product_lock:{product_id}"

            try:
                # 获取分布式锁（防止集群环境下的并发问题）
                if not acquire_lock(lock_key):
                    raise DatabaseError("Failed to acquire lock for product")

                # 检查缓存中的库存（快速失败）
                cached_product = get_cached_product(product_id)
                if cached_product and cached_product['stock'] < quantity:
                    raise InsufficientStockException(
                        f"Insufficient stock: available {cached_product['stock']}"
                    )

                # 使用事务处理每个商品
                with transaction.atomic():
                    # 悲观锁：使用select_for_update锁定商品行
                    product = Product.objects.select_for_update().get(
                        id=product_id,
                        is_active=True
                    )

                    # 双重检查库存
                    if product.stock < quantity:
                        raise InsufficientStockException(
                            f"Insufficient stock for product {product_id}, available: {product.stock}"
                        )

                    # 乐观锁检查
                    current_version = product.version
                    updated = Product.objects.filter(
                        id=product.id,
                        version=current_version
                    ).update(
                        stock=product.stock - quantity,
                        version=current_version + 1
                    )

                    if not updated:
                        raise ConcurrentUpdateException(
                            f"Concurrent update for product {product_id}, please retry."
                        )

                    # 创建订单项
                    item_price = product.price * quantity
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price=item_price,
                        status='completed'
                    )

                    # 更新订单总金额
                    order.total_amount += item_price

                    # 更新缓存
                    invalidate_product(product.id)

                    results.append({
                        "product_id": product_id,
                        "status": "success",
                        "message": "Order item processed"
                    })

            except (Product.DoesNotExist, InsufficientStockException,
                    ConcurrentUpdateException, DatabaseError) as e:
                # 创建失败的订单项
                OrderItem.objects.create(
                    order=order,
                    product_id=product_id,
                    quantity=quantity,
                    price=0,
                    status='failed',
                    error_message=str(e)
                )
                results.append({
                    "product_id": product_id,
                    "status": "failed",
                    "message": str(e)
                })
                logger.error(f"Order item {product_id} failed: {str(e)}")

            finally:
                # 确保释放锁
                release_lock(lock_key)

        # 更新订单状态
        order.update_status()
        return order.id, results


class ProductService:
    @staticmethod
    def search_products(query):
        """商品搜索服务（带缓存和降级）"""
        if not query:
            return []

        cache_key = f"product_search:{query}"
        try:
            # 尝试从缓存获取
            cached_result = product_cache.get(cache_key)
            if cached_result is not None:
                return cached_result
        except Exception as e:
            logger.error(f"Cache read failed for search '{query}': {str(e)}")

        # 数据库查询（支持名称和描述搜索）
        try:
            products = Product.objects.filter(
                models.Q(name__icontains=query) |
                models.Q(description__icontains=query),
                is_active=True
            ).order_by('id')[:100]  # 限制结果数量

            # 序列化结果
            result = [{
                'id': p.id,
                'name': p.name,
                'price': float(p.price),
                'stock': p.stock
            } for p in products]

            # 缓存结果（即使之前缓存读取失败也尝试写入）
            try:
                product_cache.set(cache_key, result, timeout=120)
            except Exception as e:
                logger.error(f"Cache write failed for search '{query}': {str(e)}")

            return result

        except Exception as e:
            logger.error(f"Search failed for '{query}': {str(e)}")
            return []  # 降级返回空结果

    @staticmethod
    def update_product(product_id, **kwargs):
        """更新商品信息并同步缓存"""
        lock_key = f"product_update:{product_id}"

        try:
            if not acquire_lock(lock_key, timeout=30):
                raise DatabaseError("Failed to acquire update lock")

            with transaction.atomic():
                product = Product.objects.select_for_update().get(id=product_id)

                # 记录旧库存用于缓存更新判断
                old_stock = product.stock

                # 更新字段
                for field, value in kwargs.items():
                    setattr(product, field, value)
                product.save()

                # 如果库存变化或商品状态变化，更新缓存
                if 'stock' in kwargs or 'is_active' in kwargs or old_stock != product.stock:
                    cache_product(product)
                    # 使搜索缓存失效（实际生产中应异步执行）
                    # from .tasks import async_invalidate_search_cache
                    # async_invalidate_search_cache.delay()

                return product

        finally:
            release_lock(lock_key)