from django.db import models
from orders.models import Order


class PaymentTransaction(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='transactions')
    transaction_id = models.CharField(max_length=100, unique=True)
    refund_reference = models.CharField(max_length=150, blank=True, default='')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)  # UPI, Card, NetBanking, COD, Wallet
    status = models.CharField(max_length=30, default='success')  # success, pending, failed, refunded
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_id} - ₹{self.amount} ({self.status})"
