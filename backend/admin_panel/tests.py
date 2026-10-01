from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory

from commissions.models import CommissionLog
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from categories.models import Brand, Category, SubCategory
from coupons.models import Coupon
from delivery.models import DeliveryPartnerProfile, DeliveryRating
from notifications.models import Notification
from orders.models import Order, OrderItem
from payments.models import PaymentTransaction
from products.models import Product, ProductImage
from reviews.models import Review
from sellers.models import PayoutRequest, SellerProfile
from support.models import SupportTicket
from users.models import User
from .models import HomepageHeroSlide, MarketplaceSettings


class SupportTicketPanelTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='support-admin', password='pass123', role='admin')
        self.seller = User.objects.create_user(username='support-seller', password='pass123', role='seller')
        self.rider = User.objects.create_user(username='support-rider', password='pass123', role='delivery')

    def test_seller_and_rider_tickets_are_visible_in_admin_switcher(self):
        self.client.force_login(self.seller)
        seller_response = self.client.post('/seller/support/', {
            'subject': 'Store payout question',
            'message': 'Please check my payout.',
        })
        self.assertRedirects(seller_response, '/seller/support/')

        self.client.force_login(self.rider)
        rider_response = self.client.post('/delivery/support/', {
            'subject': 'Delivery route issue',
            'message': 'The assigned route is blocked.',
        })
        self.assertRedirects(rider_response, '/delivery/support/')

        self.client.force_login(self.admin)
        all_response = self.client.get(reverse('admin_panel:tickets'))
        self.assertContains(all_response, 'Store payout question')
        self.assertContains(all_response, 'Delivery route issue')

        seller_response = self.client.get(reverse('admin_panel:tickets'), {'type': 'seller'})
        self.assertContains(seller_response, 'Store payout question')
        self.assertNotContains(seller_response, 'Delivery route issue')

        rider_response = self.client.get(reverse('admin_panel:tickets'), {'type': 'rider'})
        self.assertContains(rider_response, 'Delivery route issue')
        self.assertNotContains(rider_response, 'Store payout question')


class FeaturedProductsAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='showcase-admin', password='pass123', role='admin')
        seller_user = User.objects.create_user(username='showcase-seller', password='pass123', role='seller')
        seller = SellerProfile.objects.create(
            user=seller_user,
            store_name='Showcase Store',
            store_slug='showcase-store',
            phone='9876543212',
            email='showcase@example.com',
            business_address='Showcase address',
        )
        category = Category.objects.create(name='Showcase Category', slug='showcase-category')
        self.products = [
            Product.objects.create(
                seller=seller,
                title=f'Showcase Product {index}',
                slug=f'showcase-product-{index}',
                category=category,
                sku=f'SHOWCASE-SKU-{index}',
                item_code=f'SHOWCASE-ITEM-{index}',
                description='Featured slideshow test product.',
                base_price=Decimal('100.00'),
                selling_price=Decimal('120.00'),
            )
            for index in range(1, 4)
        ]
        self.client.force_login(self.admin)
        self.url = reverse('admin_panel:marketplace_content')

    def test_admin_item_code_list_controls_showcase_count_and_order(self):
        for item_codes in (
            [product.item_code for product in self.products[:1]],
            [product.item_code for product in self.products],
        ):
            response = self.client.post(self.url, {
                'action': 'featured_products_save',
                'item_codes': item_codes,
            })
            self.assertRedirects(response, self.url)

            settings = MarketplaceSettings.objects.get(pk=1)
            self.assertEqual(settings.featured_product_codes.splitlines(), item_codes)
            homepage = self.client.get(reverse('public:home'))
            self.assertEqual(
                [product.item_code for product in homepage.context['showcase_products']],
                item_codes,
            )


class HomepageHeroSlidesAdminTests(TestCase):
    def setUp(self):
        admin = User.objects.create_user(username='hero-admin', password='pass123', role='admin')
        self.client.force_login(admin)
        self.url = reverse('admin_panel:marketplace_content')

    def image_upload(self, name, color):
        output = BytesIO()
        Image.new('RGB', (24, 16), color).save(output, format='JPEG')
        return SimpleUploadedFile(name, output.getvalue(), content_type='image/jpeg')

    @override_settings(STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    })
    def test_admin_uploads_orders_and_removes_homepage_hero_slides(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(self.url, {
                'action': 'hero_save',
                'hero_badge': 'Test badge',
                'hero_title': 'Test homepage hero',
                'hero_subtitle': 'Admin controlled images.',
                'hero_images': [
                    self.image_upload('hero-one.jpg', 'red'),
                    self.image_upload('hero-two.jpg', 'green'),
                    self.image_upload('hero-three.jpg', 'blue'),
                ],
            })
            self.assertRedirects(response, self.url)

            slides = list(HomepageHeroSlide.objects.all())
            self.assertEqual(len(slides), 3)
            response = self.client.post(self.url, {
                'action': 'hero_save',
                'hero_badge': 'Test badge',
                'hero_title': 'Test homepage hero',
                'hero_subtitle': 'Admin controlled images.',
                f'hero_slide_order_{slides[0].id}': '3',
                f'hero_slide_order_{slides[1].id}': '1',
                f'hero_slide_order_{slides[2].id}': '2',
            })
            self.assertRedirects(response, self.url)

            homepage = self.client.get(reverse('public:home'))
            ordered_slides = list(HomepageHeroSlide.objects.all())
            self.assertEqual(
                homepage.context['hero_images'],
                [slide.image.url for slide in ordered_slides],
            )
            self.assertEqual(ordered_slides[0].id, slides[1].id)
            self.assertContains(homepage, 'data-home-hero-slide')
            self.assertNotContains(homepage, '<a class="home-hero-image"')

            response = self.client.post(self.url, {
                'action': 'hero_save',
                'hero_badge': 'Test badge',
                'hero_title': 'Test homepage hero',
                'hero_subtitle': 'Admin controlled images.',
                'remove_hero_slides': [str(ordered_slides[0].id)],
            })
            self.assertRedirects(response, self.url)
            self.assertEqual(HomepageHeroSlide.objects.count(), 2)


class AdminProfileTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='profile-admin',
            email='admin-profile@example.com',
            password='test-password',
            role='admin',
        )
        self.client.force_login(self.admin_user)

    def test_admin_profile_starts_read_only_and_saves_details(self):
        url = reverse('admin_panel:profile')
        response = self.client.get(url)
        self.assertContains(response, 'Edit Profile')
        self.assertContains(response, 'Reset Password')
        self.assertContains(response, 'id="adminProfileEditPanel" style="display: none;')
        self.assertContains(response, 'id="adminPasswordPanel" style="display: none;')

        edit_response = self.client.get(url, {'show': 'edit'})
        self.assertContains(edit_response, 'id="adminProfileEditPanel" style="display: block;')

        response = self.client.post(url, {
            'action': 'save_profile',
            'first_name': 'Admin',
            'last_name': 'Updated',
            'email': 'updated-admin@example.com',
            'phone': '9876500003',
        })
        self.assertRedirects(response, url)
        self.admin_user.refresh_from_db()
        self.assertEqual(self.admin_user.first_name, 'Admin')
        self.assertEqual(self.admin_user.email, 'updated-admin@example.com')
        self.assertEqual(self.admin_user.phone, '9876500003')


class AdminProductCatalogTests(TestCase):
    def test_product_catalog_and_details_show_values_and_clickable_images(self):
        admin = User.objects.create_user(username='catalog-admin', password='pass123', role='admin')
        seller_user = User.objects.create_user(username='catalog-seller', password='pass123', role='seller')
        seller = SellerProfile.objects.create(
            user=seller_user,
            store_name='Catalog Store',
            store_slug='catalog-store',
            phone='9876543210',
            email='catalog@example.com',
            business_address='Address',
        )
        product = Product.objects.create(
            seller=seller,
            title='Catalog Test Product',
            slug='catalog-test-product',
            sku='CATALOG-001',
            item_code='CATALOG-001',
            description='Test product',
            main_image_url='https://example.com/main.jpg',
            base_price=Decimal('100.00'),
            selling_price=Decimal('165.00'),
            stock=23,
            is_returnable=True,
            return_window_days=14,
        )
        ProductImage.objects.create(product=product, image_url=product.main_image_url, alt_text='Main image')
        ProductImage.objects.create(product=product, image_url='https://example.com/side.jpg', alt_text='Side image')
        self.client.force_login(admin)

        response = self.client.get(reverse('admin_panel:products'))

        self.assertContains(response, '+₹10.00')
        self.assertContains(response, '₹165.00')
        self.assertContains(response, '23 in stock')
        self.assertContains(response, '14 Days')
        self.assertContains(response, reverse('admin_panel:product_details', args=[product.id]))

        detail_response = self.client.get(reverse('admin_panel:product_details', args=[product.id]))
        self.assertContains(detail_response, 'src="https://example.com/main.jpg" alt="Catalog Test Product" data-image-viewer')
        self.assertContains(detail_response, 'data-image-src="https://example.com/side.jpg"')
        self.assertNotContains(detail_response, 'target="_blank"')


class AdminOrderDetailTests(TestCase):
    def test_order_detail_shows_line_subtotal_and_opens_invoice_route(self):
        admin = User.objects.create_user(username='order-admin', password='pass123', role='admin')
        customer = User.objects.create_user(username='order-customer', password='pass123', role='customer')
        seller_user = User.objects.create_user(username='order-seller', password='pass123', role='seller')
        seller = SellerProfile.objects.create(
            user=seller_user,
            store_name='Order Store',
            store_slug='order-store',
            phone='9876543210',
            email='order-seller@example.com',
            business_address='Address',
        )
        product = Product.objects.create(
            seller=seller,
            title='Order Test Product',
            slug='order-test-product',
            sku='ORDER-001',
            item_code='ORDER-001',
            description='Test product',
            base_price=Decimal('100.00'),
            selling_price=Decimal('125.00'),
        )
        order = Order.objects.create(
            order_number='ADMIN-ORDER-001',
            customer=customer,
            seller=seller,
            shipping_address='Test address',
            grand_total=Decimal('125.00'),
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            unit_price=Decimal('125.00'),
            total_price=Decimal('125.00'),
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('admin_panel:order_details', args=[order.id]))

        self.assertContains(response, '₹125.00')
        self.assertContains(response, reverse('customer:order_invoice', args=[order.id]))
        invoice_response = self.client.get(reverse('customer:order_invoice', args=[order.id]))
        self.assertEqual(invoice_response.status_code, 200)

    def test_cancelled_wallet_order_refund_is_applied_once(self):
        admin = User.objects.create_user(username='refund-admin', password='pass123', role='admin')
        customer = User.objects.create_user(
            username='refund-customer', password='pass123', role='customer', wallet_balance=Decimal('20.00')
        )
        seller_user = User.objects.create_user(username='refund-seller', password='pass123', role='seller')
        seller = SellerProfile.objects.create(
            user=seller_user,
            store_name='Refund Store',
            store_slug='refund-store',
            phone='9876543210',
            email='refund-seller@example.com',
            business_address='Address',
        )
        order = Order.objects.create(
            order_number='WALLET-REFUND-001',
            customer=customer,
            seller=seller,
            status='cancelled',
            payment_method='wallet',
            payment_status='paid',
            shipping_address='Test address',
            subtotal=Decimal('50.00'),
            grand_total=Decimal('50.00'),
            admin_commission_amount=Decimal('5.00'),
            seller_net_earnings=Decimal('45.00'),
        )
        payment = PaymentTransaction.objects.create(
            order=order,
            transaction_id='WALLET-REFUND-TXN-001',
            amount=Decimal('50.00'),
            payment_method='WALLET',
            status='success',
        )
        commission = CommissionLog.objects.create(
            order=order,
            order_total=Decimal('50.00'),
            admin_commission_amount=Decimal('5.00'),
            seller_payout_amount=Decimal('45.00'),
            delivery_payout_amount=Decimal('0.00'),
            status='settled',
        )
        self.client.force_login(admin)
        url = reverse('admin_panel:order_details', args=[order.id])

        self.client.post(url, {'action': 'refund_cancelled_wallet'})
        customer.refresh_from_db()
        order.refresh_from_db()
        payment.refresh_from_db()
        commission.refresh_from_db()
        self.assertEqual(customer.wallet_balance, Decimal('70.00'))
        self.assertEqual(order.payment_status, 'refunded')
        self.assertEqual(payment.status, 'refunded')
        self.assertEqual(commission.status, 'cancelled')

        self.client.post(url, {'action': 'refund_cancelled_wallet'})
        customer.refresh_from_db()
        self.assertEqual(customer.wallet_balance, Decimal('70.00'))

    def test_cancelled_external_refund_requires_and_records_provider_reference(self):
        admin = User.objects.create_user(username='external-refund-admin', password='pass123', role='admin')
        customer = User.objects.create_user(username='external-refund-customer', password='pass123', role='customer')
        seller_user = User.objects.create_user(username='external-refund-seller', password='pass123', role='seller')
        seller = SellerProfile.objects.create(
            user=seller_user,
            store_name='External Refund Store',
            store_slug='external-refund-store',
            phone='9876543210',
            email='external-refund@example.com',
            business_address='Address',
        )
        order = Order.objects.create(
            order_number='CARD-REFUND-001',
            customer=customer,
            seller=seller,
            status='cancelled',
            payment_method='card',
            payment_status='paid',
            shipping_address='Test address',
            subtotal=Decimal('80.00'),
            grand_total=Decimal('100.00'),
            admin_commission_amount=Decimal('8.00'),
            seller_net_earnings=Decimal('72.00'),
        )
        payment = PaymentTransaction.objects.create(
            order=order,
            transaction_id='CARD-REFUND-TXN-001',
            amount=Decimal('100.00'),
            payment_method='CARD',
            status='success',
        )
        self.client.force_login(admin)
        url = reverse('admin_panel:order_details', args=[order.id])

        self.client.post(url, {'action': 'record_cancelled_external_refund', 'refund_reference': ''})
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')

        self.client.post(url, {
            'action': 'record_cancelled_external_refund',
            'refund_reference': 'PROVIDER-REF-001',
        })
        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(order.payment_status, 'refunded')
        self.assertEqual(payment.status, 'refunded')
        self.assertEqual(payment.refund_reference, 'PROVIDER-REF-001')


class AdminSellerManagementTests(TestCase):
    def test_admin_can_create_valid_seller_profile(self):
        response = self.client.post(
            reverse('admin_panel:add_seller'),
            {
                'username': 'admin_seller_1',
                'email': 'seller1@example.com',
                'password': 'SecurePass123',
                'phone': '+919876543210',
                'first_name': 'Rahul',
                'last_name': 'Sharma',
                'store_name': 'Apex Electronics',
                'gst_number': '29ABCDE1234F1Z5',
                'commission_rate': '12.5',
                'store_address': '12 Market Road, New Delhi',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='admin_seller_1', role='seller').exists())
        self.assertTrue(SellerProfile.objects.filter(user__username='admin_seller_1').exists())
        seller = SellerProfile.objects.get(user__username='admin_seller_1')
        self.assertEqual(str(seller.commission_rate), '12.50')
        self.assertEqual(seller.kyc_status, 'verified')
        self.assertTrue(seller.is_approved)


class AdminCategoryTaxonomyTests(TestCase):
    def test_catalog_sidebar_pages_open(self):
        for page_name in ('products', 'categories', 'subcategories', 'brands'):
            with self.subTest(page=page_name):
                response = self.client.get(reverse(f'admin_panel:{page_name}'))
                self.assertEqual(response.status_code, 200)

    def test_admin_can_add_subcategory_and_brand_to_selected_category(self):
        category = Category.objects.create(name='Taxonomy Electronics', slug='taxonomy-electronics')

        self.client.post(reverse('admin_panel:subcategories'), {
            'category_id': category.id,
            'name': 'Audio',
        })
        subcategory = SubCategory.objects.get(category=category, name='Audio')
        self.client.post(reverse('admin_panel:brands'), {
            'category_id': category.id,
            'subcategory_id': subcategory.id,
            'name': 'SoundCo',
        })

        self.assertTrue(Brand.objects.filter(subcategory=subcategory, name='SoundCo').exists())
        response = self.client.get(reverse('admin_panel:subcategories'))
        self.assertContains(response, 'Taxonomy Electronics')
        self.assertContains(response, 'Audio')
        self.assertContains(response, 'SoundCo')
        self.assertContains(response, '/admin-panel/categories/')
        self.assertContains(response, '/admin-panel/subcategories/')
        self.assertContains(response, '/admin-panel/brands/')

    def test_brand_form_filters_subcategories_after_category_selection(self):
        category = Category.objects.create(name='Filtered Electronics', slug='filtered-electronics')
        subcategory = SubCategory.objects.create(category=category, name='Audio', slug='filtered-audio')

        response = self.client.get(reverse('admin_panel:brands'))

        self.assertContains(response, 'name="category_id"')
        self.assertContains(response, 'name="subcategory_id" class="brand-subcategory-select" required disabled')
        self.assertContains(response, f'data-category-id="{category.id}"')
        self.assertContains(response, f'<option value="{category.id}">{category.name}</option>')

    def test_subcategory_list_can_filter_by_parent_category(self):
        first_category = Category.objects.create(name='First Filter Category', slug='first-filter-category')
        second_category = Category.objects.create(name='Second Filter Category', slug='second-filter-category')
        first_subcategory = SubCategory.objects.create(category=first_category, name='First Subcategory', slug='first-filter-subcategory')
        second_subcategory = SubCategory.objects.create(category=second_category, name='Second Subcategory', slug='second-filter-subcategory')

        response = self.client.get(reverse('admin_panel:subcategories'), {'category_id': first_category.id})

        self.assertEqual(list(response.context['subcategories']), [first_subcategory])
        self.assertNotContains(response, second_subcategory.name)

    def test_brand_list_filters_by_category_subcategory_or_both(self):
        first_category = Category.objects.create(name='First Brand Category', slug='first-brand-category')
        second_category = Category.objects.create(name='Second Brand Category', slug='second-brand-category')
        first_subcategory = SubCategory.objects.create(category=first_category, name='First Brand Subcategory', slug='first-brand-subcategory')
        second_subcategory = SubCategory.objects.create(category=first_category, name='Second Brand Subcategory', slug='second-brand-subcategory')
        third_subcategory = SubCategory.objects.create(category=second_category, name='Third Brand Subcategory', slug='third-brand-subcategory')
        first_brand = Brand.objects.create(subcategory=first_subcategory, name='First Brand', slug='first-brand')
        second_brand = Brand.objects.create(subcategory=second_subcategory, name='Second Brand', slug='second-brand')
        third_brand = Brand.objects.create(subcategory=third_subcategory, name='Third Brand', slug='third-brand')

        all_brands_response = self.client.get(reverse('admin_panel:brands'))
        category_response = self.client.get(reverse('admin_panel:brands'), {'category_id': first_category.id})
        subcategory_response = self.client.get(reverse('admin_panel:brands'), {'subcategory_id': second_subcategory.id})
        combined_response = self.client.get(reverse('admin_panel:brands'), {
            'category_id': first_category.id,
            'subcategory_id': second_subcategory.id,
        })
        mismatched_response = self.client.get(reverse('admin_panel:brands'), {
            'category_id': second_category.id,
            'subcategory_id': second_subcategory.id,
        })

        self.assertContains(all_brands_response, f'data-category-id="{first_category.id}">First Brand Subcategory</option>')
        self.assertNotContains(all_brands_response, f'{first_category.name} / First Brand Subcategory</option>')
        self.assertEqual(set(category_response.context['brands']), {first_brand, second_brand})
        self.assertEqual(list(subcategory_response.context['brands']), [second_brand])
        self.assertEqual(list(combined_response.context['brands']), [second_brand])
        self.assertEqual(list(mismatched_response.context['brands']), [])
        self.assertNotIn(third_brand, category_response.context['brands'])

    def test_category_subcategory_and_brand_can_be_edited_and_deleted(self):
        category = Category.objects.create(name='Original Category', slug='original-category')
        subcategory = SubCategory.objects.create(category=category, name='Original Subcategory', slug='original-subcategory')
        brand = Brand.objects.create(subcategory=subcategory, name='Original Brand', slug='original-brand')

        self.client.post(reverse('admin_panel:categories'), {
            'action': 'edit', 'category_id': category.id, 'name': 'Updated Category', 'slug': 'updated-category', 'icon': 'fa-solid fa-tag',
        })
        self.client.post(reverse('admin_panel:subcategories'), {
            'action': 'edit', 'subcategory_id': subcategory.id, 'category_id': category.id, 'name': 'Updated Subcategory', 'slug': 'updated-subcategory',
        })
        self.client.post(reverse('admin_panel:brands'), {
            'action': 'edit', 'brand_id': brand.id, 'category_id': category.id, 'subcategory_id': subcategory.id, 'name': 'Updated Brand', 'slug': 'updated-brand',
        })

        category.refresh_from_db()
        subcategory.refresh_from_db()
        brand.refresh_from_db()
        self.assertEqual(category.name, 'Updated Category')
        self.assertEqual(subcategory.name, 'Updated Subcategory')
        self.assertEqual(brand.name, 'Updated Brand')

        self.client.post(reverse('admin_panel:brands'), {'action': 'delete', 'brand_id': brand.id})
        self.assertFalse(Brand.objects.filter(id=brand.id).exists())

        nested_brand = Brand.objects.create(subcategory=subcategory, name='Nested Brand', slug='nested-brand')
        self.client.post(reverse('admin_panel:subcategories'), {'action': 'delete', 'subcategory_id': subcategory.id})
        self.assertFalse(SubCategory.objects.filter(id=subcategory.id).exists())
        self.assertFalse(Brand.objects.filter(id=nested_brand.id).exists())

        self.client.post(reverse('admin_panel:categories'), {'action': 'delete', 'category_id': category.id})
        self.assertFalse(Category.objects.filter(id=category.id).exists())

    def test_admin_coupon_table_displays_min_value_usage_count_and_actions(self):
        coupon = Coupon.objects.create(
            code='FESTIVE20',
            discount_type='percent',
            discount_value=20,
            min_order_amount=499,
            used_count=12,
            max_uses=50,
            is_active=True,
        )

        response = self.client.get(reverse('admin_panel:coupons'))

        self.assertContains(response, '₹499.00')
        self.assertContains(response, '12 / 50')
        self.assertContains(response, 'name="action" value="edit"')
        self.assertContains(response, 'name="action" value="delete"')
        self.assertContains(response, str(coupon.code))

    def test_support_ticket_and_delivery_rating_create_notifications(self):
        admin_user = User.objects.create_user(username='admin-notify', email='admin-notify@example.com', password='pass123', role='admin')
        customer = User.objects.create_user(username='notify-customer', email='notify-customer@example.com', password='pass123', role='customer')
        rider_user = User.objects.create_user(username='notify-rider', email='notify-rider@example.com', password='pass123', role='delivery')
        rider = DeliveryPartnerProfile.objects.create(
            user=rider_user,
            vehicle_number='DL99ZZ9999',
            driving_license_no='DL-999999',
            city='Delhi',
            state='Delhi',
            pincode='110001',
            is_approved=True,
        )
        seller = SellerProfile.objects.create(
            user=User.objects.create_user(username='notify-seller', email='notify-seller@example.com', password='pass123', role='seller'),
            store_name='Notify Seller',
            store_slug='notify-seller',
            phone='9876543210',
            email='notify-seller@example.com',
            business_address='Address',
        )
        order = Order.objects.create(
            order_number='NTF-ORDER-001',
            customer=customer,
            seller=seller,
            delivery_partner=rider,
            shipping_address='Delivery notification address',
            subtotal='300.00',
            grand_total='300.00',
            payment_status='paid',
            customer_name='Notify Customer',
            customer_phone='9876543210',
        )

        SupportTicket.objects.create(
            user=customer,
            ticket_id='TKT-NOTIFY-001',
            subject='Refund issue',
            category='Order Issue',
            priority='high',
            message='My order is delayed.',
        )
        DeliveryRating.objects.create(
            order=order,
            customer=customer,
            delivery_partner=rider,
            rating=5,
            comment='Fast delivery.',
        )

        self.assertTrue(Notification.objects.filter(user=admin_user, title__icontains='Support ticket').exists() or Notification.objects.filter(user__role='admin').exists())
        self.assertTrue(Notification.objects.filter(user=rider_user, title__icontains='rating').exists())

        self.client.force_login(admin_user)
        response = self.client.get(reverse('admin_panel:notifications'))
        self.assertContains(response, 'Open')
        self.assertContains(response, reverse('admin_panel:tickets'))

        own_notification = Notification.objects.filter(user=admin_user).first()
        other_notification = Notification.objects.create(
            user=customer,
            title='Customer-only notification',
            message='Do not delete this from the admin panel.',
        )
        self.assertContains(response, 'data-select-all')
        response = self.client.post(reverse('admin_panel:notifications'), {
            'action': 'delete_selected',
            'notification_ids': [own_notification.id, other_notification.id],
        })
        self.assertRedirects(response, reverse('admin_panel:notifications'))
        self.assertFalse(Notification.objects.filter(pk=own_notification.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=other_notification.pk).exists())

    def test_admin_reviews_page_shows_product_and_delivery_reviews_with_tabs(self):
        customer = User.objects.create_user(username='review-customer', email='review-customer@example.com', password='pass123', role='customer')
        rider_user = User.objects.create_user(username='review-rider', email='review-rider@example.com', password='pass123', role='delivery')
        seller_user = User.objects.create_user(username='review-seller', email='review-seller@example.com', password='pass123', role='seller')
        seller = SellerProfile.objects.create(
            user=seller_user,
            store_name='Review Seller',
            store_slug='review-seller',
            phone='9876543210',
            email='review-seller@example.com',
            business_address='Address',
        )
        rider = DeliveryPartnerProfile.objects.create(
            user=rider_user,
            vehicle_number='DL01AB1234',
            driving_license_no='DL-123456',
            city='Delhi',
            state='Delhi',
            pincode='110001',
            is_approved=True,
        )
        product = Product.objects.filter(item_code='REV-001').first()
        if not product:
            product = Product.objects.create(
                seller=seller,
                title='Review Product',
                slug='review-product',
                sku='REV-001',
                item_code='REV-001',
                description='Test product',
                base_price='100.00',
                selling_price='120.00',
                mrp='150.00',
            )

        Review.objects.create(
            product=product,
            customer=customer,
            rating=5,
            title='Great product',
            comment='Very good quality.',
            is_verified_purchase=True,
        )
        order = Order.objects.create(
            order_number='REV-ORDER-001',
            customer=customer,
            seller=seller,
            delivery_partner=rider,
            shipping_address='Test address',
            subtotal='500.00',
            grand_total='500.00',
            payment_status='paid',
            delivery_partner_earning='50.00',
            customer_name='Review Customer',
            customer_phone='9876543210',
        )
        DeliveryRating.objects.create(
            order=order,
            customer=customer,
            delivery_partner=rider,
            rating=4,
            comment='Fast and polite delivery.',
        )

        response = self.client.get(reverse('admin_panel:reviews'))

        self.assertContains(response, 'Product Reviews')
        self.assertContains(response, 'Delivery Reviews')
        self.assertContains(response, 'Great product')
        self.assertContains(response, 'Fast and polite delivery.')
        self.assertContains(response, 'data-tab="delivery"')
        self.assertContains(response, 'class="review-tabs"')
        self.assertContains(response, 'aria-selected="true"')


class AdminDashboardFinancialMetricTests(TestCase):
    def setUp(self):
        customer = User.objects.create_user(username='dashboard-customer', password='test-password', role='customer')
        seller_user = User.objects.create_user(username='dashboard-seller', password='test-password', role='seller')
        seller = SellerProfile.objects.create(
            user=seller_user,
            store_name='Dashboard Store',
            store_slug='dashboard-store',
            phone='9876543210',
            email='dashboard@example.com',
            business_address='Dashboard seller address',
        )
        delivered = self.create_order(customer, seller, 'DASH-DELIVERED', 'delivered', 'paid', '100.00', '125.00', '10.00')
        cancelled = self.create_order(customer, seller, 'DASH-CANCELLED', 'cancelled', 'paid', '200.00', '225.00', '99.00')
        self.create_order(customer, seller, 'DASH-RETURNED', 'returned', 'refunded', '300.00', '325.00', '0.00')
        self.create_order(customer, seller, 'DASH-SHIPPED', 'shipped', 'pending', '400.00', '425.00', '40.00')

        CommissionLog.objects.create(
            order=delivered,
            order_total=delivered.grand_total,
            admin_commission_amount=Decimal('10.00'),
            seller_payout_amount=Decimal('90.00'),
            delivery_payout_amount=Decimal('5.00'),
            status='settled',
        )
        CommissionLog.objects.create(
            order=cancelled,
            order_total=cancelled.grand_total,
            admin_commission_amount=Decimal('99.00'),
            seller_payout_amount=Decimal('0.00'),
            delivery_payout_amount=Decimal('0.00'),
            status='settled',
        )
        self.seller = seller

    @staticmethod
    def create_order(customer, seller, order_number, status, payment_status, subtotal, grand_total, commission):
        return Order.objects.create(
            order_number=order_number,
            customer=customer,
            seller=seller,
            status=status,
            payment_status=payment_status,
            shipping_address='Dashboard test address',
            subtotal=Decimal(subtotal),
            grand_total=Decimal(grand_total),
            admin_commission_amount=Decimal(commission),
        )

    def test_dashboard_uses_valid_gmv_and_settled_commission_wallet(self):
        response = self.client.get(reverse('admin_panel:dashboard'))

        self.assertEqual(response.context['total_revenue'], 500.0)
        self.assertEqual(response.context['total_orders'], 4)
        self.assertEqual(response.context['total_commission'], 10.0)
        self.assertEqual(response.context['wallet_balance'], Decimal('10.00'))

        PayoutRequest.objects.create(seller=self.seller, amount=Decimal('75.00'), status='paid')
        PayoutRequest.objects.create(
            seller=self.seller,
            amount=Decimal('50.00'),
            status='paid',
            admin_note='BANK-REF-VALID',
        )
        commission_response = self.client.get(reverse('admin_panel:commissions'))
        self.assertEqual(commission_response.context['total_order_volume'], Decimal('500.00'))
        self.assertEqual(commission_response.context['total_commission'], Decimal('10.00'))
        self.assertEqual(commission_response.context['total_seller_net'], Decimal('50.00'))

    def test_payout_requires_a_transfer_reference_before_marking_paid(self):
        payout = PayoutRequest.objects.create(seller=self.seller, amount=Decimal('75.00'))
        url = reverse('admin_panel:payouts')

        self.client.post(url, {'payout_id': payout.id, 'action': 'approve', 'admin_note': ''})
        payout.refresh_from_db()
        self.assertEqual(payout.status, 'pending')

        self.client.post(url, {
            'payout_id': payout.id,
            'action': 'approve',
            'admin_note': 'BANK-TRANSFER-REF-001',
        })
        payout.refresh_from_db()
        self.assertEqual(payout.status, 'paid')
        self.assertEqual(payout.admin_note, 'BANK-TRANSFER-REF-001')


class AdminSearchTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username='lookup-customer',
            email='lookup-customer@example.com',
            first_name='Lookup',
            last_name='Customer',
            role='customer',
        )
        seller_user = User.objects.create_user(
            username='lookup-seller',
            email='lookup-seller@example.com',
            role='seller',
        )
        self.seller = SellerProfile.objects.create(
            user=seller_user,
            store_name='Lookup Outlet',
            store_slug='lookup-outlet',
            phone='9876543210',
            email='lookup-seller@example.com',
            business_address='Lookup seller address',
        )
        Order.objects.create(
            order_number='ORDER-LOOKUP-42',
            customer=self.customer,
            seller=self.seller,
            customer_name='Lookup Customer',
            status='shipped',
            shipping_address='Lookup delivery address',
            grand_total=Decimal('150.00'),
        )

    def test_typeahead_returns_admin_order_customer_and_seller_results(self):
        response = self.client.get(reverse('admin_panel:search'), {'q': 'lookup', 'suggestions': '1'})

        self.assertEqual(response.status_code, 200)
        results = response.json()['results']
        result_types = {result['type'] for result in results}
        self.assertTrue({'Order', 'Customer', 'Seller'}.issubset(result_types))
        self.assertTrue(all(result['url'].startswith('/admin-panel/') for result in results))

    def test_enter_search_renders_full_admin_results(self):
        response = self.client.get(reverse('admin_panel:search'), {'q': 'lookup'})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin_panel/search-results.html')
        self.assertContains(response, 'ORDER-LOOKUP-42')
        self.assertContains(response, 'Lookup Outlet')
