from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('payments', '0002_mark_paid_orders_transactions_success'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymenttransaction',
            name='refund_reference',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
    ]