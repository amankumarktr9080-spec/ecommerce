from django.db import models
from django.conf import settings


class DeliveryPartnerApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    full_name = models.CharField(max_length=150)
    username = models.CharField(max_length=150, blank=True, default='')
    password_hash = models.CharField(max_length=128, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    phone = models.CharField(max_length=20)
    vehicle_type = models.CharField(max_length=50)
    vehicle_number = models.CharField(max_length=30, blank=True, default='')
    driving_license_no = models.CharField(max_length=50)
    address = models.TextField()
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    pincode = models.CharField(max_length=10, blank=True, default='')
    kyc_document = models.FileField(upload_to='delivery_kyc/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.full_name} ({self.status})"


class DeliveryPartnerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delivery_profile')
    vehicle_type = models.CharField(
        max_length=50,
        choices=[('bike', 'Motorcycle / Bike'), ('scooter', 'Electric Scooter'), ('van', 'Delivery Van')],
        default='bike'
    )
    vehicle_number = models.CharField(max_length=30)
    driving_license_no = models.CharField(max_length=50)
    address = models.TextField(blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    pincode = models.CharField(max_length=10, blank=True, default='')
    kyc_document = models.FileField(upload_to='delivery_kyc/', blank=True, null=True)
    is_online = models.BooleanField(default=True)
    current_lat = models.FloatField(default=28.6139)  # Delhi default
    current_lng = models.FloatField(default=77.2090)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=4.8)
    bank_name = models.CharField(max_length=100, blank=True, default='')
    account_number = models.CharField(max_length=50, blank=True, default='')
    ifsc_code = models.CharField(max_length=20, blank=True, default='')
    upi_id = models.CharField(max_length=50, blank=True, default='')
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.vehicle_number})"


class DeliveryRating(models.Model):
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='delivery_rating')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delivery_ratings')
    delivery_partner = models.ForeignKey(DeliveryPartnerProfile, on_delete=models.CASCADE, related_name='customer_ratings')
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.rating}★ for delivery {self.order.order_number}'
