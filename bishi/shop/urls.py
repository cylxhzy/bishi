from django.urls import path
from .views import bulk_order_view, product_search_view

urlpatterns = [
    path('orders/bulk/', bulk_order_view, name='bulk-order'),
    path('products/search/', product_search_view, name='product-search'),
]