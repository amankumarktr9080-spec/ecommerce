from django.db import models


class Coupon(models.Model):
    code = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=255, blank=True)
    discount_type = models.CharField(max_length=20, choices=[('percent', 'Percentage (%)'), ('flat', 'Flat Amount (₹)')], default='percent')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    max_uses = models.PositiveIntegerField(default=0, blank=True, null=True)
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - {self.discount_value}{'%' if self.discount_type == 'percent' else '₹'} OFF"
