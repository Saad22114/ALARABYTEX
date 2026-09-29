import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.apps import apps

TARGETS = [
    ("sale_sessions", "SaleSession"),
    ("sale_sessions", "SaleSessionItem"),
    ("sales", "DailySale"),
    ("payroll", "PayrollRun"),
    ("payroll", "Payslip"),
    ("payroll", "SalaryAdvance"),
    ("payroll", "SalaryStructure"),
    ("accounting", "JournalEntry"),
    ("accounting", "JournalLine"),
    ("warehouses", "StockMovement"),
    ("warehouses", "GoodsReceipt"),
    ("warehouses", "StockCount"),
    ("warehouses", "StockCountItem"),
    ("warehouses", "StockAdjustment"),
    ("warehouses", "StockOpening"),
    ("warehouses", "StockTransfer"),
    ("customers", "Customer"),
    ("expenses", "Expense"),
    ("partners", "PartnerOperation"),
]

for app, name in TARGETS:
    model = apps.get_model(app, name)
    print(f"== {model._meta.label}")
    for f in model._meta.get_fields():
        if not getattr(f, "concrete", False):
            continue
        bits = [f.name]
        if f.is_relation:
            bits.append(
                "FK->%s (related=%s)"
                % (f.related_model._meta.label, f.remote_field.get_accessor_name() and "yes")
            )
        if getattr(f, "choices", None):
            bits.append("choices=" + ",".join(str(c[0]) for c in f.choices))
        print("   " + " ".join(bits))
    print()
