from django.db import migrations, models
import django.db.models.deletion


def move_brands_to_subcategories(apps, schema_editor):
    Brand = apps.get_model('categories', 'Brand')
    SubCategory = apps.get_model('categories', 'SubCategory')

    preferred_subcategories = {
        'apple': 'iphones',
        'samsung': 'android-phones',
        'nike': 'running-sneakers',
        'puma': 'running-sneakers',
        'adidas': 'running-sneakers',
        'boat': 'audio-headphones',
        'sony': 'audio-headphones',
        'philips': 'smart-watches',
        'dell': 'smart-watches',
        'prestige': 'cookware',
    }

    for brand in Brand.objects.select_related('category').all():
        category_id = brand.category_id
        if not category_id:
            continue
        preferred_slug = preferred_subcategories.get(brand.name.casefold())
        subcategory = None
        if preferred_slug:
            subcategory = SubCategory.objects.filter(category_id=category_id, slug=preferred_slug).first()
        if not subcategory:
            subcategory = SubCategory.objects.filter(category_id=category_id).order_by('id').first()
        if subcategory:
            brand.subcategory_id = subcategory.id
            brand.save(update_fields=['subcategory'])


class Migration(migrations.Migration):

    dependencies = [
        ('categories', '0002_brand_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='brand',
            name='subcategory',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='brands',
                to='categories.subcategory',
            ),
        ),
        migrations.RunPython(move_brands_to_subcategories, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='brand',
            name='category',
        ),
    ]