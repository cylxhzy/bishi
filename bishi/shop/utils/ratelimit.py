from django.conf import settings
from django.core.cache import cache
import re
from django.http import JsonResponse


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        client_ip = self.get_client_ip(request)

        for endpoint, limit_str in settings.RATE_LIMITS.items():
            if endpoint in path:
                limit, period = self.parse_limit(limit_str)
                if self.is_rate_limited(client_ip, endpoint, limit, period):
                    return JsonResponse(
                        {'error': 'Too many requests'},
                        status=429
                    )
        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

    def parse_limit(self, limit_str):
        """解析 '100/minute' 格式的限流配置"""
        limit, period = re.match(r'(\d+)/(\w+)', limit_str).groups()
        periods = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }
        return int(limit), periods.get(period, 60)

    def is_rate_limited(self, client_ip, endpoint, limit, period_seconds):
        key = f"ratelimit:{endpoint}:{client_ip}"
        current = cache.get(key, 0)
        if current >= limit:
            return True

        cache.set(key, current + 1, period_seconds)
        return False