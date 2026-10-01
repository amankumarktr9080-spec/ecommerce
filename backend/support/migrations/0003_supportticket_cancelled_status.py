from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0002_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='supportticket',
            name='status',
            field=models.CharField(
                choices=[
                    ('open', 'Open'),
                    ('in_progress', 'In Progress'),
                    ('resolved', 'Resolved'),
                    ('cancelled', 'Cancelled'),
                ],
                default='open',
                max_length=20,
            ),
        ),
    ]