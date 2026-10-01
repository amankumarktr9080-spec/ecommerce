from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sellers', '0007_sellerproductoffer'),
    ]

    operations = [
        migrations.AddField(
            model_name='sellerprofile',
            name='city',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='state',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='pincode',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='pan_number',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='kyc_document',
            field=models.FileField(blank=True, null=True, upload_to='seller_kyc/'),
        ),
    ]