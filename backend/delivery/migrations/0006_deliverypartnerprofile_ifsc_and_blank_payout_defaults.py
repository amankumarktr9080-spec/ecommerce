from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0005_deliverypartnerapplication_password_hash_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliverypartnerprofile',
            name='ifsc_code',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='deliverypartnerprofile',
            name='bank_name',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AlterField(
            model_name='deliverypartnerprofile',
            name='account_number',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AlterField(
            model_name='deliverypartnerprofile',
            name='upi_id',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
    ]