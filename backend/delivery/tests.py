from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import time, timedelta

from commissions.models import CommissionLog
from delivery.models import DeliveryPartnerProfile, DeliveryRating
from notifications.models import Notification
from orders.models import Order, OrderTimeline
from payments.models import PaymentTransaction
from sellers.models import SellerProfile
from users.models import User


class DeliveryActiveDeliveryTests(TestCase):
	def setUp(self):
		self.seller_user = User.objects.create_user(username='request-seller', password='test-password', role='seller')
		self.seller = SellerProfile.objects.create(
			user=self.seller_user,
			store_name='Request Store',
			store_slug='request-store',
			phone='9876543210',
			email='request-store@example.com',
			business_address='Pickup address',
		)
		self.customer = User.objects.create_user(username='request-customer', password='test-password', role='customer')
		rider_user = User.objects.create_user(username='request-rider', password='test-password', role='delivery')
		self.rider = DeliveryPartnerProfile.objects.create(
			user=rider_user,
			vehicle_number='TEST-123',
			driving_license_no='TEST-LICENSE',
		)
		self.client.force_login(rider_user)

	def create_order(self, order_number, status, delivery_partner=None):
		return Order.objects.create(
			order_number=order_number,
			customer=self.customer,
			seller=self.seller,
			status=status,
			delivery_partner=delivery_partner,
			shipping_address='Drop address',
		)

	def test_rider_profile_starts_read_only_and_saves_editable_details(self):
		url = reverse('delivery:profile')
		response = self.client.get(url)
		self.assertContains(response, 'Edit Profile')
		self.assertContains(response, 'Reset Password')
		self.assertContains(response, 'id="deliveryProfileEditPanel" style="display: none;')
		self.assertContains(response, 'id="deliveryPasswordPanel" style="display: none;')

		edit_response = self.client.get(url, {'show': 'edit'})
		self.assertContains(edit_response, 'id="deliveryProfileEditPanel" style="display: block;')

		response = self.client.post(url, {
			'action': 'save_profile',
			'first_name': 'Updated',
			'last_name': 'Rider',
			'phone': '9876500001',
			'vehicle_type': 'scooter',
			'vehicle_number': 'UPDATED-123',
			'address': 'New delivery address',
			'city': 'Patna',
			'state': 'Bihar',
			'pincode': '800001',
		})
		self.assertRedirects(response, url)
		self.rider.refresh_from_db()
		self.rider.user.refresh_from_db()
		self.assertEqual(self.rider.user.first_name, 'Updated')
		self.assertEqual(self.rider.vehicle_type, 'scooter')
		self.assertEqual(self.rider.vehicle_number, 'UPDATED-123')

	def test_active_page_lists_every_order_assigned_to_this_rider(self):
		packed_order = self.create_order('ACTIVE-PACKED', 'packed', self.rider)
		shipped_order = self.create_order('ACTIVE-SHIPPED', 'shipped', self.rider)
		transit_order = self.create_order('ACTIVE-TRANSIT', 'out_for_delivery', self.rider)
		self.create_order('ACTIVE-DONE', 'delivered', self.rider)
		other_user = User.objects.create_user(username='other-rider', password='test-password', role='delivery')
		other_rider = DeliveryPartnerProfile.objects.create(
			user=other_user, vehicle_number='OTHER-123', driving_license_no='OTHER-LICENSE',
		)
		self.create_order('ACTIVE-OTHER-RIDER', 'shipped', other_rider)

		response = self.client.get(reverse('delivery:active_delivery'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			set(response.context['assigned_orders'].values_list('id', flat=True)),
			{packed_order.id, shipped_order.id, transit_order.id},
		)
		self.assertContains(response, 'href="/delivery/active-delivery/%s/"' % packed_order.id)
		self.assertNotContains(response, 'ACTIVE-OTHER-RIDER')

	def test_cancellation_voids_unpaid_cod_and_blocks_paid_orders(self):
		cod_order = self.create_order('CANCEL-COD-UNPAID', 'shipped', self.rider)
		cod_order.payment_method = 'cod'
		cod_order.payment_status = 'pending'
		cod_order.admin_commission_amount = Decimal('10.00')
		cod_order.seller_net_earnings = Decimal('90.00')
		cod_order.save()
		cod_log = CommissionLog.objects.create(
			order=cod_order,
			order_total=Decimal('100.00'),
			admin_commission_amount=Decimal('10.00'),
			seller_payout_amount=Decimal('90.00'),
			delivery_payout_amount=Decimal('0.00'),
			status='pending',
		)
		cod_payment = PaymentTransaction.objects.create(
			order=cod_order,
			transaction_id='CANCEL-COD-TXN',
			amount=Decimal('100.00'),
			payment_method='COD',
			status='pending',
		)
		paid_order = self.create_order('CANCEL-PAID-WALLET', 'shipped', self.rider)
		paid_order.payment_method = 'wallet'
		paid_order.payment_status = 'paid'
		paid_order.save()
		paid_log = CommissionLog.objects.create(
			order=paid_order,
			order_total=Decimal('100.00'),
			admin_commission_amount=Decimal('10.00'),
			seller_payout_amount=Decimal('90.00'),
			delivery_payout_amount=Decimal('0.00'),
			status='pending',
		)
		paid_payment = PaymentTransaction.objects.create(
			order=paid_order,
			transaction_id='CANCEL-PAID-TXN',
			amount=Decimal('100.00'),
			payment_method='WALLET',
			status='success',
		)

		self.client.post(reverse('delivery:active_delivery_details', args=[cod_order.id]), {'action': 'cancel_order'})
		cod_order.refresh_from_db()
		cod_log.refresh_from_db()
		cod_payment.refresh_from_db()
		self.assertEqual(cod_order.status, 'cancelled')
		self.assertEqual(cod_order.admin_commission_amount, Decimal('0.00'))
		self.assertEqual(cod_log.status, 'cancelled')
		self.assertEqual(cod_payment.status, 'cancelled')

		self.client.post(reverse('delivery:active_delivery_details', args=[paid_order.id]), {'action': 'cancel_order'})
		paid_order.refresh_from_db()
		paid_log.refresh_from_db()
		paid_payment.refresh_from_db()
		self.assertEqual(paid_order.status, 'shipped')
		self.assertEqual(paid_log.status, 'pending')
		self.assertEqual(paid_payment.status, 'success')

	def test_topbar_search_filters_riders_assigned_orders(self):
		matched_order = self.create_order('SEARCH-MATCH', 'shipped', self.rider)
		self.create_order('SEARCH-OTHER', 'shipped', self.rider)

		response = self.client.get(reverse('delivery:active_delivery'), {'q': 'SEARCH-MATCH'})

		self.assertEqual(list(response.context['assigned_orders']), [matched_order])
		self.assertContains(response, matched_order.order_number)
		self.assertNotContains(response, 'SEARCH-OTHER')
		self.assertContains(response, 'placeholder="Search assigned orders..."')

		suggestions = self.client.get(reverse('delivery:active_delivery'), {
			'q': 'SEARCH-MATCH',
			'suggestions': '1',
		})
		self.assertEqual(suggestions.json()['results'], [{
			'id': matched_order.id,
			'title': '#SEARCH-MATCH',
			'subtitle': f'{matched_order.customer_name} · {self.seller.store_name} · Shipped',
		}])

	def test_start_opens_order_specific_workflow(self):
		order = self.create_order('DETAIL-SHIPPED', 'shipped', self.rider)

		response = self.client.get(reverse('delivery:active_delivery_details', args=[order.id]))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['order'], order)
		self.assertContains(response, 'id="deliveryCompletionForm"')
		self.assertContains(response, 'id="sigCanvas"')
		self.assertContains(response, 'id="newDeliveryEta" type="date"')
		self.assertContains(response, 'aria-label="Open date calendar"')
		self.assertNotContains(response, 'type="datetime-local"')
		self.assertContains(response, 'href="/delivery/navigation/?order_id=%s"' % order.id)
		self.assertContains(response, 'action="/delivery/active-delivery/%s/"' % order.id)
		self.assertNotContains(response, 'data-i18n="navigation">Navigation</span>')

	def test_navigation_verify_otp_opens_selected_order_completion_page(self):
		first_order = self.create_order('NAV-FIRST', 'out_for_delivery', self.rider)
		selected_order = self.create_order('NAV-SELECTED', 'out_for_delivery', self.rider)

		response = self.client.get(reverse('delivery:navigation'), {'order_id': selected_order.id})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['order'], selected_order)
		self.assertContains(response, 'href="/delivery/active-delivery/%s/"' % selected_order.id)
		self.assertNotContains(response, 'href="/delivery/active-delivery/%s/"' % first_order.id)

	def test_rider_cannot_open_another_riders_delivery(self):
		other_user = User.objects.create_user(username='another-rider', password='test-password', role='delivery')
		other_rider = DeliveryPartnerProfile.objects.create(
			user=other_user, vehicle_number='ANOTHER-123', driving_license_no='ANOTHER-LICENSE',
		)
		order = self.create_order('OTHER-DETAIL', 'shipped', other_rider)

		response = self.client.get(reverse('delivery:active_delivery_details', args=[order.id]))

		self.assertEqual(response.status_code, 404)

	def test_order_detail_requires_the_orders_actual_otp(self):
		order = self.create_order('OTP-DETAIL', 'out_for_delivery', self.rider)
		url = reverse('delivery:active_delivery_details', args=[order.id])

		response = self.client.post(url, {
			'action': 'verify_otp_deliver',
			'entered_otp': '1234',
			'signature_data': 'signature-data',
		})
		self.assertEqual(response.status_code, 200)
		order.refresh_from_db()
		self.assertEqual(order.status, 'out_for_delivery')

		response = self.client.post(url, {
			'action': 'verify_otp_deliver',
			'entered_otp': order.delivery_otp,
			'signature_data': 'signature-data',
		})
		self.assertEqual(response.status_code, 302)
		order.refresh_from_db()
		self.assertEqual(order.status, 'delivered')
		self.assertEqual(order.customer_signature, 'signature-data')

	def test_reschedule_saves_selected_eta_reason_and_notifies_customer(self):
		order = self.create_order('RESCHEDULE-ORDER', 'shipped', self.rider)
		requested_date = timezone.localdate() + timedelta(days=3)
		url = reverse('delivery:active_delivery_details', args=[order.id])

		response = self.client.post(url, {
			'action': 'reschedule_order',
			'estimated_delivery': requested_date.strftime('%Y-%m-%d'),
			'reschedule_reason': 'Customer requested a later time',
		})

		self.assertRedirects(response, reverse('delivery:active_delivery'))
		order.refresh_from_db()
		self.assertEqual(timezone.localtime(order.estimated_delivery).date(), requested_date)
		self.assertEqual(timezone.localtime(order.estimated_delivery).time(), time(16, 30))
		event = order.timeline.get(title='Delivery Rescheduled')
		self.assertIn('Customer requested a later time', event.description)
		notification = Notification.objects.get(
			user=self.customer,
			title='Delivery date updated',
			link=f'/customer/orders/{order.id}/track/',
		)
		self.assertIn(requested_date.strftime('%d %b %Y'), notification.message)

	def test_reschedule_rejects_past_datetime(self):
		order = self.create_order('RESCHEDULE-PAST', 'shipped', self.rider)
		url = reverse('delivery:active_delivery_details', args=[order.id])

		response = self.client.post(url, {
			'action': 'reschedule_order',
			'estimated_delivery': '2020-01-01T10:00',
			'reschedule_reason': 'Traffic delay',
		})

		self.assertEqual(response.status_code, 200)
		order.refresh_from_db()
		self.assertIsNone(order.estimated_delivery)
		self.assertFalse(Notification.objects.filter(user=self.customer, title='Delivery date updated').exists())

	def test_ratings_page_uses_real_ratings_delivery_times_and_otp_events(self):
		now = timezone.now()
		on_time_order = self.create_order('METRIC-ON-TIME', 'delivered', self.rider)
		on_time_order.estimated_delivery = now + timedelta(days=1)
		on_time_order.save(update_fields=['estimated_delivery'])
		late_order = self.create_order('METRIC-LATE', 'delivered', self.rider)
		late_order.estimated_delivery = now - timedelta(days=1)
		late_order.save(update_fields=['estimated_delivery'])
		for order, description in (
			(on_time_order, 'Verified with OTP 1234 and customer digital signature.'),
			(late_order, 'Delivered without an OTP verification record.'),
		):
			OrderTimeline.objects.create(
				order=order,
				status='delivered',
				title='Delivered Successfully',
				description=description,
			)
		DeliveryRating.objects.create(order=on_time_order, customer=self.customer, delivery_partner=self.rider, rating=5)
		DeliveryRating.objects.create(order=late_order, customer=self.customer, delivery_partner=self.rider, rating=3)

		response = self.client.get(reverse('delivery:ratings'))

		self.assertEqual(response.context['average_rating'], Decimal('4.0'))
		self.assertEqual(response.context['on_time_rate'], 50.0)
		self.assertEqual(response.context['otp_rate'], 50.0)
		self.assertContains(response, '50.0%')
		self.assertContains(response, '1 of 2 deliveries met ETA')
		self.assertNotContains(response, 'Top 5% Fleet Performer')

	def test_notifications_page_shows_only_rider_notifications_until_marked_read(self):
		rider_notification = Notification.objects.create(
			user=self.rider.user,
			title='Delivery assigned',
			message='Order #RIDER-NOTICE is assigned to you.',
			notification_type='delivery',
			link='/delivery/active-delivery/1/',
		)
		other_notification = Notification.objects.create(
			user=self.customer,
			title='Customer-only notice',
			message='This belongs to another account.',
		)

		response = self.client.get(reverse('delivery:notifications'))

		self.assertContains(response, rider_notification.title)
		self.assertContains(response, rider_notification.message)
		self.assertContains(response, rider_notification.link)
		self.assertNotContains(response, 'Customer-only notice')
		rider_notification.refresh_from_db()
		self.assertFalse(rider_notification.is_read)

		response = self.client.post(reverse('delivery:notifications'), {'action': 'mark_all_read'})
		self.assertRedirects(response, reverse('delivery:notifications'))
		rider_notification.refresh_from_db()
		self.assertTrue(rider_notification.is_read)

		response = self.client.post(reverse('delivery:notifications'), {
			'action': 'delete_selected',
			'notification_ids': [rider_notification.id, other_notification.id],
		})
		self.assertRedirects(response, reverse('delivery:notifications'))
		self.assertFalse(Notification.objects.filter(pk=rider_notification.pk).exists())
		self.assertTrue(Notification.objects.filter(pk=other_notification.pk).exists())

	def test_dashboard_kpis_use_actual_completed_orders_and_ratings(self):
		order = self.create_order('DASHBOARD-REAL-KPI', 'delivered', self.rider)
		order.delivery_partner_earning = Decimal('75.00')
		order.save(update_fields=['delivery_partner_earning'])
		OrderTimeline.objects.create(
			order=order,
			status='delivered',
			title='Delivered Successfully',
			description='Verified with OTP 9876.',
		)
		DeliveryRating.objects.create(
			order=order,
			customer=self.customer,
			delivery_partner=self.rider,
			rating=5,
		)

		response = self.client.get(reverse('delivery:dashboard'))

		self.assertEqual(response.context['today_deliveries'], 1)
		self.assertEqual(response.context['today_earnings'], Decimal('75.00'))
		self.assertEqual(response.context['total_deliveries'], 1)
		self.assertEqual(response.context['total_earnings'], Decimal('75.00'))
		self.assertEqual(response.context['week_deliveries'], 1)
		self.assertEqual(response.context['week_earnings'], Decimal('75.00'))
		self.assertEqual(response.context['average_rating'], 5.0)

	def test_bank_details_can_be_added_then_edited(self):
		url = reverse('delivery:bank')
		response = self.client.get(url)
		self.assertContains(response, 'Add Bank Details')
		self.assertNotContains(response, 'HDFC Bank')
		self.assertNotContains(response, '50100234567890')

		response = self.client.post(url, {
			'bank_name': 'Test Bank',
			'account_number': '1234567890',
			'ifsc_code': 'test0001234',
			'upi_id': 'rider@testbank',
		})
		self.assertRedirects(response, url)
		self.rider.refresh_from_db()
		self.assertEqual(self.rider.ifsc_code, 'TEST0001234')

		response = self.client.get(url)
		self.assertContains(response, 'Edit Bank Details')
		self.assertContains(response, '****7890')
		self.assertNotContains(response, 'value="1234567890"')

		response = self.client.get(url, {'edit': '1'})
		self.assertContains(response, 'value="1234567890"')
		self.assertContains(response, 'value="TEST0001234"')
