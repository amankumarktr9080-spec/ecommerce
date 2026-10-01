import random
import json
from uuid import uuid4
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.core.files.storage import default_storage
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.utils.text import get_valid_filename
from django.utils import timezone
from django.db.models import Sum, Count, Max, Q, Exists, OuterRef
from django.db.models.functions import TruncMonth

from sellers.models import SellerProfile, SellerProductOffer, PayoutRequest
from sellers.balances import get_seller_earnings_summary
from delivery.models import DeliveryPartnerProfile
from products.models import Product, ProductImage, ProductSpecification
from categories.models import Category, SubCategory, Brand
from orders.models import Order, OrderItem, OrderTimeline
from returns.models import ReturnRequest
from returns.services import (
    ReturnValidationError, approve_request, create_replacement,
    fallback_replacement_to_wallet_refund, inspect_return, mark_picked_up,
    process_return_refund, reject_request, schedule_pickup,
)
from reviews.models import Review
from coupons.models import Coupon
from commissions.models import CommissionLog
from notifications.models import Notification
from support.models import SupportTicket
from users.models import User


def get_current_seller(request):
    """Return only the authenticated seller attached to this request."""
    if request.user.is_authenticated and request.user.role == 'seller':
        return getattr(request.user, 'seller_profile', None)
    return None


def dashboard(request):
    seller = get_current_seller(request)
    seller_orders = Order.objects.filter(seller=seller) if seller else Order.objects.all()

    total_orders = seller_orders.count()
    pending_orders = seller_orders.filter(status__in=['pending', 'confirmed', 'processing']).count()
    completed_orders = seller_orders.filter(status='delivered').count()

    earnings_summary = get_seller_earnings_summary(seller)
    total_gross = earnings_summary['gross_sales']
    total_commission = earnings_summary['admin_commissions']
    net_earnings = earnings_summary['net_earnings']

    recent_orders = seller_orders.order_by('-created_at')[:5]
    low_stock_products = Product.objects.filter(seller=seller, stock__lte=15)[:4] if seller else Product.objects.filter(stock__lte=15)[:4]

    context = {
        'current_panel': 'seller',
        'active_menu': 'dashboard',
        'seller': seller,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'total_gross': total_gross,
        'total_commission': total_commission,
        'net_earnings': net_earnings,
        'pending_earnings': earnings_summary['pending_earnings'],
        'recent_orders': recent_orders,
        'low_stock_products': low_stock_products,
    }
    return render(request, "seller/dashboard.html", context)


def store(request):
    seller = get_current_seller(request)
    if request.method == "POST" and seller and request.POST.get('action') == 'save_profile':
        seller.user.first_name = request.POST.get('first_name', seller.user.first_name).strip()
        seller.user.last_name = request.POST.get('last_name', seller.user.last_name).strip()
        seller.user.phone = request.POST.get('phone', seller.user.phone)
        seller.user.save(update_fields=['first_name', 'last_name', 'phone'])
        for field in (
            'store_name', 'phone', 'email', 'business_address', 'city', 'state', 'pincode',
            'gst_number', 'pan_number', 'description', 'bank_name', 'account_number', 'ifsc_code', 'upi_id',
        ):
            setattr(seller, field, request.POST.get(field, getattr(seller, field)))
        seller.save()
        messages.success(request, "Profile details updated successfully!")
        return redirect("seller:store")

    context = {
        'current_panel': 'seller',
        'active_menu': 'store',
        'seller': seller,
        'profile_edit_open': request.GET.get('show') == 'edit',
        'profile_password_open': request.GET.get('show') == 'password',
    }
    return render(request, "seller/store.html", context)


def products(request):
    seller = get_current_seller(request)
    my_products = Product.objects.filter(seller=seller).order_by('-created_at') if seller else Product.objects.all().order_by('-created_at')
    query = request.GET.get('q', '').strip()
    search_term = query
    prefix, separator, value = query.partition(':')
    if separator and prefix.strip().lower() in {'code', 'sku'}:
        search_term = value.strip()

    if request.GET.get('suggestions') == '1':
        if not search_term:
            return JsonResponse({'results': []})
        matches = my_products.filter(is_active=True).filter(
            Q(title__icontains=search_term) |
            Q(item_code__icontains=search_term) |
            Q(sku__icontains=search_term) |
            Q(description__icontains=search_term) |
            Q(category__name__icontains=search_term) |
            Q(brand__name__icontains=search_term)
        ).select_related('brand')[:6]
        return JsonResponse({'results': [
            {
                'id': product.id,
                'title': product.title,
                'brand': product.brand.name if product.brand else '',
                'item_code': product.item_code,
                'price': str(product.selling_price),
                'image': product.main_image_url,
            }
            for product in matches
        ]})

    if search_term:
        my_products = my_products.filter(
            Q(title__icontains=search_term) |
            Q(item_code__icontains=search_term) |
            Q(sku__icontains=search_term) |
            Q(description__icontains=search_term) |
            Q(category__name__icontains=search_term) |
            Q(brand__name__icontains=search_term)
        )

    # Delete product handler
    if request.method == "POST" and request.POST.get('action') == 'delete':
        prod_id = request.POST.get('product_id')
        Product.objects.filter(id=prod_id, seller=seller).delete()
        messages.info(request, "Product deleted successfully.")
        return redirect("/seller/products/")

    context = {
        'current_panel': 'seller',
        'active_menu': 'products',
        'seller': seller,
        'products': my_products,
        'search_query': query,
    }
    return render(request, "seller/products.html", context)


def product_details(request, product_id):
    seller = get_current_seller(request)
    product = get_object_or_404(Product, id=product_id, seller=seller) if seller else get_object_or_404(Product, id=product_id)
    context = {
        'current_panel': 'seller',
        'active_menu': 'products',
        'product': product,
    }
    return render(request, "seller/product-details.html", context)


def add_product(request):
    seller = get_current_seller(request)
    categories = Category.objects.filter(is_active=True).order_by('name')
    subcategories = SubCategory.objects.select_related('category').filter(category__is_active=True).order_by('name')
    brands = Brand.objects.select_related('subcategory__category').filter(subcategory__category__is_active=True).order_by('name')

    if request.method == "POST":
        title = request.POST.get('title')
        cat_id = request.POST.get('category_id')
        subcategory_id = request.POST.get('subcategory_id', '').strip()
        brand_id = request.POST.get('brand_id', '').strip()
        category_obj = categories.filter(id=cat_id).first()
        if not category_obj:
            messages.error(request, 'Choose a valid product category.')
            return redirect('/seller/products/add/')
        subcategory_obj = None
        if subcategory_id:
            subcategory_obj = SubCategory.objects.filter(id=subcategory_id, category=category_obj).first()
            if not subcategory_obj:
                messages.error(request, 'Choose a subcategory from the selected category.')
                return redirect('/seller/products/add/')
        brand_obj = None
        if brand_id:
            if not subcategory_obj:
                messages.error(request, 'Choose a subcategory before choosing a brand.')
                return redirect('/seller/products/add/')
            brand_obj = Brand.objects.filter(id=brand_id, subcategory=subcategory_obj).first()
            if not brand_obj:
                messages.error(request, 'Choose a brand from the selected subcategory.')
                return redirect('/seller/products/add/')
        base_price = Decimal(request.POST.get('base_price', '1000'))
        delivery_charge = Decimal(request.POST.get('delivery_charge', '50'))
        stock = int(request.POST.get('stock', '20'))
        description = request.POST.get('description', '')
        image_url = request.POST.get('image_url', 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600')

        # Return & Replacement options defined by Seller
        is_returnable = request.POST.get('is_returnable') == 'on'
        return_days = int(request.POST.get('return_window_days', '7')) if is_returnable else 0
        is_replaceable = request.POST.get('is_replaceable') == 'on'
        replace_days = int(request.POST.get('replacement_window_days', '7')) if is_replaceable else 0

        # Unique Item Code
        cat_prefix = category_obj.name[:4].upper()
        item_code = f"ITM-{cat_prefix}-{random.randint(1000, 9999)}"

        # 10% Platform Commission Formula:
        admin_comm = round(base_price * Decimal("0.10"), 2)
        tax = round(base_price * Decimal("0.05"), 2)
        selling_price = base_price + admin_comm + delivery_charge + tax
        mrp = round(selling_price * Decimal("1.3"), 2)

        prod = Product.objects.create(
            seller=seller,
            title=title,
            slug=f"prod-{random.randint(1000, 9999)}",
            sku=f"SKU-{random.randint(10000, 99999)}",
            item_code=item_code,
            category=category_obj,
            subcategory=subcategory_obj,
            brand=brand_obj,
            base_price=base_price,
            admin_commission_percentage=Decimal("10.00"),
            delivery_charge=delivery_charge,
            tax_percentage=Decimal("5.00"),
            selling_price=selling_price,
            mrp=mrp,
            stock=stock,
            description=description,
            main_image_url=image_url,
            is_returnable=is_returnable,
            return_window_days=return_days,
            is_replaceable=is_replaceable,
            replacement_window_days=replace_days,
        )

        ProductSpecification.objects.create(product=prod, group_name="General", name="Model Code", value=item_code)
        ProductSpecification.objects.create(product=prod, group_name="General", name="Warranty", value="1 Year Brand Warranty")

        messages.success(request, f"Product listed successfully with Unique Code: {item_code}! Selling Price set to ₹{selling_price}.")
        return redirect("/seller/products/")

    context = {
        'current_panel': 'seller',
        'active_menu': 'products',
        'categories': categories,
        'brands': brands,
        'subcategories': subcategories,
    }
    return render(request, "seller/add-product.html", context)


def edit_product(request, product_id):
    seller = get_current_seller(request)
    product = get_object_or_404(Product, id=product_id, seller=seller)
    categories = Category.objects.filter(is_active=True)
    brands = Brand.objects.select_related('subcategory__category').filter(subcategory__category__is_active=True).order_by('name')
    subcategories = SubCategory.objects.select_related('category').filter(category__is_active=True).order_by('name')

    if request.method == "POST":
        gallery_uploads = request.FILES.getlist('gallery_image_files')
        remove_gallery_ids = [
            image_id for image_id in request.POST.getlist('remove_gallery_image_ids')
            if str(image_id).isdigit()
        ]
        remaining_gallery_count = product.gallery_images.exclude(id__in=remove_gallery_ids).count()
        if remaining_gallery_count + len(gallery_uploads) > 3 or any(
            not image.content_type.startswith('image/') or image.size > 5 * 1024 * 1024
            for image in gallery_uploads
        ):
            messages.error(request, 'Keep up to 3 gallery images total; each image must be smaller than 5 MB.')
            return redirect(f'/seller/products/{product.id}/edit/')

        product.title = request.POST.get('title', product.title)
        category_id = request.POST.get('category_id')
        category = categories.filter(id=category_id).first() if category_id else product.category
        if category:
            product.category = category
        elif category_id:
            messages.error(request, 'Choose a valid product category.')
            return redirect(f'/seller/products/{product.id}/edit/')
        subcategory_id = request.POST.get('subcategory_id')
        product.subcategory = None
        if subcategory_id:
            product.subcategory = SubCategory.objects.filter(id=subcategory_id, category=product.category).first()
            if not product.subcategory:
                messages.error(request, 'Choose a subcategory from the selected category.')
                return redirect(f'/seller/products/{product.id}/edit/')
        brand_id = request.POST.get('brand_id')
        product.brand = None
        if brand_id:
            product.brand = Brand.objects.filter(id=brand_id, subcategory__category=product.category).first()
            if not product.brand:
                messages.error(request, 'Choose a brand from the selected category.')
                return redirect(f'/seller/products/{product.id}/edit/')
        product.base_price = Decimal(request.POST.get('base_price', product.base_price))
        product.delivery_charge = Decimal(request.POST.get('delivery_charge', product.delivery_charge))
        product.stock = int(request.POST.get('stock', product.stock))
        product.description = request.POST.get('description', product.description)
        image_url = request.POST.get('image_url', '').strip()
        if image_url:
            product.main_image_url = image_url
        if request.POST.get('remove_main_image') == '1':
            product.main_image_url = ''
        main_image_file = request.FILES.get('main_image_file')
        if main_image_file:
            if not main_image_file.content_type.startswith('image/') or main_image_file.size > 5 * 1024 * 1024:
                messages.error(request, 'Choose an image smaller than 5 MB.')
                return redirect(f'/seller/products/{product.id}/edit/')
            safe_name = get_valid_filename(main_image_file.name)[:120]
            saved_name = default_storage.save(f'products/{product.id}/{safe_name}', main_image_file)
            product.main_image_url = default_storage.url(saved_name)

        product.gallery_images.filter(id__in=remove_gallery_ids).delete()
        for gallery_image in gallery_uploads:
            safe_name = get_valid_filename(gallery_image.name)[:120]
            saved_name = default_storage.save(f'products/{product.id}/gallery/{safe_name}', gallery_image)
            ProductImage.objects.create(product=product, image_url=default_storage.url(saved_name))
        product.mrp = Decimal(request.POST.get('mrp', product.mrp))
        product.is_active = request.POST.get('is_active') == 'on'
        product.is_featured = request.POST.get('is_featured') == 'on'
        product.is_flash_sale = request.POST.get('is_flash_sale') == 'on'

        product.is_returnable = request.POST.get('is_returnable') == 'on'
        product.return_window_days = int(request.POST.get('return_window_days', product.return_window_days))
        product.is_replaceable = request.POST.get('is_replaceable') == 'on'
        product.replacement_window_days = int(request.POST.get('replacement_window_days', product.replacement_window_days))

        comm = round(product.base_price * product.admin_commission_percentage / Decimal('100'), 2)
        tax = round(product.base_price * product.tax_percentage / Decimal('100'), 2)
        product.selling_price = product.base_price + comm + product.delivery_charge + tax
        product.discount_percentage = (
            round((product.mrp - product.selling_price) / product.mrp * Decimal('100'))
            if product.mrp > product.selling_price else Decimal('0.00')
        )
        active_offer = SellerProductOffer.objects.filter(product=product).first()
        if active_offer:
            active_offer.original_price = product.selling_price
            if active_offer.discount_type == 'percent':
                product.selling_price *= (Decimal('100') - active_offer.discount_value) / Decimal('100')
            elif active_offer.discount_value < product.selling_price:
                product.selling_price -= active_offer.discount_value
            else:
                active_offer.delete()
                active_offer = None
                messages.warning(request, 'The offer was removed because the new price is too low for its discount.')
            if active_offer:
                product.selling_price = product.selling_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                active_offer.save(update_fields=['original_price', 'updated_at'])
        product.save()

        messages.success(request, f"Product {product.item_code} updated successfully!")
        return redirect("/seller/products/")

    context = {
        'current_panel': 'seller',
        'active_menu': 'products',
        'product': product,
        'categories': categories,
        'brands': brands,
        'subcategories': subcategories,
    }
    return render(request, "seller/edit-product.html", context)


def categories(request):
    cats = Category.objects.filter(is_active=True)
    context = {
        'current_panel': 'seller',
        'active_menu': 'categories',
        'categories': cats,
    }
    return render(request, "seller/categories.html", context)


def inventory(request):
    seller = get_current_seller(request)

    if request.method == "POST" and request.POST.get('action') == 'update_stock':
        prod_id = request.POST.get('product_id')
        new_stock = int(request.POST.get('stock', 0))
        Product.objects.filter(id=prod_id, seller=seller).update(stock=new_stock)
        messages.success(request, "Stock quantity updated!")
        return redirect("/seller/inventory/")

    my_products = Product.objects.filter(seller=seller) if seller else Product.objects.all()
    context = {
        'current_panel': 'seller',
        'active_menu': 'inventory',
        'products': my_products,
    }
    return render(request, "seller/inventory.html", context)


def orders(request):
    seller = get_current_seller(request)
    orders_qs = Order.objects.filter(seller=seller).order_by('-created_at') if seller else Order.objects.all().order_by('-created_at')
    orders_qs = orders_qs.annotate(
        has_reschedule=Exists(
            OrderTimeline.objects.filter(order_id=OuterRef('pk'), title='Delivery Rescheduled')
        )
    )

    if request.method == "POST":
        order_id = request.POST.get('order_id')
        action = request.POST.get('action')
        new_status = request.POST.get('status')
        order = get_object_or_404(Order, id=order_id, seller=seller)

        if action == 'assign_delivery':
            if order.status not in ['packed', 'shipped']:
                messages.error(request, 'Pack or ship the order before assigning a delivery partner.')
                return redirect('/seller/orders/')
            rider = get_object_or_404(
                DeliveryPartnerProfile,
                id=request.POST.get('delivery_partner_id'),
                is_approved=True,
            )
            order.delivery_partner = rider
            order.save(update_fields=['delivery_partner', 'updated_at'])
            OrderTimeline.objects.create(
                order=order,
                status=order.status,
                title='Delivery Partner Assigned by Seller',
                description=f'Assigned to {rider.user.get_full_name() or rider.user.username}.',
            )
            messages.success(request, f'{rider.user.get_full_name() or rider.user.username} assigned to Order #{order.order_number}.')
            return redirect('/seller/orders/')

        order.status = new_status
        order.save()

        status_titles = {
            'confirmed': 'Order Accepted by Seller',
            'packed': 'Order Packed & Boxed',
            'shipped': 'Order Shipped to Logistics Hub',
        }
        OrderTimeline.objects.create(
            order=order,
            status=new_status,
            title=status_titles.get(new_status, f'Status changed to {new_status}'),
            description=f'Vendor updated order status to {new_status}.'
        )
        messages.success(request, f"Order #{order.order_number} status updated to {new_status.upper()}!")
        return redirect("/seller/orders/")

    context = {
        'current_panel': 'seller',
        'active_menu': 'orders',
        'orders': orders_qs,
        'delivery_partners': DeliveryPartnerProfile.objects.filter(is_approved=True).select_related('user').order_by('-is_online', '-rating'),
    }
    return render(request, "seller/orders.html", context)


def order_details(request, order_id):
    seller = get_current_seller(request)
    order = get_object_or_404(Order, id=order_id)
    items = order.items.select_related('product').all()
    timeline = order.timeline.all().order_by('timestamp')

    context = {
        'current_panel': 'seller',
        'active_menu': 'orders',
        'order': order,
        'items': items,
        'timeline': timeline,
    }
    return render(request, "seller/order-details.html", context)


def shipping(request):
    seller = get_current_seller(request)
    shipped_orders = Order.objects.filter(seller=seller, status__in=['packed', 'shipped', 'out_for_delivery']).order_by('-created_at') if seller else Order.objects.filter(status__in=['packed', 'shipped', 'out_for_delivery'])
    context = {
        'current_panel': 'seller',
        'active_menu': 'shipping',
        'orders': shipped_orders,
    }
    return render(request, "seller/shipping.html", context)


def returns(request):
    seller = get_current_seller(request)
    if seller is None:
        return HttpResponseForbidden()

    if request.method == "POST":
        ret_id = request.POST.get('return_id')
        decision = request.POST.get('decision') or request.POST.get('action')
        remarks = request.POST.get('remarks', '')
        allowed_statuses = {
            'approved': ['pending'],
            'rejected': ['pending'],
            'schedule_pickup': ['approved'],
            'picked_up': ['approved', 'pickup_scheduled'],
            'inspect_pass': ['item_picked_up'],
            'inspect_fail': ['item_picked_up'],
            'refund': ['inspection_passed'],
            'replace': ['inspection_passed'],
            'replacement_refund': ['replacement_failed'],
        }.get(decision, [])

        ret = get_object_or_404(
            ReturnRequest,
            id=ret_id,
            order__seller=seller,
            status__in=allowed_statuses,
        )
        try:
            if decision == 'approved':
                approve_request(ret.id, remarks=remarks)
            elif decision == 'rejected':
                reject_request(ret.id, remarks=remarks)
            elif decision == 'picked_up':
                mark_picked_up(ret.id)
            elif decision == 'schedule_pickup':
                pickup_partner = DeliveryPartnerProfile.objects.filter(
                    id=request.POST.get('pickup_partner_id'), is_approved=True,
                ).first()
                schedule_pickup(
                    ret.id, pickup_partner=pickup_partner,
                    tracking_id=request.POST.get('pickup_tracking_id', ''),
                )
            elif decision == 'inspect_pass':
                inspect_return(ret.id, passed=True, remarks=remarks)
            elif decision == 'inspect_fail':
                inspect_return(ret.id, passed=False, remarks=remarks)
            elif decision == 'refund':
                processed, refund_amount = process_return_refund(ret.id)
                messages.success(request, f'Refund of ₹{refund_amount} credited to customer wallet.') if processed else messages.info(request, 'Refund was already processed.')
            elif decision == 'replace':
                replacement = create_replacement(ret.id)
                if replacement is None:
                    messages.info(request, 'Replacement stock is unavailable. Issue a wallet refund from this request.')
            elif decision == 'replacement_refund':
                fallback_replacement_to_wallet_refund(ret.id)
            else:
                raise ReturnValidationError('Unknown return action.')
        except ReturnValidationError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f'Return request updated: {decision}.')

        return redirect("/seller/returns/")

    my_returns = ReturnRequest.objects.filter(order__seller=seller).select_related('order_item__product').order_by('-created_at')
    context = {
        'current_panel': 'seller',
        'active_menu': 'returns',
        'returns': my_returns,
        'pickup_partners': DeliveryPartnerProfile.objects.filter(is_approved=True).select_related('user').order_by('user__username'),
    }
    return render(request, "seller/returns.html", context)


def earnings(request):
    seller = get_current_seller(request)
    earnings_summary = get_seller_earnings_summary(seller)
    gross_sales = earnings_summary['gross_sales']
    admin_commissions = earnings_summary['admin_commissions']
    net_earnings = earnings_summary['net_earnings']
    pending_earnings = earnings_summary['pending_earnings']
    available_payout = earnings_summary['available_payout']

    if request.method == 'POST' and seller:
        if available_payout <= 0:
            messages.error(request, 'No earnings are currently available for payout.')
        elif not seller.bank_name and not seller.upi_id:
            messages.error(request, 'Add bank or UPI payout details before requesting a transfer.')
        else:
            PayoutRequest.objects.create(
                seller=seller,
                amount=available_payout,
                bank_name=seller.bank_name,
                account_number=seller.account_number,
                upi_id=seller.upi_id,
            )
            messages.success(request, f'Payout request of ₹{available_payout:.2f} sent to Admin for review.')
        return redirect('/seller/earnings/')

    commission_logs = CommissionLog.objects.filter(order__seller=seller).order_by('-created_at') if seller else CommissionLog.objects.all().order_by('-created_at')

    context = {
        'current_panel': 'seller',
        'active_menu': 'earnings',
        'seller': seller,
        'gross_sales': gross_sales,
        'admin_commissions': admin_commissions,
        'net_earnings': net_earnings,
        'pending_earnings': pending_earnings,
        'wallet_balance': available_payout,
        'available_payout': available_payout,
        'payout_requests': PayoutRequest.objects.filter(seller=seller) if seller else PayoutRequest.objects.none(),
        'commission_logs': commission_logs,
    }
    return render(request, "seller/earnings.html", context)


def reviews(request):
    seller = get_current_seller(request)

    if request.method == "POST":
        rev_id = request.POST.get('review_id')
        reply_text = request.POST.get('seller_reply', '').strip()
        Review.objects.filter(id=rev_id).update(seller_reply=reply_text)
        messages.success(request, "Your reply has been published to the customer!")
        return redirect("/seller/reviews/")

    product_reviews = Review.objects.filter(product__seller=seller).order_by('-created_at') if seller else Review.objects.all().order_by('-created_at')
    context = {
        'current_panel': 'seller',
        'active_menu': 'reviews',
        'reviews': product_reviews,
    }
    return render(request, "seller/reviews.html", context)


@login_required(login_url='/auth/login/')
def offers(request):
    if request.user.role != 'seller':
        return HttpResponseForbidden()

    seller = SellerProfile.objects.filter(user=request.user).first()
    if seller is None:
        return HttpResponseForbidden()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            offer = get_object_or_404(
                SellerProductOffer.objects.select_related('product'),
                id=request.POST.get('offer_id'),
                product__seller=seller,
            )
            product = offer.product
            product.selling_price = offer.original_price
            product.save(update_fields=['selling_price', 'discount_percentage'])
            offer.delete()
            messages.success(request, 'Offer removed and product price restored.')
            return redirect('/seller/offers/')

        if action in {'create', 'update'}:
            try:
                discount_value = Decimal(request.POST.get('discount_value', '').strip())
            except (InvalidOperation, AttributeError):
                discount_value = Decimal('0')

            discount_type = request.POST.get('discount_type')
            title = request.POST.get('title', '').strip()
            if not title or len(title) > 150 or discount_value <= 0 or discount_type not in {'percent', 'flat'}:
                messages.error(request, 'Enter an offer name and a valid discount.')
                return redirect('/seller/offers/')

            if action == 'create':
                product = get_object_or_404(
                    Product.objects.filter(seller=seller, seller_offer__isnull=True),
                    id=request.POST.get('product_id'),
                )
                original_price = product.selling_price
                offer = SellerProductOffer(product=product, original_price=original_price)
            else:
                offer = get_object_or_404(
                    SellerProductOffer.objects.select_related('product'),
                    id=request.POST.get('offer_id'),
                    product__seller=seller,
                )
                original_price = offer.original_price

            if (discount_type == 'percent' and discount_value >= 100) or (
                discount_type == 'flat' and discount_value >= original_price
            ):
                messages.error(request, 'Discount must leave a positive product price.')
                return redirect('/seller/offers/')

            if discount_type == 'percent':
                new_price = original_price * (Decimal('100') - discount_value) / Decimal('100')
            else:
                new_price = original_price - discount_value
            new_price = new_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if new_price <= 0:
                messages.error(request, 'Discount must leave a positive product price.')
                return redirect('/seller/offers/')

            offer.title = title
            offer.discount_type = discount_type
            offer.discount_value = discount_value
            offer.save()
            product = offer.product
            product.selling_price = new_price
            product.save(update_fields=['selling_price', 'discount_percentage'])
            messages.success(request, 'Product offer saved.')
            return redirect('/seller/offers/')

        messages.error(request, 'Invalid offer action.')
        return redirect('/seller/offers/')

    offers_list = SellerProductOffer.objects.filter(product__seller=seller).select_related('product')
    available_products = Product.objects.filter(seller=seller, seller_offer__isnull=True).order_by('title')
    context = {
        'current_panel': 'seller',
        'active_menu': 'offers',
        'offers': offers_list,
        'available_products': available_products,
    }
    return render(request, "seller/offers.html", context)


@login_required(login_url='/auth/login/')
def customers(request):
    if request.user.role != 'seller':
        return HttpResponseForbidden()

    seller = SellerProfile.objects.filter(user=request.user).first()
    if seller is None:
        return HttpResponseForbidden()

    seller_orders = Q(customer_orders__seller=seller)
    my_customers = User.objects.filter(
        role='customer',
        customer_orders__seller=seller,
    ).annotate(
        total_orders=Count('customer_orders', filter=seller_orders, distinct=True),
        total_spent=Sum(
            'customer_orders__grand_total',
            filter=Q(customer_orders__seller=seller, customer_orders__status='delivered'),
        ),
        last_order_date=Max('customer_orders__created_at', filter=seller_orders),
    ).distinct().order_by('-last_order_date', 'first_name', 'last_name')
    context = {
        'current_panel': 'seller',
        'active_menu': 'customers',
        'customers': my_customers,
    }
    return render(request, "seller/customers.html", context)


def reports(request):
    seller = get_current_seller(request)
    seller_orders = Order.objects.filter(seller=seller) if seller else Order.objects.all()
    delivered_orders = seller_orders.filter(status='delivered', payment_status='paid')
    gross_sales = delivered_orders.aggregate(total=Sum('subtotal'))['total'] or Decimal('0.00')
    commissions = delivered_orders.aggregate(total=Sum('admin_commission_amount'))['total'] or Decimal('0.00')
    net_earnings = delivered_orders.aggregate(total=Sum('seller_net_earnings'))['total'] or Decimal('0.00')
    units_sold = OrderItem.objects.filter(order__in=delivered_orders).aggregate(total=Sum('quantity'))['total'] or 0

    monthly_rows = list(delivered_orders.annotate(month=TruncMonth('created_at')).values('month').annotate(
        sales=Sum('subtotal'), net=Sum('seller_net_earnings'), orders=Count('id')
    ).order_by('month'))[-6:]
    month_labels = [row['month'].strftime('%b %Y') for row in monthly_rows]
    monthly_sales = [float(row['sales'] or 0) for row in monthly_rows]
    monthly_net = [float(row['net'] or 0) for row in monthly_rows]
    if not monthly_rows:
        month_labels = ['Current Period']
        monthly_sales = [float(gross_sales)]
        monthly_net = [float(net_earnings)]

    category_rows = list(delivered_orders.values('items__product__category__name').annotate(
        revenue=Sum('subtotal')
    ).order_by('-revenue')[:6])
    category_labels = [row['items__product__category__name'] or 'Uncategorised' for row in category_rows]
    category_values = [float(row['revenue'] or 0) for row in category_rows]
    if not category_rows:
        category_labels, category_values = ['No sales yet'], [1]

    status_rows = seller_orders.values('status').annotate(total=Count('id')).order_by('-total')
    status_labels = [row['status'].replace('_', ' ').title() for row in status_rows]
    status_values = [row['total'] for row in status_rows]
    product_rows = list(OrderItem.objects.filter(order__in=delivered_orders).values(
        'product__title'
    ).annotate(units=Sum('quantity')).order_by('-units')[:5])
    product_labels = [row['product__title'][:24] for row in product_rows]
    product_values = [row['units'] for row in product_rows]
    if not product_rows:
        product_labels, product_values = ['No products yet'], [0]

    context = {
        'current_panel': 'seller',
        'active_menu': 'reports',
        'total_orders': seller_orders.count(),
        'delivered_orders': delivered_orders.count(),
        'cancelled_orders': seller_orders.filter(status='cancelled').count(),
        'gross_sales': gross_sales,
        'net_earnings': net_earnings,
        'admin_commissions': commissions,
        'wallet_balance': net_earnings,
        'units_sold': units_sold,
        'return_count': ReturnRequest.objects.filter(order__seller=seller).count() if seller else ReturnRequest.objects.count(),
        'chart_month_labels': json.dumps(month_labels),
        'chart_monthly_sales': json.dumps(monthly_sales),
        'chart_monthly_net': json.dumps(monthly_net),
        'chart_category_labels': json.dumps(category_labels),
        'chart_category_values': json.dumps(category_values),
        'chart_status_labels': json.dumps(status_labels),
        'chart_status_values': json.dumps(status_values),
        'chart_product_labels': json.dumps(product_labels),
        'chart_product_values': json.dumps(product_values),
    }
    return render(request, "seller/reports.html", context)


@login_required(login_url='/auth/login/')
def notifications(request):
    if request.user.role != 'seller':
        return HttpResponseForbidden()

    seller = SellerProfile.objects.filter(user=request.user).first()
    if seller is None:
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
        return redirect('/seller/notifications/')

    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')
    context = {
        'current_panel': 'seller',
        'active_menu': 'notifications',
        'notifications': notifs,
        'unread_count': notifs.filter(is_read=False).count(),
        'seller': seller,
    }
    return render(request, "seller/notifications.html", context)


def settings(request):
    seller = get_current_seller(request)
    context = {
        'current_panel': 'seller',
        'active_menu': 'settings',
        'seller': seller,
    }
    return render(request, "seller/settings.html", context)


def refunds(request):
    return returns(request)


def withdrawals(request):
    return earnings(request)


def supports(request):
    if not request.user.is_authenticated or request.user.role != 'seller':
        return HttpResponseForbidden()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action in {'edit', 'cancel'}:
            ticket = SupportTicket.objects.filter(
                ticket_id=request.POST.get('ticket_id'), user=request.user, status='open'
            ).first()
            if ticket is None:
                messages.error(request, 'Only your open support tickets can be changed.')
            elif action == 'cancel':
                ticket.status = 'cancelled'
                ticket.save(update_fields=['status', 'updated_at'])
                messages.success(request, f'Support ticket #{ticket.ticket_id} cancelled.')
            else:
                subject = request.POST.get('subject', '').strip()
                message = request.POST.get('message', '').strip()
                if not subject or not message or len(subject) > 200:
                    messages.error(request, 'Enter a subject (up to 200 characters) and a message.')
                else:
                    ticket.subject = subject
                    ticket.message = message
                    ticket.save(update_fields=['subject', 'message', 'updated_at'])
                    messages.success(request, f'Support ticket #{ticket.ticket_id} updated.')
            suffix = '?all=1' if request.POST.get('show_all') == '1' else ''
            return redirect(f'/seller/support/{suffix}')

        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        if not subject or not message or len(subject) > 200:
            messages.error(request, 'Enter a subject (up to 200 characters) and a message.')
            return redirect('/seller/support/')

        ticket = SupportTicket.objects.create(
            user=request.user,
            ticket_id=f'SEL-{uuid4().hex[:10].upper()}',
            subject=subject,
            category='Seller Support',
            message=message,
        )
        Notification.objects.bulk_create([
            Notification(
                user=admin,
                title=f'New seller support ticket #{ticket.ticket_id}',
                message=f'{request.user.get_full_name() or request.user.username}: {subject}',
                notification_type='support',
                link='/admin-panel/tickets/?type=seller',
            )
            for admin in User.objects.filter(role='admin', is_active=True)
        ])
        messages.success(request, f'Support ticket #{ticket.ticket_id} submitted successfully.')
        return redirect('/seller/support/')

    ticket_list = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    show_all = request.GET.get('all') == '1'
    context = {
        'current_panel': 'seller',
        'active_menu': 'support',
        'tickets': ticket_list if show_all else ticket_list[:3],
        'ticket_count': ticket_list.count(),
        'show_all_tickets': show_all,
    }
    return render(request, "seller/supports.html", context)

support = supports