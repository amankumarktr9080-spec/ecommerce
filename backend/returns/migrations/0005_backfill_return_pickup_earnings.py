from decimal import Decimal

from django.db import migrations, models


def credit_assigned_return_pickups(apps, schema_editor):
    ReturnRequest = apps.get_model('returns', 'ReturnRequest')
    Order = apps.get_model('orders', 'Order')
    CommissionLog = apps.get_model('commissions', 'CommissionLog')
    database = schema_editor.connection.alias
    fee = Decimal('50.00')

    pickups = ReturnRequest.objects.using(database).filter(
        pickup_partner__isnull=False,
        picked_up_at__isnull=False,
        pickup_earning=Decimal('0.00'),
    )
    for pickup in pickups.iterator():
        pickup.pickup_earning = fee
        pickup.save(update_fields=['pickup_earning'], using=database)
        Order.objects.using(database).filter(pk=pickup.order_id).update(
            seller_net_earnings=models.F('seller_net_earnings') - fee,
        )
        CommissionLog.objects.using(database).filter(order_id=pickup.order_id).update(
            seller_payout_amount=models.F('seller_payout_amount') - fee,
            delivery_payout_amount=models.F('delivery_payout_amount') + fee,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('commissions', '0003_reconcile_cancelled_and_returned_logs'),
        ('orders', '0003_order_delivered_at_order_replacement_for'),
        ('returns', '0004_returnrequest_pickup_earning_and_more'),
    ]

    operations = [
        migrations.RunPython(credit_assigned_return_pickups, migrations.RunPython.noop),
    ]