import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("warehouses", "0008_stocktransfer_cancellation_reason_and_more"),
        ("sale_sessions", "0033_supplier_fabric_sales_window"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsumableRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
                ("yards", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="الكمية (ياردة)")),
                ("date", models.DateField(default=django.utils.timezone.localdate, verbose_name="تاريخ الطلب/الصرف")),
                ("status", models.CharField(choices=[("requested", "بانتظار موافقة المدير"), ("approved", "تم الصرف"), ("rejected", "مرفوض")], default="requested", max_length=12, verbose_name="الحالة")),
                ("approved_at", models.DateTimeField(blank=True, null=True, verbose_name="وقت الاعتماد")),
                ("decision_note", models.CharField(blank=True, max_length=255, verbose_name="ملاحظة القرار")),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_consumable_requests", to="sale_sessions.employee", verbose_name="المعتمد")),
                ("fabric", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="consumable_requests", to="suppliers.fabric", verbose_name="القماش")),
                ("requested_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="consumable_requests", to="sale_sessions.employee", verbose_name="مقدم الطلب")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="consumable_requests", to="warehouses.warehouse", verbose_name="المخزن/الفرع")),
            ],
            options={"verbose_name": "طلب مستهلكات", "verbose_name_plural": "طلبات المستهلكات", "ordering": ["-date", "-id"]},
        ),
        migrations.AlterField(
            model_name="stockmovement",
            name="movement_type",
            field=models.CharField(choices=[("receipt", "استلام من مورد"), ("transfer_out", "تحويل صادر"), ("transfer_in", "تحويل ياردةد"), ("adjustment_in", "تسوية إضافة"), ("adjustment_out", "تسوية خصم"), ("count", "تسوية جرد"), ("sale", "مبيعات"), ("consumption", "مستهلكات"), ("opening", "رصيد افتتاحي")], max_length=20, verbose_name="نوع الحركة"),
        ),
    ]
