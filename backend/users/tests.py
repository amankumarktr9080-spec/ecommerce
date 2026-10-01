from django.test import TestCase
from django.urls import reverse

from delivery.models import DeliveryPartnerProfile
from sellers.models import SellerProfile
from users.models import User


class ForgotPasswordTests(TestCase):
	def setUp(self):
		self.email = 'shared@example.com'
		self.customer = User.objects.create_user(
			username='shared_customer', email=self.email, password='cust1234', role='customer'
		)
		self.seller = User.objects.create_user(
			username='shared_seller', email=self.email, password='sell1234', role='seller'
		)
		self.rider = User.objects.create_user(
			username='shared_rider', email=self.email, password='ride1234', role='delivery'
		)

	def test_forgot_password_targets_exact_user_id_and_email(self):
		response = self.client.post(
			reverse('users:forgot_password'),
			{'username': 'shared_seller', 'email': self.email},
		)

		self.assertEqual(response.status_code, 200)
		self.seller.refresh_from_db()
		self.customer.refresh_from_db()
		self.rider.refresh_from_db()
		self.assertTrue(self.seller.reset_token)
		self.assertIsNone(self.customer.reset_token)
		self.assertIsNone(self.rider.reset_token)

	def test_forgot_password_rejects_wrong_user_id_for_shared_email(self):
		response = self.client.post(
			reverse('users:forgot_password'),
			{'username': 'wrong_user', 'email': self.email},
		)

		self.assertEqual(response.status_code, 200)
		self.assertFalse(self.seller.reset_token)
		self.assertFalse(self.customer.reset_token)
		self.assertFalse(self.rider.reset_token)


class SuspendedAccountLoginTests(TestCase):
	def setUp(self):
		self.customer = User.objects.create_user(
			username='suspended_customer', password='SecurePass123', role='customer', is_active=False
		)
		self.seller = User.objects.create_user(
			username='suspended_seller', password='SecurePass123', role='seller'
		)
		SellerProfile.objects.create(
			user=self.seller,
			store_name='Suspended Store',
			store_slug='suspended-store',
			phone='1234567890',
			email='seller@example.com',
			business_address='Test address',
			is_approved=False,
		)
		self.rider = User.objects.create_user(
			username='suspended_rider', password='SecurePass123', role='delivery'
		)
		DeliveryPartnerProfile.objects.create(
			user=self.rider,
			vehicle_number='TEST-123',
			driving_license_no='TEST-LICENSE',
			is_approved=False,
		)

	def test_suspended_customer_cannot_login(self):
		self.assert_suspended_login(self.customer)

	def test_suspended_seller_cannot_login(self):
		self.assert_suspended_login(self.seller)

	def test_suspended_rider_cannot_login(self):
		self.assert_suspended_login(self.rider)

	def test_wrong_password_does_not_reveal_suspension(self):
		response = self.client.post(
			reverse('users:login'),
			{'username': self.customer.username, 'password': 'wrong-password'},
			follow=True,
		)

		self.assertContains(response, 'Invalid username/email or password.')
		self.assertNotContains(response, 'Your account is suspended.')

	def assert_suspended_login(self, user):
		response = self.client.post(
			reverse('users:login'),
			{'username': user.username, 'password': 'SecurePass123'},
			follow=True,
		)

		self.assertContains(response, 'Your account is suspended.')
		self.assertNotIn('_auth_user_id', self.client.session)
