import random
import json
from uuid import uuid4
from datetime import datetime, time, timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Avg, Count, F, Min, Q, Sum
from django.db import transaction

from delivery.models import DeliveryPartnerProfile, DeliveryRating
from orders.models import Order, OrderTimeline
from returns.models import ReturnRequest
from returns.services import ReturnValidationError, mark_picked_up
from payments.models import PaymentTransaction
from commissions.models import CommissionLog
from notifications.models import Notification
from support.models import SupportTicket
from users.models import User


def get_current_rider(request):
    if request.user.is_authenticated and request.user.role == 'delivery':
        return getattr(request.user, 'delivery_profile', None) or DeliveryPartnerProfile.objects.first()
    return DeliveryPartnerProfile.objects.first()


def get_delivery_chart_data(orders, rider=None):
    today = timezone.localdate()
    dates = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    labels = [day.strftime('%a') for day in dates]
    earnings = []
    deliveries = []
    for day in dates:
        completed_order_ids = OrderTimeline.objects.filter(
            order__in=orders,
            title='Delivered Successfully',
            timestamp__date=day,
        ).values('order_id')
        day_orders = orders.filter(status='delivered', id__in=completed_order_ids).distinct()
        daily_earnings = day_orders.aggregate(total=Sum('delivery_partner_earning'))['total'] or Decimal('0.00')
        daily_deliveries = day_orders.count()
        if rider:
            daily_pickups = ReturnRequest.objects.filter(
                pickup_partner=rider, picked_up_at__date=day,
            )
            daily_earnings += daily_pickups.aggregate(total=Sum('pickup_earning'))['total'] or Decimal('0.00')
            daily_deliveries += daily_pickups.count()
        earnings.append(float(daily_earnings))
        deliveries.append(daily_deliveries)
    return json.dumps(labels), json.dumps(earnings), json.dumps(deliveries)


def dashboard(request):
    rider = get_current_rider(request)
    my_orders = Order.objects.filter(delivery_partner=rider) if rider else Order.objects.none()
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    completed_orders = my_orders.filter(status='delivered')
    today_completed_orders = completed_orders.filter(
        timeline__title='Delivered Successfully',
        timeline__timestamp__date=today,
    ).distinct()
    week_completed_orders = completed_orders.filter(
        timeline__title='Delivered Successfully',
        timeline__timestamp__date__gte=week_start,
        timeline__timestamp__date__lte=today,
    ).distinct()
    pickup_earnings = ReturnRequest.objects.filter(pickup_partner=rider, picked_up_at__isnull=False) if rider else ReturnRequest.objects.none()
    today_pickups = pickup_earnings.filter(picked_up_at__date=today)
    week_pickups = pickup_earnings.filter(picked_up_at__date__gte=week_start, picked_up_at__date__lte=today)

    today_deliveries = today_completed_orders.count() + today_pickups.count()
    today_earnings = (today_completed_orders.aggregate(total=Sum('delivery_partner_earning'))['total'] or Decimal('0.00')) + (
        today_pickups.aggregate(total=Sum('pickup_earning'))['total'] or Decimal('0.00')
    )
    total_summary = completed_orders.aggregate(
        deliveries=Count('id'),
        earnings=Sum('delivery_partner_earning'),
    )
    total_deliveries = (total_summary['deliveries'] or 0) + pickup_earnings.count()
    total_earnings = (total_summary['earnings'] or Decimal('0.00')) + (
        pickup_earnings.aggregate(total=Sum('pickup_earning'))['total'] or Decimal('0.00')
    )
    week_deliveries = week_completed_orders.count() + week_pickups.count()
    week_earnings = (week_completed_orders.aggregate(total=Sum('delivery_partner_earning'))['total'] or Decimal('0.00')) + (
        week_pickups.aggregate(total=Sum('pickup_earning'))['total'] or Decimal('0.00')
    )
    average_rating = DeliveryRating.objects.filter(delivery_partner=rider).aggregate(average=Avg('rating'))['average'] if rider else None

    active_order = my_orders.filter(status__in=['shipped', 'out_for_delivery']).first() or Order.objects.filter(status='out_for_delivery').first()
    chart_labels, chart_earnings, chart_deliveries = get_delivery_chart_data(my_orders, rider)

    context = {
        'current_panel': 'delivery',
        'active_menu': 'dashboard',
        'rider': rider,
        'today_deliveries': today_deliveries,
        'today_earnings': today_earnings,
        'total_deliveries': total_deliveries,
        'total_earnings': total_earnings,
        'week_deliveries': week_deliveries,
        'week_earnings': week_earnings,
        'average_rating': average_rating,
        'active_order': active_order,
        'chart_labels': chart_labels,
        'chart_earnings': chart_earnings,
        'chart_deliveries': chart_deliveries,
    }
    return render(request, "delivery/dashboard.html", context)


def toggle_duty(request):
    rider = get_current_rider(request)
    if rider:
        rider.is_online = not rider.is_online
        rider.save()
        messages.success(request, f"Duty status changed: {'ONLINE 🟢' if rider.is_online else 'OFFLINE 🔴'}")
    return redirect("/delivery/dashboard/")


@login_required(login_url='/auth/login/')
def active_delivery(request):
    if request.user.role != 'delivery':
        return HttpResponseForbidden()

    rider = DeliveryPartnerProfile.objects.filter(user=request.user).first()
    if rider is None:
        return HttpResponseForbidden()
    assigned_orders = Order.objects.filter(
        delivery_partner=rider,
        status__in=['packed', 'shipped', 'out_for_delivery'],
    ).select_related('seller').order_by('created_at')
    assigned_return_pickups = ReturnRequest.objects.filter(
        pickup_partner=rider, status='pickup_scheduled',
    ).select_related('order', 'order_item__product', 'customer').order_by('created_at')
    search_query = request.GET.get('q', '').strip()
    if search_query:
        assigned_orders = assigned_orders.filter(
            Q(order_number__icontains=search_query)
            | Q(customer_name__icontains=search_query)
            | Q(customer_phone__icontains=search_query)
            | Q(shipping_address__icontains=search_query)
            | Q(seller__store_name__icontains=search_query)
        )
        assigned_return_pickups = assigned_return_pickups.filter(
            Q(order__order_number__icontains=search_query)
            | Q(customer__username__icontains=search_query)
            | Q(order__shipping_address__icontains=search_query)
        )
    if request.GET.get('suggestions') == '1':
        return JsonResponse({
            'results': [
                {
                    'id': order.id,
                    'title': f'#{order.order_number}',
                    'subtitle': f'{order.customer_name} · {order.seller.store_name} · {order.get_status_display()}',
                }
                for order in assigned_orders[:6]
            ]
        })
    context = {
        'current_panel': 'delivery',
        'active_menu': 'active',
        'rider': rider,
        'assigned_orders': assigned_orders,
        'assigned_return_pickups': assigned_return_pickups,
        'search_query': search_query,
    }
    return render(request, "delivery/active-deliveries.html", context)


@login_required(login_url='/auth/login/')
def return_pickup_details(request, return_id):
    if request.user.role != 'delivery':
        return HttpResponseForbidden()
    rider = DeliveryPartnerProfile.objects.filter(user=request.user).first()
    if rider is None:
        return HttpResponseForbidden()
    pickup = get_object_or_404(
        ReturnRequest.objects.select_related('order', 'order_item__product', 'customer'),
        id=return_id, pickup_partner=rider,
    )
    if pickup.status != 'pickup_scheduled':
        messages.info(request, f'Return pickup #{pickup.id} is already {pickup.get_status_display().lower()}.')
        return redirect('/delivery/active-delivery/')
    if request.method == 'POST' and request.POST.get('action') == 'confirm_pickup':
        try:
            mark_picked_up(pickup.id, pickup_partner=rider)
        except ReturnValidationError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f'Return pickup #{pickup.id} confirmed.')
        return redirect('/delivery/active-delivery/')
    return render(request, 'delivery/return-pickup-details.html', {
        'current_panel': 'delivery',
        'active_menu': 'active',
        'rider': rider,
        'pickup': pickup,
    })


@login_required(login_url='/auth/login/')
def _delivery_order_workflow(request, delivery_id):
    if request.user.role != 'delivery':
        return HttpResponseForbidden()

    rider = DeliveryPartnerProfile.objects.filter(user=request.user).first()
    if rider is None:
        return HttpResponseForbidden()
    assigned_orders = Order.objects.filter(
        delivery_partner=rider,
        status__in=['packed', 'shipped', 'out_for_delivery'],
    ).select_related('seller').order_by('created_at')
    active_order = get_object_or_404(assigned_orders, id=delivery_id)

    # Workflow Actions & OTP Verification
    if request.method == "POST" and active_order:
        action = request.POST.get('action')

        if action == 'skip_order':
            active_order.delivery_partner = None
            active_order.status = 'shipped'
            active_order.save(update_fields=['delivery_partner', 'status', 'updated_at'])
            OrderTimeline.objects.create(order=active_order, status='shipped', title='Delivery Skipped', description='Rider skipped this assignment for reassignment.')
            messages.info(request, f'Order #{active_order.order_number} removed from your active deliveries.')
            return redirect('/delivery/active-delivery/')

        if action == 'reschedule_order':
            try:
                requested_date = parse_date(request.POST.get('estimated_delivery', '').strip())
            except (TypeError, ValueError):
                requested_date = None
            requested_eta = (
                timezone.make_aware(
                    datetime.combine(requested_date, time(hour=16, minute=30)),
                    timezone.get_current_timezone(),
                )
                if requested_date else None
            )
            reason = request.POST.get('reschedule_reason', '').strip()

            if requested_eta is None:
                messages.error(request, 'Choose a valid new delivery date.')
            elif requested_eta <= timezone.now():
                messages.error(request, 'Choose a delivery date that is still available.')
            elif not reason:
                messages.error(request, 'Enter a reason for rescheduling this delivery.')
            elif len(reason) > 300:
                messages.error(request, 'The reschedule reason must be 300 characters or fewer.')
            else:
                previous_eta = (
                    timezone.localtime(active_order.estimated_delivery).strftime('%d %b %Y')
                    if active_order.estimated_delivery else 'Not set'
                )
                active_order.estimated_delivery = requested_eta
                with transaction.atomic():
                    active_order.save(update_fields=['estimated_delivery', 'updated_at'])
                    OrderTimeline.objects.create(
                        order=active_order,
                        status=active_order.status,
                        title='Delivery Rescheduled',
                        description=(
                            f'Previous estimate: {previous_eta}. '
                            f'New estimate: {timezone.localtime(requested_eta):%d %b %Y}. '
                            f'Reason: {reason}'
                        ),
                    )
                    Notification.objects.create(
                        user=active_order.customer,
                        title='Delivery date updated',
                        message=(
                            f'Order #{active_order.order_number} is now expected on '
                            f'{timezone.localtime(requested_eta):%d %b %Y}. Reason: {reason}'
                        ),
                        notification_type='delivery',
                        link=f'/customer/orders/{active_order.id}/track/',
                    )
                messages.success(request, 'The new delivery date has been saved and the customer was notified.')
                return redirect('/delivery/active-delivery/')

        if action == 'cancel_order':
            if active_order.payment_status == 'paid':
                messages.error(request, 'Paid orders cannot be cancelled here. Contact Admin to arrange a refund first.')
                return redirect(f'/delivery/active-delivery/{active_order.id}/')

            active_order.status = 'cancelled'
            active_order.delivery_partner = None
            active_order.admin_commission_amount = Decimal('0.00')
            active_order.seller_net_earnings = Decimal('0.00')
            active_order.save(update_fields=[
                'status', 'delivery_partner', 'admin_commission_amount',
                'seller_net_earnings', 'updated_at',
            ])
            CommissionLog.objects.filter(order=active_order).update(status='cancelled')
            PaymentTransaction.objects.filter(order=active_order, status='pending').update(status='cancelled')
            OrderTimeline.objects.create(order=active_order, status='cancelled', title='Delivery Cancelled', description='Delivery assignment cancelled by rider.')
            messages.warning(request, f'Order #{active_order.order_number} cancelled.')
            return redirect('/delivery/active-delivery/')

        if action == 'reached_seller':
            OrderTimeline.objects.create(order=active_order, status='processing', title='Rider Reached Store', description='At vendor warehouse collecting parcel.')
            messages.info(request, "Status updated: Reached Vendor Store.")
            return redirect(f'/delivery/active-delivery/{active_order.id}/')

        elif action == 'picked_up':
            active_order.status = 'out_for_delivery'
            active_order.save()
            OrderTimeline.objects.create(order=active_order, status='out_for_delivery', title='Parcel Picked Up', description='Rider is traveling to customer.')
            messages.success(request, "Parcel picked up! Starting navigation.")
            return redirect(f'/delivery/active-delivery/{active_order.id}/')

        elif action == 'reached_customer':
            OrderTimeline.objects.create(order=active_order, status='out_for_delivery', title='Rider at Doorstep', description='Arrived at customer shipping address.')
            messages.info(request, "Status updated: Arrived at customer doorstep. Ask for 4-digit OTP.")
            return redirect(f'/delivery/active-delivery/{active_order.id}/')

        elif action == 'verify_otp_deliver':
            entered_otp = request.POST.get('entered_otp', '').strip()
            signature_data = request.POST.get('signature_data', '')

            # Verify OTP
            if entered_otp == active_order.delivery_otp:
                active_order.status = 'delivered'
                active_order.delivered_at = timezone.now()
                active_order.payment_status = 'paid'
                active_order.customer_signature = signature_data
                active_order.save(update_fields=['status', 'delivered_at', 'payment_status', 'customer_signature', 'updated_at'])
                PaymentTransaction.objects.filter(order=active_order, status='pending').update(status='success')
                CommissionLog.objects.filter(order=active_order).update(status='settled')

                OrderTimeline.objects.create(
                    order=active_order,
                    status='delivered',
                    title='Delivered Successfully',
                    description=f'Verified with OTP {entered_otp} and customer digital signature.'
                )

                replacement_request = ReturnRequest.objects.filter(
                    replacement_order=active_order,
                    status='replacement_dispatched',
                ).first()
                if replacement_request:
                    replacement_request.status = 'replacement_delivered'
                    replacement_request.save(update_fields=['status', 'updated_at'])
                    original_order = replacement_request.order
                    original_order.status = 'replaced'
                    original_order.save(update_fields=['status', 'updated_at'])
                    Notification.objects.create(
                        user=original_order.customer,
                        title='Replacement delivered',
                        message=f'Replacement order #{active_order.order_number} was delivered successfully.',
                        notification_type='order', link=f'/customer/orders/{original_order.id}/track/',
                    )
                    Notification.objects.create(
                        user=original_order.seller.user,
                        title='Replacement delivered',
                        message=f'Replacement order #{active_order.order_number} was delivered to the customer.',
                        notification_type='order', link='/seller/orders/',
                    )
                    OrderTimeline.objects.create(
                        order=original_order,
                        status='replaced',
                        title='Replacement delivered',
                        description=f'Replacement order #{active_order.order_number} delivered successfully.',
                    )

                messages.success(request, f"OTP Verified! Order #{active_order.order_number} marked DELIVERED! ₹{active_order.delivery_partner_earning} added to your earnings.")
                return redirect("/delivery/dashboard/")
            else:
                messages.error(request, f"Incorrect OTP '{entered_otp}'! Please check with customer.")

    local_now = timezone.localtime()
    default_eta = active_order.estimated_delivery or (timezone.now() + timedelta(days=1))
    if default_eta <= timezone.now():
        default_eta = timezone.now() + timedelta(days=1)
    minimum_reschedule_date = local_now.date()
    if local_now.time() >= time(hour=16, minute=30):
        minimum_reschedule_date += timedelta(days=1)
    context = {
        'current_panel': 'delivery',
        'active_menu': 'active',
        'rider': rider,
        'order': active_order,
        'assigned_orders': assigned_orders,
        'reschedule_min': minimum_reschedule_date.strftime('%Y-%m-%d'),
        'reschedule_value': timezone.localtime(default_eta).strftime('%Y-%m-%d'),
        'reschedule_reason': request.POST.get('reschedule_reason', ''),
    }
    return render(request, "delivery/active-delivery.html", context)


def delivery_details(request, delivery_id):
    return _delivery_order_workflow(request, delivery_id)


def navigation(request):
    rider = get_current_rider(request)
    active_orders = Order.objects.filter(
        delivery_partner=rider,
        status__in=['shipped', 'out_for_delivery'],
    ) if rider else Order.objects.none()
    selected_order_id = request.GET.get('order_id')
    active_order = active_orders.filter(id=selected_order_id).first() if selected_order_id else active_orders.first()
    context = {
        'current_panel': 'delivery',
        'active_menu': 'navigation',
        'rider': rider,
        'order': active_order,
    }
    return render(request, "delivery/navigation.html", context)


def delivery_history(request):
    rider = get_current_rider(request)
    past_deliveries = Order.objects.filter(delivery_partner=rider, status='delivered').order_by('-created_at') if rider else Order.objects.filter(status='delivered').order_by('-created_at')
    context = {
        'current_panel': 'delivery',
        'active_menu': 'history',
        'rider': rider,
        'orders': past_deliveries,
    }
    return render(request, "delivery/delivery-history.html", context)


def earnings(request):
    rider = get_current_rider(request)
    past_deliveries = Order.objects.filter(delivery_partner=rider, status='delivered') if rider else Order.objects.filter(status='delivered')

    return_pickups = ReturnRequest.objects.filter(
        pickup_partner=rider, picked_up_at__isnull=False,
    ).select_related('order', 'customer') if rider else ReturnRequest.objects.none()
    total_earned = (past_deliveries.aggregate(total=Sum('delivery_partner_earning'))['total'] or Decimal('0.00')) + (
        return_pickups.aggregate(total=Sum('pickup_earning'))['total'] or Decimal('0.00')
    )
    weekly_incentive = Decimal('0.00')
    wallet_balance = total_earned

    context = {
        'current_panel': 'delivery',
        'active_menu': 'earnings',
        'rider': rider,
        'total_earned': total_earned,
        'weekly_incentive': weekly_incentive,
        'wallet_balance': wallet_balance,
        'orders': past_deliveries,
        'return_pickups': return_pickups,
    }
    return render(request, "delivery/earnings.html", context)


def reports(request):
    rider = get_current_rider(request)
    orders = Order.objects.filter(delivery_partner=rider) if rider else Order.objects.all()
    delivered_orders = orders.filter(status='delivered')
    status_rows = list(orders.values('status').annotate(total=Count('id')).order_by('-total'))
    status_labels = [row['status'].replace('_', ' ').title() for row in status_rows] or ['No jobs']
    status_values = [row['total'] for row in status_rows] or [0]
    earnings_rows = list(delivered_orders.values('status').annotate(total=Sum('delivery_partner_earning')))
    return_pickups = ReturnRequest.objects.filter(
        pickup_partner=rider, picked_up_at__isnull=False,
    ) if rider else ReturnRequest.objects.none()
    total_earned = (delivered_orders.aggregate(total=Sum('delivery_partner_earning'))['total'] or Decimal('0.00')) + (
        return_pickups.aggregate(total=Sum('pickup_earning'))['total'] or Decimal('0.00')
    )
    chart_labels, chart_earnings, chart_deliveries = get_delivery_chart_data(orders, rider)
    return render(request, 'delivery/reports.html', {
        'current_panel': 'delivery',
        'active_menu': 'reports',
        'total_jobs': orders.count() + return_pickups.count(),
        'delivered_jobs': delivered_orders.count() + return_pickups.count(),
        'total_earned': total_earned,
        'average_earning': round(float(total_earned / (delivered_orders.count() + return_pickups.count())), 2) if delivered_orders.exists() or return_pickups.exists() else 0,
        'chart_status_labels': json.dumps(status_labels),
        'chart_status_values': json.dumps(status_values),
        'chart_earning_labels': json.dumps(['Delivered earnings']),
        'chart_earning_values': json.dumps([float(total_earned)]),
        'chart_labels': chart_labels,
        'chart_earnings': chart_earnings,
        'chart_deliveries': chart_deliveries,
    })


def ratings(request):
    rider = get_current_rider(request)
    received_ratings = DeliveryRating.objects.filter(delivery_partner=rider) if rider else DeliveryRating.objects.none()
    rating_summary = received_ratings.aggregate(average=Avg('rating'), count=Count('id'))
    fleet_averages = list(
        DeliveryRating.objects.values('delivery_partner_id')
        .annotate(average=Avg('rating'))
        .order_by('-average', 'delivery_partner_id')
    )
    fleet_rank = next(
        (rank for rank, row in enumerate(fleet_averages, start=1) if rider and row['delivery_partner_id'] == rider.id),
        None,
    )

    delivered_orders = Order.objects.filter(delivery_partner=rider, status='delivered') if rider else Order.objects.none()
    completed_with_eta = delivered_orders.filter(
        estimated_delivery__isnull=False,
        timeline__title='Delivered Successfully',
    ).annotate(actual_delivery_at=Min('timeline__timestamp')).distinct()
    on_time_eligible_count = completed_with_eta.count()
    on_time_count = completed_with_eta.filter(actual_delivery_at__lte=F('estimated_delivery')).count()
    delivered_count = delivered_orders.count()
    otp_verified_count = delivered_orders.filter(
        timeline__title='Delivered Successfully',
        timeline__description__startswith='Verified with OTP',
    ).distinct().count()

    context = {
        'current_panel': 'delivery',
        'active_menu': 'ratings',
        'rider': rider,
        'average_rating': rating_summary['average'],
        'rating_count': rating_summary['count'],
        'fleet_rank': fleet_rank,
        'rated_fleet_count': len(fleet_averages),
        'on_time_rate': round(on_time_count * 100 / on_time_eligible_count, 1) if on_time_eligible_count else None,
        'on_time_count': on_time_count,
        'on_time_eligible_count': on_time_eligible_count,
        'otp_rate': round(otp_verified_count * 100 / delivered_count, 1) if delivered_count else None,
        'otp_verified_count': otp_verified_count,
        'delivered_count': delivered_count,
        'ratings': received_ratings,
    }
    return render(request, "delivery/ratings.html", context)


def documents(request):
    rider = get_current_rider(request)
    context = {
        'current_panel': 'delivery',
        'active_menu': 'documents',
        'rider': rider,
    }
    return render(request, "delivery/documents.html", context)


def bank(request):
    if not request.user.is_authenticated or request.user.role != 'delivery':
        return HttpResponseForbidden()
    rider = DeliveryPartnerProfile.objects.filter(user=request.user).first()
    if rider is None:
        return HttpResponseForbidden()

    if request.method == "POST":
        bank_values = {
            'bank_name': request.POST.get('bank_name', '').strip(),
            'account_number': request.POST.get('account_number', '').strip(),
            'ifsc_code': request.POST.get('ifsc_code', '').strip().upper(),
            'upi_id': request.POST.get('upi_id', '').strip(),
        }
        if not all(bank_values.values()):
            messages.error(request, 'Complete all bank and UPI fields before saving.')
            form_open = True
        else:
            for field, value in bank_values.items():
                setattr(rider, field, value)
            rider.save(update_fields=list(bank_values))
            messages.success(request, 'Payout bank details saved.')
            return redirect('/delivery/bank/')
    else:
        form_open = request.GET.get('edit') == '1'
        bank_values = {
            'bank_name': rider.bank_name if rider.ifsc_code else '',
            'account_number': rider.account_number if rider.ifsc_code else '',
            'ifsc_code': rider.ifsc_code,
            'upi_id': rider.upi_id if rider.ifsc_code else '',
        }

    has_payout_details = all((rider.bank_name, rider.account_number, rider.ifsc_code, rider.upi_id))

    context = {
        'current_panel': 'delivery',
        'active_menu': 'bank',
        'rider': rider,
        'has_payout_details': has_payout_details,
        'bank_form_open': form_open,
        'bank_values': bank_values,
    }
    return render(request, "delivery/bank.html", context)


def profile(request):
    rider = get_current_rider(request)
    if request.method == 'POST' and rider and request.POST.get('action') == 'save_profile':
        rider.user.first_name = request.POST.get('first_name', rider.user.first_name).strip()
        rider.user.last_name = request.POST.get('last_name', rider.user.last_name).strip()
        rider.user.phone = request.POST.get('phone', rider.user.phone)
        rider.user.save(update_fields=['first_name', 'last_name', 'phone'])

        vehicle_type = request.POST.get('vehicle_type', rider.vehicle_type)
        if vehicle_type in dict(DeliveryPartnerProfile._meta.get_field('vehicle_type').choices):
            rider.vehicle_type = vehicle_type
        rider.vehicle_number = request.POST.get('vehicle_number', rider.vehicle_number).strip()
        rider.address = request.POST.get('address', rider.address).strip()
        rider.city = request.POST.get('city', rider.city).strip()
        rider.state = request.POST.get('state', rider.state).strip()
        rider.pincode = request.POST.get('pincode', rider.pincode).strip()
        rider.save()
        messages.success(request, 'Profile details updated successfully.')
        return redirect('delivery:profile')

    context = {
        'current_panel': 'delivery',
        'active_menu': 'profile',
        'rider': rider,
        'vehicle_type_choices': DeliveryPartnerProfile._meta.get_field('vehicle_type').choices,
        'profile_edit_open': request.GET.get('show') == 'edit',
        'profile_password_open': request.GET.get('show') == 'password',
    }
    return render(request, "delivery/profile.html", context)


def settings(request):
    rider = get_current_rider(request)
    context = {
        'current_panel': 'delivery',
        'active_menu': 'settings',
        'rider': rider,
    }
    return render(request, "delivery/settings.html", context)


def support(request):
    if not request.user.is_authenticated or request.user.role != 'delivery':
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
            return redirect(f'/delivery/support/{suffix}')

        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        if not subject or not message or len(subject) > 200:
            messages.error(request, 'Enter a subject (up to 200 characters) and a message.')
            return redirect('/delivery/support/')

        ticket = SupportTicket.objects.create(
            user=request.user,
            ticket_id=f'RID-{uuid4().hex[:10].upper()}',
            subject=subject,
            category='Rider Support',
            message=message,
        )
        Notification.objects.bulk_create([
            Notification(
                user=admin,
                title=f'New rider support ticket #{ticket.ticket_id}',
                message=f'{request.user.get_full_name() or request.user.username}: {subject}',
                notification_type='support',
                link='/admin-panel/tickets/?type=rider',
            )
            for admin in User.objects.filter(role='admin', is_active=True)
        ])
        messages.success(request, f'Support ticket #{ticket.ticket_id} submitted successfully.')
        return redirect('/delivery/support/')

    rider = get_current_rider(request)
    ticket_list = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    show_all = request.GET.get('all') == '1'
    context = {
        'current_panel': 'delivery',
        'active_menu': 'support',
        'rider': rider,
        'tickets': ticket_list if show_all else ticket_list[:3],
        'ticket_count': ticket_list.count(),
        'show_all_tickets': show_all,
    }
    return render(request, "delivery/support.html", context)


def incentives(request):
    return earnings(request)


@login_required(login_url='/auth/login/')
def notifications(request):
    if request.user.role != 'delivery':
        return HttpResponseForbidden()

    rider = DeliveryPartnerProfile.objects.filter(user=request.user).first()
    if rider is None:
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
        return redirect('/delivery/notifications/')

    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')
    context = {
        'current_panel': 'delivery',
        'active_menu': 'notifications',
        'notifications': notifs,
        'unread_count': notifs.filter(is_read=False).count(),
        'rider': rider,
    }
    return render(request, "delivery/notifications.html", context)


def withdrawals(request):
    return earnings(request)