import base64
import mimetypes
from pathlib import Path
import uuid

from django.conf import settings
from django.db import migrations, models


def persist_existing_bank_two_qr(apps, schema_editor):
    AppSettings = apps.get_model("appsettings", "AppSettings")
    try:
        row = AppSettings.objects.get(pk=1)
    except AppSettings.DoesNotExist:
        return
    rel = row.bank_transfer_qr_image_2
    if not rel or rel.startswith("db:"):
        return
    root = (Path(settings.MEDIA_ROOT) / "sales_qr").resolve()
    path = (Path(settings.MEDIA_ROOT) / rel).resolve()
    if path.parent != root or not path.is_file() or path.stat().st_size > 5 * 1024 * 1024:
        return
    content_type = mimetypes.guess_type(path.name)[0]
    if content_type not in {"image/png", "image/jpeg", "image/webp"}:
        return
    row.bank_transfer_qr_image_2_data = (
        f"data:{content_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
    )
    row.bank_transfer_qr_image_2 = f"db:{uuid.uuid4().hex}"
    row.save(update_fields=["bank_transfer_qr_image_2_data", "bank_transfer_qr_image_2"])


class Migration(migrations.Migration):
    dependencies = [
        ("appsettings", "0024_appsettings_bank_transfer_name_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="bank_transfer_qr_image_2_data",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="بيانات صورة رمز البنك الثاني",
            ),
        ),
        migrations.RunPython(persist_existing_bank_two_qr, migrations.RunPython.noop),
    ]
