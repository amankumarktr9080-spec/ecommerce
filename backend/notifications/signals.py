from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from notifications.models import Notification
from orders.models import Order
from support.models import SupportTicket
from delivery.models import DeliveryRating
from reviews.models import Review
from users.models import User


def _create_notification(user, title, message, notification_type, link):
    if user:
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link,
        )


def _notify_delivery_assignment(order, notify_customer=True):
    partner_user = order.delivery_partner.user
    _create_notification(
        partner_user,
        'Delivery assigned',
        f'Order #{order.order_number} has been assigned to you.',
        'delivery',
        f'/delivery/active-delivery/{order.id}/',
    )
    if notify_customer:
        _create_notification(
            order.customer,
            'Delivery partner assigned',
            f'A delivery partner has been assigned to order #{order.order_number}.',
            'delivery',
            f'/customer/orders/{order.id}/track/',
        )


@receiver(pre_save, sender=Order)
def remember_order_notification_state(sender, instance, **kwargs):
    instance._notification_previous_state = None
    if instance.pk:
        instance._notification_previous_state = sender.objects.filter(pk=instance.pk).values(
            'status', 'delivery_partner_id'
        ).first()


@receiver(post_save, sender=Order)
def notify_order_events(sender, instance, created, **kwargs):
    order_link = f'/customer/orders/{instance.id}/track/'

    if created:
        _create_notification(
            instance.customer,
            'Order confirmed',
            f'Your order #{instance.order_number} has been placed.',
            'order',
            order_link,
        )
        seller_user = instance.seller.user if instance.seller_id else None
        _create_notification(
            seller_user,
            'New order received',
            f'Order #{instance.order_number} is ready for processing.',
            'order',
            '/seller/orders/',
        )
        if instance.delivery_partner_id:
            _notify_delivery_assignment(instance)
        return

    previous = getattr(instance, '_notification_previous_state', None)
    if not previous:
        return

    if previous['status'] != instance.status:
        _create_notification(
            instance.customer,
            'Order status updated',
            f'Order #{instance.order_number} is now {instance.get_status_display()}.',
            'order',
            order_link,
        )

    if previous['delivery_partner_id'] != instance.delivery_partner_id and instance.delivery_partner_id:
        _notify_delivery_assignment(instance, notify_customer=previous['status'] == instance.status)


@receiver(post_save, sender=SupportTicket)
def notify_support_ticket_created(sender, instance, created, **kwargs):
    if not created:
        return

    for admin_user in User.objects.filter(role='admin'):
        _create_notification(
            admin_user,
            'New support ticket raised',
            f'Support ticket #{instance.ticket_id} for {instance.category}: {instance.subject}',
            'alert',
            '/admin-panel/tickets/',
        )


@receiver(pre_save, sender=Review)
def remember_review_notification_state(sender, instance, **kwargs):
    instance._notification_previous_state = None
    if instance.pk:
        instance._notification_previous_state = sender.objects.filter(pk=instance.pk).values(
            'rating', 'title', 'comment'
        ).first()


@receiver(post_save, sender=Review)
def notify_seller_of_new_product_review(sender, instance, created, **kwargs):
    previous = getattr(instance, '_notification_previous_state', None)
    if not created and (
        not previous
        or (
            previous['rating'] == instance.rating
            and previous['title'] == instance.title
            and previous['comment'] == instance.comment
        )
    ):
        return

    _create_notification(
        instance.product.seller.user,
        'New product review received',
        f'{instance.customer.get_full_name() or instance.customer.username} rated {instance.product.title} {instance.rating}/5: {instance.title}',
        'alert',
        '/seller/reviews/',
    )


@receiver(pre_save, sender=DeliveryRating)
def remember_delivery_rating_notification_state(sender, instance, **kwargs):
    instance._notification_previous_state = None
    if instance.pk:
        instance._notification_previous_state = sender.objects.filter(pk=instance.pk).values(
            'rating', 'comment', 'delivery_partner_id'
        ).first()


@receiver(post_save, sender=DeliveryRating)
def notify_delivery_rating_created(sender, instance, created, **kwargs):
    previous = getattr(instance, '_notification_previous_state', None)
    if not created and (
        not previous
        or (
            previous['rating'] == instance.rating
            and previous['comment'] == instance.comment
            and previous['delivery_partner_id'] == instance.delivery_partner_id
        )
    ):
        return

    _create_notification(
        instance.delivery_partner.user,
        'New delivery rating received',
        f'Customer {instance.customer.get_full_name() or instance.customer.username} rated your delivery {instance.rating}/5.',
        'delivery',
        '/delivery/ratings/',
    )