from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0002_faqitem_marketplacesettings_cancellation_policy_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='marketplacesettings',
            name='featured_product_codes',
            field=models.TextField(blank=True, default=''),
        ),
    ]