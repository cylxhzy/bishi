from django.db import models
from django.core.validators import MinValueValidator


class Product(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=0)  # 乐观锁版本号
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=['name'], name='product_name_idx'),
            models.Index(fields=['is_active'], name='product_active_idx'),
        ]


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('partial', 'Partially Fulfilled'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def update_status(self):
        items = self.items.all()
        if all(item.status == 'completed' for item in items):
            self.status = 'completed'
        elif any(item.status == 'completed' for item in items):
            self.status = 'partial'
        else:
            self.status = 'failed'
        self.save()


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=10, decimal_places=2)  # 价格快照
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES, default='pending')
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['status'], name='orderitem_status_idx'),
        ]