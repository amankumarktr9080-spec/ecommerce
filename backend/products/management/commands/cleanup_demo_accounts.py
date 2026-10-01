from django.core.management.base import BaseCommand
from django.db import transaction

from delivery.models import DeliveryPartnerProfile
from products.models import Product
from sellers.models import SellerProfile
from users.models import User


class Command(BaseCommand):
    help = "Keep two sellers and two riders, remove customers and extra demo accounts"

    @transaction.atomic
    def handle(self, *args, **options):
        sellers = list(SellerProfile.objects.filter(id__in=[1, 2]).order_by("id"))
        riders = list(DeliveryPartnerProfile.objects.filter(id__in=[1, 2]).order_by("id"))
        if len(sellers) != 2 or len(riders) != 2:
            raise RuntimeError("Expected seller profiles 1, 2 and rider profiles 1, 2")

        products = list(Product.objects.order_by("id"))
        for index, product in enumerate(products):
            product.seller = sellers[index % 2]
            product.save(update_fields=["seller"])

        User.objects.filter(role="customer").delete()
        SellerProfile.objects.exclude(id__in=[seller.id for seller in sellers]).delete()
        DeliveryPartnerProfile.objects.exclude(id__in=[rider.id for rider in riders]).delete()
        User.objects.filter(role="seller").exclude(
            id__in=[seller.user_id for seller in sellers]
        ).delete()
        User.objects.filter(role="delivery").exclude(
            id__in=[rider.user_id for rider in riders]
        ).delete()

        admin = User.objects.get(username="admin")
        admin.set_password("Admin@123")
        admin.save(update_fields=["password"])

        for seller in sellers:
            seller.user.set_password("Seller@123")
            seller.user.is_active = True
            seller.user.save(update_fields=["password", "is_active"])

        for rider in riders:
            rider.user.set_password("Rider@123")
            rider.user.is_active = True
            rider.user.save(update_fields=["password", "is_active"])

        self.stdout.write(self.style.SUCCESS(
            f"Kept {len(sellers)} sellers, {len(riders)} riders, and reassigned {len(products)} products."
        ))
