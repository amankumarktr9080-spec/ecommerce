from django.db import models
from django.conf import settings
from sellers.models import SellerProfile
from delivery.models import DeliveryPartnerProfile
from products.models import Product


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Order Placed'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('packed', 'Packed'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
        ('replaced', 'Replaced'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('upi', 'UPI / QR Code'),
        ('card', 'Credit/Debit Card'),
        ('netbanking', 'Net Banking'),
        ('wallet', 'E-Wallet'),
    ]

    order_number = models.CharField(max_length=30, unique=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_orders')
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name='seller_orders')
    delivery_partner = models.ForeignKey(
        DeliveryPartnerProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_orders'
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    customer_name = models.CharField(max_length=100, default='Customer')
    customer_phone = models.CharField(max_length=20, default='9876543210')
    shipping_address = models.TextField()

    # Financial breakdown
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Multi-party Earnings
    admin_commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    seller_net_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivery_partner_earning = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)

    # Payment details
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='cod')
    payment_status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('paid', 'Paid'), ('failed', 'Failed'), ('refunded', 'Refunded')],
        default='pending'
    )

    # Delivery verification & Tracking
    delivery_otp = models.CharField(max_length=6, default='4921')
    customer_signature = models.TextField(blank=True, default='')
    proof_image_url = models.CharField(max_length=500, blank=True, default='')
    tracking_id = models.CharField(max_length=50, blank=True, default='')
    estimated_delivery = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    replacement_for = models.ForeignKey(
        'returns.ReturnRequest', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='replacement_orders',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.order_number} ({self.get_status_display()}) - ₹{self.grand_total}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}x {self.product.title} in {self.order.order_number}"


class OrderTimeline(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='timeline')
    status = models.CharField(max_length=30)
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order.order_number} - {self.title}"
