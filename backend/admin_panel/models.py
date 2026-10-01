from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class MarketplaceSettings(models.Model):
	id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
	platform_commission = models.DecimalField(
		max_digits=5,
		decimal_places=2,
		default=10.00,
		validators=[MinValueValidator(0), MaxValueValidator(100)],
	)
	tax_rate = models.DecimalField(
		max_digits=5,
		decimal_places=2,
		default=18.00,
		validators=[MinValueValidator(0), MaxValueValidator(100)],
	)
	base_delivery_fee = models.DecimalField(
		max_digits=10,
		decimal_places=2,
		default=50.00,
		validators=[MinValueValidator(0)],
	)
	max_return_window = models.PositiveSmallIntegerField(
		default=7,
		validators=[MinValueValidator(0), MaxValueValidator(365)],
	)
	hero_image = models.ImageField(upload_to='homepage/', blank=True, null=True)
	hero_badge = models.CharField(max_length=120, default='Mega Electronics & Lifestyle Sale')
	hero_title = models.CharField(max_length=200, default='Smart Shopping. Express OTP Delivery.')
	hero_subtitle = models.TextField(default="India's premier e-commerce marketplace with verified stores, secure doorstep delivery, and instant wallet refunds.")
	featured_product_codes = models.TextField(blank=True, default='')
	facebook_url = models.URLField(blank=True)
	instagram_url = models.URLField(blank=True)
	youtube_url = models.URLField(blank=True)
	twitter_url = models.URLField(blank=True)
	privacy_policy = models.TextField(default='We may collect information required to create accounts, process orders and provide services.\n\nInformation may be used to process orders, provide customer support and improve our services.\n\nWe take reasonable measures to protect user information.')
	terms_conditions = models.TextField(default='Users must use the platform lawfully and responsibly.\n\nUsers are responsible for maintaining the security of their account credentials.\n\nOrders are subject to product availability, pricing and applicable policies.')
	refund_policy = models.TextField(default='Refund eligibility depends on the product, order status and applicable return conditions.\n\nOnce an eligible return is approved, the refund will be processed according to the applicable payment method.')
	shipping_policy = models.TextField(default='Orders are shipped to the address provided during checkout.\n\nDelivery time may vary depending on location, product availability and shipping conditions.\n\nWhere available, customers can track their order from the order details page.')
	cancellation_policy = models.TextField(default='Customers may cancel an order when cancellation is available for that order.\n\nOrders that have already been shipped may not be eligible for cancellation and may need to follow the return process.\n\nEligible cancelled orders will be handled according to the applicable refund policy.')
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return "Marketplace settings"


class HomepageHeroSlide(models.Model):
	image = models.ImageField(upload_to='homepage/slides/')
	ordering = models.PositiveSmallIntegerField(default=1)

	class Meta:
		ordering = ('ordering', 'id')

	def __str__(self):
		return f"Homepage hero slide {self.ordering}"


class FAQItem(models.Model):
	question = models.CharField(max_length=255)
	answer = models.TextField()
	is_active = models.BooleanField(default=True)
	ordering = models.PositiveIntegerField(default=0)

	class Meta:
		ordering = ('ordering', 'id')

	def __str__(self):
		return self.question
