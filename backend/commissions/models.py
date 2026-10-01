from django.db import models
from orders.models import Order


class CommissionLog(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='commission_log')
    rate_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    order_total = models.DecimalField(max_digits=10, decimal_places=2)
    admin_commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    seller_payout_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_payout_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default='settled')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.order.order_number} - Admin: ₹{self.admin_commission_amount}, Seller: ₹{self.seller_payout_amount}"
