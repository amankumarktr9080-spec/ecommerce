from decimal import Decimal

from django.db import models
from django.conf import settings


class SellerRegistrationApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    full_name = models.CharField(max_length=150)
    store_name = models.CharField(max_length=150)
    username = models.CharField(max_length=150, blank=True, default='')
    password_hash = models.CharField(max_length=128, blank=True, default='')
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    business_address = models.TextField()
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    pincode = models.CharField(max_length=10, blank=True, default='')
    gstin = models.CharField(max_length=30, blank=True, default='')
    pan_number = models.CharField(max_length=20, blank=True, default='')
    kyc_document = models.FileField(upload_to='seller_kyc/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.store_name} ({self.status})"


class SellerProfile(models.Model):
    KYC_STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='seller_profile')
    store_name = models.CharField(max_length=150)
    store_slug = models.SlugField(unique=True)
    logo_url = models.CharField(max_length=500, blank=True, default='')
    banner_url = models.CharField(max_length=500, blank=True, default='')
    description = models.TextField(blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    business_address = models.TextField()
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    pincode = models.CharField(max_length=10, blank=True, default='')
    gst_number = models.CharField(max_length=50, blank=True)
    pan_number = models.CharField(max_length=20, blank=True, default='')
    kyc_document = models.FileField(upload_to='seller_kyc/', blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, default='State Bank of India')
    account_number = models.CharField(max_length=50, blank=True, default='987654321012')
    ifsc_code = models.CharField(max_length=20, blank=True, default='SBIN0001234')
    upi_id = models.CharField(max_length=50, blank=True, default='store@upi')
    is_approved = models.BooleanField(default=True)
    is_top_rated = models.BooleanField(default=False)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    kyc_status = models.CharField(max_length=20, choices=KYC_STATUS_CHOICES, default='verified')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.store_name} ({self.user.username})"


class SellerProductOffer(models.Model):
    DISCOUNT_TYPES = [
        ('percent', 'Percentage (%)'),
        ('flat', 'Flat Amount (₹)'),
    ]

    product = models.OneToOneField('products.Product', on_delete=models.CASCADE, related_name='seller_offer')
    title = models.CharField(max_length=150)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default='percent')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.product.title}"

    @property
    def savings_amount(self):
        return max(self.original_price - self.product.selling_price, Decimal('0.00'))


class PayoutRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Admin Review'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ]

    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name='payout_requests')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    bank_name = models.CharField(max_length=100, blank=True, default='')
    account_number = models.CharField(max_length=50, blank=True, default='')
    upi_id = models.CharField(max_length=50, blank=True, default='')
    admin_note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.seller.store_name} - ₹{self.amount} ({self.get_status_display()})"
