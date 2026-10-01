from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from uuid import uuid4
from django.utils.text import slugify
from collections import OrderedDict
from categories.models import Category
from cart.models import Cart
from products.models import Product
from wishlist.models import Wishlist
from offers.models import OfferBanner
from support.models import SupportTicket
from admin_panel.models import FAQItem, HomepageHeroSlide, MarketplaceSettings
from users.models import User
from sellers.models import SellerRegistrationApplication
from delivery.models import DeliveryPartnerApplication


def _is_valid_kyc_pdf(upload):
    if not upload or not upload.name.lower().endswith('.pdf') or upload.size > 5 * 1024 * 1024:
        return False
    try:
        is_pdf = upload.read(5) == b'%PDF-'
        upload.seek(0)
        return is_pdf
    except (AttributeError, OSError):
        return False


def username_availability(request):
    username = request.GET.get('username', '').strip()
    username_exists = bool(username) and (
        User.objects.filter(username__iexact=username).exists()
        or SellerRegistrationApplication.objects.filter(username__iexact=username, status='pending').exists()
        or DeliveryPartnerApplication.objects.filter(username__iexact=username, status='pending').exists()
    )
    return JsonResponse({
        'available': not username_exists,
        'message': 'This User ID is already taken.' if username_exists else 'User ID is available.',
        'username_available': not username_exists,
        'username_message': 'This User ID is already taken.' if username_exists else 'User ID is available.',
    })


def _create_partner_enquiry_ticket(request, subject, category, message):
    ticket_user = request.user if request.user.is_authenticated else User.objects.filter(role='customer').first() or User.objects.order_by('id').first()
    if ticket_user is None:
        ticket_user = User.objects.create_user(
            username=f'guest_{uuid4().hex[:8]}',
            email=f'guest_{uuid4().hex[:8]}@example.com',
            password='Guest@123',
            first_name='Guest',
            role='customer',
        )

    SupportTicket.objects.create(
        user=ticket_user,
        ticket_id=f'TKT-{uuid4().hex[:10].upper()}',
        subject=subject,
        category=category,
        priority='medium',
        message=message,
    )
    messages.success(request, 'Your enquiry has been submitted successfully. Our admin team will review it and contact you soon.')
    return redirect(request.path)


def home(request):
    marketplace_settings, _ = MarketplaceSettings.objects.get_or_create(pk=1)
    hero_slides = list(HomepageHeroSlide.objects.all())
    if hero_slides:
        hero_images = [slide.image.url for slide in hero_slides]
    elif marketplace_settings.hero_image:
        hero_images = [marketplace_settings.hero_image.url]
    else:
        hero_images = ['https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=1000&q=85']
    categories = Category.objects.filter(is_active=True).order_by('id')[:10]
    featured_products = Product.objects.filter(is_active=True).select_related('category', 'seller').order_by('category__name', '-created_at')
    grouped_products = OrderedDict()
    for product in featured_products:
        category_name = product.category.name if product.category else 'Other Products'
        grouped_products.setdefault(category_name, []).append(product)

    if request.user.is_authenticated and getattr(request.user, 'role', None) == 'customer':
        cart = Cart.objects.filter(user=request.user).first()
        cart_quantities = dict(cart.items.values_list('product_id', 'quantity')) if cart else {}
    else:
        cart_quantities = {
            int(product_id): int(quantity)
            for product_id, quantity in request.session.get('guest_cart', {}).items()
            if str(product_id).isdigit()
        }
    compare_product_ids = [
        int(product_id) for product_id in request.session.get('compare_product_ids', [])
        if str(product_id).isdigit()
    ]
    for products in grouped_products.values():
        for product in products:
            product.cart_quantity = cart_quantities.get(product.id, 0)

    category_product_rows = [
        {'name': category_name, 'products': products}
        for category_name, products in grouped_products.items()
    ]
    showcase_codes = [code.strip() for code in marketplace_settings.featured_product_codes.replace(',', '\n').splitlines() if code.strip()]
    products_by_code = {
        product.item_code: product
        for product in Product.objects.filter(is_active=True, item_code__in=showcase_codes)
    }
    showcase_products = [products_by_code[code] for code in showcase_codes if code in products_by_code]
    banners = OfferBanner.objects.filter(is_active=True)[:4]
    if request.user.is_authenticated and getattr(request.user, 'role', None) == 'customer':
        wishlist = Wishlist.objects.filter(user=request.user).first()
        user_wishlist_ids = set(wishlist.items.values_list('product_id', flat=True)) if wishlist else set()
    else:
        user_wishlist_ids = {
            int(product_id) for product_id in request.session.get('guest_wishlist', [])
            if str(product_id).isdigit()
        }

    context = {
        'current_panel': 'customer',
        'hero_images': hero_images,
        'categories': categories,
        'featured_products': featured_products,
        'showcase_products': showcase_products,
        'category_product_rows': category_product_rows,
        'banners': banners,
        'user_wishlist_ids': user_wishlist_ids,
        'compare_product_ids': compare_product_ids,
    }
    return render(request, "public/home.html", context)


def about(request):
    return render(request, "public/about.html", {'current_panel': 'customer'})


def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        ticket_user = request.user if request.user.is_authenticated else User.objects.filter(role='customer').first()

        if ticket_user:
            SupportTicket.objects.create(
                user=ticket_user,
                ticket_id=f'WEB-{uuid4().hex[:10].upper()}',
                subject=subject,
                category='Contact Inquiry',
                priority='medium',
                message=f'Name: {name}\nEmail: {email}\n\n{message}',
            )
            messages.success(request, 'Your message has been sent to the ShopVerse support team.')
        else:
            messages.error(request, 'Unable to send your message right now. Please try again.')
        return redirect('/contact/')

    return render(request, "public/contact.html", {'current_panel': 'customer'})


def faq(request):
    return render(request, "public/faq.html", {'current_panel': 'customer', 'faq_items': FAQItem.objects.filter(is_active=True)})


def help_page(request):
    return render(request, "public/help.html", {'current_panel': 'customer'})


def privacy(request):
    return render(request, "public/privacy.html", {'current_panel': 'customer', 'policy_title': 'Privacy Policy', 'policy_content': MarketplaceSettings.objects.filter(pk=1).values_list('privacy_policy', flat=True).first()})


def terms(request):
    return render(request, "public/terms.html", {'current_panel': 'customer', 'policy_title': 'Terms & Conditions', 'policy_content': MarketplaceSettings.objects.filter(pk=1).values_list('terms_conditions', flat=True).first()})


def refund_policy(request):
    return render(request, "public/refund-policy.html", {'current_panel': 'customer', 'policy_title': 'Refund Policy', 'policy_content': MarketplaceSettings.objects.filter(pk=1).values_list('refund_policy', flat=True).first()})


def shipping_policy(request):
    return render(request, "public/shipping-policy.html", {'current_panel': 'customer', 'policy_title': 'Shipping Policy', 'policy_content': MarketplaceSettings.objects.filter(pk=1).values_list('shipping_policy', flat=True).first()})


def cancellation_policy(request):
    return render(request, "public/cancellation-policy.html", {'current_panel': 'customer', 'policy_title': 'Cancellation Policy', 'policy_content': MarketplaceSettings.objects.filter(pk=1).values_list('cancellation_policy', flat=True).first()})


def seller_register(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        business_name = request.POST.get('business_name', '').strip() or request.POST.get('store_name', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        business_address = request.POST.get('business_address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        gstin = request.POST.get('gstin', '').strip()
        pan_number = request.POST.get('pan_number', '').strip()
        kyc_document = request.FILES.get('kyc_document')

        if not all((
            full_name, business_name, username, password, confirm_password, email, phone,
            business_address, city, state, pincode, gstin, pan_number,
        )):
            messages.error(request, 'Please complete all required seller details before submitting your application.')
            return render(request, "public/seller-register.html", {'current_panel': 'customer', 'is_admin_provisioned': True})
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, "public/seller-register.html", {'current_panel': 'customer', 'is_admin_provisioned': True})
        if User.objects.filter(username__iexact=username).exists() or SellerRegistrationApplication.objects.filter(username__iexact=username, status='pending').exists():
            messages.error(request, 'This username is already in use. Please choose another.')
            return render(request, "public/seller-register.html", {'current_panel': 'customer', 'is_admin_provisioned': True})
        if not kyc_document:
            messages.error(request, 'Upload the required seller KYC PDF before submitting.')
            return render(request, "public/seller-register.html", {'current_panel': 'customer', 'is_admin_provisioned': True})
        if not _is_valid_kyc_pdf(kyc_document):
            messages.error(request, 'KYC document must be a valid PDF file no larger than 5 MB.')
            return render(request, "public/seller-register.html", {'current_panel': 'customer', 'is_admin_provisioned': True})

        SellerRegistrationApplication.objects.create(
            full_name=full_name,
            store_name=business_name,
            username=username,
            password_hash=make_password(password),
            email=email,
            phone=phone,
            business_address=business_address,
            city=city,
            state=state,
            pincode=pincode,
            gstin=gstin,
            pan_number=pan_number,
            kyc_document=kyc_document,
        )

        messages.success(request, 'Your seller registration has been submitted successfully. Our admin team will review your KYC and approve the account before login access is enabled.')
        return redirect('/seller-register/')

    context = {
        'current_panel': 'customer',
        'is_admin_provisioned': True,
    }
    return render(request, "public/seller-register.html", context)


def delivery_register(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        vehicle_type = request.POST.get('vehicle_type', '').strip()
        license_number = request.POST.get('license_number', '').strip() or request.POST.get('driving_license_no', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        vehicle_number = request.POST.get('vehicle_number', '').strip()
        kyc_document = request.FILES.get('kyc_document')

        if not all((
            full_name, username, password, confirm_password, email, phone, vehicle_type,
            license_number, vehicle_number, address, city, state, pincode,
        )):
            messages.error(request, 'Please complete all rider details before submitting your application.')
            return render(request, "public/delivery-register.html", {'current_panel': 'customer', 'is_admin_provisioned': True})
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, "public/delivery-register.html", {'current_panel': 'customer', 'is_admin_provisioned': True})
        if User.objects.filter(username__iexact=username).exists() or DeliveryPartnerApplication.objects.filter(username__iexact=username, status='pending').exists():
            messages.error(request, 'This username is already in use. Please choose another.')
            return render(request, "public/delivery-register.html", {'current_panel': 'customer', 'is_admin_provisioned': True})
        if not kyc_document:
            messages.error(request, 'Upload the required rider KYC PDF before submitting.')
            return render(request, "public/delivery-register.html", {'current_panel': 'customer', 'is_admin_provisioned': True})
        if not _is_valid_kyc_pdf(kyc_document):
            messages.error(request, 'KYC document must be a valid PDF file no larger than 5 MB.')
            return render(request, "public/delivery-register.html", {'current_panel': 'customer', 'is_admin_provisioned': True})

        DeliveryPartnerApplication.objects.create(
            full_name=full_name,
            username=username,
            password_hash=make_password(password),
            email=email,
            phone=phone,
            vehicle_type=vehicle_type,
            vehicle_number=vehicle_number,
            driving_license_no=license_number,
            address=address,
            city=city,
            state=state,
            pincode=pincode,
            kyc_document=kyc_document,
        )

        messages.success(request, 'Your delivery partner registration is submitted and pending admin verification. You will be able to log in only after approval.')
        return redirect('/delivery-register/')

    context = {
        'current_panel': 'customer',
        'is_admin_provisioned': True,
    }
    return render(request, "public/delivery-register.html", context)