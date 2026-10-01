from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
        ('sellers', '0006_sellerprofile_commission_rate_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SellerProductOffer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=150)),
                ('discount_type', models.CharField(choices=[('percent', 'Percentage (%)'), ('flat', 'Flat Amount (₹)')], default='percent', max_length=10)),
                ('discount_value', models.DecimalField(decimal_places=2, max_digits=10)),
                ('original_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='seller_offer', to='products.product')),
            ],
        ),
    ]