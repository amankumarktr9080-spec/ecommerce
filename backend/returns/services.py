from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from commissions.models import CommissionLog
from delivery.models import DeliveryPartnerProfile
from notifications.models import Notification
from orders.models import Order, OrderItem, OrderTimeline
from payments.models import PaymentTransaction
from products.models import Product
from returns.models import ReturnRequest


RETURN_PICKUP_FEE = Decimal('50.00')


class ReturnValidationError(ValueError):
    pass


def _notify(user, title, message, link='/customer/returns/'):
    if user:
        Notification.objects.create(
            user=user, title=title, message=message,
            notification_type='order', link=link,
        )


def _notify_admins(title, message):
    from users.models import User
    for admin in User.objects.filter(role='admin', is_active=True):
        _notify(admin, title, message, '/admin-panel/returns/')


def _delivered_at(order):
    return order.delivered_at or order.updated_at


def _has_existing_request(item):
    return ReturnRequest.objects.filter(order_item=item).exclude(status='cancelled').exists()


@transaction.atomic
def create_return_request(*, customer, order_id, order_item_id, quantity, request_type,
                          reason, details='', photo_url=''):
    order = Order.objects.select_for_update().filter(
        id=order_id, customer=customer, status='delivered'
    ).first()
    if order is None:
        raise ReturnValidationError('Only your delivered orders can be returned.')

    if not order_item_id and not OrderItem.objects.filter(order=order).exists():
        if request_type not in {'return', 'replace'} or reason not in dict(ReturnRequest.REASON_CHOICES):
            raise ReturnValidationError('Choose a valid resolution and reason.')
        if not details.strip():
            raise ReturnValidationError('Please describe the issue.')
        return ReturnRequest.objects.create(
            order=order, customer=customer, request_type=request_type,
            reason=reason, quantity=1, details=details.strip(),
            photo_url=photo_url, status='pending',
        )

    item = OrderItem.objects.select_related('product').filter(
        id=order_item_id, order=order
    ).first()
    if item is None:
        raise ReturnValidationError('Select a valid product from this order.')
    if request_type not in {'return', 'replace'}:
        raise ReturnValidationError('Choose a valid resolution type.')
    if reason not in dict(ReturnRequest.REASON_CHOICES):
        raise ReturnValidationError('Choose a valid return reason.')
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ReturnValidationError('Quantity must be a positive number.')
    if quantity < 1 or quantity > item.quantity:
        raise ReturnValidationError('Requested quantity is not available.')

    product = item.product
    allowed = product.is_returnable if request_type == 'return' else product.is_replaceable
    window = product.return_window_days if request_type == 'return' else product.replacement_window_days
    if not allowed:
        raise ReturnValidationError('This product is not eligible for this resolution.')
    if timezone.now() > _delivered_at(order) + timezone.timedelta(days=window):
        raise ReturnValidationError('The return/replacement window has expired.')
    if _has_existing_request(item):
        raise ReturnValidationError('Cancel the existing request for this product before submitting another one.')
    if not details.strip():
        raise ReturnValidationError('Please describe the issue.')

    request = ReturnRequest.objects.create(
        order=order, order_item=item, customer=customer,
        request_type=request_type, reason=reason, quantity=quantity,
        details=details.strip(), photo_url=photo_url, status='pending',
    )
    OrderTimeline.objects.create(
        order=order, status='pending', title='Return request submitted',
        description=f'{request.get_request_type_display()} for {item.product.title} (x{quantity}).',
    )
    _notify(
        order.seller.user,
        'New return/replacement request',
        f'Request #{request.id} was submitted for order #{order.order_number}.',
        '/seller/returns/',
    )
    _notify_admins('New return/replacement request', f'Request #{request.id} needs review.')
    return request


@transaction.atomic
def approve_request(return_id, *, remarks='', approved_by='seller'):
    request = ReturnRequest.objects.select_for_update().select_related('order', 'customer').get(id=return_id)
    if request.status != 'pending':
        raise ReturnValidationError('Only pending requests can be approved.')
    request.status = 'approved'
    request.approved_at = timezone.now()
    if approved_by == 'admin':
        request.admin_remarks = remarks
    else:
        request.seller_remarks = remarks
    request.save(update_fields=['status', 'approved_at', 'seller_remarks', 'admin_remarks', 'updated_at'])
    OrderTimeline.objects.create(order=request.order, status='approved', title='Return request approved')
    _notify(request.customer, 'Return request approved', f'Request #{request.id} has been approved and is ready for pickup.')
    _notify_admins('Return request approved', f'Request #{request.id} was approved by {approved_by}.')
    return request


@transaction.atomic
def reject_request(return_id, *, remarks='', rejected_by='seller'):
    request = ReturnRequest.objects.select_for_update().get(id=return_id)
    if request.status != 'pending':
        raise ReturnValidationError('Only pending requests can be rejected.')
    request.status = 'rejected'
    if rejected_by == 'admin':
        request.admin_remarks = remarks
    else:
        request.seller_remarks = remarks
    request.save(update_fields=['status', 'seller_remarks', 'admin_remarks', 'updated_at'])
    _notify(request.customer, 'Return request rejected', f'Request #{request.id} was rejected.', '/customer/returns/')
    _notify_admins('Return request rejected', f'Request #{request.id} was rejected.')
    return request


@transaction.atomic
def cancel_return_request(return_id, *, customer):
    request = ReturnRequest.objects.select_for_update().get(id=return_id, customer=customer)
    if request.status not in {'pending', 'approved', 'pickup_scheduled'}:
        raise ReturnValidationError('This request can no longer be cancelled.')
    request.status = 'cancelled'
    request.save(update_fields=['status', 'updated_at'])
    return request


@transaction.atomic
def schedule_pickup(return_id, *, pickup_partner=None, tracking_id=''):
    request = ReturnRequest.objects.select_for_update().select_related('order', 'customer').get(id=return_id)
    if request.status != 'approved':
        raise ReturnValidationError('Only approved requests can be scheduled for pickup.')
    request.status = 'pickup_scheduled'
    request.pickup_partner = pickup_partner
    request.pickup_tracking_id = tracking_id.strip() or f'RPU-{uuid4().hex[:12].upper()}'
    request.save(update_fields=['status', 'pickup_partner', 'pickup_tracking_id', 'updated_at'])
    OrderTimeline.objects.create(
        order=request.order, status='pickup_scheduled', title='Manual return pickup scheduled',
        description=f'Pickup tracking: {request.pickup_tracking_id}.',
    )
    _notify(request.customer, 'Return pickup scheduled', f'Request #{request.id} pickup is scheduled. Tracking: {request.pickup_tracking_id}.')
    _notify(request.order.seller.user, 'Return pickup scheduled', f'Request #{request.id} is assigned for manual pickup.', '/seller/returns/')
    _notify_admins('Return pickup scheduled', f'Request #{request.id} pickup was scheduled.')
    if pickup_partner:
        _notify(
            pickup_partner.user, 'Manual return pickup assigned',
            f'Pickup request #{request.id} is assigned to you. Reference: {request.pickup_tracking_id}.',
            '/delivery/active-delivery/',
        )
    return request


@transaction.atomic
def mark_picked_up(return_id, pickup_partner=None):
    request = ReturnRequest.objects.select_for_update().select_related('order').get(id=return_id)
    if request.status not in {'approved', 'pickup_scheduled'}:
        raise ReturnValidationError('This request is not ready for pickup.')
    request.status = 'item_picked_up'
    if pickup_partner is not None:
        request.pickup_partner = pickup_partner
    request.pickup_tracking_id = request.pickup_tracking_id or f'RPU-{uuid4().hex[:12].upper()}'
    request.picked_up_at = timezone.now()
    if request.pickup_partner and request.pickup_earning == Decimal('0.00'):
        request.pickup_earning = RETURN_PICKUP_FEE
        order = Order.objects.select_for_update().get(id=request.order_id)
        order.seller_net_earnings -= RETURN_PICKUP_FEE
        order.save(update_fields=['seller_net_earnings', 'updated_at'])
        CommissionLog.objects.filter(order=order).update(
            seller_payout_amount=F('seller_payout_amount') - RETURN_PICKUP_FEE,
            delivery_payout_amount=F('delivery_payout_amount') + RETURN_PICKUP_FEE,
        )
    request.save(update_fields=[
        'status', 'pickup_partner', 'pickup_tracking_id', 'picked_up_at',
        'pickup_earning', 'updated_at',
    ])
    OrderTimeline.objects.create(order=request.order, status='item_picked_up', title='Return item picked up')
    _notify(request.customer, 'Return item picked up', f'Request #{request.id} item was picked up.', '/customer/returns/')
    _notify(request.order.seller.user, 'Return item picked up', f'Request #{request.id} item was collected.', '/seller/returns/')
    _notify_admins('Return item picked up', f'Request #{request.id} item was collected.')
    return request


@transaction.atomic
def inspect_return(return_id, *, passed, remarks=''):
    request = ReturnRequest.objects.select_for_update().select_related('order').get(id=return_id)
    if request.status != 'item_picked_up':
        raise ReturnValidationError('Only picked-up items can be inspected.')
    request.inspected_at = timezone.now()
    if not passed:
        request.status = 'inspection_failed'
        request.admin_remarks = remarks or 'Inspection failed.'
        request.save(update_fields=['status', 'inspected_at', 'admin_remarks', 'updated_at'])
        OrderTimeline.objects.create(
            order=request.order, status='inspection_failed', title='Return inspection failed',
            description=request.admin_remarks,
        )
        _notify(request.customer, 'Return inspection failed', f'Request #{request.id} inspection failed.', '/customer/returns/')
        _notify(request.order.seller.user, 'Return inspection failed', f'Request #{request.id} inspection failed.', '/seller/returns/')
        return request
    request.status = 'inspection_passed'
    request.admin_remarks = remarks
    request.save(update_fields=['status', 'inspected_at', 'admin_remarks', 'updated_at'])
    OrderTimeline.objects.create(
        order=request.order, status='inspection_passed', title='Return inspection passed',
        description=remarks or 'Returned item passed inspection.',
    )
    _notify(request.customer, 'Return inspection passed', f'Request #{request.id} passed inspection.', '/customer/returns/')
    _notify(request.order.seller.user, 'Return inspection passed', f'Request #{request.id} passed inspection.', '/seller/returns/')
    if request.request_type == 'return':
        if request.order_item_id is None:
            raise ReturnValidationError('This legacy request has no item selected for inspection.')
        item = OrderItem.objects.select_related('product').get(id=request.order_item_id)
        product = Product.objects.select_for_update().get(id=item.product_id)
        product.stock += request.quantity
        product.save(update_fields=['stock'])
    return request


def _item_refund_amount(request):
    item = request.order_item
    return (item.total_price / item.quantity * request.quantity).quantize(Decimal('0.01'))


@transaction.atomic
def fallback_replacement_to_wallet_refund(return_id):
    request = ReturnRequest.objects.select_for_update().select_related('order', 'customer').get(id=return_id)
    if request.request_type != 'replace' or request.status != 'replacement_failed':
        raise ReturnValidationError('Only failed replacements can be converted to a wallet refund.')
    if request.order_item_id is None:
        raise ReturnValidationError('This legacy request has no item selected for refund.')
    item = OrderItem.objects.get(id=request.order_item_id)
    product = Product.objects.select_for_update().get(id=item.product_id)
    product.stock += request.quantity
    product.save(update_fields=['stock'])
    refund_amount = _item_refund_amount(request) if request.order.payment_status == 'paid' else Decimal('0.00')
    request.refund_amount = refund_amount
    request.refund_method = 'wallet' if refund_amount else 'none'
    request.status = 'refund_processed'
    request.admin_remarks = 'Replacement unavailable; wallet refund issued.'
    request.save(update_fields=['refund_amount', 'refund_method', 'status', 'admin_remarks', 'updated_at'])
    if refund_amount:
        customer = request.customer.__class__.objects.select_for_update().get(pk=request.customer_id)
        customer.wallet_balance += refund_amount
        customer.save(update_fields=['wallet_balance'])
    return True, refund_amount


@transaction.atomic
def process_return_refund(return_id):
    request = ReturnRequest.objects.select_for_update().select_related('order', 'customer').get(id=return_id)
    if request.status == 'refund_processed':
        return False, request.refund_amount
    if request.request_type != 'return' or request.status != 'inspection_passed':
        raise ReturnValidationError('Refund is allowed only after a passed inspection.')
    if request.order_item_id is None:
        raise ReturnValidationError('This legacy request has no item selected and cannot be refunded safely.')
    request.order_item = OrderItem.objects.get(id=request.order_item_id)

    refund_amount = _item_refund_amount(request) if request.order.payment_status == 'paid' else Decimal('0.00')
    request.refund_amount = refund_amount
    request.refund_method = 'wallet' if refund_amount else 'none'
    request.status = 'refund_processed'
    request.save(update_fields=['refund_amount', 'refund_method', 'status', 'updated_at'])
    OrderTimeline.objects.create(
        order=request.order, status='refund_processed', title='Wallet refund completed',
        description=f'₹{refund_amount} credited to the customer wallet.',
    )
    _notify(request.customer, 'Wallet refund completed', f'₹{refund_amount} was credited for request #{request.id}.', '/customer/returns/')
    _notify(request.order.seller.user, 'Return refund completed', f'Wallet refund for request #{request.id} was processed.', '/seller/returns/')
    _notify_admins('Return refund completed', f'Wallet refund for request #{request.id} was processed.')

    if refund_amount:
        customer = request.customer.__class__.objects.select_for_update().get(pk=request.customer_id)
        customer.wallet_balance += refund_amount
        customer.save(update_fields=['wallet_balance'])
        order = request.order
        total_refunded = ReturnRequest.objects.filter(
            order=order, status='refund_processed'
        ).aggregate(total=Sum('refund_amount'))['total'] or Decimal('0.00')
        if total_refunded >= order.grand_total:
            order.payment_status = 'refunded'
            order.status = 'returned'
            order.save(update_fields=['payment_status', 'status', 'updated_at'])
            PaymentTransaction.objects.filter(order=order, status='success').update(status='refunded')
            CommissionLog.objects.filter(order=order).update(status='refunded')
        else:
            order.save(update_fields=['updated_at'])
    return True, refund_amount


@transaction.atomic
def create_replacement(return_id):
    request = ReturnRequest.objects.select_for_update().select_related('order').get(id=return_id)
    if request.request_type != 'replace' or request.status != 'inspection_passed':
        raise ReturnValidationError('Replacement can start only after a passed inspection.')
    if request.order_item_id is None:
        raise ReturnValidationError('This legacy request has no item selected for replacement.')
    if request.replacement_order_id:
        return request.replacement_order
    item = OrderItem.objects.get(id=request.order_item_id)
    product = Product.objects.select_for_update().get(id=item.product_id)
    if product.stock < request.quantity:
        request.status = 'replacement_failed'
        request.admin_remarks = 'Replacement stock is unavailable.'
        request.save(update_fields=['status', 'admin_remarks', 'updated_at'])
        OrderTimeline.objects.create(
            order=request.order, status='replacement_failed', title='Replacement unavailable',
            description=request.admin_remarks,
        )
        _notify(request.customer, 'Replacement unavailable', f'Request #{request.id} can be refunded to your wallet.', '/customer/returns/')
        _notify(request.order.seller.user, 'Replacement unavailable', f'Request #{request.id} has no replacement stock.', '/seller/returns/')
        return None
    product.stock -= request.quantity
    product.save(update_fields=['stock'])
    partner = DeliveryPartnerProfile.objects.filter(is_approved=True, is_online=True).first()
    replacement = Order.objects.create(
        order_number=f'REP-{uuid4().hex[:20].upper()}', customer=request.customer,
        seller=request.order.seller, delivery_partner=partner, status='packed',
        customer_name=request.order.customer_name, customer_phone=request.order.customer_phone,
        shipping_address=request.order.shipping_address, subtotal=Decimal('0.00'),
        delivery_charge=Decimal('0.00'), tax=Decimal('0.00'), grand_total=Decimal('0.00'),
        seller_net_earnings=-RETURN_PICKUP_FEE,
        delivery_partner_earning=RETURN_PICKUP_FEE,
        payment_method=request.order.payment_method, payment_status='paid',
        tracking_id=f'REP-{uuid4().hex[:12].upper()}', replacement_for=request,
    )
    CommissionLog.objects.create(
        order=replacement, rate_percentage=Decimal('0.00'),
        order_total=Decimal('0.00'), admin_commission_amount=Decimal('0.00'),
        seller_payout_amount=-RETURN_PICKUP_FEE,
        delivery_payout_amount=RETURN_PICKUP_FEE, status='pending',
    )
    OrderItem.objects.create(order=replacement, product=product, quantity=request.quantity,
                             unit_price=Decimal('0.00'), total_price=Decimal('0.00'))
    request.replacement_order = replacement
    request.status = 'replacement_dispatched'
    request.save(update_fields=['replacement_order', 'status', 'updated_at'])
    OrderTimeline.objects.create(
        order=request.order, status='replacement_dispatched', title='Replacement dispatched',
        description=f'Replacement order #{replacement.order_number} created and dispatched.',
    )
    _notify(request.customer, 'Replacement dispatched', f'Replacement order #{replacement.order_number} is on the way.', '/customer/returns/')
    _notify(request.order.seller.user, 'Replacement dispatched', f'Replacement order #{replacement.order_number} was created.', '/seller/returns/')
    if partner:
        _notify(partner.user, 'Replacement delivery assigned', f'Replacement order #{replacement.order_number} is assigned to you.', '/delivery/active-delivery/')
    _notify_admins('Replacement dispatched', f'Replacement order #{replacement.order_number} was created.')
    OrderTimeline.objects.create(order=replacement, status='packed', title='Replacement dispatched')
    return replacement


@transaction.atomic
def refund_cancelled_wallet_order(order_id):
    order = Order.objects.select_for_update().select_related('customer').get(id=order_id)
    if order.status != 'cancelled' or order.payment_status != 'paid' or order.payment_method != 'wallet':
        return False, Decimal('0.00')
    payment = PaymentTransaction.objects.select_for_update().filter(order=order, payment_method__iexact='wallet', status='success').order_by('id').first()
    if payment is None or payment.amount != order.grand_total:
        return False, Decimal('0.00')
    order.customer.wallet_balance += payment.amount
    order.customer.save(update_fields=['wallet_balance'])
    payment.status = 'refunded'
    payment.save(update_fields=['status'])
    order.payment_status = 'refunded'
    order.admin_commission_amount = Decimal('0.00')
    order.seller_net_earnings = Decimal('0.00')
    order.save(update_fields=['payment_status', 'admin_commission_amount', 'seller_net_earnings', 'updated_at'])
    CommissionLog.objects.filter(order=order).update(status='cancelled')
    return True, payment.amount


@transaction.atomic
def record_cancelled_external_refund(order_id, refund_reference):
    order = Order.objects.select_for_update().get(id=order_id)
    refund_reference = refund_reference.strip()
    if order.status != 'cancelled' or order.payment_status != 'paid' or order.payment_method == 'wallet' or not refund_reference:
        return False, Decimal('0.00')
    payments = list(PaymentTransaction.objects.select_for_update().filter(order=order, status='success').order_by('id'))
    refund_amount = sum((payment.amount for payment in payments), Decimal('0.00'))
    if not payments or refund_amount != order.grand_total:
        return False, Decimal('0.00')
    for payment in payments:
        payment.status = 'refunded'
        payment.refund_reference = refund_reference
        payment.save(update_fields=['status', 'refund_reference'])
    order.payment_status = 'refunded'
    order.admin_commission_amount = Decimal('0.00')
    order.seller_net_earnings = Decimal('0.00')
    order.save(update_fields=['payment_status', 'admin_commission_amount', 'seller_net_earnings', 'updated_at'])
    CommissionLog.objects.filter(order=order).update(status='cancelled')
    return True, refund_amount
