from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings
from orders.models import Order, OrderItem


class ReturnRequest(models.Model):
    TYPE_CHOICES = [
        ('return', 'Return & Refund'),
        ('replace', 'Replacement'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending Seller Review'),
        ('cancelled', 'Cancelled by Customer'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pickup_failed', 'Pickup Failed'),
        ('pickup_scheduled', 'Pickup Scheduled'),
        ('item_picked_up', 'Item Picked Up'),
        ('inspection_passed', 'Inspection Passed'),
        ('inspection_failed', 'Inspection Failed'),
        ('refund_pending', 'Refund Pending'),
        ('refund_processed', 'Refund Completed'),
        ('refund_failed', 'Refund Failed'),
        ('replacement_pending', 'Replacement Pending'),
        ('replacement_reserved', 'Replacement Reserved'),
        ('replacement_dispatched', 'Replacement Dispatched'),
        ('replacement_delivered', 'Replacement Delivered'),
        ('replacement_failed', 'Replacement Failed'),
    ]
    REASON_CHOICES = [
        ('defective', 'Defective / Not Working'),
        ('damaged', 'Damaged in Transit'),
        ('wrong_item', 'Received Wrong Item'),
        ('not_as_described', 'Product Not as Described'),
        ('size_issue', 'Size / Fit Issue'),
        ('other', 'Other Reason'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='return_requests')
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.PROTECT, related_name='return_requests',
        null=True, blank=True,
    )
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_returns')
    request_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='return')
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    details = models.TextField(blank=True)
    photo_url = models.CharField(max_length=500, blank=True, default='')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    pickup_earning = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    refund_method = models.CharField(max_length=30, default='wallet')  # wallet or original
    seller_remarks = models.TextField(blank=True, default='')
    admin_remarks = models.TextField(blank=True, default='')
    pickup_partner = models.ForeignKey(
        'delivery.DeliveryPartnerProfile', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='return_pickups',
    )
    pickup_tracking_id = models.CharField(max_length=80, blank=True, default='')
    approved_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    inspected_at = models.DateTimeField(null=True, blank=True)
    refund_reference = models.CharField(max_length=150, blank=True, default='')
    replacement_order = models.OneToOneField(
        Order, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='source_return_request',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_request_type_display()} for {self.order.order_number} ({self.get_status_display()})"
