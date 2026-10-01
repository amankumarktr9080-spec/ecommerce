from decimal import Decimal
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.test import override_settings

from categories.models import Brand, Category, SubCategory
from notifications.models import Notification
from orders.models import Order
from products.models import Product, ProductImage
from sellers.models import PayoutRequest, SellerProductOffer, SellerProfile
from users.models import User


class SellerEarningsTests(TestCase):
	def setUp(self):
		self.seller_user = User.objects.create_user(
			username='ledger-seller',
			password='test-password',
			role='seller',
		)
		self.seller = SellerProfile.objects.create(
			user=self.seller_user,
			store_name='Ledger Store',
			store_slug='ledger-store',
			phone='9876543210',
			email='ledger@example.com',
			business_address='Test seller address',
		)
		self.customer = User.objects.create_user(
			username='ledger-customer',
			password='test-password',
			role='customer',
		)
		self.client.force_login(self.seller_user)

	def create_order(self, order_number, status, subtotal, commission, seller_net):
		return Order.objects.create(
			order_number=order_number,
			customer=self.customer,
			seller=self.seller,
			status=status,
			payment_status='paid' if status == 'delivered' else 'pending',
			shipping_address='Test customer address',
			subtotal=subtotal,
			grand_total=subtotal,
			admin_commission_amount=commission,
			seller_net_earnings=seller_net,
		)

	def test_dashboard_uses_zero_instead_of_fabricated_sales(self):
		response = self.client.get(reverse('seller:dashboard'))

		self.assertEqual(response.context['total_gross'], Decimal('0.00'))
		self.assertEqual(response.context['total_commission'], Decimal('0.00'))
		self.assertEqual(response.context['net_earnings'], Decimal('0.00'))

	def test_wallet_matches_available_payout_and_separates_pending_earnings(self):
		self.create_order('ORD-LEDGER-DONE', 'delivered', 1000, 100, 900)
		self.create_order('ORD-LEDGER-PACKED', 'packed', 500, 50, 450)
		PayoutRequest.objects.create(seller=self.seller, amount=200)

		response = self.client.get(reverse('seller:earnings'))

		self.assertEqual(response.context['net_earnings'], Decimal('900.00'))
		self.assertEqual(response.context['pending_earnings'], Decimal('450.00'))
		self.assertEqual(response.context['available_payout'], Decimal('700.00'))
		self.assertEqual(response.context['wallet_balance'], Decimal('700.00'))
		self.assertEqual(response.context['wallet_balance'], response.context['seller_wallet_balance'])
		self.assertContains(response, 'Awaiting Delivery')

	def test_assign_rider_select_uses_native_browser_dropdown(self):
		self.create_order('ORD-LEDGER-PACKED', 'packed', 500, 50, 450)

		response = self.client.get(reverse('seller:orders'))

		self.assertContains(response, 'name="delivery_partner_id" data-native-select="true"')

	def test_seller_search_only_returns_own_products(self):
		category = Category.objects.create(name='Search Category', slug='search-category')
		own_product = Product.objects.create(
			seller=self.seller,
			title='Seller Search Shoe',
			slug='seller-search-shoe',
			category=category,
			sku='SELLER-SEARCH-SKU',
			item_code='SELLER-SEARCH-CODE',
			description='Seller catalog search test',
			base_price=100,
			selling_price=120,
		)
		other_user = User.objects.create_user(
			username='other-search-seller',
			password='test-password',
			role='seller',
		)
		other_seller = SellerProfile.objects.create(
			user=other_user,
			store_name='Other Store',
			store_slug='other-store',
			phone='9876543211',
			email='other@example.com',
			business_address='Other seller address',
		)
		Product.objects.create(
			seller=other_seller,
			title='Seller Search Shoe Other',
			slug='seller-search-shoe-other',
			category=category,
			sku='OTHER-SEARCH-SKU',
			item_code='OTHER-SEARCH-CODE',
			description='Other seller catalog search test',
			base_price=100,
			selling_price=120,
		)

		suggestions = self.client.get(reverse('seller:products'), {
			'suggestions': '1',
			'q': 'Seller Search Shoe',
		})
		self.assertEqual([item['id'] for item in suggestions.json()['results']], [own_product.id])

		products_response = self.client.get(reverse('seller:products'), {'q': 'Seller Search Shoe'})
		self.assertEqual(list(products_response.context['products']), [own_product])
		self.assertContains(products_response, 'action="/seller/products/"')
		self.assertContains(products_response, 'data-product-detail-url="/seller/products/{id}/"')

		detail_response = self.client.get(reverse('seller:product_details', args=[own_product.id]))
		self.assertEqual(detail_response.status_code, 200)
		self.assertContains(detail_response, 'Seller Search Shoe')
		self.assertContains(detail_response, 'href="/seller/products/')

		other_product = Product.objects.get(item_code='OTHER-SEARCH-CODE')
		other_detail_response = self.client.get(reverse('seller:product_details', args=[other_product.id]))
		self.assertEqual(other_detail_response.status_code, 404)

	def test_product_detail_and_edit_show_complete_product_fields(self):
		category = Category.objects.create(name='Full Details Category', slug='full-details-category')
		subcategory = SubCategory.objects.create(category=category, name='Full Details Subcategory', slug='full-details-subcategory')
		brand = Brand.objects.create(subcategory=subcategory, name='Full Details Brand', slug='full-details-brand')
		product = Product.objects.create(
			seller=self.seller,
			title='Complete Product',
			slug='complete-product',
			category=category,
			subcategory=subcategory,
			brand=brand,
			sku='COMPLETE-PRODUCT-SKU',
			item_code='COMPLETE-PRODUCT-CODE',
			description='Complete product record',
			base_price=100,
			delivery_charge=20,
			selling_price=135,
			mrp=180,
			stock=12,
		)

		detail_response = self.client.get(reverse('seller:product_details', args=[product.id]))
		edit_response = self.client.get(reverse('seller:edit_product', args=[product.id]))

		self.assertEqual(detail_response.status_code, 200)
		self.assertContains(detail_response, product.sku)
		self.assertContains(detail_response, subcategory.name)
		self.assertContains(detail_response, brand.name)
		self.assertContains(detail_response, 'Platform fee')
		self.assertContains(detail_response, 'Returns')
		self.assertEqual(edit_response.status_code, 200)
		for field in ('category_id', 'subcategory_id', 'brand_id', 'base_price', 'delivery_charge', 'mrp', 'stock', 'is_featured', 'is_flash_sale'):
			self.assertContains(edit_response, f'name="{field}"')
		self.assertContains(edit_response, f'data-category-id="{category.id}" data-subcategory-id="{subcategory.id}"')
		self.assertContains(edit_response, 'id="editGalleryImageFiles" name="gallery_image_files" accept="image/*" multiple')

	def test_edit_product_updates_all_seller_managed_fields_and_price(self):
		category = Category.objects.create(name='Edited Category', slug='edited-category')
		subcategory = SubCategory.objects.create(category=category, name='Edited Subcategory', slug='edited-subcategory')
		brand = Brand.objects.create(subcategory=subcategory, name='Edited Brand', slug='edited-brand')
		product = Product.objects.create(
			seller=self.seller,
			title='Before Edit',
			slug='before-edit',
			category=category,
			sku='BEFORE-EDIT-SKU',
			item_code='BEFORE-EDIT-CODE',
			description='Old description',
			base_price=100,
			delivery_charge=50,
			selling_price=165,
			mrp=200,
			stock=5,
		)

		response = self.client.post(reverse('seller:edit_product', args=[product.id]), {
			'title': 'After Edit',
			'category_id': category.id,
			'subcategory_id': subcategory.id,
			'brand_id': brand.id,
			'image_url': 'https://example.com/updated-product.jpg',
			'description': 'Updated full description',
			'base_price': '200',
			'delivery_charge': '20',
			'mrp': '300',
			'stock': '8',
			'is_active': 'on',
			'is_featured': 'on',
			'is_returnable': 'on',
			'return_window_days': '14',
			'replacement_window_days': '10',
		})

		self.assertEqual(response.status_code, 302)
		product.refresh_from_db()
		self.assertEqual(product.title, 'After Edit')
		self.assertEqual(product.category, category)
		self.assertEqual(product.subcategory, subcategory)
		self.assertEqual(product.brand, brand)
		self.assertEqual(product.base_price, Decimal('200.00'))
		self.assertEqual(product.delivery_charge, Decimal('20.00'))
		self.assertEqual(product.selling_price, Decimal('250.00'))
		self.assertEqual(product.discount_percentage, Decimal('17'))
		self.assertEqual(product.stock, 8)
		self.assertTrue(product.is_featured)
		self.assertFalse(product.is_flash_sale)
		self.assertEqual(product.return_window_days, 14)
		self.assertFalse(product.is_replaceable)

	def test_edit_product_saves_cover_image_as_media_file(self):
		product = Product.objects.create(
			seller=self.seller,
			title='Image Edit Product',
			slug='image-edit-product',
			sku='IMAGE-EDIT-SKU',
			item_code='IMAGE-EDIT-CODE',
			description='Image upload test',
			base_price=100,
			selling_price=165,
		)
		upload = SimpleUploadedFile('cover.png', b'\x89PNG\r\n\x1a\nimage-data', content_type='image/png')

		with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
			response = self.client.post(reverse('seller:edit_product', args=[product.id]), {
				'title': product.title,
				'image_url': product.main_image_url,
				'base_price': '100',
				'delivery_charge': '50',
				'mrp': '200',
				'stock': '5',
				'main_image_file': upload,
			})

			self.assertEqual(response.status_code, 302)
			product.refresh_from_db()
			self.assertIn('products/', product.main_image_url)
			self.assertLess(len(product.main_image_url), 500)

	def test_edit_product_can_remove_gallery_image_and_add_multiple_images(self):
		category = Category.objects.create(name='Gallery Edit Category', slug='gallery-edit-category')
		product = Product.objects.create(
			 seller=self.seller,
			 title='Gallery Edit Product',
			 slug='gallery-edit-product',
			 category=category,
			 sku='GALLERY-EDIT-SKU',
			 item_code='GALLERY-EDIT-CODE',
			 description='Gallery image edit test',
			 base_price=100,
			 selling_price=165,
		)
		remove_image = ProductImage.objects.create(product=product, image_url='https://example.com/remove.jpg')
		keep_image = ProductImage.objects.create(product=product, image_url='https://example.com/keep.jpg')
		uploads = [
			SimpleUploadedFile('gallery-1.png', b'gallery-one', content_type='image/png'),
			SimpleUploadedFile('gallery-2.png', b'gallery-two', content_type='image/png'),
		]

		with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
			response = self.client.post(reverse('seller:edit_product', args=[product.id]), {
				'title': product.title,
				'category_id': category.id,
				'image_url': product.main_image_url,
				'base_price': '100',
				'delivery_charge': '50',
				'mrp': '200',
				'stock': '5',
				'remove_gallery_image_ids': [remove_image.id],
				'gallery_image_files': uploads,
			})

		self.assertEqual(response.status_code, 302)
		self.assertFalse(ProductImage.objects.filter(pk=remove_image.pk).exists())
		self.assertTrue(ProductImage.objects.filter(pk=keep_image.pk).exists())
		new_images = ProductImage.objects.filter(product=product).exclude(pk=keep_image.pk)
		self.assertEqual(new_images.count(), 2)
		self.assertTrue(all(image.image_url.startswith('/media/products/') for image in new_images))


class SellerOfferTests(TestCase):
	def setUp(self):
		self.seller_user = User.objects.create_user(username='offer-seller', password='test-password', role='seller')
		self.seller = SellerProfile.objects.create(
			user=self.seller_user,
			store_name='Offer Store',
			store_slug='offer-store',
			phone='9876543210',
			email='offers@example.com',
			business_address='Offer seller address',
		)
		self.client.force_login(self.seller_user)
		self.product = self.create_product(self.seller, 'Offer Product', 'OFFER-SKU', 'OFFER-CODE')

	def create_product(self, seller, title, sku, item_code):
		return Product.objects.create(
			seller=seller,
			title=title,
			slug=sku.lower(),
			sku=sku,
			item_code=item_code,
			description='Offer test product',
			base_price=100,
			selling_price=120,
		)

	def test_seller_can_create_edit_and_delete_offer_for_own_product(self):
		url = reverse('seller:offers')
		response = self.client.post(url, {
			'action': 'create', 'product_id': self.product.id, 'title': 'Launch Offer',
			'discount_type': 'percent', 'discount_value': '10',
		})
		self.assertRedirects(response, url)
		offer = SellerProductOffer.objects.get(product=self.product)
		self.product.refresh_from_db()
		self.assertEqual(self.product.selling_price, Decimal('108.00'))

		self.client.post(url, {
			'action': 'update', 'offer_id': offer.id, 'title': 'Updated Offer',
			'discount_type': 'flat', 'discount_value': '20',
		})
		offer.refresh_from_db()
		self.product.refresh_from_db()
		self.assertEqual(offer.title, 'Updated Offer')
		self.assertEqual(self.product.selling_price, Decimal('100.00'))

		self.client.post(url, {'action': 'delete', 'offer_id': offer.id})
		self.assertFalse(SellerProductOffer.objects.filter(id=offer.id).exists())
		self.product.refresh_from_db()
		self.assertEqual(self.product.selling_price, Decimal('120.00'))

	def test_product_price_edit_updates_offer_price_and_restore_baseline(self):
		url = reverse('seller:offers')
		self.client.post(url, {
			'action': 'create', 'product_id': self.product.id, 'title': 'Launch Offer',
			'discount_type': 'percent', 'discount_value': '10',
		})
		offer = SellerProductOffer.objects.get(product=self.product)

		self.client.post(reverse('seller:edit_product', args=[self.product.id]), {
			'title': self.product.title,
			'base_price': '200',
			'delivery_charge': '50',
			'mrp': '400',
			'stock': '5',
		})
		offer.refresh_from_db()
		self.product.refresh_from_db()
		self.assertEqual(offer.original_price, Decimal('280.00'))
		self.assertEqual(self.product.selling_price, Decimal('252.00'))

		self.client.post(url, {'action': 'delete', 'offer_id': offer.id})
		self.product.refresh_from_db()
		self.assertEqual(self.product.selling_price, Decimal('280.00'))

	def test_seller_cannot_access_another_sellers_product_or_offer(self):
		other_user = User.objects.create_user(username='other-offer-seller', password='test-password', role='seller')
		other_seller = SellerProfile.objects.create(
			user=other_user,
			store_name='Other Offer Store',
			store_slug='other-offer-store',
			phone='9876543211',
			email='other-offers@example.com',
			business_address='Other offer seller address',
		)
		other_product = self.create_product(other_seller, 'Other Product', 'OTHER-OFFER-SKU', 'OTHER-OFFER-CODE')
		other_offer = SellerProductOffer.objects.create(
			product=other_product, title='Other Seller Offer', discount_type='percent',
			discount_value=10, original_price=120,
		)
		url = reverse('seller:offers')
		page = self.client.get(url)
		self.assertEqual(list(page.context['available_products']), [self.product])
		self.assertNotContains(page, 'Other Product')

		for payload in (
			{'action': 'update', 'offer_id': other_offer.id, 'title': 'Hijacked', 'discount_type': 'flat', 'discount_value': '10'},
			{'action': 'delete', 'offer_id': other_offer.id},
			{'action': 'create', 'product_id': other_product.id, 'title': 'Unauthorized', 'discount_type': 'percent', 'discount_value': '10'},
		):
			self.assertEqual(self.client.post(url, payload).status_code, 404)
		other_offer.refresh_from_db()
		self.assertEqual(other_offer.title, 'Other Seller Offer')
		self.assertEqual(other_product.selling_price, Decimal('120.00'))

	def test_non_seller_cannot_access_offer_management(self):
		customer = User.objects.create_user(username='offer-customer', password='test-password', role='customer')
		self.client.force_login(customer)
		self.assertEqual(self.client.get(reverse('seller:offers')).status_code, 403)


class SellerCustomerDirectoryTests(TestCase):
	def setUp(self):
		self.seller_user = User.objects.create_user(username='directory-seller', password='test-password', role='seller')
		self.seller = SellerProfile.objects.create(
			user=self.seller_user,
			store_name='Directory Store',
			store_slug='directory-store',
			phone='9876543210',
			email='directory@example.com',
			business_address='Directory seller address',
		)
		self.customer = User.objects.create_user(
			username='repeat-customer',
			password='test-password',
			role='customer',
			first_name='Riya',
			last_name='Shah',
			email='riya@example.com',
			phone='9000012345',
		)
		self.client.force_login(self.seller_user)

	def create_order(self, number, customer, seller, status, total):
		return Order.objects.create(
			order_number=number,
			customer=customer,
			seller=seller,
			status=status,
			shipping_address='Test address',
			subtotal=total,
			grand_total=total,
		)

	def test_directory_shows_real_seller_customer_order_aggregates(self):
		self.create_order('DIR-DELIVERED-1', self.customer, self.seller, 'delivered', 200)
		self.create_order('DIR-DELIVERED-2', self.customer, self.seller, 'delivered', 100)
		self.create_order('DIR-CANCELLED', self.customer, self.seller, 'cancelled', 75)
		other_user = User.objects.create_user(username='directory-other-seller', password='test-password', role='seller')
		other_seller = SellerProfile.objects.create(
			user=other_user,
			store_name='Other Directory Store',
			store_slug='other-directory-store',
			phone='9876543211',
			email='other-directory@example.com',
			business_address='Other seller address',
		)
		other_customer = User.objects.create_user(
			username='other-customer', password='test-password', role='customer', email='other@example.com',
		)
		self.create_order('DIR-OTHER-SELLER', other_customer, other_seller, 'delivered', 999)

		response = self.client.get(reverse('seller:customers'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.context['customers']), 1)
		row = response.context['customers'][0]
		self.assertEqual(row.total_orders, 3)
		self.assertEqual(row.total_spent, Decimal('300.00'))
		self.assertContains(response, 'Riya Shah')
		self.assertContains(response, 'Repeat Buyer')
		self.assertContains(response, 'riya@example.com')
		self.assertContains(response, 'tel:9000012345')
		self.assertNotContains(response, 'other@example.com')
		self.assertNotContains(response, 'Aman Kumar')

	def test_customer_directory_rejects_non_sellers(self):
		customer = User.objects.create_user(username='directory-customer', password='test-password', role='customer')
		self.client.force_login(customer)
		self.assertEqual(self.client.get(reverse('seller:customers')).status_code, 403)


class SellerNotificationTests(TestCase):
	def setUp(self):
		self.seller_user = User.objects.create_user(username='notice-seller', password='test-password', role='seller')
		SellerProfile.objects.create(
			user=self.seller_user,
			store_name='Notice Store',
			store_slug='notice-store',
			phone='9876543210',
			email='notice@example.com',
			business_address='Seller address',
		)
		self.other_user = User.objects.create_user(username='other-notice-user', password='test-password', role='seller')
		self.client.force_login(self.seller_user)

	def test_seller_profile_starts_read_only_and_saves_store_details(self):
		url = reverse('seller:store')
		response = self.client.get(url)
		self.assertContains(response, 'Edit Profile')
		self.assertContains(response, 'Reset Password')
		self.assertContains(response, 'id="sellerProfileEditPanel" class="glass-card"')
		self.assertContains(response, 'margin: 40px auto; padding: 32px;')
		self.assertContains(response, 'id="sellerPasswordPanel" style="display: none;')

		edit_response = self.client.get(url, {'show': 'edit'})
		self.assertContains(edit_response, 'id="sellerProfileEditPanel" class="glass-card"')
		self.assertContains(edit_response, 'display: block; max-width: 800px; margin: 40px auto; padding: 32px;')

		response = self.client.post(url, {
			'action': 'save_profile',
			'first_name': 'Store',
			'last_name': 'Owner',
			'store_name': 'Updated Store',
			'phone': '9876500002',
			'email': 'updated@example.com',
			'business_address': 'Updated address',
			'city': 'Patna',
			'state': 'Bihar',
			'pincode': '800001',
			'gst_number': 'GST-UPDATED',
			'pan_number': 'PAN-UPDATED',
			'description': 'Updated store description',
			'bank_name': 'New Bank',
			'account_number': '123456789',
			'ifsc_code': 'BANK0001234',
			'upi_id': 'updated@upi',
		})
		self.assertRedirects(response, url)
		self.seller_user.refresh_from_db()
		self.seller = SellerProfile.objects.get(user=self.seller_user)
		self.assertEqual(self.seller.store_name, 'Updated Store')
		self.assertEqual(self.seller.account_number, '123456789')
		self.assertEqual(self.seller_user.first_name, 'Store')

	def test_seller_sees_own_notifications_and_can_mark_them_read(self):
		own_notification = Notification.objects.create(
			user=self.seller_user,
			title='New order received',
			message='Order #NOTICE-1 is ready for processing.',
			link='/seller/orders/',
		)
		other_notification = Notification.objects.create(user=self.other_user, title='Private alert', message='Not for this seller.')
		url = reverse('seller:notifications')

		response = self.client.get(url)
		self.assertContains(response, 'Order #NOTICE-1 is ready for processing.')
		self.assertContains(response, 'href="/seller/orders/"')
		self.assertContains(response, 'Open')
		self.assertNotContains(response, 'Private alert')
		self.assertContains(response, 'Mark all as read (1)')

		response = self.client.post(url, {'action': 'mark_all_read'}, follow=True)
		self.assertContains(response, 'Mark all as read (0)')
		own_notification.refresh_from_db()
		self.assertTrue(own_notification.is_read)

		response = self.client.post(url, {
			'action': 'delete_selected',
			'notification_ids': [own_notification.id, other_notification.id],
		})
		self.assertRedirects(response, url)
		self.assertFalse(Notification.objects.filter(pk=own_notification.pk).exists())
		self.assertTrue(Notification.objects.filter(pk=other_notification.pk).exists())


class SellerProductTaxonomyTests(TestCase):
	def setUp(self):
		self.seller_user = User.objects.create_user(username='taxonomy-seller', password='test-password', role='seller')
		self.seller = SellerProfile.objects.create(
			user=self.seller_user,
			store_name='Taxonomy Store',
			store_slug='taxonomy-store',
			phone='9876543210',
			email='taxonomy@example.com',
			business_address='Seller address',
		)
		self.category = Category.objects.create(name='Taxonomy Electronics', slug='taxonomy-electronics')
		self.other_category = Category.objects.create(name='Taxonomy Fashion', slug='taxonomy-fashion')
		self.subcategory = SubCategory.objects.create(category=self.category, name='Audio', slug='taxonomy-audio')
		self.other_subcategory = SubCategory.objects.create(category=self.other_category, name='Clothing', slug='taxonomy-clothing')
		self.brand = Brand.objects.create(subcategory=self.subcategory, name='SoundCo', slug='soundco')
		self.other_brand = Brand.objects.create(subcategory=self.other_subcategory, name='StyleCo', slug='styleco')
		self.client.force_login(self.seller_user)

	def test_add_product_form_filters_brands_and_subcategories_by_category(self):
		response = self.client.get(reverse('seller:add_product'))

		self.assertContains(response, f'value="{self.subcategory.id}" data-category-id="{self.category.id}"')
		self.assertContains(response, f'value="{self.brand.id}" data-category-id="{self.category.id}" data-subcategory-id="{self.subcategory.id}"')
		self.assertContains(response, f'value="{self.other_brand.id}" data-category-id="{self.other_category.id}" data-subcategory-id="{self.other_subcategory.id}"')
		self.assertContains(response, 'id="productSubcategorySelect" name="subcategory_id" disabled')
		self.assertContains(response, 'id="productBrandSelect" name="brand_id" disabled')

	def test_product_is_saved_with_selected_category_subcategory_and_brand(self):
		response = self.client.post(reverse('seller:add_product'), {
			'title': 'Category-scoped product',
			'category_id': self.category.id,
			'subcategory_id': self.subcategory.id,
			'brand_id': self.brand.id,
			'base_price': '100',
			'delivery_charge': '50',
			'stock': '10',
			'image_url': 'https://example.com/item.jpg',
			'description': 'Test product',
		})

		self.assertEqual(response.status_code, 302)
		product = Product.objects.get(title='Category-scoped product')
		self.assertEqual(product.category, self.category)
		self.assertEqual(product.subcategory, self.subcategory)
		self.assertEqual(product.brand, self.brand)

	def test_product_rejects_brand_from_another_category(self):
		response = self.client.post(reverse('seller:add_product'), {
			'title': 'Invalid taxonomy product',
			'category_id': self.category.id,
			'subcategory_id': self.subcategory.id,
			'brand_id': self.other_brand.id,
			'base_price': '100',
			'delivery_charge': '50',
			'stock': '10',
			'image_url': 'https://example.com/item.jpg',
		})

		self.assertEqual(response.status_code, 302)
		self.assertFalse(Product.objects.filter(title='Invalid taxonomy product').exists())

	def test_product_rejects_brand_from_another_subcategory_in_same_category(self):
		other_subcategory = SubCategory.objects.create(category=self.category, name='Keyboards', slug='taxonomy-keyboards')
		other_brand = Brand.objects.create(subcategory=other_subcategory, name='KeyBrand', slug='key-brand')

		response = self.client.post(reverse('seller:add_product'), {
			'title': 'Mismatched subcategory brand product',
			'category_id': self.category.id,
			'subcategory_id': self.subcategory.id,
			'brand_id': other_brand.id,
			'base_price': '100',
			'delivery_charge': '50',
			'stock': '10',
			'image_url': 'https://example.com/item.jpg',
		})

		self.assertEqual(response.status_code, 302)
		self.assertFalse(Product.objects.filter(title='Mismatched subcategory brand product').exists())


