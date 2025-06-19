class BusinessException(Exception):
    """业务异常基类"""

    def __init__(self, message, code=400):
        self.message = message
        self.code = code
        super().__init__(message)


class InsufficientStockException(BusinessException):
    """库存不足异常"""

    def __init__(self, message="Insufficient stock"):
        super().__init__(message, 400)


class ConcurrentUpdateException(BusinessException):
    """并发更新异常"""

    def __init__(self, message="Concurrent update detected"):
        super().__init__(message, 409)


class CacheUnavailableException(BusinessException):
    """缓存不可用异常"""

    def __init__(self, message="Cache service unavailable"):
        super().__init__(message, 503)
