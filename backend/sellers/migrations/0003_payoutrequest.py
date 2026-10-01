from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('sellers', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PayoutRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('status', models.CharField(choices=[('pending', 'Pending Admin Review'), ('approved', 'Approved'), ('paid', 'Paid'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('bank_name', models.CharField(blank=True, default='', max_length=100)),
                ('account_number', models.CharField(blank=True, default='', max_length=50)),
                ('upi_id', models.CharField(blank=True, default='', max_length=50)),
                ('admin_note', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('seller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payout_requests', to='sellers.sellerprofile')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]