from categories.models import Category
from cart.models import Cart
from notifications.models import Notification
from orders.models import Order
from commissions.models import CommissionLog
from delivery.models import DeliveryPartnerProfile
from sellers.models import SellerProfile
from sellers.balances import get_seller_earnings_summary
from support.models import SupportTicket
from users.models import User
from decimal import Decimal
from django.db.models import Sum
from admin_panel.models import MarketplaceSettings


def global_ecommerce_context(request):
    ctx = {
        'global_categories': Category.objects.filter(is_active=True)[:10] if Category._meta.db_table in [t for t in []] or True else [],
        'cart_count': 0,
        'unread_notifications_count': 0,
        'wallet_balance': Decimal('0.00'),
        'delivery_wallet_balance': None,
        'seller_wallet_balance': None,
        'admin_wallet_balance': None,
        'open_support_tickets_count': 0,
        'compare_product_ids': request.session.get('compare_product_ids', []) if hasattr(request, 'session') else [],
		'marketplace_settings': MarketplaceSettings.objects.filter(pk=1).first(),
    }
    try:
        ctx['global_categories'] = Category.objects.filter(is_active=True)[:10]
    except Exception:
        pass

    if request.path.startswith('/admin-panel/') or getattr(request.user, 'role', None) == 'admin':
        log_commission = CommissionLog.objects.filter(
            status='settled', order__status='delivered', order__payment_status='paid'
        ).aggregate(total=Sum('admin_commission_amount'))['total'] or Decimal('0.00')
        ctx['admin_wallet_balance'] = log_commission
        ctx['wallet_balance'] = ctx['admin_wallet_balance']
        ctx['open_support_tickets_count'] = SupportTicket.objects.filter(
            status__in=['open', 'in_progress']
        ).count()

    if request.user.is_authenticated:
        try:
            cart = Cart.objects.filter(user=request.user).first()
            if cart:
                ctx['cart_count'] = cart.items.count()
            ctx['unread_notifications_count'] = Notification.objects.filter(user=request.user, is_read=False).count()
            role = getattr(request.user, 'role', None)
            ctx['wallet_balance'] = request.user.wallet_balance if role == 'customer' else Decimal('0.00')

            if request.path.startswith('/delivery/') or getattr(request.user, 'role', None) == 'delivery':
                delivery_profile = getattr(request.user, 'delivery_profile', None)
                delivery_profile = delivery_profile or DeliveryPartnerProfile.objects.first()
                delivered_orders = Order.objects.filter(
                    delivery_partner=delivery_profile,
                    status='delivered',
                ) if delivery_profile else Order.objects.filter(status='delivered')
                ctx['delivery_wallet_balance'] = delivered_orders.aggregate(
                    total=Sum('delivery_partner_earning')
                )['total'] or Decimal('0.00')
                ctx['wallet_balance'] = ctx['delivery_wallet_balance']

            if request.path.startswith('/seller/') or getattr(request.user, 'role', None) == 'seller':
                seller_profile = getattr(request.user, 'seller_profile', None) or SellerProfile.objects.first()
                ctx['seller_wallet_balance'] = get_seller_earnings_summary(seller_profile)['available_payout']
                ctx['wallet_balance'] = ctx['seller_wallet_balance']

            if request.path.startswith('/admin-panel/') or getattr(request.user, 'role', None) == 'admin':
                ctx['wallet_balance'] = ctx['admin_wallet_balance']
        except Exception:
            pass

    if request.path.startswith('/delivery/') and ctx['delivery_wallet_balance'] is None:
        delivery_profile = DeliveryPartnerProfile.objects.first()
        delivered_orders = Order.objects.filter(
            delivery_partner=delivery_profile,
            status='delivered',
        ) if delivery_profile else Order.objects.none()
        ctx['delivery_wallet_balance'] = delivered_orders.aggregate(
            total=Sum('delivery_partner_earning')
        )['total'] or Decimal('0.00')
        ctx['wallet_balance'] = ctx['delivery_wallet_balance']

    if request.path.startswith('/seller/') and ctx['seller_wallet_balance'] is None:
        seller_profile = SellerProfile.objects.first()
        seller_orders = Order.objects.filter(
            seller=seller_profile,
            status='delivered',
        ) if seller_profile else Order.objects.none()
        ctx['seller_wallet_balance'] = seller_orders.aggregate(
            total=Sum('seller_net_earnings')
        )['total'] or Decimal('0.00')
        ctx['wallet_balance'] = ctx['seller_wallet_balance']

    if request.path.startswith('/customer/') and (
        not request.user.is_authenticated or getattr(request.user, 'role', None) != 'customer'
    ):
        guest_cart = request.session.get('guest_cart', {})
        ctx['cart_count'] = sum(
            int(quantity) for quantity in guest_cart.values() if str(quantity).isdigit()
        )
        ctx['unread_notifications_count'] = 0
        ctx['wallet_balance'] = Decimal('0.00')

    return ctx
