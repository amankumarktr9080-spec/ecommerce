from decimal import Decimal
from datetime import datetime, timedelta
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from cart.models import Cart, CartItem
from categories.models import Category
from coupons.models import Coupon
from delivery.models import DeliveryPartnerProfile, DeliveryRating
from notifications.models import Notification
from orders.models import Order, OrderTimeline
from payments.models import PaymentTransaction
from products.models import Product
from returns.models import ReturnRequest
from reviews.models import Review
from sellers.models import SellerProductOffer, SellerProfile
from users.models import Address, User
from wishlist.models import WishlistItem


class CustomerAuthenticationTests(TestCase):
    def test_customer_dashboard_requires_login(self):
        response = self.client.get(reverse('customer:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_customer_products_is_public(self):
        response = self.client.get(reverse('customer:products'))
        self.assertEqual(response.status_code, 200)

        public_home = self.client.get(reverse('public:home'))
        self.assertEqual(public_home.status_code, 200)
        self.assertContains(public_home, 'id="globalSearchInput"')
        self.assertContains(public_home, 'id="searchSuggestions"')
        self.assertContains(public_home, 'data-suggestions-url="/customer/search/"')

    def test_guest_can_save_cart_and_wishlist_items(self):
        product = Product.objects.filter(is_active=True).first()
        if product is None:
            self.skipTest('No active product available')

        self.client.post(reverse('customer:cart'), {
            'action': 'add',
            'product_id': product.id,
        })
        self.client.post(reverse('customer:wishlist'), {
            'action': 'toggle',
            'product_id': product.id,
        })

        session = self.client.session
        self.assertEqual(session['guest_cart'][str(product.id)], 1)
        self.assertIn(str(product.id), session['guest_wishlist'])

    def test_guest_can_compare_products(self):
        product = Product.objects.filter(is_active=True).first()
        if product is None:
            self.skipTest('No active product available')

        self.client.post(reverse('customer:compare'), {
            'action': 'toggle',
            'product_id': product.id,
        })

        response = self.client.get(reverse('customer:compare'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(product, response.context['compare_products'])


class CheckoutAddressTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username='checkout-customer',
            password='test-password',
            role='customer',
            first_name='Asha',
            last_name='Kumar',
            phone='9876543210',
        )
        seller_user = User.objects.create_user(
            username='checkout-seller',
            password='test-password',
            role='seller',
        )
        seller = SellerProfile.objects.create(
            user=seller_user,
            store_name='Test Store',
            store_slug='test-store',
            phone='9876543211',
            email='seller@example.com',
            business_address='Test business address',
        )
        category = Category.objects.create(name='Test Category', slug='test-category')
        product = Product.objects.create(
            seller=seller,
            title='Test Product',
            slug='test-product',
            category=category,
            sku='CHECKOUT-TEST-001',
            item_code='CHECKOUT-ITEM-001',
            description='Product used by checkout tests.',
            base_price=100,
            selling_price=100,
        )
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        self.client.force_login(self.customer)

    def test_product_search_matches_prefixed_item_code(self):
        response = self.client.get(reverse('customer:products'), {'q': 'CODE: CHECKOUT-ITEM-001'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Product')

    def test_wishlist_toggle_returns_json_without_redirect(self):
        product = Product.objects.get(item_code='CHECKOUT-ITEM-001')

        response = self.client.post(
            reverse('customer:wishlist'),
            {'action': 'toggle', 'product_id': product.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': True, 'added': True})
        self.assertTrue(WishlistItem.objects.filter(wishlist__user=self.customer, product=product).exists())

        response = self.client.post(
            reverse('customer:wishlist'),
            {'action': 'toggle', 'product_id': product.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.json(), {'success': True, 'added': False})
        self.assertFalse(WishlistItem.objects.filter(wishlist__user=self.customer, product=product).exists())

    def test_guest_ajax_wishlist_can_add_and_remove(self):
        guest_client = Client()
        product = Product.objects.get(item_code='CHECKOUT-ITEM-001')

        response = guest_client.post(
            reverse('customer:wishlist'),
            {'action': 'toggle', 'product_id': product.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.json(), {'success': True, 'added': True})
        self.assertIn(str(product.id), guest_client.session['guest_wishlist'])

        response = guest_client.post(
            reverse('customer:wishlist'),
            {'action': 'toggle', 'product_id': product.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.json(), {'success': True, 'added': False})
        self.assertNotIn(str(product.id), guest_client.session['guest_wishlist'])

    def test_search_suggestions_match_sku_and_code_prefix(self):
        response = self.client.get(reverse('customer:search'), {
            'suggestions': '1',
            'q': 'SKU: CHECKOUT-TEST-001',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['item_code'], 'CHECKOUT-ITEM-001')

    def test_database_coupon_applies_to_cart_and_checkout(self):
        Coupon.objects.create(
            code='COPY20',
            description='Test coupon',
            discount_type='flat',
            discount_value=20,
            min_order_amount=100,
            max_discount_amount=100,
            is_active=True,
        )

        cart_response = self.client.get(reverse('customer:cart'), {'coupon': ' copy20 '})
        checkout_response = self.client.get(reverse('customer:checkout'), {'coupon': ' copy20 '})
        coupons_response = self.client.get(reverse('customer:coupons'))

        self.assertEqual(cart_response.context['coupon_discount'], Decimal('20.00'))
        self.assertEqual(checkout_response.context['coupon_discount'], Decimal('20.00'))
        self.assertContains(coupons_response, 'COPY20')
        self.assertContains(coupons_response, 'href="/customer/cart/?coupon=COPY20"')

    def test_customer_sees_seller_offer_savings_on_product_cart_and_checkout(self):
        product = Product.objects.get(item_code='CHECKOUT-ITEM-001')
        Product.objects.filter(id=product.id).update(selling_price=80)
        SellerProductOffer.objects.create(
            product=product,
            title='Weekend Deal',
            discount_type='flat',
            discount_value=20,
            original_price=100,
        )
        CartItem.objects.filter(cart__user=self.customer, product=product).update(quantity=2)

        product_response = self.client.get(reverse('customer:product_detail_view', args=[product.id]))
        listing_response = self.client.get(reverse('customer:products'))
        cart_response = self.client.get(reverse('customer:cart'))
        checkout_response = self.client.get(reverse('customer:checkout'))

        self.assertContains(product_response, 'Weekend Deal: You save ₹20.00')
        self.assertContains(listing_response, 'Weekend Deal: Save ₹20.00')
        self.assertContains(cart_response, 'Weekend Deal: Save ₹20.00 each')
        self.assertContains(cart_response, 'Save ₹40.00')
        self.assertContains(checkout_response, 'Weekend Deal: Save ₹20.00 each')
        self.assertContains(checkout_response, '₹40.00')
        self.assertEqual(cart_response.context['seller_offer_discount'], Decimal('40.00'))
        self.assertEqual(checkout_response.context['seller_offer_discount'], Decimal('40.00'))

    def test_product_detail_cart_actions_stay_in_place_and_respect_stock(self):
        product = Product.objects.get(item_code='CHECKOUT-ITEM-001')
        product.stock = 3
        product.save(update_fields=['stock'])
        cart_item = CartItem.objects.filter(cart__user=self.customer, product=product).first()
        if cart_item:
            cart_item.delete()

        headers = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        add_response = self.client.post(reverse('customer:cart'), {
            'action': 'add',
            'product_id': product.id,
        }, **headers)
        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(add_response.json()['quantity'], 1)
        self.assertEqual(CartItem.objects.get(cart__user=self.customer, product=product).quantity, 1)

        update_response = self.client.post(reverse('customer:cart'), {
            'action': 'update_qty',
            'product_id': product.id,
            'quantity': '9',
        }, **headers)
        self.assertEqual(update_response.json()['quantity'], 3)
        self.assertEqual(CartItem.objects.get(cart__user=self.customer, product=product).quantity, 3)

        limit_response = self.client.post(reverse('customer:cart'), {
            'action': 'add',
            'product_id': product.id,
        }, **headers)
        self.assertEqual(limit_response.status_code, 409)

        listing_response = self.client.get(reverse('customer:products'))
        self.assertContains(listing_response, 'class="ajax-cart-form"')
        self.assertContains(listing_response, 'data-stock="3" data-quantity="3"')
        self.assertContains(listing_response, 'data-cart-increment')

        product_response = self.client.get(reverse('customer:product_detail_view', args=[product.id]))
        self.assertEqual(product_response.context['cart_quantity'], 3)
        self.assertNotContains(product_response, 'productCartForm')
        self.assertContains(product_response, 'class="ajax-cart-form"')
        self.assertContains(product_response, 'class="detail-cart-stepper"')
        self.assertContains(product_response, 'data-quantity="3"')
        self.assertContains(product_response, 'data-i18n="add_to_cart">Add to Cart</span>')

        CartItem.objects.filter(cart__user=self.customer, product=product).delete()
        redirect_response = self.client.post(reverse('customer:cart'), {
            'action': 'add',
            'product_id': product.id,
        })
        self.assertRedirects(redirect_response, reverse('customer:cart'))

        Review.objects.create(
            product=product,
            customer=self.customer,
            rating=5,
            title='Long review',
            comment='a' * 600,
            photo_url_1='/media/review-1.png',
            photo_url_2='/media/review-2.png',
            photo_url_3='/media/review-3.png',
        )
        product_response = self.client.get(reverse('customer:product_detail_view', args=[product.id]))
        self.assertContains(product_response, 'class="product-review-comment"')
        self.assertContains(product_response, 'overflow-wrap: anywhere;')
        self.assertContains(product_response, 'alt="Customer review photo 1"')
        self.assertContains(product_response, 'alt="Customer review photo 2"')
        self.assertContains(product_response, 'alt="Customer review photo 3"')

    def test_checkout_explains_coupon_minimum(self):
        Coupon.objects.create(
            code='MIN150',
            description='Minimum order test',
            discount_type='flat',
            discount_value=20,
            min_order_amount=150,
            max_discount_amount=100,
            is_active=True,
        )

        response = self.client.get(reverse('customer:checkout'), {'coupon': 'MIN150'})

        self.assertEqual(response.context['coupon_discount'], Decimal('0.00'))
        self.assertContains(response, 'This coupon requires a minimum cart total of ₹150.00.')

    def test_checkout_keeps_new_address_form_hidden_until_selected(self):
        response = self.client.get(reverse('customer:checkout'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add a new delivery address')
        self.assertContains(response, 'id="checkoutNewAddressFields" class="checkout-address-fields" hidden')
        self.assertContains(response, 'style="display: none; grid-template-columns: repeat(2, minmax(0, 1fr));')
        self.assertContains(response, 'id="checkoutPaymentSection" class="glass-card" style="padding: 24px;"')
        self.assertNotContains(response, 'Connaught Place, New Delhi')

    def test_checkout_can_save_address_without_placing_order(self):
        response = self.client.post(reverse('customer:checkout'), {
            'checkout_action': 'save_address',
            'address_id': 'new',
            'new_full_name': 'Asha Kumar',
            'new_phone': '9876543210',
            'new_street_address': '12 Market Road',
            'new_city': 'Patna',
            'new_state': 'Bihar',
            'new_pincode': '800001',
            'new_address_type': 'home',
        })

        self.assertEqual(response.status_code, 302)
        self.assertIn('#deliveryAddress', response.url)
        self.assertTrue(Address.objects.filter(user=self.customer, pincode='800001').exists())
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())

        checkout_response = self.client.get(reverse('customer:checkout'))
        self.assertContains(checkout_response, 'id="checkoutPaymentSection" class="glass-card" style="padding: 24px;"')
        self.assertNotContains(checkout_response, 'name="address_id" value="1" checked')

    def test_checkout_saves_and_uses_new_delivery_address(self):
        response = self.client.post(reverse('customer:checkout'), {
            'address_id': 'new',
            'new_full_name': 'Asha Kumar',
            'new_phone': '9876543210',
            'new_street_address': '12 Market Road',
            'new_city': 'Patna',
            'new_state': 'Bihar',
            'new_pincode': '800001',
            'new_address_type': 'home',
            'payment_method': 'cod',
        })

        self.assertEqual(response.status_code, 302)
        address = Address.objects.get(user=self.customer)
        order = Order.objects.get(customer=self.customer)
        self.assertEqual(address.pincode, '800001')
        self.assertEqual(order.shipping_address, '12 Market Road, Patna, Bihar - 800001')

    def test_checkout_rejects_missing_address_instead_of_using_a_default(self):
        response = self.client.post(reverse('customer:checkout'), {
            'payment_method': 'cod',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select a saved delivery address or add a new one.')
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())

    def test_review_submission_is_saved_and_confirmation_is_visible(self):
        order = Order.objects.create(
            order_number='ORD-REVIEW-DELIVERED',
            customer=self.customer,
            seller=Product.objects.get(item_code='CHECKOUT-ITEM-001').seller,
            status='delivered',
            shipping_address='12 Market Road, Patna, Bihar - 800001',
        )
        product = Product.objects.get(item_code='CHECKOUT-ITEM-001')
        from orders.models import OrderItem
        OrderItem.objects.create(order=order, product=product, quantity=1, unit_price=100, total_price=100)

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(reverse('customer:reviews'), {
                'product_id': product.id,
                'rating': '5',
                'title': 'Great product',
                'comment': 'Works exactly as expected.',
                'review_photos': [
                    SimpleUploadedFile('review-1.png', b'photo-one', content_type='image/png'),
                    SimpleUploadedFile('review-2.png', b'photo-two', content_type='image/png'),
                    SimpleUploadedFile('review-3.png', b'photo-three', content_type='image/png'),
                ],
            }, follow=True)

        review = Review.objects.get(customer=self.customer, product=product)
        product.refresh_from_db()
        self.assertContains(response, 'Your review for Test Product was submitted successfully.')
        self.assertContains(response, 'Great product')
        self.assertEqual(product.total_reviews_count, 1)
        self.assertEqual(float(product.average_rating), 5.0)
        self.assertEqual(review.order, order)
        self.assertTrue(review.photo_url_1)
        self.assertTrue(review.photo_url_2)
        self.assertTrue(review.photo_url_3)
        self.assertContains(response, 'alt="Review photo 1"')
        self.assertContains(response, 'alt="Review photo 2"')
        self.assertContains(response, 'alt="Review photo 3"')
        self.assertContains(response, 'Edit')
        self.assertContains(response, 'Delete')

        edit_response = self.client.get(reverse('customer:reviews'), {'edit': review.id})
        self.assertContains(edit_response, 'Edit Product Review')
        self.assertContains(edit_response, f'name="review_id" value="{review.id}"')
        self.assertContains(edit_response, 'value="Great product"')
        self.assertContains(edit_response, 'alt="Existing review photo 1"')
        self.assertContains(edit_response, 'alt="Existing review photo 2"')
        self.assertContains(edit_response, 'alt="Existing review photo 3"')
        self.assertContains(edit_response, 'data-remove-photo-slot="2"')

        seller_user = product.seller.user
        review_notification = Notification.objects.get(user=seller_user, title='New product review received')
        self.assertIn('Great product', review_notification.message)
        self.assertEqual(review_notification.link, '/seller/reviews/')

        review_notification.delete()
        self.client.post(reverse('customer:reviews'), {
            'review_id': review.id,
            'product_id': product.id,
            'rating': '4',
            'title': 'Updated review',
            'comment': 'Updated after more use.',
            'remove_photo_slots': ['2'],
        }, follow=True)
        review.refresh_from_db()
        self.assertTrue(review.photo_url_1)
        self.assertEqual(review.photo_url_2, '')
        self.assertTrue(review.photo_url_3)
        updated_notification = Notification.objects.get(user=seller_user, title='New product review received')
        self.assertIn('Updated review', updated_notification.message)
        self.assertIn('4/5', updated_notification.message)

        self.client.force_login(seller_user)
        seller_notifications_response = self.client.get(reverse('seller:notifications'))
        self.assertContains(seller_notifications_response, 'New product review received')
        self.assertContains(seller_notifications_response, 'href="/seller/reviews/"')

        other_customer = User.objects.create_user(username='review-not-owner', password='test-password', role='customer')
        self.client.force_login(other_customer)
        self.assertEqual(self.client.post(reverse('customer:reviews'), {
            'action': 'delete_review',
            'review_id': review.id,
        }).status_code, 404)
        self.assertTrue(Review.objects.filter(pk=review.pk).exists())

        self.client.force_login(self.customer)
        delete_response = self.client.post(reverse('customer:reviews'), {
            'action': 'delete_review',
            'review_id': review.id,
        })
        self.assertRedirects(delete_response, reverse('customer:reviews'))
        self.assertFalse(Review.objects.filter(pk=review.pk).exists())
        product.refresh_from_db()
        self.assertEqual(product.total_reviews_count, 0)
        self.assertEqual(float(product.average_rating), 0.0)

    def test_my_orders_tracks_the_selected_customers_order(self):
        product = Product.objects.get(item_code='CHECKOUT-ITEM-001')
        order = Order.objects.create(
            order_number='ORD-TRACK-OWN',
            customer=self.customer,
            seller=product.seller,
            shipping_address='12 Market Road, Patna, Bihar - 800001',
            tracking_id='TRACK-OWN-001',
            estimated_delivery=timezone.now() + timedelta(days=2),
        )
        other_customer = User.objects.create_user(
            username='other-customer',
            password='test-password',
            role='customer',
        )
        other_order = Order.objects.create(
            order_number='ORD-TRACK-OTHER',
            customer=other_customer,
            seller=product.seller,
            shipping_address='Other address',
        )

        orders_response = self.client.get(reverse('customer:orders'))
        self.assertContains(orders_response, f'href="/customer/orders/{order.id}/track/"')

        tracking_response = self.client.get(reverse('customer:track_order', args=[order.id]))
        self.assertEqual(tracking_response.status_code, 200)
        self.assertEqual(tracking_response.context['order'], order)
        self.assertEqual(tracking_response.context['order'].tracking_id, 'TRACK-OWN-001')
        self.assertContains(
            tracking_response,
            f'Estimated Delivery {order.estimated_delivery.strftime("%d %b %Y")}',
        )
        OrderTimeline.objects.create(
            order=order,
            status=order.status,
            title='Delivery Rescheduled',
            description='New estimate: 28 Sep 2026. Reason: Customer requested a later date',
        )
        OrderTimeline.objects.create(
            order=order,
            status=order.status,
            title='Delivery Rescheduled',
            description='New estimate: 29 Sep 2026. Reason: Latest customer request',
        )
        tracking_response = self.client.get(reverse('customer:track_order', args=[order.id]))
        self.assertContains(tracking_response, 'Delivery Rescheduled')
        self.assertContains(tracking_response, 'Latest customer request')
        self.assertNotContains(tracking_response, 'Customer requested a later date')
        self.assertEqual(tracking_response.content.decode().count('Delivery Rescheduled'), 1)

        other_tracking_response = self.client.get(reverse('customer:track_order', args=[other_order.id]))
        self.assertEqual(other_tracking_response.status_code, 404)

    def test_order_history_filters_by_month_and_year(self):
        product = Product.objects.get(item_code='CHECKOUT-ITEM-001')
        orders = []
        for order_number in ['ORD-FILTER-MAR-2025', 'ORD-FILTER-APR-2025', 'ORD-FILTER-MAR-2024']:
            orders.append(Order.objects.create(
                order_number=order_number,
                customer=self.customer,
                seller=product.seller,
                shipping_address='Filter test address',
            ))

        for order, date in zip(orders, [datetime(2025, 3, 15, 12), datetime(2025, 4, 15, 12), datetime(2024, 3, 15, 12)]):
            Order.objects.filter(pk=order.pk).update(created_at=timezone.make_aware(date))

        response = self.client.get(reverse('customer:orders'), {'year': '2025', 'month': '3'})

        self.assertEqual(list(response.context['orders'].values_list('order_number', flat=True)), ['ORD-FILTER-MAR-2025'])
        self.assertContains(response, 'name="year"')
        self.assertContains(response, 'name="month"')

    def test_customer_can_delete_selected_notifications_only(self):
        own_notification = Notification.objects.create(
            user=self.customer,
            title='Own alert',
            message='Delete this selected alert.',
        )
        other_user = User.objects.create_user(username='notification-owner-other', password='test-password', role='customer')
        other_notification = Notification.objects.create(
            user=other_user,
            title='Other alert',
            message='Keep this alert private.',
        )

        response = self.client.get(reverse('customer:notifications'))
        self.assertContains(response, 'data-select-all')
        self.assertContains(response, 'data-delete-mode')
        response = self.client.post(reverse('customer:notifications'), {
            'action': 'delete_selected',
            'notification_ids': [own_notification.id, other_notification.id],
        })

        self.assertRedirects(response, reverse('customer:notifications'))
        self.assertFalse(Notification.objects.filter(pk=own_notification.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=other_notification.pk).exists())

    def test_order_creation_and_status_updates_create_notifications(self):
        product = Product.objects.get(item_code='CHECKOUT-ITEM-001')
        rider_user = User.objects.create_user(
            username='order-notify-rider',
            password='test-password',
            role='delivery',
        )
        rider = DeliveryPartnerProfile.objects.create(
            user=rider_user,
            vehicle_number='ORDER-NOTIFY-123',
            driving_license_no='ORDER-NOTIFY-LICENSE',
        )
        order = Order.objects.create(
            order_number='ORD-NOTIFY-001',
            customer=self.customer,
            seller=product.seller,
            delivery_partner=rider,
            shipping_address='12 Market Road, Patna, Bihar - 800001',
        )

        customer_notification = Notification.objects.get(
            user=self.customer,
            title='Order confirmed',
            link=f'/customer/orders/{order.id}/track/',
        )
        seller_notification = Notification.objects.get(user=product.seller.user, link='/seller/orders/')
        self.assertIn(order.order_number, customer_notification.message)
        self.assertIn(order.order_number, seller_notification.message)

        notifications_response = self.client.get(reverse('customer:notifications'))
        self.assertContains(notifications_response, 'Open')
        self.assertContains(notifications_response, f'href="/customer/orders/{order.id}/track/"')

        self.client.force_login(product.seller.user)
        seller_response = self.client.get(reverse('seller:notifications'))
        self.assertContains(seller_response, 'New order received')
        self.assertContains(seller_response, 'Open')
        self.assertContains(seller_response, 'href="/seller/orders/"')

        self.client.force_login(rider_user)
        rider_response = self.client.get(reverse('delivery:notifications'))
        self.assertContains(rider_response, 'Delivery assigned')
        self.assertContains(rider_response, f'href="/delivery/active-delivery/{order.id}/"')

        self.client.force_login(self.customer)

        order.status = 'shipped'
        order.save(update_fields=['status'])
        status_notification = Notification.objects.filter(
            user=self.customer,
            link=f'/customer/orders/{order.id}/track/',
        ).first()
        self.assertEqual(status_notification.title, 'Order status updated')
        self.assertIn('Shipped', status_notification.message)

        orders_response = self.client.get(reverse('customer:orders'))
        self.assertContains(orders_response, 'aria-label="3 unread notifications"')

    def test_delivery_rating_submission_notifies_rider_for_existing_rating(self):
        rider_user = User.objects.create_user(
            username='rating-notify-rider',
            password='test-password',
            role='delivery',
        )
        rider = DeliveryPartnerProfile.objects.create(
            user=rider_user,
            vehicle_number='RATING-123',
            driving_license_no='RATING-LICENSE',
        )
        order = Order.objects.create(
            order_number='ORD-RATING-NOTIFY',
            customer=self.customer,
            seller=Product.objects.get(item_code='CHECKOUT-ITEM-001').seller,
            status='delivered',
            delivery_partner=rider,
            shipping_address='Rating delivery address',
        )
        rating = DeliveryRating.objects.create(
            order=order,
            customer=self.customer,
            delivery_partner=rider,
            rating=3,
            comment='Initial feedback',
        )
        Notification.objects.filter(user=rider_user).delete()

        response = self.client.post(reverse('customer:track_order', args=[order.id]), {
            'action': 'rate_delivery',
            'rating': '5',
            'comment': 'Updated feedback',
        })

        self.assertEqual(response.status_code, 302)
        rating.refresh_from_db()
        self.assertEqual(rating.rating, 5)
        rider_notification = Notification.objects.get(user=rider_user)
        self.assertIn('5/5', rider_notification.message)

        self.client.force_login(rider_user)
        response = self.client.get(reverse('delivery:notifications'))
        self.assertContains(response, 'New delivery rating received')
        self.assertContains(response, '/delivery/ratings/')

    def test_cod_payment_transaction_becomes_success_after_delivery_otp(self):
        product = Product.objects.get(item_code='CHECKOUT-ITEM-001')
        rider_user = User.objects.create_user(
            username='delivery-rider',
            password='test-password',
            role='delivery',
        )
        rider = DeliveryPartnerProfile.objects.create(
            user=rider_user,
            vehicle_number='TEST-123',
            driving_license_no='TEST-LICENSE',
        )
        order = Order.objects.create(
            order_number='ORD-COD-PENDING',
            customer=self.customer,
            seller=product.seller,
            delivery_partner=rider,
            status='out_for_delivery',
            payment_method='cod',
            payment_status='pending',
            delivery_otp='4321',
            shipping_address='12 Market Road, Patna, Bihar - 800001',
        )
        transaction = PaymentTransaction.objects.create(
            order=order,
            transaction_id='TXN-COD-PENDING',
            amount=100,
            payment_method='COD',
            status='pending',
        )
        delivery_client = Client()
        delivery_client.force_login(rider_user)

        response = delivery_client.post(reverse('delivery:active_delivery_details', args=[order.id]), {
            'order_id': order.id,
            'action': 'verify_otp_deliver',
            'entered_otp': '4321',
        })

        self.assertEqual(response.status_code, 302)
        transaction.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(transaction.status, 'success')
        self.assertEqual(order.payment_status, 'paid')

    def test_return_proof_photo_is_saved_as_file_not_base64_text(self):
        product = Product.objects.get(item_code='CHECKOUT-ITEM-001')
        order = Order.objects.create(
            order_number='ORD-RETURN-PHOTO',
            customer=self.customer,
            seller=product.seller,
            status='delivered',
            payment_status='paid',
            shipping_address='12 Market Road, Patna, Bihar - 800001',
        )
        proof = SimpleUploadedFile('proof.png', b'\x89PNG\r\n\x1a\nimage-bytes', content_type='image/png')

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(reverse('customer:returns'), {
                'order_number': order.order_number,
                'request_type': 'return',
                'reason': 'defective',
                'details': 'The item does not work.',
                'proof_photo': proof,
            })

            self.assertEqual(response.status_code, 302)
            return_request = ReturnRequest.objects.get(order=order)
            self.assertTrue(return_request.photo_url)
            self.assertLess(len(return_request.photo_url), 500)

    def test_customer_profile_starts_read_only_and_saves_only_in_edit_mode(self):
        url = reverse('customer:profile')
        response = self.client.get(url)
        self.assertContains(response, 'Edit Profile')
        self.assertContains(response, 'Reset Password')
        self.assertContains(response, 'id="customerProfileEditPanel" class="glass-card"')
        self.assertContains(response, 'margin: 40px auto; padding: 32px;')
        self.assertContains(response, 'id="customerPasswordPanel" style="display: none;')
        self.assertContains(response, 'Member Since')
        self.assertContains(response, 'My Referral Code')
        self.assertContains(response, 'Wallet Balance')
        self.assertContains(response, 'Reward Points')
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.referral_code.startswith('REF-'))
        self.assertContains(response, self.customer.referral_code)

        edit_response = self.client.get(url, {'show': 'edit'})
        self.assertContains(edit_response, 'id="customerProfileEditPanel" class="glass-card"')
        self.assertContains(edit_response, 'style="display: block; max-width: 800px; margin: 40px auto; padding: 32px;"')
        self.assertContains(edit_response, 'name="phone"')
        self.assertContains(edit_response, 'Referral Code')
        self.assertContains(edit_response, 'max-width: 800px; margin: 40px auto; padding: 32px;')

        save_response = self.client.post(url, {
            'action': 'save_profile',
            'first_name': 'Updated',
            'last_name': 'Customer',
            'phone': '9876500000',
        })
        self.assertRedirects(save_response, url)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, 'Updated')
        self.assertEqual(self.customer.phone, '9876500000')
