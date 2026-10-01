from django.db import models


class OfferBanner(models.Model):
    title = models.CharField(max_length=150)
    subtitle = models.CharField(max_length=255, blank=True)
    discount_tag = models.CharField(max_length=50, default='UP TO 60% OFF')
    image_url = models.CharField(max_length=500)
    link_url = models.CharField(max_length=255, default='/customer/products/')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.discount_tag})"
