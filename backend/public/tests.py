from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from sellers.models import SellerRegistrationApplication
from delivery.models import DeliveryPartnerApplication
from categories.models import Category
from users.models import User


class MerchantOnboardingTests(TestCase):
    def test_username_availability_detects_existing_user(self):
        User.objects.create_user(username='existing_user', password='Pass12345')

        response = self.client.get(
            reverse('public:username_availability'),
            {'username': 'EXISTING_USER'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['available'])

    def test_username_availability_accepts_new_user_id(self):
        response = self.client.get(
            reverse('public:username_availability'),
            {'username': 'new_user_id'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['available'])

    def test_seller_registration_creates_pending_application(self):
        response = self.client.post(
            reverse('public:seller_register'),
            {
                'full_name': 'Aman Kumar',
                'business_name': 'Apex Tech',
                'username': 'apex_seller',
                'password': 'SellerPass123',
                'confirm_password': 'SellerPass123',
                'email': 'seller@example.com',
                'phone': '+919876543210',
                'business_address': '12, Market Road, New Delhi',
                'city': 'New Delhi',
                'state': 'Delhi',
                'pincode': '110001',
                'gstin': '29ABCDE1234F1Z5',
                'pan_number': 'ABCDE1234F',
                'kyc_document': SimpleUploadedFile('seller_kyc.pdf', b'%PDF-1.4\nseller', content_type='application/pdf'),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(SellerRegistrationApplication.objects.filter(email='seller@example.com', status='pending').exists())

    def test_delivery_registration_creates_pending_application(self):
        response = self.client.post(
            reverse('public:delivery_register'),
            {
                'full_name': 'Ravi Sharma',
                'username': 'ravi_rider',
                'password': 'RiderPass123',
                'confirm_password': 'RiderPass123',
                'email': 'rider@example.com',
                'phone': '+919988776655',
                'vehicle_type': 'Motorcycle / Bike',
                'license_number': 'DL-042021008765',
                'vehicle_number': 'DL 01 AB 1234',
                'address': '7, Ashok Vihar, Delhi',
                'city': 'Delhi',
                'state': 'Delhi',
                'pincode': '110052',
                'kyc_document': SimpleUploadedFile('rider_kyc.pdf', b'%PDF-1.4\nrider', content_type='application/pdf'),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(DeliveryPartnerApplication.objects.filter(phone='+919988776655', status='pending').exists())

    def test_unapproved_seller_cannot_login(self):
        user = User.objects.create_user(
            username='pending_seller',
            email='pending@example.com',
            password='SecurePass123',
            role='seller',
        )

        response = self.client.post(
            reverse('users:login'),
            {'username': 'pending_seller', 'password': 'SecurePass123'},
            follow=True,
        )

        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(response.redirect_chain)
        self.assertEqual(user.role, 'seller')


class HomepageCategoryTests(TestCase):
    def test_homepage_limits_category_strip_to_ten_items(self):
        categories = [
            Category.objects.create(name=f'Homepage Category {index}', slug=f'homepage-category-{index}')
            for index in range(1, 12)
        ]

        response = self.client.get(reverse('public:home'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['categories']), 10)
        self.assertContains(response, categories[9].name)
        self.assertNotContains(response, categories[10].name)
