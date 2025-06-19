import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from .services import OrderService, ProductService
from .exceptions import BusinessException

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def bulk_order_view(request):
    try:
        data = json.loads(request.body)
        if not data or 'items' not in data:
            raise BusinessException("Invalid order format: missing 'items' field")

        items = data['items']
        if not isinstance(items, list) or len(items) == 0:
            raise BusinessException("'items' must be a non-empty list")

        # 验证每个订单项
        for item in items:
            if 'product_id' not in item or 'quantity' not in item:
                raise BusinessException("Each item must have 'product_id' and 'quantity'")
            if item['quantity'] <= 0:
                raise BusinessException("Quantity must be positive integer")

        # 处理订单
        order_id, results = OrderService.process_bulk_order(items)
        return JsonResponse({
            'order_id': order_id,
            'results': results
        }, status=201)

    except BusinessException as e:
        logger.warning(f"Business exception: {str(e)}")
        return JsonResponse({'error': e.message}, status=e.code)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)
    except Exception as e:
        logger.error(f"System error: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)


@require_GET
def product_search_view(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'error': 'Search query is required'}, status=400)

    try:
        results = ProductService.search_products(query)
        return JsonResponse({'results': results})
    except Exception as e:
        logger.error(f"Search error: {str(e)}", exc_info=True)
        # 降级处理：返回空结果
        return JsonResponse({'results': []})
