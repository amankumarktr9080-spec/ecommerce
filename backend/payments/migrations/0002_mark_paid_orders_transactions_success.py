from django.db import migrations


def mark_paid_transactions_success(apps, schema_editor):
    payment_transaction = apps.get_model('payments', 'PaymentTransaction')
    payment_transaction.objects.filter(
        status='pending',
        order__payment_status='paid',
    ).update(status='success')


class Migration(migrations.Migration):
    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(mark_paid_transactions_success, migrations.RunPython.noop),
    ]