from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("appsettings", "0020_appsettings_auto_backup_every_minutes")]

    operations = [
        migrations.AddField("appsettings", "instagram_url", models.CharField(blank=True, max_length=300, verbose_name="رابط انستجرام")),
        migrations.AddField("appsettings", "snapchat_url", models.CharField(blank=True, max_length=300, verbose_name="رابط سناب شات")),
        migrations.AddField("appsettings", "tiktok_url", models.CharField(blank=True, max_length=300, verbose_name="رابط تيك توك")),
        migrations.AddField("appsettings", "facebook_url", models.CharField(blank=True, max_length=300, verbose_name="رابط فيسبوك")),
        migrations.AddField("appsettings", "bank_transfer_url", models.CharField(blank=True, max_length=500, verbose_name="رابط التحويل البنكي")),
        migrations.AddField("appsettings", "bank_transfer_phone", models.CharField(blank=True, max_length=40, verbose_name="هاتف التحويل البنكي")),
    ]
