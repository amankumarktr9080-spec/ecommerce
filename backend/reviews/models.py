from django.db import models
from django.conf import settings
from products.models import Product


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='product_reviews')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(default=5)  # 1 to 5
    title = models.CharField(max_length=200)
    comment = models.TextField()
    photo_url_1 = models.CharField(max_length=500, blank=True, default='')
    photo_url_2 = models.CharField(max_length=500, blank=True, default='')
    photo_url_3 = models.CharField(max_length=500, blank=True, default='')
    seller_reply = models.TextField(blank=True, default='')
    is_verified_purchase = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.rating}★ by {self.customer.username} on {self.product.title}"
