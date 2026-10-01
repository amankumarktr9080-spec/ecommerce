from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=60, default='fa-solid fa-layer-group')
    image_url = models.CharField(max_length=500, blank=True, default='')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    slug = models.SlugField()

    class Meta:
        verbose_name_plural = 'SubCategories'

    def __str__(self):
        return f"{self.category.name} > {self.name}"


class Brand(models.Model):
    subcategory = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='brands',
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(blank=True)
    logo_url = models.CharField(max_length=500, blank=True, default='')
    is_featured = models.BooleanField(default=False)

    def __str__(self):
        return self.name
