from decimal import Decimal

from django.db import models
from categories.models import Category, SubCategory, Brand
from sellers.models import SellerProfile


class Product(models.Model):
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name='products')
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    subcategory = models.ForeignKey(SubCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    sku = models.CharField(max_length=50, unique=True)
    item_code = models.CharField(max_length=50, unique=True, help_text="Unique item code e.g. ITM-10023")
    description = models.TextField()

    # Pricing & 10% Platform Commission
    base_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Seller base earning")
    admin_commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Customer displayed price")
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    # Stock & Availability
    stock = models.IntegerField(default=15)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_flash_sale = models.BooleanField(default=False)
    flash_sale_end = models.DateTimeField(blank=True, null=True)

    # Return & Replacement Rules (Seller Configurable)
    is_returnable = models.BooleanField(default=True)
    return_window_days = models.IntegerField(default=7)
    is_replaceable = models.BooleanField(default=True)
    replacement_window_days = models.IntegerField(default=7)

    # Images
    main_image_url = models.CharField(max_length=500, blank=True, default='')
    average_rating = models.DecimalField(max_digits=3, decimal_places=1, default=4.5)
    total_reviews_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.item_code:
            import uuid
            self.item_code = f"ITM-{uuid.uuid4().hex[:8].upper()}"
        # Auto-calculate selling price if not provided: base + 10% commission + delivery + tax
        if not self.selling_price or self.selling_price == 0:
            comm = (self.base_price * self.admin_commission_percentage) / 100
            tax = (self.base_price * self.tax_percentage) / 100
            self.selling_price = round(self.base_price + comm + self.delivery_charge + tax, 2)
        if not self.mrp or self.mrp == 0:
            self.mrp = round(float(self.selling_price) * 1.3, 2)
        if self.mrp > self.selling_price:
            self.discount_percentage = round(((float(self.mrp) - float(self.selling_price)) / float(self.mrp)) * 100)
        super().save(*args, **kwargs)

    @property
    def admin_commission_amount(self):
        return (self.base_price * self.admin_commission_percentage / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def admin_tax_amount(self):
        return (self.base_price * self.tax_percentage / Decimal("100")).quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.title} - ₹{self.selling_price}"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gallery_images')
    image_url = models.CharField(max_length=500)
    alt_text = models.CharField(max_length=200, blank=True, default='')

    def __str__(self):
        return f"Image for {self.product.title}"


class ProductSpecification(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='specifications')
    group_name = models.CharField(max_length=100, default='General')  # e.g., General, Display, Performance
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.product.title}: {self.name} = {self.value}"
