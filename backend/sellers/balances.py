from decimal import Decimal

from django.db.models import Sum

from orders.models import Order
from sellers.models import PayoutRequest


def get_seller_earnings_summary(seller):
    empty_summary = {
        'gross_sales': Decimal('0.00'),
        'admin_commissions': Decimal('0.00'),
        'net_earnings': Decimal('0.00'),
        'pending_earnings': Decimal('0.00'),
        'available_payout': Decimal('0.00'),
    }
    if not seller:
        return empty_summary

    delivered_orders = Order.objects.filter(seller=seller, status='delivered', payment_status='paid')
    gross_sales = delivered_orders.aggregate(total=Sum('subtotal'))['total'] or Decimal('0.00')
    admin_commissions = delivered_orders.aggregate(total=Sum('admin_commission_amount'))['total'] or Decimal('0.00')
    net_earnings = delivered_orders.aggregate(total=Sum('seller_net_earnings'))['total'] or Decimal('0.00')
    pending_earnings = Order.objects.filter(seller=seller).exclude(
        status__in=['delivered', 'cancelled', 'returned', 'replaced']
    ).aggregate(total=Sum('seller_net_earnings'))['total'] or Decimal('0.00')
    reserved_payouts = PayoutRequest.objects.filter(
        seller=seller,
        status__in=['pending', 'approved', 'paid'],
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    return {
        'gross_sales': gross_sales,
        'admin_commissions': admin_commissions,
        'net_earnings': net_earnings,
        'pending_earnings': pending_earnings,
        'available_payout': max(Decimal('0.00'), net_earnings - reserved_payouts),
    }