import json
import csv
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from users.models import User, Address
from sellers.models import SellerProfile, PayoutRequest, SellerRegistrationApplication
from delivery.models import DeliveryPartnerProfile, DeliveryPartnerApplication, DeliveryRating
from products.models import Product, ProductImage, ProductSpecification
from categories.models import Category, SubCategory, Brand
from orders.models import Order, OrderItem, OrderTimeline
from commissions.models import CommissionLog
from payments.models import PaymentTransaction
from returns.models import ReturnRequest
from returns.services import (
    ReturnValidationError,
    approve_request,
    create_replacement,
    fallback_replacement_to_wallet_refund,
    inspect_return,
    mark_picked_up,
    process_return_refund,
    reject_request,
    schedule_pickup,
    record_cancelled_external_refund,
    refund_cancelled_wallet_order,
)
from coupons.models import Coupon
from offers.models import OfferBanner
from reviews.models import Review
from support.models import SupportTicket
from notifications.models import Notification
from .forms import FAQItemForm, FeaturedProductsForm, HomepageHeroSlidesForm, MarketplaceContentForm, MarketplaceSettingsForm
from .models import FAQItem, HomepageHeroSlide, MarketplaceSettings


def _is_valid_kyc_pdf(upload):
    if not upload or not upload.name.lower().endswith('.pdf') or upload.size > 5 * 1024 * 1024:
        return False
    try:
        valid_pdf = upload.read(5) == b'%PDF-'
        upload.seek(0)
        return valid_pdf
    except (AttributeError, OSError):
        return False


# =========================================
# DASHBOARD
# =========================================

def profile(request):
    if request.method == 'POST' and request.POST.get('action') == 'save_profile':
        admin_user = request.user
        admin_user.first_name = request.POST.get('first_name', admin_user.first_name).strip()
        admin_user.last_name = request.POST.get('last_name', admin_user.last_name).strip()
        admin_user.email = request.POST.get('email', admin_user.email).strip()
        admin_user.phone = request.POST.get('phone', admin_user.phone)
        admin_user.save(update_fields=['first_name', 'last_name', 'email', 'phone'])
        messages.success(request, 'Profile details updated successfully.')
        return redirect('admin_panel:profile')

    return render(request, "admin_panel/profile.html", {
        'current_panel': 'admin',
        'active_menu': 'profile',
        'admin_user': request.user,
        'profile_edit_open': request.GET.get('show') == 'edit',
        'profile_password_open': request.GET.get('show') == 'password',
    })


def _admin_search_results(query):
    results = []
    if not query:
        return results

    for order in Order.objects.filter(
        Q(order_number__icontains=query) |
        Q(customer_name__icontains=query) |
        Q(customer_phone__icontains=query) |
        Q(customer__username__icontains=query) |
        Q(seller__store_name__icontains=query)
    ).select_related('customer', 'seller').order_by('-created_at')[:5]:
        results.append({
            'type': 'Order',
            'title': f'Order #{order.order_number}',
            'subtitle': f'{order.customer_name} · {order.get_status_display()} · ₹{order.grand_total:.2f}',
            'url': reverse('admin_panel:order_details', args=[order.id]),
            'icon': 'fa-solid fa-box-open',
        })

    for product in Product.objects.filter(
        Q(title__icontains=query) |
        Q(item_code__icontains=query) |
        Q(sku__icontains=query) |
        Q(brand__name__icontains=query) |
        Q(category__name__icontains=query) |
        Q(seller__store_name__icontains=query)
    ).select_related('brand', 'category', 'seller').order_by('-created_at')[:5]:
        results.append({
            'type': 'Product',
            'title': product.title,
            'subtitle': f'{product.item_code} · {product.brand.name if product.brand else "Unbranded"} · ₹{product.selling_price:.2f}',
            'url': reverse('admin_panel:product_details', args=[product.id]),
            'icon': 'fa-solid fa-box',
        })

    for customer in User.objects.filter(role='customer').filter(
        Q(username__icontains=query) |
        Q(email__icontains=query) |
        Q(phone__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    ).order_by('-date_joined')[:5]:
        results.append({
            'type': 'Customer',
            'title': customer.get_full_name() or customer.username,
            'subtitle': f'{customer.email} · {customer.phone}',
            'url': reverse('admin_panel:customer_details', args=[customer.id]),
            'icon': 'fa-solid fa-user',
        })

    for seller in SellerProfile.objects.filter(
        Q(store_name__icontains=query) |
        Q(user__username__icontains=query) |
        Q(user__email__icontains=query) |
        Q(phone__icontains=query)
    ).select_related('user').order_by('-created_at')[:5]:
        results.append({
            'type': 'Seller',
            'title': seller.store_name,
            'subtitle': f'{seller.user.username} · {seller.email}',
            'url': reverse('admin_panel:seller_details', args=[seller.id]),
            'icon': 'fa-solid fa-store',
        })

    for partner in DeliveryPartnerProfile.objects.filter(
        Q(user__username__icontains=query) |
        Q(user__email__icontains=query) |
        Q(user__phone__icontains=query)
    ).select_related('user').order_by('-created_at')[:5]:
        results.append({
            'type': 'Delivery Partner',
            'title': partner.user.get_full_name() or partner.user.username,
            'subtitle': f'{partner.user.phone} · {"Approved" if partner.is_approved else "Pending approval"}',
            'url': reverse('admin_panel:delivery_details', args=[partner.id]),
            'icon': 'fa-solid fa-motorcycle',
        })

    return results


def admin_search(request):
    query = request.GET.get('q', '').strip()
    results = _admin_search_results(query)
    if request.GET.get('suggestions') == '1':
        return JsonResponse({'results': results[:8]})

    return render(request, 'admin_panel/search-results.html', {
        'current_panel': 'admin',
        'active_menu': 'search',
        'query': query,
        'results': results,
    })


def dashboard(request):
    total_customers = User.objects.filter(role='customer').count()
    total_sellers = SellerProfile.objects.count()
    total_riders = DeliveryPartnerProfile.objects.count()
    total_orders = Order.objects.count()

    gmv_orders = Order.objects.exclude(status__in=['cancelled', 'returned'])
    raw_rev = gmv_orders.aggregate(s=Sum('subtotal'))['s'] or Decimal("0.00")
    raw_comm = CommissionLog.objects.filter(
        status='settled', order__status='delivered', order__payment_status='paid'
    ).aggregate(s=Sum('admin_commission_amount'))['s'] or Decimal("0.00")
    paid_delivered_orders = Order.objects.filter(status='delivered', payment_status='paid')
    raw_seller = paid_delivered_orders.aggregate(s=Sum('seller_net_earnings'))['s'] or Decimal("0.00")
    raw_rider = paid_delivered_orders.aggregate(s=Sum('delivery_partner_earning'))['s'] or Decimal("0.00")

    total_revenue = round(float(raw_rev), 2)
    total_commission = round(float(raw_comm), 2)
    total_seller_payout = round(float(raw_seller), 2)
    total_rider_payout = round(float(raw_rider), 2)

    recent_orders = Order.objects.select_related('customer').order_by('-created_at')[:8]
    pending_sellers = SellerProfile.objects.filter(is_approved=False)[:5]
    pending_returns = ReturnRequest.objects.filter(status='requested')[:5]
    open_tickets = SupportTicket.objects.filter(status__in=['open', 'in_progress'])[:5]

    context = {
        'current_panel': 'admin',
        'active_menu': 'dashboard',
        'total_customers': total_customers,
        'total_sellers': total_sellers,
        'total_riders': total_riders,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'total_commission': total_commission,
        'total_seller_payout': total_seller_payout,
        'total_rider_payout': total_rider_payout,
        'recent_orders': recent_orders,
        'pending_sellers': pending_sellers,
        'pending_returns': pending_returns,
        'open_tickets': open_tickets,
    }
    return render(request, "admin_panel/dashboard.html", context)


# =========================================
# CUSTOMERS
# =========================================

def customers(request):
    search_q = request.GET.get('q', '').strip()
    customer_list = User.objects.filter(role='customer').order_by('-date_joined')
    if search_q:
        customer_list = customer_list.filter(
            Q(username__icontains=search_q) |
            Q(email__icontains=search_q) |
            Q(phone__icontains=search_q) |
            Q(first_name__icontains=search_q) |
            Q(last_name__icontains=search_q)
        )

    context = {
        'current_panel': 'admin',
        'active_menu': 'customers',
        'customers': customer_list,
        'search_q': search_q,
    }
    return render(request, "admin_panel/customers.html", context)


def customer_details(request, customer_id):
    customer = get_object_or_404(User, id=customer_id, role='customer')
    orders = Order.objects.filter(customer=customer).order_by('-created_at')
    addresses = customer.addresses.all()
    context = {
        'current_panel': 'admin',
        'active_menu': 'customers',
        'customer': customer,
        'orders': orders,
        'addresses': addresses,
    }
    return render(request, "admin_panel/customer-details.html", context)


def toggle_customer_block(request, customer_id):
    customer = get_object_or_404(User, id=customer_id, role='customer')
    customer.is_active = not customer.is_active
    customer.save()
    status_str = "unblocked" if customer.is_active else "blocked"
    messages.success(request, f"Customer {customer.username} has been {status_str}.")
    return redirect("admin_panel:customers")


# =========================================
# SELLERS (Admin Onboarding & Management)
# =========================================

def sellers(request):
    seller_list = SellerProfile.objects.select_related('user').order_by('-created_at')
    context = {
        'current_panel': 'admin',
        'active_menu': 'sellers',
        'sellers': seller_list,
    }
    return render(request, "admin_panel/sellers.html", context)


def seller_applications(request):
    applications = SellerRegistrationApplication.objects.order_by('-created_at')

    if request.method == 'POST':
        app_id = request.POST.get('application_id')
        action = request.POST.get('action')
        application = get_object_or_404(SellerRegistrationApplication, id=app_id)

        if action == 'approve':
            username = application.username
            if not username or not application.password_hash:
                messages.error(request, 'This old application has no login credentials. Ask the applicant to submit the new registration form again.')
                return redirect('admin_panel:seller_applications')
            if User.objects.filter(username__iexact=username).exists():
                messages.error(request, f"Username '{username}' is already in use. Please choose another.")
                return redirect('admin_panel:seller_applications')
            user = User.objects.create_user(
                username=username,
                email=application.email,
                password='approval-password-placeholder',
                first_name=application.full_name.split()[0],
                last_name=' '.join(application.full_name.split()[1:]),
                phone=application.phone,
                role='seller',
            )
            user.password = application.password_hash
            user.save(update_fields=['password'])

            store_slug = slugify(application.store_name) or 'seller'
            SellerProfile.objects.create(
                user=user,
                store_name=application.store_name,
                store_slug=f"{store_slug}-{user.id}",
                phone=application.phone,
                email=application.email,
                business_address=application.business_address,
                gst_number=application.gstin,
                commission_rate=Decimal('10.00'),
                is_approved=True,
                kyc_status='verified',
            )
            application.status = 'approved'
            application.admin_note = request.POST.get('admin_note', 'Approved after KYC verification.')
            application.reviewed_at = timezone.now()
            application.save(update_fields=['status', 'admin_note', 'reviewed_at'])
            messages.success(request, f"Seller application approved. Login User ID: {username}. The applicant's selected password is now active.")
        elif action == 'reject':
            application.status = 'rejected'
            application.admin_note = request.POST.get('admin_note', 'Rejected by admin after review.')
            application.reviewed_at = timezone.now()
            application.save(update_fields=['status', 'admin_note', 'reviewed_at'])
            messages.info(request, 'Seller application rejected.')

        return redirect('admin_panel:seller_applications')

    context = {
        'current_panel': 'admin',
        'active_menu': 'seller_applications',
        'applications': applications,
    }
    return render(request, "admin_panel/seller-applications.html", context)


def add_seller(request):
    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip() or password
        phone = request.POST.get('phone', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        if not full_name:
            full_name = f"{request.POST.get('first_name', '').strip()} {request.POST.get('last_name', '').strip()}".strip()
        name_parts = full_name.split()
        first_name = name_parts[0] if name_parts else ''
        last_name = ' '.join(name_parts[1:])

        store_name = request.POST.get('store_name', '').strip()
        store_address = request.POST.get('store_address', '').strip()
        city = request.POST.get('city', '').strip() or 'Not provided'
        state = request.POST.get('state', '').strip() or 'Not provided'
        pincode = request.POST.get('pincode', '').strip() or '000000'
        gst_number = request.POST.get('gstin', '').strip() or request.POST.get('gst_number', '').strip()
        pan_number = request.POST.get('pan_number', '').strip() or 'NOT-PROVIDED'
        kyc_document = request.FILES.get('kyc_document')
        commission_rate = request.POST.get('commission_rate', '10.00').strip()

        if not all((username, email, password, confirm_password, full_name, phone, store_name, store_address, city, state, pincode, gst_number, pan_number, commission_rate)):
            messages.error(request, 'Complete all seller registration fields before creating the account.')
            return redirect("admin_panel:sellers")
        if password != confirm_password:
            messages.error(request, 'Seller passwords do not match.')
            return redirect("admin_panel:sellers")
        if kyc_document and not _is_valid_kyc_pdf(kyc_document):
            messages.error(request, 'Upload a valid seller KYC PDF no larger than 5 MB.')
            return redirect("admin_panel:sellers")

        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, f"Username '{username}' already exists. Please pick another.")
            return render(request, "admin_panel/sellers.html", {'active_menu': 'sellers', 'show_add_modal': True})

        if User.objects.filter(email=email).exists():
            messages.error(request, f"Email '{email}' is already registered.")
            return render(request, "admin_panel/sellers.html", {'active_menu': 'sellers', 'show_add_modal': True})

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role='seller'
        )

        seller = SellerProfile.objects.create(
            user=user,
            store_name=store_name,
            store_slug=f"{slugify(store_name) or 'seller'}-{user.id}",
            phone=phone,
            email=email,
            business_address=store_address,
            gst_number=gst_number,
            city=city,
            state=state,
            pincode=pincode,
            pan_number=pan_number,
            kyc_document=kyc_document,
            commission_rate=Decimal(commission_rate) if commission_rate else Decimal("10.00"),
            is_approved=True,
            kyc_status='verified'
        )

        messages.success(request, f"Seller account '{store_name}' created successfully for {username}.")
        return redirect("admin_panel:sellers")

    return redirect("admin_panel:sellers")


def seller_details(request, seller_id):
    seller = get_object_or_404(SellerProfile, id=seller_id)
    products = Product.objects.filter(seller=seller)
    return render(
        request,
        "admin_panel/seller-details.html",
        {"seller": seller, "products": products, "current_panel": "admin", "active_menu": "sellers"}
    )


def toggle_seller_status(request, seller_id):
    seller = get_object_or_404(SellerProfile, id=seller_id)
    seller.is_approved = not seller.is_approved
    seller.save(update_fields=['is_approved'])
    status = 'APPROVED' if seller.is_approved else 'SUSPENDED'
    messages.success(request, f"Seller '{seller.store_name}' status set to {status}.")
    return redirect("admin_panel:sellers")


def notifications(request):
    if not request.user.is_authenticated or request.user.role != 'admin':
        return HttpResponseForbidden()

    if request.method == 'POST':
        if request.POST.get('action') == 'mark_all_read':
            updated_count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
            messages.success(request, f'{updated_count} notification(s) marked as read.')
        elif request.POST.get('action') == 'delete_selected':
            deleted_count, _ = Notification.objects.filter(
                user=request.user,
                id__in=request.POST.getlist('notification_ids'),
            ).delete()
            messages.success(request, f'{deleted_count} notification(s) deleted.')
        else:
            messages.error(request, 'Invalid notification action.')
        return redirect('/admin-panel/notifications/')

    user_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'admin_panel/notifications.html', {
        'current_panel': 'admin',
        'active_menu': 'notifications',
        'notifications': user_notifications,
        'unread_count': user_notifications.filter(is_read=False).count(),
    })


# =========================================
# DELIVERY PARTNERS (Admin Onboarding)
# =========================================

def delivery_partners(request):
    rider_list = DeliveryPartnerProfile.objects.select_related('user').order_by('-created_at')
    context = {
        'current_panel': 'admin',
        'active_menu': 'delivery_partners',
        'riders': rider_list,
    }
    return render(request, "admin_panel/delivery-partners.html", context)


def delivery_applications(request):
    applications = DeliveryPartnerApplication.objects.order_by('-created_at')

    if request.method == 'POST':
        app_id = request.POST.get('application_id')
        action = request.POST.get('action')
        application = get_object_or_404(DeliveryPartnerApplication, id=app_id)

        if action == 'approve':
            username = application.username
            if not username or not application.password_hash:
                messages.error(request, 'This old application has no login credentials. Ask the rider to submit the new registration form again.')
                return redirect('admin_panel:delivery_applications')
            if User.objects.filter(username__iexact=username).exists():
                messages.error(request, f"Username '{username}' is already in use. Please choose another.")
                return redirect('admin_panel:delivery_applications')
            user = User.objects.create_user(
                username=username,
                email=application.email or f"rider_{application.id}@shopverse.local",
                password='approval-password-placeholder',
                first_name=application.full_name.split()[0],
                last_name=' '.join(application.full_name.split()[1:]),
                phone=application.phone,
                role='delivery',
            )
            user.password = application.password_hash
            user.save(update_fields=['password'])

            DeliveryPartnerProfile.objects.create(
                user=user,
                vehicle_type=application.vehicle_type,
                vehicle_number=application.vehicle_number or 'NA',
                driving_license_no=application.driving_license_no,
                is_approved=True,
                is_online=True,
            )
            application.status = 'approved'
            application.admin_note = request.POST.get('admin_note', 'Approved after KYC verification.')
            application.reviewed_at = timezone.now()
            application.save(update_fields=['status', 'admin_note', 'reviewed_at'])
            messages.success(request, f"Delivery registration approved. Login User ID: {username}. The applicant's selected password is now active.")
        elif action == 'reject':
            application.status = 'rejected'
            application.admin_note = request.POST.get('admin_note', 'Rejected by admin after review.')
            application.reviewed_at = timezone.now()
            application.save(update_fields=['status', 'admin_note', 'reviewed_at'])
            messages.info(request, 'Delivery application rejected.')

        return redirect('admin_panel:delivery_applications')

    context = {
        'current_panel': 'admin',
        'active_menu': 'delivery_applications',
        'applications': applications,
    }
    return render(request, "admin_panel/delivery-applications.html", context)


def add_delivery_partner(request):
    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        phone = request.POST.get('phone', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        name_parts = full_name.split()
        first_name = name_parts[0] if name_parts else ''
        last_name = ' '.join(name_parts[1:])

        vehicle_type = request.POST.get('vehicle_type', '').strip()
        vehicle_number = request.POST.get('vehicle_number', '').strip()
        driving_license = request.POST.get('driving_license', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        kyc_document = request.FILES.get('kyc_document')
        bank_name = request.POST.get('bank_name', '').strip()
        account_number = request.POST.get('account_number', '').strip()
        ifsc_code = request.POST.get('ifsc_code', '').strip().upper()
        upi_id = request.POST.get('upi_id', '').strip()

        if not all((username, email, password, confirm_password, phone, full_name, vehicle_type, vehicle_number, driving_license, address, city, state, pincode)):
            messages.error(request, 'Complete all public delivery registration fields before creating the account.')
            return redirect("admin_panel:delivery_partners")
        if password != confirm_password:
            messages.error(request, 'Rider passwords do not match.')
            return redirect("admin_panel:delivery_partners")
        if vehicle_type not in {'bike', 'scooter', 'van'}:
            messages.error(request, 'Choose a valid vehicle type.')
            return redirect("admin_panel:delivery_partners")
        if not _is_valid_kyc_pdf(kyc_document):
            messages.error(request, 'Upload a valid rider KYC PDF no larger than 5 MB.')
            return redirect("admin_panel:delivery_partners")

        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, f"Username '{username}' already exists. Please choose another.")
            return redirect("admin_panel:delivery_partners")

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role='delivery'
        )

        rider = DeliveryPartnerProfile.objects.create(
            user=user,
            vehicle_type=vehicle_type,
            vehicle_number=vehicle_number,
            driving_license_no=driving_license,
            address=address,
            city=city,
            state=state,
            pincode=pincode,
            kyc_document=kyc_document,
            bank_name=bank_name,
            account_number=account_number,
            ifsc_code=ifsc_code,
            upi_id=upi_id,
            is_approved=True,
            is_online=True
        )

        messages.success(request, f"Delivery partner '{user.get_full_name() or username}' created successfully.")
        return redirect("admin_panel:delivery_partners")

    return redirect("admin_panel:delivery_partners")


def delivery_details(request, partner_id):
    partner = get_object_or_404(DeliveryPartnerProfile, id=partner_id)
    deliveries = Order.objects.filter(delivery_partner=partner).order_by('-created_at')
    return render(
        request,
        "admin_panel/delivery-details.html",
        {"partner": partner, "deliveries": deliveries, "current_panel": "admin", "active_menu": "delivery_partners"}
    )


def toggle_delivery_status(request, partner_id):
    partner = get_object_or_404(DeliveryPartnerProfile, id=partner_id)
    partner.is_approved = not partner.is_approved
    partner.save()
    messages.success(request, f"Rider {partner.user.username} approval status: {'APPROVED' if partner.is_approved else 'SUSPENDED'}.")
    return redirect("admin_panel:delivery_partners")


# =========================================
# PRODUCTS & CATALOG
# =========================================

def products(request):
    search_q = request.GET.get('q', '').strip()
    product_list = Product.objects.select_related('seller', 'category', 'subcategory', 'brand').order_by('-created_at')
    if search_q:
        product_list = product_list.filter(
            Q(title__icontains=search_q) |
            Q(item_code__icontains=search_q) |
            Q(sku__icontains=search_q)
        )

    context = {
        'current_panel': 'admin',
        'active_menu': 'products',
        'products': product_list,
        'search_q': search_q,
    }
    return render(request, "admin_panel/products.html", context)


def product_details(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(
        request,
        "admin_panel/product-details.html",
        {"product": product, "current_panel": "admin", "active_menu": "products"}
    )


def toggle_product_status(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.is_active = not product.is_active
    product.save()
    messages.success(request, f"Product '{product.title}' is now {'ACTIVE' if product.is_active else 'INACTIVE'}.")
    return redirect("admin_panel:products")


# =========================================
# CATEGORIES & BRANDS
# =========================================

def categories(request):
    if request.method == "POST":
        action = request.POST.get('action', 'create')
        if action == 'delete':
            category = get_object_or_404(Category, id=request.POST.get('category_id'))
            name = category.name
            category.delete()
            messages.success(request, f"Category '{name}' and its subcategories and brands were deleted. Related products remain, with taxonomy links cleared.")
            return redirect("admin_panel:categories")

        name = request.POST.get('name', '').strip()
        slug = slugify(request.POST.get('slug', '').strip() or name)
        icon = request.POST.get('icon', 'fa-solid fa-tag')
        category_id = request.POST.get('category_id')
        category = get_object_or_404(Category, id=category_id) if action == 'edit' else None

        if not name or not slug:
            messages.error(request, 'Enter a category name and a valid slug.')
        elif Category.objects.filter(slug=slug).exclude(id=category.id if category else None).exists():
            messages.error(request, f"Category slug '{slug}' is already in use.")
        elif action == 'edit':
            category.name = name
            category.slug = slug
            category.icon = icon
            category.save(update_fields=['name', 'slug', 'icon'])
            messages.success(request, f"Category '{name}' updated.")
        else:
            Category.objects.create(name=name, slug=slug, icon=icon)
            messages.success(request, f"Category '{name}' created successfully!")
        return redirect("admin_panel:categories")

    cat_list = Category.objects.prefetch_related('subcategories__brands').all()
    context = {
        'current_panel': 'admin',
        'active_menu': 'categories',
        'categories': cat_list,
    }
    return render(request, "admin_panel/categories.html", context)


def subcategories(request):
    if request.method == 'POST':
        action = request.POST.get('action', 'create')
        if action == 'delete':
            subcategory = get_object_or_404(SubCategory, id=request.POST.get('subcategory_id'))
            name = subcategory.name
            subcategory.delete()
            messages.success(request, f"Subcategory '{name}' and its brands were deleted. Related products remain, with taxonomy links cleared.")
            return redirect('admin_panel:subcategories')

        category = Category.objects.filter(id=request.POST.get('category_id')).first()
        name = request.POST.get('name', '').strip()
        slug = slugify(request.POST.get('slug', '').strip() or name)
        subcategory_id = request.POST.get('subcategory_id')
        subcategory = get_object_or_404(SubCategory, id=subcategory_id) if action == 'edit' else None
        if not category or not name:
            messages.error(request, 'Choose a category and enter a subcategory name.')
        elif SubCategory.objects.filter(category=category, name__iexact=name).exclude(id=subcategory.id if subcategory else None).exists():
            messages.error(request, f'{name} already exists under {category.name}.')
        elif not slug:
            messages.error(request, 'Enter a valid subcategory name or slug.')
        elif action == 'edit':
            subcategory.category = category
            subcategory.name = name
            subcategory.slug = slug
            subcategory.save(update_fields=['category', 'name', 'slug'])
            messages.success(request, f'Subcategory {name} updated.')
        else:
            SubCategory.objects.create(category=category, name=name, slug=slug or slugify(name))
            messages.success(request, f'Subcategory {name} added under {category.name}.')
        return redirect('admin_panel:subcategories')

    category_filter = request.GET.get('category_id', '').strip()
    subcategory_list = SubCategory.objects.select_related('category').prefetch_related('brands').order_by('category__name', 'name')
    if category_filter:
        subcategory_list = subcategory_list.filter(category_id=category_filter)

    context = {
        'current_panel': 'admin',
        'active_menu': 'subcategories',
        'categories': Category.objects.order_by('name'),
        'subcategories': subcategory_list,
        'selected_category_id': category_filter,
    }
    return render(request, 'admin_panel/subcategories.html', context)


def brands(request):
    if request.method == "POST":
        action = request.POST.get('action', 'create')
        if action == 'delete':
            brand = get_object_or_404(Brand, id=request.POST.get('brand_id'))
            name = brand.name
            brand.delete()
            messages.success(request, f"Brand '{name}' deleted. Related products remain, with their brand cleared.")
            return redirect("admin_panel:brands")

        name = request.POST.get('name', '').strip()
        slug = slugify(request.POST.get('slug', '').strip() or name)
        category_id = request.POST.get('category_id')
        subcategory_id = request.POST.get('subcategory_id')
        subcategory = SubCategory.objects.select_related('category').filter(
            id=subcategory_id,
            category_id=category_id,
        ).first()
        brand_id = request.POST.get('brand_id')
        brand = get_object_or_404(Brand, id=brand_id) if action == 'edit' else None
        if not name or not subcategory or not slug:
            messages.error(request, 'Choose a subcategory and enter a brand name.')
        elif Brand.objects.filter(subcategory=subcategory, name__iexact=name).exclude(id=brand.id if brand else None).exists():
            messages.error(request, f"Brand '{name}' already exists under {subcategory.category.name} > {subcategory.name}.")
        elif action == 'edit':
            brand.subcategory = subcategory
            brand.name = name
            brand.slug = slug
            brand.save(update_fields=['subcategory', 'name', 'slug'])
            messages.success(request, f"Brand '{name}' updated under {subcategory.category.name} > {subcategory.name}.")
        else:
            Brand.objects.create(subcategory=subcategory, name=name, slug=slug)
            messages.success(request, f"Brand '{name}' added under {subcategory.category.name} > {subcategory.name}.")
        return redirect("admin_panel:brands")

    category_filter = request.GET.get('category_id', '').strip()
    subcategory_filter = request.GET.get('subcategory_id', '').strip()
    brand_list = Brand.objects.select_related('subcategory__category').all()
    if category_filter:
        brand_list = brand_list.filter(subcategory__category_id=category_filter)
    if subcategory_filter:
        brand_list = brand_list.filter(subcategory_id=subcategory_filter)
    context = {
        'current_panel': 'admin',
        'active_menu': 'brands',
        'brands': brand_list,
        'selected_category_id': category_filter,
        'selected_subcategory_id': subcategory_filter,
        'categories': Category.objects.order_by('name'),
        'subcategories': SubCategory.objects.select_related('category').order_by('category__name', 'name'),
    }
    return render(request, "admin_panel/brands.html", context)


# =========================================
# ORDERS
# =========================================

def orders(request):
    order_list = Order.objects.select_related('customer', 'delivery_partner').prefetch_related('items').order_by('-created_at')
    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        order_list = order_list.filter(status=status_filter)

    context = {
        'current_panel': 'admin',
        'active_menu': 'orders',
        'orders': order_list,
        'status_filter': status_filter,
    }
    return render(request, "admin_panel/orders.html", context)


def order_details(request, order_id):
    order = get_object_or_404(Order.objects.select_related('customer', 'delivery_partner').prefetch_related('items__product', 'timeline'), id=order_id)
    if request.method == 'POST' and request.POST.get('action') == 'refund_cancelled_wallet':
        refunded, amount = refund_cancelled_wallet_order(order.id)
        if refunded:
            messages.success(request, f'₹{amount:.2f} refunded to the customer wallet.')
        else:
            messages.error(request, 'Wallet refund was not applied. Check order status and payment transaction before retrying.')
        return redirect('admin_panel:order_details', order_id=order.id)
    if request.method == 'POST' and request.POST.get('action') == 'record_cancelled_external_refund':
        refunded, amount = record_cancelled_external_refund(
            order.id, request.POST.get('refund_reference', '')
        )
        if refunded:
            messages.success(request, f'₹{amount:.2f} external refund recorded.')
        else:
            messages.error(request, 'Refund was not recorded. Verify the cancelled order, payment amount, and provider reference.')
        return redirect('admin_panel:order_details', order_id=order.id)

    return render(
        request,
        "admin_panel/order-details.html",
        {"order": order, "current_panel": "admin", "active_menu": "orders"}
    )


# =========================================
# 10% ADMIN COMMISSIONS & PAYMENTS
# =========================================

def commissions(request):
    logs = CommissionLog.objects.select_related('order__seller').order_by('-created_at')
    total_commission = logs.filter(
        status='settled', order__status='delivered', order__payment_status='paid'
    ).aggregate(s=Sum('admin_commission_amount'))['s'] or Decimal("0.00")
    total_order_volume = Order.objects.exclude(
        status__in=['cancelled', 'returned']
    ).aggregate(s=Sum('subtotal'))['s'] or Decimal("0.00")
    total_seller_net = PayoutRequest.objects.filter(status='paid').exclude(
        admin_note=''
    ).aggregate(s=Sum('amount'))['s'] or Decimal("0.00")

    context = {
        'current_panel': 'admin',
        'active_menu': 'commissions',
        'logs': logs,
        'total_commission': total_commission,
        'total_order_volume': total_order_volume,
        'total_seller_net': total_seller_net,
    }
    return render(request, "admin_panel/commisions.html", context)


def payments(request):
    transactions = PaymentTransaction.objects.select_related('order').order_by('-created_at')
    total_paid = transactions.filter(status='success').aggregate(s=Sum('amount'))['s'] or Decimal("0.00")
    context = {
        'current_panel': 'admin',
        'active_menu': 'payments',
        'transactions': transactions,
        'total_paid': total_paid,
    }
    return render(request, "admin_panel/payments.html", context)


def payouts(request):
    if request.method == 'POST':
        payout = get_object_or_404(PayoutRequest, id=request.POST.get('payout_id'))
        action = request.POST.get('action')
        if payout.status != 'pending':
            messages.info(request, 'This payout request has already been processed.')
        elif action == 'approve':
            transfer_reference = request.POST.get('admin_note', '').strip()
            if not transfer_reference:
                messages.error(request, 'Enter the completed bank/UPI transfer reference before marking this payout paid.')
            else:
                payout.status = 'paid'
                payout.admin_note = transfer_reference
                payout.save(update_fields=['status', 'admin_note', 'updated_at'])
                messages.success(request, f'Payout of ₹{payout.amount} recorded with transfer reference for {payout.seller.store_name}.')
        elif action == 'reject':
            payout.status = 'rejected'
            payout.admin_note = request.POST.get('admin_note', 'Rejected by Admin.')
            payout.save(update_fields=['status', 'admin_note', 'updated_at'])
            messages.info(request, 'Payout request rejected; amount is available again to the seller.')
        return redirect('/admin-panel/payouts/')

    return render(request, 'admin_panel/payouts.html', {
        'current_panel': 'admin',
        'active_menu': 'payouts',
        'payouts': PayoutRequest.objects.select_related('seller').all(),
    })


# =========================================
# RETURNS & REFUNDS
# =========================================

def returns(request):
    if not request.user.is_authenticated or request.user.role != 'admin':
        return HttpResponseForbidden()
    return_requests = ReturnRequest.objects.select_related('order', 'customer').order_by('-created_at')
    
    if request.method == "POST":
        req_id = request.POST.get('return_id')
        action = request.POST.get('action')
        ret = get_object_or_404(ReturnRequest, id=req_id)
        try:
            remarks = request.POST.get('notes', '')
            if action == 'approve':
                approve_request(ret.id, remarks=remarks, approved_by='admin')
            elif action == 'refund':
                processed, refund_amount = process_return_refund(ret.id)
                messages.success(request, f'Refund of ₹{refund_amount} credited to customer wallet.') if processed else messages.info(request, 'Refund was already processed.')
            elif action == 'reject':
                reject_request(ret.id, remarks=remarks or 'Rejected by admin.', rejected_by='admin')
            elif action == 'picked_up':
                mark_picked_up(ret.id)
            elif action == 'schedule_pickup':
                pickup_partner = DeliveryPartnerProfile.objects.filter(
                    id=request.POST.get('pickup_partner_id'), is_approved=True,
                ).first()
                schedule_pickup(
                    ret.id, pickup_partner=pickup_partner,
                    tracking_id=request.POST.get('pickup_tracking_id', ''),
                )
            elif action == 'inspect_pass':
                inspect_return(ret.id, passed=True, remarks=remarks)
            elif action == 'inspect_fail':
                inspect_return(ret.id, passed=False, remarks=remarks)
            elif action == 'replace':
                replacement = create_replacement(ret.id)
                if replacement is None:
                    messages.info(request, 'Replacement stock is unavailable. Issue a wallet refund from this request.')
            elif action == 'replacement_refund':
                fallback_replacement_to_wallet_refund(ret.id)
            else:
                raise ReturnValidationError('Unknown return action.')
        except ReturnValidationError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f'Return #{ret.id} updated: {action}.')
        return redirect("admin_panel:returns")

    context = {
        'current_panel': 'admin',
        'active_menu': 'returns',
        'returns': return_requests,
        'pickup_partners': DeliveryPartnerProfile.objects.filter(is_approved=True).select_related('user').order_by('user__username'),
    }
    return render(request, "admin_panel/returns.html", context)


def refunds(request):
    if not request.user.is_authenticated or request.user.role != 'admin':
        return HttpResponseForbidden()
    completed_refunds = ReturnRequest.objects.filter(status='refund_processed').select_related('order', 'customer').order_by('-updated_at')
    context = {
        'current_panel': 'admin',
        'active_menu': 'refunds',
        'refunds': completed_refunds,
    }
    return render(request, "admin_panel/refunds.html", context)


# =========================================
# COUPONS & OFFERS
# =========================================

def coupons(request):
    if request.method == "POST":
        action = request.POST.get('action', 'create')

        if action == 'delete':
            coupon = get_object_or_404(Coupon, id=request.POST.get('coupon_id'))
            code = coupon.code
            coupon.delete()
            messages.success(request, f"Coupon '{code}' deleted.")
            return redirect("admin_panel:coupons")

        if action == 'edit':
            coupon = get_object_or_404(Coupon, id=request.POST.get('coupon_id'))
            code = request.POST.get('code', coupon.code).strip().upper()
            discount_type = request.POST.get('discount_type', coupon.discount_type)
            discount_type = {'percentage': 'percent', 'fixed': 'flat'}.get(discount_type, discount_type)
            discount_value = Decimal(request.POST.get('discount_value', coupon.discount_value))
            min_order = Decimal(request.POST.get('min_order', coupon.min_order_amount or '0.00'))
            max_uses_raw = request.POST.get('max_uses', '')
            max_uses = int(max_uses_raw) if max_uses_raw and max_uses_raw.isdigit() else None

            if not code:
                messages.error(request, 'Coupon code is required.')
                return redirect("admin_panel:coupons")

            coupon.code = code
            coupon.discount_type = discount_type
            coupon.discount_value = discount_value
            coupon.min_order_amount = min_order
            coupon.max_uses = max_uses if max_uses is not None else 0
            coupon.save(update_fields=['code', 'discount_type', 'discount_value', 'min_order_amount', 'max_uses'])
            messages.success(request, f"Coupon '{code}' updated.")
            return redirect("admin_panel:coupons")

        code = request.POST.get('code', '').strip().upper()
        discount_type = request.POST.get('discount_type', 'percentage')
        discount_type = {'percentage': 'percent', 'fixed': 'flat'}.get(discount_type, discount_type)
        discount_value = Decimal(request.POST.get('discount_value', '10.00'))
        min_order = Decimal(request.POST.get('min_order', '499.00'))
        max_uses_raw = request.POST.get('max_uses', '')
        max_uses = int(max_uses_raw) if max_uses_raw and max_uses_raw.isdigit() else 0

        if code:
            Coupon.objects.create(
                code=code,
                discount_type=discount_type,
                discount_value=discount_value,
                min_order_amount=min_order,
                max_uses=max_uses,
                is_active=True,
            )
            messages.success(request, f"Coupon '{code}' created!")
            return redirect("admin_panel:coupons")

    coupon_list = Coupon.objects.all().order_by('-created_at')
    context = {
        'current_panel': 'admin',
        'active_menu': 'coupons',
        'coupons': coupon_list,
    }
    return render(request, "admin_panel/coupons.html", context)


def offers(request):
    banners = OfferBanner.objects.all().order_by('-created_at')
    context = {
        'current_panel': 'admin',
        'active_menu': 'offers',
        'banners': banners,
    }
    return render(request, "admin_panel/offers.html", context)


def banners(request):
    return offers(request)


# =========================================
# REVIEWS
# =========================================

def reviews(request):
    product_reviews = Review.objects.select_related('customer', 'product', 'order').order_by('-created_at')
    delivery_reviews = DeliveryRating.objects.select_related('customer', 'delivery_partner__user', 'order').order_by('-created_at')
    context = {
        'current_panel': 'admin',
        'active_menu': 'reviews',
        'reviews': product_reviews,
        'product_reviews': product_reviews,
        'delivery_reviews': delivery_reviews,
    }
    return render(request, "admin_panel/reviews.html", context)


# =========================================
# REPORTS & ANALYTICS
# =========================================

def reports(request):
    orders = Order.objects.select_related('seller', 'customer').all().order_by('-created_at')
    revenue = orders.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
    commission = orders.aggregate(total=Sum('admin_commission_amount'))['total'] or Decimal('0.00')
    category_rows = list(orders.filter(status='delivered').values('items__product__category__name').annotate(total=Sum('grand_total')).order_by('-total')[:6])
    category_labels = [row['items__product__category__name'] or 'Uncategorised' for row in category_rows] or ['No sales yet']
    category_values = [float(row['total'] or 0) for row in category_rows] or [1]
    status_rows = list(orders.values('status').annotate(
        total=Count('id'), revenue=Sum('grand_total'), commission=Sum('admin_commission_amount')
    ).order_by('-total'))
    context = {
        'current_panel': 'admin',
        'active_menu': 'reports',
        'total_orders': orders.count(),
        'revenue': revenue,
        'commission': commission,
        'delivered_orders': orders.filter(status='delivered').count(),
        'chart_status_labels': json.dumps([row['status'].replace('_', ' ').title() for row in status_rows] or ['No orders']),
        'chart_status_values': json.dumps([row['total'] for row in status_rows] or [0]),
        'chart_revenue_values': json.dumps([float(row['revenue'] or 0) for row in status_rows] or [0]),
        'chart_commission_values': json.dumps([float(row['commission'] or 0) for row in status_rows] or [0]),
        'chart_category_labels': json.dumps(category_labels),
        'chart_category_values': json.dumps(category_values),
    }
    return render(request, "admin_panel/reports.html", context)


def export_report(request, report_type):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="shopverse-{report_type}-report.csv"'
    writer = csv.writer(response)

    if report_type == 'commission':
        writer.writerow(['Order Number', 'Seller', 'Gross Total', 'Admin Commission', 'Status', 'Created At'])
        rows = Order.objects.select_related('seller').order_by('-created_at')
        for order in rows:
            writer.writerow([order.order_number, order.seller.store_name, order.grand_total, order.admin_commission_amount, order.status, order.created_at])
    elif report_type == 'tax':
        writer.writerow(['Order Number', 'Customer', 'Subtotal', 'Tax', 'Grand Total', 'Payment Status', 'Created At'])
        for order in Order.objects.select_related('customer').order_by('-created_at'):
            writer.writerow([order.order_number, order.customer_name, order.subtotal, order.tax, order.grand_total, order.payment_status, order.created_at])
    elif report_type == 'fleet':
        writer.writerow(['Order Number', 'Delivery Partner', 'Delivery Earning', 'Status', 'Delivered At'])
        rows = Order.objects.select_related('delivery_partner__user').order_by('-created_at')
        for order in rows:
            rider = order.delivery_partner.user.get_full_name() if order.delivery_partner else 'Unassigned'
            writer.writerow([order.order_number, rider, order.delivery_partner_earning, order.status, order.created_at])
    else:
        writer.writerow(['Error'])
        writer.writerow(['Unknown report type'])
    return response


def analytics(request):
    context = {
        'current_panel': 'admin',
        'active_menu': 'analytics',
    }
    return render(request, "admin_panel/analytics.html", context)


def live_operations(request):
    riders = DeliveryPartnerProfile.objects.select_related('user').all()
    riders_json = json.dumps([
        {
            'id': rider.id,
            'name': rider.user.get_full_name() or rider.user.username,
            'vehicle_number': rider.vehicle_number,
            'rating': float(rider.rating),
            'is_online': rider.is_online,
            'lat': float(rider.current_lat),
            'lng': float(rider.current_lng),
            'status': 'ONLINE' if rider.is_online else 'OFFLINE',
        }
        for rider in riders
    ])
    active_deliveries = Order.objects.filter(status__in=['shipped', 'out_for_delivery']).select_related('delivery_partner', 'customer')
    context = {
        'current_panel': 'admin',
        'active_menu': 'live_operations',
        'riders': riders,
        'riders_json': riders_json,
        'deliveries': active_deliveries,
    }
    return render(request, "admin_panel/live-operations.html", context)


# =========================================
# SUPPORT & TICKETS
# =========================================

def support(request):
    return tickets(request)


def tickets(request):
    ticket_list = SupportTicket.objects.select_related('user').order_by('-created_at')
    ticket_type = request.GET.get('type', 'all')
    role_by_type = {'customer': 'customer', 'seller': 'seller', 'rider': 'delivery'}
    if ticket_type in role_by_type:
        ticket_list = ticket_list.filter(user__role=role_by_type[ticket_type])
    else:
        ticket_type = 'all'

    if request.method == "POST":
        ticket_id = request.POST.get('ticket_id')
        status = request.POST.get('status', 'resolved')
        redirect_type = request.POST.get('ticket_type', ticket_type)
        if redirect_type not in {'all', 'customer', 'seller', 'rider'}:
            redirect_type = 'all'
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
        ticket.status = status
        ticket.save()
        messages.success(request, f"Ticket #{ticket.ticket_id} updated to {status.upper()}.")
        redirect_url = request.path if redirect_type == 'all' else f'{request.path}?type={redirect_type}'
        return redirect(redirect_url)

    context = {
        'current_panel': 'admin',
        'active_menu': 'tickets',
        'tickets': ticket_list,
        'ticket_type': ticket_type,
    }
    return render(request, "admin_panel/tickets.html", context)


# =========================================
# ADMINS & ROLES
# =========================================

def admins(request):
    admin_users = User.objects.filter(role='admin').order_by('-date_joined')
    context = {
        'current_panel': 'admin',
        'active_menu': 'admins',
        'admins': admin_users,
    }
    return render(request, "admin_panel/admins.html", context)


def roles_permissions(request):
    context = {
        'current_panel': 'admin',
        'active_menu': 'roles_permissions',
    }
    return render(request, "admin_panel/roles-permissions.html", context)


# =========================================
# AI ASSISTANT
# =========================================

def ai_assistant(request):
    context = {
        'current_panel': 'admin',
        'active_menu': 'ai_assistant',
    }
    return render(request, "admin_panel/ai-assistant.html", context)


# =========================================
# SETTINGS
# =========================================

def settings(request):
    if not request.user.is_authenticated or request.user.role != 'admin':
        return HttpResponseForbidden()

    marketplace_settings, _ = MarketplaceSettings.objects.get_or_create(pk=1)
    form = MarketplaceSettingsForm(instance=marketplace_settings)
    faq_form = FAQItemForm()
    edit_open = False

    if request.method == 'POST':
        action = request.POST.get('action', 'settings')
        if action == 'faq_delete':
            FAQItem.objects.filter(pk=request.POST.get('faq_id')).delete()
            messages.success(request, 'FAQ deleted successfully.')
            return redirect('admin_panel:settings')
        if action == 'faq_save':
            faq = FAQItem.objects.filter(pk=request.POST.get('faq_id')).first() if request.POST.get('faq_id') else None
            faq_form = FAQItemForm(request.POST, instance=faq)
            if faq_form.is_valid():
                faq_form.save()
                messages.success(request, 'FAQ saved successfully.')
                return redirect('admin_panel:settings')
            messages.error(request, 'Please correct the FAQ errors below.')
        else:
            form = MarketplaceSettingsForm(request.POST, request.FILES, instance=marketplace_settings)
            if form.is_valid():
                form.save()
                messages.success(request, 'Homepage and marketplace settings updated successfully.')
                return redirect('admin_panel:settings')
            messages.error(request, 'Please correct the errors below.')
            edit_open = True

    context = {
        'current_panel': 'admin',
        'active_menu': 'settings',
        'marketplace_settings': marketplace_settings,
        'settings_form': form,
        'settings_edit_open': edit_open,
        'faq_form': faq_form,
        'faq_items': FAQItem.objects.all(),
    }
    return render(request, "admin_panel/settings.html", context)


def marketplace_content(request):
    if not request.user.is_authenticated or request.user.role != 'admin':
        return HttpResponseForbidden()

    marketplace_settings, _ = MarketplaceSettings.objects.get_or_create(pk=1)
    content_form = MarketplaceContentForm(instance=marketplace_settings)
    featured_products_form = FeaturedProductsForm(instance=marketplace_settings)
    hero_slides_form = HomepageHeroSlidesForm()
    hero_slides = list(HomepageHeroSlide.objects.all())
    featured_product_code_rows = marketplace_settings.featured_product_codes.splitlines() or ['', '']
    faq_form = FAQItemForm()

    if request.method == 'POST':
        action = request.POST.get('action', 'content')
        if action == 'policy_save':
            policy_fields = {'privacy_policy', 'terms_conditions', 'refund_policy', 'shipping_policy', 'cancellation_policy'}
            field = request.POST.get('field')
            if field in policy_fields:
                setattr(marketplace_settings, field, request.POST.get('value', '').strip())
                marketplace_settings.save(update_fields=[field, 'updated_at'])
                messages.success(request, 'Policy updated successfully.')
            return redirect('admin_panel:marketplace_content')
        if action == 'social_save':
            for field in ('facebook_url', 'instagram_url', 'youtube_url', 'twitter_url'):
                setattr(marketplace_settings, field, request.POST.get(field, '').strip())
            marketplace_settings.save(update_fields=['facebook_url', 'instagram_url', 'youtube_url', 'twitter_url', 'updated_at'])
            messages.success(request, 'Social media links updated successfully.')
            return redirect('admin_panel:marketplace_content')
        if action == 'hero_save':
            hero_slides_form = HomepageHeroSlidesForm(request.POST, request.FILES)
            remove_slide_ids = set(request.POST.getlist('remove_hero_slides'))
            removed_slides = [slide for slide in hero_slides if str(slide.pk) in remove_slide_ids]
            retained_slides = [slide for slide in hero_slides if str(slide.pk) not in remove_slide_ids]
            remove_legacy_image = request.POST.get('remove_legacy_hero_image') == '1'

            if hero_slides_form.is_valid():
                uploads = hero_slides_form.cleaned_data['hero_images']
                promote_legacy_image = bool(
                    uploads and not retained_slides and marketplace_settings.hero_image and not remove_legacy_image
                )
                slide_count = len(retained_slides) + len(uploads) + int(promote_legacy_image)
                if slide_count > 10:
                    hero_slides_form.add_error('hero_images', 'Keep no more than 10 hero images in the slideshow.')

            if hero_slides_form.is_valid():
                for slide in removed_slides:
                    slide.image.delete(save=False)
                    slide.delete()

                ordered_slides = []
                for slide in retained_slides:
                    try:
                        requested_order = int(request.POST.get(f'hero_slide_order_{slide.pk}', slide.ordering))
                    except (TypeError, ValueError):
                        requested_order = slide.ordering
                    ordered_slides.append((max(1, min(requested_order, 10)), slide.pk, slide))
                ordered_slides.sort(key=lambda item: (item[0], item[1]))

                for field in ('hero_badge', 'hero_title', 'hero_subtitle'):
                    setattr(marketplace_settings, field, request.POST.get(field, '').strip())

                for position, (_, _, slide) in enumerate(ordered_slides, start=1):
                    slide.ordering = position
                    slide.save(update_fields=['ordering'])

                next_order = len(ordered_slides) + 1
                if promote_legacy_image:
                    HomepageHeroSlide.objects.create(
                        image=marketplace_settings.hero_image.name,
                        ordering=next_order,
                    )
                    marketplace_settings.hero_image = None
                    next_order += 1
                elif remove_legacy_image and marketplace_settings.hero_image:
                    marketplace_settings.hero_image.delete(save=False)

                for image in hero_slides_form.cleaned_data['hero_images']:
                    HomepageHeroSlide.objects.create(image=image, ordering=next_order)
                    next_order += 1

                marketplace_settings.save()
                messages.success(request, 'Homepage hero slideshow updated successfully.')
                return redirect('admin_panel:marketplace_content')
            messages.error(request, 'Please correct the hero slideshow images.')
        if action == 'featured_products_save':
            featured_product_code_rows = request.POST.getlist('item_codes')
            featured_products_data = request.POST.copy()
            featured_products_data['featured_product_codes'] = '\n'.join(featured_product_code_rows)
            featured_products_form = FeaturedProductsForm(featured_products_data, instance=marketplace_settings)
            if featured_products_form.is_valid():
                featured_products_form.save()
                messages.success(request, 'Homepage featured products updated successfully.')
                return redirect('admin_panel:marketplace_content')
            messages.error(request, 'Please correct the featured product codes.')
        elif action == 'faq_delete':
            FAQItem.objects.filter(pk=request.POST.get('faq_id')).delete()
            messages.success(request, 'FAQ deleted successfully.')
            return redirect('admin_panel:marketplace_content')
        elif action == 'faq_save':
            faq = FAQItem.objects.filter(pk=request.POST.get('faq_id')).first() if request.POST.get('faq_id') else None
            faq_form = FAQItemForm(request.POST, instance=faq)
            if faq_form.is_valid():
                faq_form.save()
                messages.success(request, 'FAQ saved successfully.')
                return redirect('admin_panel:marketplace_content')
            messages.error(request, 'Please correct the FAQ errors below.')
        elif action == 'content':
            content_form = MarketplaceContentForm(request.POST, request.FILES, instance=marketplace_settings)
            if content_form.is_valid():
                content_form.save()
                messages.success(request, 'Marketplace content updated successfully.')
                return redirect('admin_panel:marketplace_content')
            messages.error(request, 'Please correct the content errors below.')

    return render(request, 'admin_panel/marketplace-content.html', {
        'current_panel': 'admin',
        'active_menu': 'marketplace_content',
        'marketplace_settings': marketplace_settings,
        'content_form': content_form,
        'hero_slides_form': hero_slides_form,
        'hero_slides': hero_slides,
        'legacy_hero_image': marketplace_settings.hero_image if not hero_slides else None,
        'featured_products_form': featured_products_form,
        'featured_product_code_rows': featured_product_code_rows,
        'faq_form': faq_form,
        'faq_items': FAQItem.objects.all(),
        'policy_rows': [
            ('privacy_policy', 'Privacy Policy', marketplace_settings.privacy_policy),
            ('terms_conditions', 'Terms & Conditions', marketplace_settings.terms_conditions),
            ('refund_policy', 'Refund Policy', marketplace_settings.refund_policy),
            ('shipping_policy', 'Shipping Policy', marketplace_settings.shipping_policy),
            ('cancellation_policy', 'Cancellation Policy', marketplace_settings.cancellation_policy),
        ],
    })