from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0006_deliverypartnerprofile_ifsc_and_blank_payout_defaults'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliverypartnerprofile',
            name='address',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='deliverypartnerprofile',
            name='city',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='deliverypartnerprofile',
            name='state',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='deliverypartnerprofile',
            name='pincode',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
        migrations.AddField(
            model_name='deliverypartnerprofile',
            name='kyc_document',
            field=models.FileField(blank=True, null=True, upload_to='delivery_kyc/'),
        ),
    ]