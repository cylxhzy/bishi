from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Product
from .utils.cache import invalidate_product, cache_product


@receiver(post_save, sender=Product)
def product_saved(sender, instance, **kwargs):
    """商品保存后更新缓存"""
    cache_product(instance)


@receiver(post_delete, sender=Product)
def product_deleted(sender, instance, **kwargs):
    """商品删除后失效缓存"""
    invalidate_product(instance.id)
