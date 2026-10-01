from django.db import migrations


def reconcile_order_commission_statuses(apps, schema_editor):
    CommissionLog = apps.get_model('commissions', 'CommissionLog')
    database = schema_editor.connection.alias
    CommissionLog.objects.using(database).filter(order__status='cancelled').exclude(
        status__in=['cancelled', 'refunded']
    ).update(status='cancelled')
    CommissionLog.objects.using(database).filter(order__status='returned').exclude(
        status='refunded'
    ).update(status='refunded')


class Migration(migrations.Migration):
    dependencies = [
        ('commissions', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(reconcile_order_commission_statuses, migrations.RunPython.noop),
    ]