from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from commissions.models import CommissionLog
from delivery.models import DeliveryPartnerProfile
from orders.models import Order, OrderItem
from products.models import Product
from returns.models import ReturnRequest
from returns.services import (
	ReturnValidationError,
	approve_request,
	create_replacement,
	create_return_request,
	fallback_replacement_to_wallet_refund,
	inspect_return,
	mark_picked_up,
	process_return_refund,
	schedule_pickup,
)
from sellers.models import SellerProfile
from users.models import User


class ReturnReplacementServiceTests(TestCase):
	def setUp(self):
		self.customer = User.objects.create_user(username='return-customer', password='pass', role='customer')
		seller_user = User.objects.create_user(username='return-seller', password='pass', role='seller')
		self.seller = SellerProfile.objects.create(
			user=seller_user, store_name='Return Store', store_slug='return-store',
			phone='9999999999', email='seller@example.com', business_address='Street',
		)
		self.product = Product.objects.create(
			seller=self.seller, title='Return Product', slug='return-product', sku='RET-SKU',
			item_code='RET-ITEM', description='Test product', base_price=Decimal('80.00'),
			selling_price=Decimal('100.00'), mrp=Decimal('120.00'), stock=5,
		)
		self.order = Order.objects.create(
			order_number='RET-ORDER-1', customer=self.customer, seller=self.seller,
			status='delivered', payment_status='paid', payment_method='wallet',
			shipping_address='Customer address', subtotal=Decimal('200.00'),
			grand_total=Decimal('200.00'), delivered_at=timezone.now(),
		)
		self.item = OrderItem.objects.create(
			order=self.order, product=self.product, quantity=2,
			unit_price=Decimal('100.00'), total_price=Decimal('200.00'),
		)

	def make_request(self, request_type='return', quantity=1):
		return create_return_request(
			customer=self.customer, order_id=self.order.id, order_item_id=self.item.id,
			quantity=quantity, request_type=request_type, reason='defective',
			details='The product is not working.',
		)

	def test_policy_window_and_duplicate_quantity_are_enforced(self):
		self.make_request(quantity=1)
		with self.assertRaises(ReturnValidationError):
			self.make_request(quantity=2)
		with self.assertRaises(ReturnValidationError):
			self.make_request(request_type='replace', quantity=2)

		self.order.delivered_at = timezone.now() - timedelta(days=8)
		self.order.save(update_fields=['delivered_at'])
		with self.assertRaises(ReturnValidationError):
			self.make_request()

	def test_completed_return_quantity_cannot_be_requested_again(self):
		self.item.quantity = 1
		self.item.total_price = Decimal('100.00')
		self.item.save(update_fields=['quantity', 'total_price'])
		request = self.make_request()
		request.status = 'refund_processed'
		request.save(update_fields=['status'])

		with self.assertRaises(ReturnValidationError):
			self.make_request(request_type='replace')

	def test_delivery_partner_gets_return_pickup_fee_charged_to_seller(self):
		rider_user = User.objects.create_user(username='return-rider', password='pass', role='delivery')
		rider = DeliveryPartnerProfile.objects.create(
			user=rider_user, vehicle_number='RET-50', driving_license_no='RET-LIC',
		)
		self.order.seller_net_earnings = Decimal('150.00')
		self.order.save(update_fields=['seller_net_earnings'])
		commission = CommissionLog.objects.create(
			order=self.order, order_total=Decimal('200.00'),
			admin_commission_amount=Decimal('20.00'),
			seller_payout_amount=Decimal('150.00'),
			delivery_payout_amount=Decimal('50.00'),
		)
		request = self.make_request()
		approve_request(request.id)
		schedule_pickup(request.id, pickup_partner=rider)

		mark_picked_up(request.id, pickup_partner=rider)

		request.refresh_from_db()
		self.order.refresh_from_db()
		commission.refresh_from_db()
		self.assertEqual(request.pickup_earning, Decimal('50.00'))
		self.assertEqual(self.order.seller_net_earnings, Decimal('100.00'))
		self.assertEqual(commission.seller_payout_amount, Decimal('100.00'))
		self.assertEqual(commission.delivery_payout_amount, Decimal('100.00'))

	def test_partial_return_refunds_only_item_quantity_after_inspection(self):
		request = self.make_request()
		approve_request(request.id)
		mark_picked_up(request.id)
		inspect_return(request.id, passed=True)
		starting_wallet = Decimal(str(self.customer.wallet_balance))

		processed, amount = process_return_refund(request.id)

		self.assertTrue(processed)
		self.assertEqual(amount, Decimal('100.00'))
		self.assertEqual(ReturnRequest.objects.get(id=request.id).status, 'refund_processed')
		self.assertEqual(User.objects.get(id=self.customer.id).wallet_balance, starting_wallet + amount)
		self.assertEqual(Product.objects.get(id=self.product.id).stock, 6)
		self.assertEqual(Order.objects.get(id=self.order.id).payment_status, 'paid')

	def test_manual_pickup_schedule_creates_reference_before_confirmation(self):
		request = self.make_request()
		approve_request(request.id)
		schedule_pickup(request.id, tracking_id='MANUAL-PICKUP-1')

		request.refresh_from_db()
		self.assertEqual(request.status, 'pickup_scheduled')
		self.assertEqual(request.pickup_tracking_id, 'MANUAL-PICKUP-1')

	def test_failed_replacement_converts_to_wallet_refund(self):
		request = self.make_request(request_type='replace')
		approve_request(request.id)
		mark_picked_up(request.id)
		inspect_return(request.id, passed=True)
		self.product.stock = 0
		self.product.save(update_fields=['stock'])
		self.assertIsNone(create_replacement(request.id))

		starting_wallet = Decimal(str(self.customer.wallet_balance))
		fallback_replacement_to_wallet_refund(request.id)

		request.refresh_from_db()
		self.assertEqual(request.status, 'refund_processed')
		self.assertEqual(request.refund_method, 'wallet')
		self.assertEqual(request.refund_amount, Decimal('100.00'))
		self.assertEqual(User.objects.get(id=self.customer.id).wallet_balance, starting_wallet + Decimal('100.00'))
		self.assertEqual(Product.objects.get(id=self.product.id).stock, 1)

	def test_replacement_reserves_stock_and_creates_fulfillment_order(self):
		request = self.make_request(request_type='replace')
		approve_request(request.id)
		mark_picked_up(request.id)
		inspect_return(request.id, passed=True)

		replacement = create_replacement(request.id)

		request.refresh_from_db()
		self.assertEqual(request.status, 'replacement_dispatched')
		self.assertEqual(request.replacement_order_id, replacement.id)
		self.assertEqual(replacement.status, 'packed')
		self.assertEqual(replacement.items.get().quantity, 1)
		self.assertEqual(Product.objects.get(id=self.product.id).stock, 4)
