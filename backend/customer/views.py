import calendar
import json
import random
import uuid
from collections import OrderedDict
import razorpay
from decimal import Decimal
from django.conf import settings as django_settings
from django.core.files.storage import default_storage
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.utils.text import get_valid_filename
from django.db import transaction
from django.db.models import Exists, OuterRef, Prefetch, Q, Count, Sum

from products.models import Product, ProductImage, ProductSpecification
from categories.models import Category, SubCategory, Brand
from orders.models import Order, OrderItem, OrderTimeline
from cart.models import Cart, CartItem
from wishlist.models import Wishlist, WishlistItem
from returns.models import ReturnRequest
from returns.services import (
    ReturnValidationError, cancel_return_request, create_return_request,
    refund_cancelled_wallet_order,
)
from reviews.models import Review
from delivery.models import DeliveryRating
from coupons.models import Coupon
from commissions.models import CommissionLog
from payments.models import PaymentTransaction
from notifications.models import Notification
from support.models import SupportTicket
from users.models import User, Address


class GuestCartItems(list):
    """List adapter that keeps the existing cart template compatible."""
    def count(self):
        return len(self)


class GuestCartItem:
    def __init__(self, product, quantity):
        self.product = product
        self.quantity = quantity

    def subtotal(self):
        return self.product.selling_price * self.quantity


def get_guest_cart_items(request):
    quantities = request.session.get('guest_cart', {})
    product_ids = [int(product_id) for product_id in quantities]
    products = Product.objects.filter(id__in=product_ids, is_active=True).select_related('seller_offer')
    return GuestCartItems(
        [GuestCartItem(product, int(quantities[str(product.id)]))
         for product in products]
    )


def get_seller_offer_discount(cart_items):
    total = Decimal('0.00')
    for item in cart_items:
        offer = getattr(item.product, 'seller_offer', None)
        if offer:
            total += offer.savings_amount * item.quantity
    return total.quantize(Decimal('0.01'))


def get_current_customer(request):
    """Helper to get the logged-in customer only."""
    if request.user.is_authenticated and request.user.role == 'customer':
        return request.user
    return None


def latest_return_requests(queryset):
    visible_requests = []
    latest_by_item = {}
    for return_request in queryset:
        key = (
            (return_request.order_id, return_request.order_item_id)
            if return_request.order_item_id else ('legacy', return_request.id)
        )
        if key in latest_by_item:
            latest_by_item[key].duplicate_request_count += 1
            continue
        return_request.duplicate_request_count = 1
        latest_by_item[key] = return_request
        visible_requests.append(return_request)
    return visible_requests


def ensure_customer_referral_code(customer):
    if customer.referral_code:
        return

    referral_code = f"REF-{customer.username[:4].upper()}-{uuid.uuid4().hex[:8].upper()}"
    while User.objects.filter(referral_code__iexact=referral_code).exists():
        referral_code = f"REF-{customer.username[:4].upper()}-{uuid.uuid4().hex[:8].upper()}"

    User.objects.filter(pk=customer.pk).filter(
        Q(referral_code__isnull=True) | Q(referral_code='')
    ).update(referral_code=referral_code)
    customer.refresh_from_db(fields=['referral_code'])


def get_wishlist_product_ids(request, customer):
    if customer:
        wishlist = Wishlist.objects.filter(user=customer).first()
        return set(wishlist.items.values_list('product_id', flat=True)) if wishlist else set()
    return {
        int(product_id) for product_id in request.session.get('guest_wishlist', [])
        if str(product_id).isdigit()
    }


def dashboard(request):
    customer = get_current_customer(request)
    recent_orders = Order.objects.filter(customer=customer).order_by('-created_at')[:5] if customer else Order.objects.all()[:5]
    featured_products = Product.objects.filter(is_featured=True, is_active=True)[:6]
    flash_deals = Product.objects.filter(is_flash_sale=True, is_active=True)[:4]

    total_orders_count = Order.objects.filter(customer=customer).count() if customer else Order.objects.count()
    active_orders_count = Order.objects.filter(customer=customer, status__in=['pending', 'confirmed', 'processing', 'packed', 'shipped', 'out_for_delivery']).count() if customer else 3

    user_wishlist_ids = get_wishlist_product_ids(request, customer)

    context = {
        'current_panel': 'customer',
        'active_menu': 'dashboard',
        'customer': customer,
        'recent_orders': recent_orders,
        'featured_products': featured_products,
        'flash_deals': flash_deals,
        'total_orders_count': total_orders_count,
        'active_orders_count': active_orders_count,
        'wallet_balance': customer.wallet_balance if customer else Decimal('0.00'),
        'reward_points': getattr(customer, 'reward_points', 250),
        'reward_value': (customer.reward_points // 2) if customer else 0,
        'user_wishlist_ids': user_wishlist_ids,
    }
    return render(request, "customer/dashboard.html", context)


def products(request):
    query = request.GET.get('q', '').strip()
    search_prefix, separator, search_value = query.partition(':')
    search_term = (
        search_value.strip()
        if separator and search_prefix.strip().lower() in {'code', 'sku'}
        else query
    )
    cat_slug = request.GET.get('category', '')
    brand_id = request.GET.get('brand', '')
    sort = request.GET.get('sort', 'newest')

    products_qs = Product.objects.filter(is_active=True).select_related('seller_offer')

    if search_term:
        products_qs = products_qs.filter(
            Q(title__icontains=search_term) |
            Q(item_code__icontains=search_term) |
            Q(description__icontains=search_term) |
            Q(brand__name__icontains=search_term)
        )

    if cat_slug:
        products_qs = products_qs.filter(category__slug=cat_slug)

    if brand_id:
        products_qs = products_qs.filter(brand_id=brand_id)

    if sort == 'price_asc':
        products_qs = products_qs.order_by('selling_price')
    elif sort == 'price_desc':
        products_qs = products_qs.order_by('-selling_price')
    elif sort == 'rating':
        products_qs = products_qs.order_by('-average_rating')
    else:
        products_qs = products_qs.order_by('-created_at')

    all_categories = Category.objects.filter(is_active=True)
    all_brands = Brand.objects.all()
    grouped_products = OrderedDict()
    for product in products_qs:
        category_slug = product.category.slug if product.category else 'other-products'
        category_name = product.category.name if product.category else 'Other Products'
        category_row = grouped_products.setdefault(category_slug, {'name': category_name, 'products': []})
        category_row['products'].append(product)
    category_product_rows = [
        {'slug': category_slug, **category_row}
        for category_slug, category_row in grouped_products.items()
    ]

    customer = get_current_customer(request)
    user_wishlist_ids = get_wishlist_product_ids(request, customer)
    if customer:
        cart_quantities = dict(
            CartItem.objects.filter(cart__user=customer, product__in=products_qs)
            .values_list('product_id', 'quantity')
        )
    else:
        cart_quantities = {
            int(product_id): int(quantity)
            for product_id, quantity in request.session.get('guest_cart', {}).items()
            if str(product_id).isdigit()
        }
    for product in products_qs:
        product.cart_quantity = cart_quantities.get(product.id, 0)

    context = {
        'current_panel': 'customer',
        'active_menu': 'products',
        'products': products_qs,
        'category_product_rows': category_product_rows,
        'categories': all_categories,
        'brands': all_brands,
        'selected_category': cat_slug,
        'selected_brand': brand_id,
        'selected_sort': sort,
        'search_query': query,
        'user_wishlist_ids': user_wishlist_ids,
        'cart_quantities': cart_quantities,
        'compare_product_ids': request.session.get('compare_product_ids', []),
    }
    return render(request, "customer/products.html", context)


def product_details(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    gallery = product.gallery_images.all()
    specs = product.specifications.all()
    reviews = product.reviews.all().order_by('-created_at')

    # Frequently bought together bundles (random sample of other products)
    related_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:3]

    # Handle Review Submission
    if request.method == "POST" and request.POST.get('action') == 'submit_review':
        customer = get_current_customer(request)
        if customer:
            delivered_order = Order.objects.filter(
                customer=customer,
                status='delivered',
                items__product=product,
            ).distinct().first()
            if not delivered_order:
                messages.error(request, "You can review this product after it has been delivered.")
                return redirect(f"/customer/product/{product.id}/")
            rating = int(request.POST.get('rating', 5))
            title = request.POST.get('title', '').strip()
            comment = request.POST.get('comment', '').strip()
            photo_url = request.POST.get('photo_url', '').strip()

            Review.objects.update_or_create(
                product=product,
                customer=customer,
                defaults={
                    'order': delivered_order,
                    'rating': max(1, min(rating, 5)),
                    'title': title,
                    'comment': comment,
                    'photo_url_1': photo_url,
                    'is_verified_purchase': True,
                },
            )
            product_reviews = Review.objects.filter(product=product)
            product.total_reviews_count = product_reviews.count()
            product.average_rating = round(sum(review.rating for review in product_reviews) / product.total_reviews_count, 1)
            product.save(update_fields=['total_reviews_count', 'average_rating'])
            messages.success(request, "Thank you! Your review with photo has been posted successfully.")
            return redirect(f"/customer/product/{product.id}/")

    customer = get_current_customer(request)
    is_in_wishlist = product.id in get_wishlist_product_ids(request, customer)
    if customer:
        cart_quantity = CartItem.objects.filter(cart__user=customer, product=product).values_list('quantity', flat=True).first() or 0
    else:
        cart_quantity = int(request.session.get('guest_cart', {}).get(str(product.id), 0))

    context = {
        'current_panel': 'customer',
        'active_menu': 'products',
        'product': product,
        'seller_offer': getattr(product, 'seller_offer', None),
        'seller_offer_savings': getattr(getattr(product, 'seller_offer', None), 'savings_amount', Decimal('0.00')),
        'gallery': gallery,
        'specs': specs,
        'reviews': reviews,
        'related_products': related_products,
        'total_reviews': reviews.count(),
        'is_in_wishlist': is_in_wishlist,
        'is_in_compare': product.id in request.session.get('compare_product_ids', []),
        'cart_quantity': cart_quantity,
        'can_review': Order.objects.filter(customer=customer, status='delivered', items__product=product).exists() if customer else False,
    }
    return render(request, "customer/product-details.html", context)


def categories(request):
    cats = Category.objects.filter(is_active=True)
    context = {
        'current_panel': 'customer',
        'active_menu': 'categories',
        'categories': cats,
    }
    return render(request, "customer/categories.html", context)


def category_products(request, category_id):
    cat = get_object_or_404(Category, id=category_id)
    return redirect(f"/customer/products/?category={cat.slug}")


def search(request):
    if request.GET.get('suggestions') == '1':
        query = request.GET.get('q', '').strip()
        prefix, separator, value = query.partition(':')
        if separator and prefix.strip().lower() in {'code', 'sku'}:
            query = value.strip()
        if not query:
            return JsonResponse({'results': []})

        matches = Product.objects.filter(is_active=True).filter(
            Q(title__icontains=query) |
            Q(item_code__icontains=query) |
            Q(sku__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query) |
            Q(brand__name__icontains=query)
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
    return products(request)


def cart(request):
    customer = get_current_customer(request)
    cart_obj = None
    if customer:
        cart_obj, _ = Cart.objects.get_or_create(user=customer)
    else:
        guest_cart = request.session.get('guest_cart', {})

    # Actions: Add, Remove, Update Quantity, Apply Coupon
    if request.method == "POST":
        action = request.POST.get('action')
        prod_id = request.POST.get('product_id')

        if action == 'add' and prod_id:
            prod = get_object_or_404(Product, id=prod_id)
            if customer:
                item = CartItem.objects.filter(cart=cart_obj, product=prod).first()
                current_quantity = item.quantity if item else 0
            else:
                current_quantity = int(guest_cart.get(str(prod.id), 0))

            if prod.stock < 1 or current_quantity >= prod.stock:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'error': 'No more stock is available.', 'quantity': current_quantity, 'stock': prod.stock}, status=409)
                messages.error(request, 'No more stock is available for this product.')
                return redirect("/customer/cart/")

            quantity = current_quantity + 1
            if customer:
                CartItem.objects.update_or_create(cart=cart_obj, product=prod, defaults={'quantity': quantity})
            else:
                guest_cart[str(prod.id)] = quantity
                request.session['guest_cart'] = guest_cart
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                cart_count = cart_obj.items.count() if customer else len(guest_cart)
                return JsonResponse({'quantity': quantity, 'stock': prod.stock, 'cart_count': cart_count})
            messages.success(request, f"{prod.title} added to cart!")
            return redirect("/customer/cart/")

        elif action == 'buy_now' and prod_id:
            prod = get_object_or_404(Product, id=prod_id)
            if customer:
                CartItem.objects.filter(cart=cart_obj).exclude(product=prod).delete()
                CartItem.objects.update_or_create(cart=cart_obj, product=prod, defaults={'quantity': 1})
            else:
                request.session['guest_cart'] = {str(prod.id): 1}
            return redirect("/customer/checkout/")

        elif action == 'remove' and prod_id:
            if customer:
                CartItem.objects.filter(cart=cart_obj, product_id=prod_id).delete()
            else:
                guest_cart.pop(str(prod_id), None)
                request.session['guest_cart'] = guest_cart
            messages.info(request, "Item removed from cart.")
            return redirect("/customer/cart/")

        elif action == 'update_qty' and prod_id:
            product = get_object_or_404(Product, id=prod_id)
            try:
                qty = int(request.POST.get('quantity', 1))
            except (TypeError, ValueError):
                qty = 1
            qty = min(qty, product.stock)
            if customer:
                if qty <= 0:
                    CartItem.objects.filter(cart=cart_obj, product_id=prod_id).delete()
                else:
                    CartItem.objects.filter(cart=cart_obj, product_id=prod_id).update(quantity=qty)
            else:
                if qty <= 0:
                    guest_cart.pop(str(prod_id), None)
                else:
                    guest_cart[str(prod_id)] = qty
                request.session['guest_cart'] = guest_cart
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                cart_count = cart_obj.items.count() if customer else len(guest_cart)
                return JsonResponse({'quantity': max(qty, 0), 'stock': product.stock, 'cart_count': cart_count})
            return redirect("/customer/cart/")

    cart_items = cart_obj.items.select_related('product', 'product__seller_offer').all() if customer else get_guest_cart_items(request)
    subtotal = sum(item.subtotal() for item in cart_items)
    seller_offer_discount = get_seller_offer_discount(cart_items)
    delivery_charge = Decimal("50.00") if (subtotal > 0 and subtotal < 500) else Decimal("0.00")
    tax = round(subtotal * Decimal("0.05"), 2)

    # Check coupon
    coupon_code = request.GET.get('coupon', '').strip()
    coupon_discount = Decimal("0.00")
    applied_coupon = None
    coupon_error = ''
    if coupon_code:
        coupon_match = Coupon.objects.filter(code__iexact=coupon_code, is_active=True).first()
        if not coupon_match:
            coupon_error = 'This coupon code is invalid or inactive.'
        elif subtotal < coupon_match.min_order_amount:
            coupon_error = f"This coupon requires a minimum cart total of ₹{coupon_match.min_order_amount:.2f}."
        else:
            applied_coupon = coupon_match
            if coupon_match.discount_type == 'percent':
                coupon_discount = round((subtotal * coupon_match.discount_value) / 100, 2)
            else:
                coupon_discount = coupon_match.discount_value
            if coupon_discount > coupon_match.max_discount_amount:
                coupon_discount = coupon_match.max_discount_amount
            messages.success(request, f"Coupon '{coupon_match.code}' applied! Saved ₹{coupon_discount}.")
        if coupon_error:
            messages.error(request, "Invalid coupon code or minimum order requirement not met.")

    grand_total = max(Decimal("0.00"), subtotal + delivery_charge + tax - coupon_discount)

    context = {
        'current_panel': 'customer',
        'active_menu': 'cart',
        'cart': cart_obj,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'seller_offer_discount': seller_offer_discount,
        'delivery_charge': delivery_charge,
        'tax': tax,
        'coupon_discount': coupon_discount,
        'applied_coupon': applied_coupon,
        'coupon_code': coupon_code,
        'coupon_error': coupon_error,
        'grand_total': grand_total,
    }
    return render(request, "customer/cart.html", context)


def wishlist(request):
    customer = get_current_customer(request)
    wish_obj = None
    if customer:
        wish_obj, _ = Wishlist.objects.get_or_create(user=customer)
    guest_wishlist = request.session.get('guest_wishlist', [])

    # Action: Toggle Wishlist or Move to Cart
    if request.method == "POST":
        action = request.POST.get('action')
        prod_id = request.POST.get('product_id')
        if action == 'toggle' and prod_id:
            is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
            item = WishlistItem.objects.filter(wishlist=wish_obj, product_id=prod_id).first() if customer else (str(prod_id) if str(prod_id) in guest_wishlist else None)
            added = not bool(item)
            if item:
                if customer:
                    item.delete()
                else:
                    guest_wishlist.remove(str(prod_id))
                    request.session['guest_wishlist'] = guest_wishlist
                if not is_ajax:
                    messages.info(request, "Removed from wishlist.")
            else:
                if customer:
                    WishlistItem.objects.create(wishlist=wish_obj, product_id=prod_id)
                else:
                    guest_wishlist.append(str(prod_id))
                    request.session['guest_wishlist'] = guest_wishlist
                if not is_ajax:
                    messages.success(request, "Added to wishlist ❤️")
            if is_ajax:
                return JsonResponse({'success': True, 'added': added})
            return redirect(request.META.get('HTTP_REFERER', '/customer/wishlist/'))

        elif action == 'move_to_cart' and prod_id:
            prod = get_object_or_404(Product, id=prod_id)
            if customer:
                cart_obj, _ = Cart.objects.get_or_create(user=customer)
                item, created = CartItem.objects.get_or_create(cart=cart_obj, product=prod)
                if not created:
                    item.quantity += 1
                    item.save()
                WishlistItem.objects.filter(wishlist=wish_obj, product_id=prod_id).delete()
            else:
                guest_cart = request.session.get('guest_cart', {})
                guest_cart[str(prod.id)] = int(guest_cart.get(str(prod.id), 0)) + 1
                request.session['guest_cart'] = guest_cart
                guest_wishlist.remove(str(prod_id))
                request.session['guest_wishlist'] = guest_wishlist
            messages.success(request, f"Moved {prod.title} to Cart!")
            return redirect("/customer/cart/")

    if customer:
        items = wish_obj.items.select_related('product').all()
    else:
        products = Product.objects.filter(id__in=[int(product_id) for product_id in guest_wishlist], is_active=True)
        items = [type('GuestWishlistItem', (), {'product': product})() for product in products]
    context = {
        'current_panel': 'customer',
        'active_menu': 'wishlist',
        'items': items,
    }
    return render(request, "customer/wishlist.html", context)


def compare(request):
    compare_ids = request.session.get('compare_product_ids', [])

    if request.method == 'POST':
        action = request.POST.get('action')
        product_id = request.POST.get('product_id')
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        added = False

        if action == 'clear':
            compare_ids = []
        elif product_id and product_id.isdigit():
            product_id = int(product_id)
            if action == 'remove':
                compare_ids = [item_id for item_id in compare_ids if int(item_id) != product_id]
            elif action == 'toggle':
                compare_ids = [int(item_id) for item_id in compare_ids]
                if product_id in compare_ids:
                    compare_ids.remove(product_id)
                elif len(compare_ids) < 4 and Product.objects.filter(id=product_id, is_active=True).exists():
                    compare_ids.append(product_id)
                    added = True
                elif len(compare_ids) >= 4:
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': 'Compare up to 4 products at a time.'}, status=400)

        request.session['compare_product_ids'] = compare_ids
        request.session.modified = True
        if is_ajax:
            return JsonResponse({
                'success': True,
                'added': added,
                'compare_count': len(compare_ids),
            })
        return redirect(request.META.get('HTTP_REFERER', '/customer/compare/'))

    compare_ids = [int(item_id) for item_id in compare_ids]
    products_to_compare = list(
        Product.objects.filter(id__in=compare_ids, is_active=True)
        .select_related('brand', 'category', 'seller')
        .prefetch_related('specifications')
    )
    products_to_compare.sort(key=lambda item: compare_ids.index(item.id))
    specification_names = sorted({
        specification.name
        for product in products_to_compare
        for specification in product.specifications.all()
    })

    return render(request, 'customer/compare.html', {
        'current_panel': 'customer',
        'active_menu': 'compare',
        'compare_products': products_to_compare,
        'specification_names': specification_names,
        'compare_product_ids': compare_ids,
    })


def checkout(request):
    customer = get_current_customer(request)
    addresses = Address.objects.filter(user=customer)
    cart_obj, _ = Cart.objects.get_or_create(user=customer)
    cart_items = cart_obj.items.select_related('product', 'product__seller_offer').all()

    if not cart_items.exists():
        messages.warning(request, "Your cart is empty! Add products to proceed to checkout.")
        return redirect("/customer/products/")

    subtotal = sum(item.subtotal() for item in cart_items)
    seller_offer_discount = get_seller_offer_discount(cart_items)
    delivery_charge = Decimal("0.00") if subtotal > 500 else Decimal("50.00")
    tax = round(subtotal * Decimal("0.05"), 2)
    coupon_code = request.POST.get('coupon', request.GET.get('coupon', '')).strip()
    coupon_discount = Decimal('0.00')
    applied_coupon = None
    coupon_error = ''
    if coupon_code:
        applied_coupon = Coupon.objects.filter(code__iexact=coupon_code, is_active=True).first()
        if not applied_coupon:
            coupon_error = 'This coupon code is invalid or inactive.'
        elif subtotal < applied_coupon.min_order_amount:
            coupon_error = f"This coupon requires a minimum cart total of ₹{applied_coupon.min_order_amount:.2f}."
            applied_coupon = None
        else:
            if applied_coupon.discount_type == 'percent':
                coupon_discount = round((subtotal * applied_coupon.discount_value) / 100, 2)
            else:
                coupon_discount = applied_coupon.discount_value
            coupon_discount = min(coupon_discount, applied_coupon.max_discount_amount)
        if coupon_error and request.method == 'POST' and request.POST.get('checkout_action') != 'save_address':
            messages.error(request, coupon_error)
            return redirect('/customer/checkout/')
    grand_total = max(Decimal('0.00'), subtotal + delivery_charge + tax - coupon_discount)

    context = {
        'current_panel': 'customer',
        'active_menu': 'cart',
        'addresses': addresses,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'seller_offer_discount': seller_offer_discount,
        'delivery_charge': delivery_charge,
        'tax': tax,
        'coupon_discount': coupon_discount,
        'applied_coupon': applied_coupon,
        'coupon_error': coupon_error,
        'grand_total': grand_total,
        'wallet_balance': customer.wallet_balance if customer else Decimal('0.00'),
        'coupon_code': coupon_code,
        'selected_address_id': '',
        'new_address_selected': False,
        'new_address_values': {},
    }

    # Place Order Handler
    if request.method == "POST":
        save_address_only = request.POST.get('checkout_action') == 'save_address'
        address_id = request.POST.get('address_id', '').strip()
        if save_address_only:
            address_id = 'new'
        payment_method = request.POST.get('payment_method', 'upi')
        if not save_address_only and payment_method == 'wallet' and customer.wallet_balance < grand_total:
            messages.error(
                request,
                f"Insufficient wallet balance. Available ₹{customer.wallet_balance:.2f}, required ₹{grand_total:.2f}."
            )
            return redirect('/customer/checkout/')

        if address_id == 'new':
            new_address = {
                'full_name': request.POST.get('new_full_name', '').strip(),
                'phone': request.POST.get('new_phone', '').strip(),
                'street_address': request.POST.get('new_street_address', '').strip(),
                'city': request.POST.get('new_city', '').strip(),
                'state': request.POST.get('new_state', '').strip(),
                'pincode': request.POST.get('new_pincode', '').strip(),
                'address_type': request.POST.get('new_address_type', 'home').strip(),
            }
            required_lengths = {
                'full_name': 100,
                'phone': 20,
                'street_address': 255,
                'city': 100,
                'state': 100,
                'pincode': 10,
            }
            invalid_address = (
                any(not new_address[field] or len(new_address[field]) > limit for field, limit in required_lengths.items())
                or not new_address['pincode'].isdigit()
                or len(new_address['pincode']) != 6
                or new_address['address_type'] not in {'home', 'work', 'other'}
            )
            if invalid_address:
                messages.error(request, 'Enter all address details and a valid 6-digit PIN code.')
                context.update({
                    'new_address_selected': True,
                    'new_address_values': request.POST,
                })
                return render(request, "customer/checkout.html", context)
            shipping_addr = Address.objects.create(user=customer, **new_address)
            if save_address_only:
                messages.success(request, 'Delivery address saved.')
                return redirect('/customer/checkout/#deliveryAddress')
        else:
            shipping_addr = addresses.filter(id=address_id).first() if address_id.isdigit() else None
            if not shipping_addr:
                messages.error(request, 'Select a saved delivery address or add a new one.')
                context['new_address_selected'] = False
                return render(request, "customer/checkout.html", context)

        addr_text = f"{shipping_addr.street_address}, {shipping_addr.city}, {shipping_addr.state} - {shipping_addr.pincode}"

        # Create Order for first seller (or primary items)
        first_product = cart_items.first().product
        seller = first_product.seller

        order_num = f"ORD-{timezone.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        admin_comm = round(subtotal * Decimal("0.10"), 2)
        seller_net = round(subtotal - admin_comm, 2)
        delivery_otp = str(random.randint(1000, 9999))

        order = Order.objects.create(
            order_number=order_num,
            customer=customer,
            seller=seller,
            status='confirmed',
            customer_name=f"{customer.first_name} {customer.last_name}",
            customer_phone=customer.phone or "9876543210",
            shipping_address=addr_text,
            subtotal=subtotal,
            delivery_charge=delivery_charge,
            tax=tax,
            coupon_discount=coupon_discount,
            grand_total=grand_total,
            admin_commission_amount=admin_comm,
            seller_net_earnings=seller_net,
            delivery_partner_earning=Decimal("50.00"),
            payment_method=payment_method,
            payment_status='paid' if payment_method != 'cod' else 'pending',
            delivery_otp=delivery_otp,
            tracking_id=f"TRK-{random.randint(100000, 999999)}"
        )

        for ci in cart_items:
            OrderItem.objects.create(
                order=order,
                product=ci.product,
                quantity=ci.quantity,
                unit_price=ci.product.selling_price,
                total_price=ci.subtotal()
            )

        OrderTimeline.objects.create(
            order=order,
            status='confirmed',
            title='Order Placed & Confirmed',
            description=f'Order placed via {payment_method.upper()}. Vendor notified.'
        )

        CommissionLog.objects.create(
            order=order,
            rate_percentage=Decimal("10.00"),
            order_total=grand_total,
            admin_commission_amount=admin_comm,
            seller_payout_amount=seller_net,
            delivery_payout_amount=Decimal("50.00"),
            status='pending'
        )

        PaymentTransaction.objects.create(
            order=order,
            transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
            amount=grand_total,
            payment_method=payment_method.upper(),
            status='success' if payment_method != 'cod' else 'pending'
        )

        if payment_method == 'wallet':
            customer.wallet_balance -= grand_total
            customer.save(update_fields=['wallet_balance'])

        # Clear Cart
        cart_items.delete()

        messages.success(request, f"Order #{order_num} placed successfully! Delivery OTP: {delivery_otp}")
        return redirect(f"/customer/orders/{order.id}/track/")

    return render(request, "customer/checkout.html", context)


@transaction.atomic
def cancel_customer_order(order_id, customer):
    order = get_object_or_404(
        Order.objects.select_for_update(), id=order_id, customer=customer,
    )
    if order.status not in {'pending', 'confirmed', 'processing', 'packed'}:
        raise ValueError('Orders can only be cancelled before shipment.')

    order.status = 'cancelled'
    order.save(update_fields=['status', 'updated_at'])
    refund_amount = Decimal('0.00')
    external_refund_pending = False

    if order.payment_status == 'paid' and order.grand_total > 0:
        if order.payment_method == 'wallet':
            refunded, refund_amount = refund_cancelled_wallet_order(order.id)
            if not refunded:
                raise ValueError('Wallet refund could not be verified; contact Support to cancel this order.')
        else:
            external_refund_pending = True
            CommissionLog.objects.filter(order=order).update(status='cancelled')
            for admin in User.objects.filter(role='admin', is_active=True):
                Notification.objects.create(
                    user=admin,
                    title='External refund required for cancelled order',
                    message=f'Customer cancelled order #{order.order_number}; record the provider refund after processing.',
                    notification_type='order',
                    link=f'/admin-panel/orders/{order.id}/',
                )
    else:
        order.admin_commission_amount = Decimal('0.00')
        order.seller_net_earnings = Decimal('0.00')
        order.delivery_partner_earning = Decimal('0.00')
        order.save(update_fields=[
            'admin_commission_amount', 'seller_net_earnings',
            'delivery_partner_earning', 'updated_at',
        ])
        CommissionLog.objects.filter(order=order).update(
            status='cancelled', admin_commission_amount=Decimal('0.00'),
            seller_payout_amount=Decimal('0.00'), delivery_payout_amount=Decimal('0.00'),
        )
        PaymentTransaction.objects.filter(order=order, status='pending').update(status='cancelled')

    OrderTimeline.objects.create(
        order=order, status='cancelled', title='Order cancelled by customer',
        description='Customer cancelled the order before shipment.',
    )
    return refund_amount, external_refund_pending


def orders(request):
    customer = get_current_customer(request)
    if request.method == 'POST' and request.POST.get('action') == 'cancel_order':
        try:
            refund_amount, external_refund_pending = cancel_customer_order(
                request.POST.get('order_id'), customer,
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            if refund_amount:
                messages.success(request, f'Order cancelled. ₹{refund_amount:.2f} was returned to your wallet.')
            elif external_refund_pending:
                messages.success(request, 'Order cancelled. Your external payment refund will be processed by Support.')
            else:
                messages.success(request, 'Order cancelled successfully.')
        return redirect('/customer/orders/')

    status_filter = request.GET.get('status')
    completed_returns = ReturnRequest.objects.filter(
        order_id=OuterRef('pk'), status='refund_processed',
    )
    orders_qs = (
        Order.objects.filter(customer=customer).annotate(has_completed_return=Exists(completed_returns))
        if customer else Order.objects.none()
    )
    available_years = [value.year for value in orders_qs.dates('created_at', 'year', order='DESC')]

    try:
        selected_year = int(request.GET.get('year', ''))
    except (TypeError, ValueError):
        selected_year = None
    if selected_year not in available_years:
        selected_year = None

    try:
        selected_month = int(request.GET.get('month', ''))
    except (TypeError, ValueError):
        selected_month = None
    if selected_month not in range(1, 13):
        selected_month = None

    if status_filter:
        orders_qs = orders_qs.filter(status=status_filter)
    if selected_year:
        orders_qs = orders_qs.filter(created_at__year=selected_year)
    if selected_month:
        orders_qs = orders_qs.filter(created_at__month=selected_month)

    orders_qs = orders_qs.order_by('-created_at')

    context = {
        'current_panel': 'customer',
        'active_menu': 'orders',
        'orders': orders_qs,
        'selected_status': status_filter,
        'available_years': available_years,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'months': [(month, calendar.month_name[month]) for month in range(1, 13)],
    }
    return render(request, "customer/orders.html", context)


def order_details(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    items = order.items.select_related('product').all()
    timeline = order.timeline.all().order_by('timestamp')

    context = {
        'current_panel': 'customer',
        'active_menu': 'orders',
        'order': order,
        'items': items,
        'timeline': timeline,
    }
    return render(request, "customer/order-details.html", context)


def track_order(request, order_id=None):
    customer = get_current_customer(request)
    if order_id:
        order = get_object_or_404(Order, id=order_id, customer=customer)
    else:
        order = Order.objects.filter(customer=customer).order_by('-created_at').first() if customer else Order.objects.first()
        if not order:
            order = Order.objects.first()

    timeline = order.timeline.all().order_by('timestamp') if order else []
    latest_reschedule = order.timeline.filter(title='Delivery Rescheduled').order_by('-timestamp').first() if order else None
    order_cancelled_event = order.timeline.filter(status='cancelled').order_by('-timestamp').first() if order else None
    return_requests = latest_return_requests(order.return_requests.select_related(
        'order_item__product', 'replacement_order'
    ).order_by('-created_at', '-id')) if order else []
    has_completed_return = any(
        return_request.status == 'refund_processed' for return_request in return_requests
    )
    progress_ranks = {
        'confirmed': 1, 'processing': 1, 'packed': 1,
        'shipped': 2, 'out_for_delivery': 3,
        'delivered': 4, 'returned': 4, 'replaced': 4,
        'refund_processed': 4, 'replacement_dispatched': 4,
        'replacement_delivered': 4,
    }
    order_progress_rank = max(
        [progress_ranks.get(order.status, 0)]
        + [progress_ranks.get(status, 0) for status in order.timeline.values_list('status', flat=True)]
    ) if order else 0

    if request.method == 'POST' and order and request.POST.get('action') == 'rate_delivery':
        if order.status != 'delivered' or order.customer != customer or not order.delivery_partner:
            messages.error(request, 'Delivery rating is available only after this order is delivered.')
        else:
            rating = max(1, min(int(request.POST.get('rating', 5)), 5))
            DeliveryRating.objects.update_or_create(
                order=order,
                defaults={
                    'customer': customer,
                    'delivery_partner': order.delivery_partner,
                    'rating': rating,
                    'comment': request.POST.get('comment', '').strip(),
                },
            )
            partner_ratings = DeliveryRating.objects.filter(delivery_partner=order.delivery_partner)
            order.delivery_partner.rating = round(sum(item.rating for item in partner_ratings) / partner_ratings.count(), 1)
            order.delivery_partner.save(update_fields=['rating'])
            messages.success(request, 'Thank you for rating the delivery partner.')
        return redirect(f'/customer/orders/{order.id}/track/')

    context = {
        'current_panel': 'customer',
        'active_menu': 'orders',
        'order': order,
        'timeline': timeline,
        'latest_reschedule': latest_reschedule,
        'order_cancelled_event': order_cancelled_event,
        'return_requests': return_requests,
        'has_completed_return': has_completed_return,
        'order_progress_rank': order_progress_rank,
    }
    return render(request, "customer/track-order.html", context)


def order_invoice(request, order_id):
    """Dynamic PDF / Printable GST Tax Invoice"""
    order = get_object_or_404(Order, id=order_id)
    items = order.items.select_related('product').all()
    context = {
        'order': order,
        'items': items,
        'company_name': 'ShopVerse Logistics & Retail India Ltd.',
        'gstin': '07AAACS1429B1ZX',
    }
    return render(request, "customer/invoice.html", context)


def returns(request):
    customer = get_current_customer(request)

    if request.method == 'POST' and request.POST.get('action') == 'cancel_return':
        try:
            cancel_return_request(int(request.POST.get('return_id', '')), customer=customer)
        except (ReturnValidationError, TypeError, ValueError) as exc:
            messages.error(request, str(exc) or 'Invalid return request.')
        else:
            messages.success(request, 'Return/replacement request cancelled.')
        return redirect('/customer/returns/')

    # Submit Return or Replacement Request
    if request.method == "POST":
        order_num = request.POST.get('order_number')
        item_id = request.POST.get('order_item_id')
        rtype = request.POST.get('request_type', 'return')
        reason = request.POST.get('reason')
        details = request.POST.get('details', '')
        quantity = request.POST.get('quantity', '1')
        proof_photo = request.FILES.get('proof_photo')

        if not order_num or not item_id:
            messages.error(request, 'Choose a delivered product without an existing return/replacement request.')
            return redirect('/customer/returns/')

        matched_order = Order.objects.filter(
            order_number=order_num,
            customer=customer,
            status='delivered',
        ).first()
        if matched_order and customer:
            photo_url = ''
            if proof_photo:
                if not proof_photo.content_type.startswith('image/') or proof_photo.size > 5 * 1024 * 1024:
                    messages.error(request, 'Choose an image smaller than 5 MB.')
                    return redirect('/customer/returns/')
                safe_name = get_valid_filename(proof_photo.name)[:120]
                saved_name = default_storage.save(f'return_proofs/{uuid.uuid4().hex}_{safe_name}', proof_photo)
                photo_url = default_storage.url(saved_name)
            try:
                create_return_request(
                    customer=customer, order_id=matched_order.id, order_item_id=item_id,
                    quantity=quantity, request_type=rtype, reason=reason,
                    details=details, photo_url=photo_url,
                )
            except ReturnValidationError as exc:
                messages.error(request, str(exc))
                return redirect('/customer/returns/')
            messages.success(request, f"{rtype.title()} request submitted for Order #{order_num}! Seller will review.")
            return redirect("/customer/returns/")
        else:
            messages.error(request, "Order number not found or customer session is invalid.")

    my_returns = latest_return_requests(
        ReturnRequest.objects.filter(customer=customer).select_related(
            'order', 'order_item__product', 'replacement_order'
        ).order_by('-created_at', '-id')
    ) if customer else latest_return_requests(
        ReturnRequest.objects.select_related(
            'order', 'order_item__product', 'replacement_order'
        ).order_by('-created_at', '-id')
    )
    existing_item_requests = ReturnRequest.objects.filter(
        order_item_id=OuterRef('pk'),
    ).exclude(status='cancelled')
    order_items = OrderItem.objects.annotate(
        has_return_request=Exists(existing_item_requests),
    )
    delivered_orders = (
        Order.objects.filter(customer=customer, status='delivered')
        .prefetch_related(Prefetch('items', queryset=order_items))
        if customer else Order.objects.filter(status='delivered').prefetch_related(
            Prefetch('items', queryset=order_items),
        )
    )
    has_returnable_items = any(
        not item.has_return_request
        for order in delivered_orders
        for item in order.items.all()
    )

    context = {
        'current_panel': 'customer',
        'active_menu': 'returns',
        'returns': my_returns,
        'delivered_orders': delivered_orders,
        'has_returnable_items': has_returnable_items,
    }
    return render(request, "customer/returns.html", context)


def refunds(request):
    return returns(request)


def coupons(request):
    all_coupons = Coupon.objects.filter(is_active=True).order_by('-discount_value')
    context = {
        'current_panel': 'customer',
        'active_menu': 'coupons',
        'coupons': all_coupons,
    }
    return render(request, "customer/coupons.html", context)


def reviews(request):
    customer = get_current_customer(request)

    if request.method == 'POST' and customer:
        if request.POST.get('action') == 'delete_review':
            review = get_object_or_404(
                Review.objects.select_related('product'),
                id=request.POST.get('review_id'),
                customer=customer,
            )
            product = review.product
            review.delete()
            remaining_reviews = Review.objects.filter(product=product)
            review_count = remaining_reviews.count()
            product.total_reviews_count = review_count
            product.average_rating = round(
                sum(item.rating for item in remaining_reviews) / review_count,
                1,
            ) if review_count else 0
            product.save(update_fields=['total_reviews_count', 'average_rating'])
            messages.success(request, 'Your review was deleted.')
            return redirect('/customer/reviews/')

        product_id = request.POST.get('product_id')
        delivered_item = OrderItem.objects.filter(
            order__customer=customer,
            order__status='delivered',
            product_id=product_id,
        ).select_related('order', 'product').first()
        if not delivered_item:
            messages.error(request, 'Select a product from one of your delivered orders.')
            return redirect('/customer/reviews/')

        title = request.POST.get('title', '').strip()
        comment = request.POST.get('comment', '').strip()
        try:
            rating = int(request.POST.get('rating', '5'))
        except (TypeError, ValueError):
            rating = 0
        if not title or len(title) > 200 or not comment or rating not in range(1, 6):
            messages.error(request, 'Enter a review title, feedback, and a rating from 1 to 5.')
            return redirect('/customer/reviews/')

        review_id = request.POST.get('review_id')
        if review_id:
            review = get_object_or_404(
                Review,
                id=review_id,
                product=delivered_item.product,
                customer=customer,
            )
        else:
            review = Review.objects.filter(product=delivered_item.product, customer=customer).first()
        photo_urls = [review.photo_url_1, review.photo_url_2, review.photo_url_3] if review else ['', '', '']

        remove_photo_slots = {
            slot for slot in request.POST.getlist('remove_photo_slots')
            if slot in {'1', '2', '3'}
        }
        for slot in remove_photo_slots:
            photo_urls[int(slot) - 1] = ''

        photo_files = request.FILES.getlist('review_photos')
        remaining_photo_count = sum(bool(photo_url) for photo_url in photo_urls)
        if remaining_photo_count + len(photo_files) > 3 or any(
            not photo.content_type.startswith('image/') or photo.size > 5 * 1024 * 1024
            for photo in photo_files
        ):
            messages.error(request, 'Choose up to 3 photos total, each smaller than 5 MB.')
            return redirect('/customer/reviews/')

        for photo in photo_files:
            index = next(slot for slot, photo_url in enumerate(photo_urls) if not photo_url)
            safe_name = get_valid_filename(photo.name)[:120]
            saved_name = default_storage.save(f'review_photos/{uuid.uuid4().hex}_{safe_name}', photo)
            photo_urls[index] = default_storage.url(saved_name)

        Review.objects.update_or_create(
            product=delivered_item.product,
            customer=customer,
            defaults={
                'order': delivered_item.order,
                'rating': rating,
                'title': title,
                'comment': comment,
                'photo_url_1': photo_urls[0],
                'photo_url_2': photo_urls[1],
                'photo_url_3': photo_urls[2],
                'is_verified_purchase': True,
            },
        )
        product_reviews = Review.objects.filter(product=delivered_item.product)
        review_count = product_reviews.count()
        delivered_item.product.total_reviews_count = review_count
        delivered_item.product.average_rating = round(
            sum(review.rating for review in product_reviews) / review_count,
            1,
        )
        delivered_item.product.save(update_fields=['total_reviews_count', 'average_rating'])
        messages.success(request, f'Your review for {delivered_item.product.title} was submitted successfully.')
        return redirect('/customer/reviews/')

    my_reviews = Review.objects.filter(customer=customer).select_related('product').order_by('-created_at') if customer else Review.objects.all()
    delivered_items = OrderItem.objects.filter(
        order__customer=customer,
        order__status='delivered',
    ).select_related('product', 'order').order_by('-order__created_at') if customer else OrderItem.objects.filter(
        order__status='delivered',
    ).select_related('product', 'order').order_by('-order__created_at')
    edit_review = None
    edit_review_photos = []
    if customer and request.GET.get('edit'):
        edit_review = get_object_or_404(Review, id=request.GET.get('edit'), customer=customer)
        edit_review_photos = [
            {'slot': slot, 'url': photo_url}
            for slot, photo_url in enumerate(
                [edit_review.photo_url_1, edit_review.photo_url_2, edit_review.photo_url_3],
                start=1,
            )
            if photo_url
        ]

    context = {
        'current_panel': 'customer',
        'active_menu': 'reviews',
        'reviews': my_reviews,
        'edit_review': edit_review,
        'edit_review_photos': edit_review_photos,
        'delivered_items': delivered_items,
    }
    return render(request, "customer/reviews.html", context)


def reports(request):
    customer = get_current_customer(request)
    orders = Order.objects.filter(customer=customer) if customer else Order.objects.all()
    status_rows = list(orders.values('status').annotate(total=Count('id')).order_by('-total'))
    status_labels = [row['status'].replace('_', ' ').title() for row in status_rows] or ['No orders']
    status_values = [row['total'] for row in status_rows] or [0]
    spending = orders.filter(status='delivered').aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
    delivered = orders.filter(status='delivered').count()
    reviews_count = Review.objects.filter(customer=customer).count() if customer else Review.objects.count()
    wishlist_count = WishlistItem.objects.filter(wishlist__user=customer).count() if customer else WishlistItem.objects.count()
    cart = Cart.objects.filter(user=customer).first() if customer else None
    cart_units = cart.items.aggregate(total=Sum('quantity'))['total'] or 0 if cart else 0

    return render(request, 'customer/reports.html', {
        'current_panel': 'customer',
        'active_menu': 'reports',
        'total_orders': orders.count(),
        'delivered_orders': delivered,
        'spending': spending,
        'reviews_count': reviews_count,
        'wishlist_count': wishlist_count,
        'cart_units': cart_units,
        'chart_status_labels': json.dumps(status_labels),
        'chart_status_values': json.dumps(status_values),
    })


def notifications(request):
    customer = get_current_customer(request)
    if customer is None:
        return HttpResponseForbidden()

    if request.method == 'POST':
        if request.POST.get('action') == 'mark_all_read':
            updated_count = Notification.objects.filter(user=customer, is_read=False).update(is_read=True)
            messages.success(request, f'{updated_count} notification(s) marked as read.')
        elif request.POST.get('action') == 'delete_selected':
            deleted_count, _ = Notification.objects.filter(
                user=customer,
                id__in=request.POST.getlist('notification_ids'),
            ).delete()
            messages.success(request, f'{deleted_count} notification(s) deleted.')
        else:
            messages.error(request, 'Invalid notification action.')
        return redirect('/customer/notifications/')

    notifs = Notification.objects.filter(user=customer).order_by('-created_at')
    context = {
        'current_panel': 'customer',
        'active_menu': 'notifications',
        'notifications': notifs,
        'unread_count': notifs.filter(is_read=False).count(),
    }
    return render(request, "customer/notifications.html", context)


def payments(request):
    customer = get_current_customer(request)
    if request.method == "POST":
        action = request.POST.get('action')
        if action == 'topup':
            amount = Decimal(request.POST.get('amount', '0'))
            if amount > 0 and customer:
                customer.wallet_balance += amount
                customer.save()
                messages.success(request, f"Successfully topped up ₹{amount:.2f} into your E-Wallet balance!")
                return redirect("/customer/payments/")

    txns = PaymentTransaction.objects.filter(order__customer=customer).order_by('-created_at') if customer else PaymentTransaction.objects.all()
    context = {
        'current_panel': 'customer',
        'active_menu': 'payments',
        'transactions': txns,
        'wallet_balance': customer.wallet_balance if customer else Decimal('0.00'),
    }
    return render(request, "customer/payments.html", context)


def profile(request):
    customer = get_current_customer(request)
    if customer:
        ensure_customer_referral_code(customer)
    if request.method == "POST" and request.POST.get('action') == 'save_profile':
        customer.first_name = request.POST.get('first_name', customer.first_name)
        customer.last_name = request.POST.get('last_name', customer.last_name)
        customer.phone = request.POST.get('phone', customer.phone)
        customer.save()
        messages.success(request, "Profile details updated successfully!")
        return redirect("/customer/profile/")

    context = {
        'current_panel': 'customer',
        'active_menu': 'profile',
        'customer': customer,
        'profile_edit_open': request.GET.get('show') == 'edit',
        'profile_password_open': request.GET.get('show') == 'password',
    }
    return render(request, "customer/profile.html", context)


def addresses(request):
    customer = get_current_customer(request)

    if request.method == "POST":
        action = request.POST.get('action')
        if action == 'add':
            Address.objects.create(
                user=customer,
                full_name=request.POST.get('full_name'),
                phone=request.POST.get('phone'),
                street_address=request.POST.get('street_address'),
                city=request.POST.get('city'),
                state=request.POST.get('state'),
                pincode=request.POST.get('pincode'),
                address_type=request.POST.get('address_type', 'home'),
                is_default=False
            )
            messages.success(request, "New delivery address saved!")
            return redirect("/customer/addresses/")
        elif action == 'edit':
            addr_id = request.POST.get('address_id')
            addr = Address.objects.filter(id=addr_id, user=customer).first() if customer else Address.objects.filter(id=addr_id).first()
            if addr:
                addr.full_name = request.POST.get('full_name', addr.full_name)
                addr.phone = request.POST.get('phone', addr.phone)
                addr.street_address = request.POST.get('street_address', addr.street_address)
                addr.city = request.POST.get('city', addr.city)
                addr.state = request.POST.get('state', addr.state)
                addr.pincode = request.POST.get('pincode', addr.pincode)
                addr.address_type = request.POST.get('address_type', addr.address_type)
                addr.save()
                messages.success(request, "Delivery address updated successfully!")
                return redirect("/customer/addresses/")
        elif action == 'delete':
            addr_id = request.POST.get('address_id')
            Address.objects.filter(id=addr_id, user=customer).delete()
            messages.info(request, "Address removed.")
            return redirect("/customer/addresses/")

    my_addresses = Address.objects.filter(user=customer) if customer else Address.objects.all()
    context = {
        'current_panel': 'customer',
        'active_menu': 'addresses',
        'addresses': my_addresses,
    }
    return render(request, "customer/addresses.html", context)


def rewards(request):
    customer = get_current_customer(request)
    context = {
        'current_panel': 'customer',
        'active_menu': 'rewards',
        'customer': customer,
        'reward_points': getattr(customer, 'reward_points', 250),
        'reward_value': (customer.reward_points // 2) if customer else 0,
        'referral_code': getattr(customer, 'referral_code', 'REF-AMAN100'),
    }
    return render(request, "customer/rewards.html", context)


def support(request):
    customer = get_current_customer(request)
    if customer is None:
        return HttpResponseForbidden()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action in {'edit', 'cancel'}:
            ticket = SupportTicket.objects.filter(
                ticket_id=request.POST.get('ticket_id'), user=customer, status='open'
            ).first()
            if ticket is None:
                messages.error(request, 'Only your open support tickets can be changed.')
            elif action == 'cancel':
                ticket.status = 'cancelled'
                ticket.save(update_fields=['status', 'updated_at'])
                messages.success(request, f'Support ticket #{ticket.ticket_id} cancelled.')
            else:
                subject = request.POST.get('subject', '').strip()
                description = request.POST.get('description', '').strip()
                if not subject or not description or len(subject) > 200:
                    messages.error(request, 'Enter a subject (up to 200 characters) and a description.')
                else:
                    ticket.subject = subject
                    ticket.message = description
                    ticket.save(update_fields=['subject', 'message', 'updated_at'])
                    messages.success(request, f'Support ticket #{ticket.ticket_id} updated.')
            suffix = '?all=1' if request.POST.get('show_all') == '1' else ''
            return redirect(f'/customer/support/{suffix}')

        subject = request.POST.get('subject', '').strip()
        description = request.POST.get('description', '').strip()
        if not subject or not description:
            messages.error(request, 'Enter a subject and description for your support request.')
            return redirect('/customer/support/')
        if len(subject) > 200:
            messages.error(request, 'The support ticket subject must be 200 characters or fewer.')
            return redirect('/customer/support/')

        ticket = SupportTicket.objects.create(
            user=customer,
            ticket_id=f'TKT-{uuid.uuid4().hex[:10].upper()}',
            subject=subject,
            category='Customer Support',
            message=description,
        )
        admin_notifications = [
            Notification(
                user=admin,
                title=f'New customer support ticket #{ticket.ticket_id}',
                message=f'{customer.get_full_name() or customer.username}: {subject}',
                notification_type='support',
                link='/admin-panel/tickets/',
            )
            for admin in User.objects.filter(role='admin', is_active=True)
        ]
        if admin_notifications:
            Notification.objects.bulk_create(admin_notifications)
        messages.success(request, f'Support ticket #{ticket.ticket_id} submitted successfully.')
        return redirect('/customer/support/')

    ticket_list = SupportTicket.objects.filter(user=customer).order_by('-created_at')
    show_all = request.GET.get('all') == '1'
    context = {
        'current_panel': 'customer',
        'active_menu': 'support',
        'customer': customer,
        'tickets': ticket_list if show_all else ticket_list[:3],
        'ticket_count': ticket_list.count(),
        'show_all_tickets': show_all,
    }
    return render(request, "customer/support.html", context)


def settings(request):
    customer = get_current_customer(request)
    context = {
        'current_panel': 'customer',
        'active_menu': 'settings',
        'customer': customer,
    }
    return render(request, "customer/settings.html", context)


def payment(request):
    return redirect("/customer/checkout/")


def payment_success(request):
    return render(request, "customer/payment-success.html", {'current_panel': 'customer'})


def payment_failed(request):
    return render(request, "customer/payment-failed.html", {'current_panel': 'customer'})


@csrf_exempt
def razorpay_create_order(request):
    """Create Razorpay Order via REST SDK for Wallet Topup or Checkout"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            amount = float(data.get('amount', 0))
            purpose = data.get('purpose', 'topup')
            
            client = razorpay.Client(auth=(django_settings.RAZORPAY_KEY_ID, django_settings.RAZORPAY_KEY_SECRET))
            amount_in_paise = int(amount * 100)
            
            razorpay_order = client.order.create({
                'amount': amount_in_paise,
                'currency': 'INR',
                'payment_capture': 1,
                'notes': {
                    'purpose': purpose,
                    'user_id': str(request.user.id) if request.user.is_authenticated else 'guest'
                }
            })
            
            return JsonResponse({
                'status': 'success',
                'key_id': django_settings.RAZORPAY_KEY_ID,
                'order_id': razorpay_order['id'],
                'amount': razorpay_order['amount'],
                'currency': razorpay_order['currency']
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


@csrf_exempt
def razorpay_verify_payment(request):
    """Verify Razorpay payment signature and credit E-Wallet or Confirm Order"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            razorpay_order_id = data.get('razorpay_order_id')
            razorpay_payment_id = data.get('razorpay_payment_id')
            razorpay_signature = data.get('razorpay_signature')
            purpose = data.get('purpose', 'topup')
            amount = Decimal(str(data.get('amount', '0')))
            
            client = razorpay.Client(auth=(django_settings.RAZORPAY_KEY_ID, django_settings.RAZORPAY_KEY_SECRET))
            
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            
            # Verify signature using Razorpay SDK
            client.utility.verify_payment_signature(params_dict)
            
            customer = get_current_customer(request)
            if purpose == 'topup' and customer:
                customer.wallet_balance += amount
                customer.save()
                messages.success(request, f"Razorpay Payment Verified! ₹{amount:.2f} credited to your E-Wallet.")
                
            return JsonResponse({
                'status': 'success',
                'message': 'Razorpay payment verified successfully!',
                'payment_id': razorpay_payment_id
            })
        except razorpay.errors.SignatureVerificationError:
            return JsonResponse({'status': 'error', 'message': 'Razorpay payment signature verification failed'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)