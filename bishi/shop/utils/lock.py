import redis
import time
from django.conf import settings

redis_client = redis.StrictRedis(
    host=settings.REDIS_LOCK_CONN['host'],
    port=settings.REDIS_LOCK_CONN['port'],
    db=settings.REDIS_LOCK_CONN['db'],
    decode_responses=settings.REDIS_LOCK_CONN.get('decode_responses', True)
)


def acquire_lock(lock_name, timeout=10, retry=3, delay=0.1):
    """获取分布式锁（带重试机制）"""
    for _ in range(retry):
        if redis_client.set(lock_name, "locked", nx=True, ex=timeout):
            return True
        time.sleep(delay)
    return False


def release_lock(lock_name):
    """释放分布式锁"""
    redis_client.delete(lock_name)
