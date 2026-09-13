import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand

from branches.models import Branch
from expenses import models as expenses_models
from sales.models import DailySale
from suppliers.models import Fabric, LedgerEntry, PurchaseItem, Supplier

DEMO_BRANCHES = [
    {"code": "MNH", "name": "الفرع الرئيسي", "city": "مسقط"},
    {"code": "SIB", "name": "فرع السيب", "city": "السيب"},
    {"code": "BWR", "name": "فرع بوشر", "city": "بوشر"},
]

DEMO_SUPPLIERS = [
    {"name": "مؤسسة النسيج الحديث", "company_name": "مؤسسة النسيج الحديث", "phone": "97651122", "city": "مسقط", "country": "عمان"},
    {"name": "شركة الشامل للأقمشة", "company_name": "شركة الشامل للأقمشة", "phone": "99654321", "city": "السيب", "country": "عمان"},
    {"name": "مصنع النور", "company_name": "مصنع النور", "phone": "98001122", "city": "صنعاء", "country": "اليمن"},
    {"name": "تجارة الأمل", "company_name": "تجارة الأمل", "phone": "97778899", "city": "بوشر", "country": "عمان"},
    {"name": "مؤسسة الراية للنسيج", "company_name": "مؤسسة الراية للنسيج", "phone": "95554433", "city": "مسقط", "country": "عمان"},
    {"name": "شركة الخليج للاستيراد", "company_name": "شركة الخليج للاستيراد", "phone": "99334455", "city": "دبي", "country": "الإمارات"},
    {"name": "بيت القماش", "company_name": "بيت القماش", "phone": "99445566", "city": "مسقط", "country": "عمان"},
]

DEMO_FABRICS = [
    {"name": "قماش قطن", "unit": "yard", "yards_per_roll": 50},
    {"name": "قماش حرير", "unit": "yard", "yards_per_roll": 40},
    {"name": "قماش صوف", "unit": "yard", "yards_per_roll": 45},
    {"name": "قماش بوليستر", "unit": "yard", "yards_per_roll": 60},
    {"name": "قماش شامواه", "unit": "yard", "yards_per_roll": 30},
    {"name": "قماش دانتيل", "unit": "yard", "yards_per_roll": 20},
    {"name": "قماش شيفون", "unit": "yard", "yards_per_roll": 25},
    {"name": "قماش مخمل", "unit": "roll", "yards_per_roll": 40},
]

DEMO_RECEIVERS = [
    "أمين الصندوق - خالد",
    "المحاسب - أحمد",
    "سعيد البلوشي",
    "مسؤول المخزن - سلمى",
]

DEMO_EXPENSE_NOTES = [
    "قرطاسية",
    "صيانة جهاز",
    "نقل بضاعة",
    "فاتورة كهرباء",
    "أدوات تنظيف",
    "قفة ضيافة",
]


class Command(BaseCommand):
    help = "إنشاء بيانات تجريبية للمعاينة (فروع، موردون، مبيعات، مصاريف، أقمشة، دفتر موردين)"

    def handle(self, *args, **options):
        call_command("seed_categories", verbosity=0)

        branches = [Branch.objects.get_or_create(code=b["code"], defaults=b)[0] for b in DEMO_BRANCHES]
        suppliers = [Supplier.objects.get_or_create(name=s["name"], defaults=s)[0] for s in DEMO_SUPPLIERS]
        categories = list(expenses_models.ExpenseCategory.objects.all())

        random.seed(2024)
        today = date.today()
        sales_count = 0
        expenses_count = 0

        if not DailySale.objects.exists():
            for offset in range(0, 30):
                day = today - timedelta(days=offset)
                for branch in branches:
                    total = random.randint(80, 4000)
                    cash = random.randint(0, total)
                    transfer = random.randint(0, total - cash)
                    card = random.randint(0, total - cash - transfer)
                    other = total - cash - transfer - card
                    DailySale.objects.create(
                        branch=branch, date=day, total_sales=total,
                        cash_amount=cash, transfer_amount=transfer,
                        card_amount=card, other_amount=other,
                    )
                    sales_count += 1

                    for _ in range(random.randint(0, 3)):
                        expenses_models.Expense.objects.create(
                            branch=branch,
                            category=random.choice(categories),
                            date=day,
                            amount=random.randint(5, 250),
                            description=random.choice(DEMO_EXPENSE_NOTES),
                        )
                        expenses_count += 1

        fabric_count = 0
        for i, f in enumerate(DEMO_FABRICS):
            defaults = {
                "name": f["name"],
                "unit": f["unit"].value if hasattr(f["unit"], "value") else f["unit"],
                "sale_price_yard": Decimal(str(random.uniform(1.5, 9))).quantize(Decimal("0.001")),
                "yards_per_roll": f.get("yards_per_roll"),
            }
            obj, created = Fabric.objects.get_or_create(code=f"FAB-{i + 1:02d}", defaults=defaults)
            if created:
                fabric_count += 1
            else:
                Fabric.objects.filter(pk=obj.pk).update(yards_per_roll=f.get("yards_per_roll"))

        fabrics = list(Fabric.objects.all())
        ledger_count = 0
        items_count = 0

        for supplier in suppliers:
            if supplier.ledger_entries.exists():
                continue

            balance = Decimal("0")

            opening_amount = Decimal(str(random.uniform(100, 2000))).quantize(Decimal("0.01"))
            LedgerEntry.objects.create(
                supplier=supplier,
                date=today - timedelta(days=random.randint(25, 30)),
                entry_type=LedgerEntry.EntryType.OPENING,
                amount=opening_amount,
                description="رصيد افتتاحي",
            )
            balance += opening_amount
            ledger_count += 1

            for _ in range(random.randint(1, 3)):
                purchase_day = today - timedelta(days=random.randint(0, 24))
                n_items = random.randint(1, 3)
                total = Decimal("0")
                items = []
                for _ in range(n_items):
                    fabric = random.choice(fabrics)
                    quantity = random.randint(20, 300)
                    price = Decimal(str(random.uniform(1, 9))).quantize(Decimal("0.001"))
                    item_total = (Decimal(quantity) * price).quantize(Decimal("0.01"))
                    items.append((fabric, quantity, price, item_total))
                    total += item_total
                entry = LedgerEntry.objects.create(
                    supplier=supplier,
                    date=purchase_day,
                    entry_type=LedgerEntry.EntryType.PURCHASE,
                    amount=total,
                    description="فاتورة شراء",
                    receipt_no=f"INV-{random.randint(1000, 9999)}",
                )
                ledger_count += 1
                for fabric, quantity, price, item_total in items:
                    ypr = Decimal(str(fabric.yards_per_roll)) if fabric.yards_per_roll else None
                    if ypr:
                        rolls = (Decimal(quantity) / ypr).quantize(Decimal("0.01"))
                    else:
                        rolls = random.randint(0, 5)
                    PurchaseItem.objects.create(
                        entry=entry,
                        fabric=fabric,
                        quantity_yards=Decimal(quantity),
                        rolls=rolls,
                        unit_price=price,
                        total=item_total,
                    )
                    items_count += 1
                balance += total

            for _ in range(random.randint(1, 2)):
                if balance <= 0:
                    break
                upper = float(balance)
                payment_amount = Decimal(str(random.uniform(min(10.0, upper), upper))).quantize(Decimal("0.01"))
                method = random.choice(
                    [LedgerEntry.PaymentMethod.CASH, LedgerEntry.PaymentMethod.BANK]
                )
                bank_reference = ""
                receiver_name = ""
                if method == LedgerEntry.PaymentMethod.BANK:
                    bank_reference = f"TR{random.randint(100000, 999999)}"
                elif method == LedgerEntry.PaymentMethod.CASH:
                    receiver_name = random.choice(DEMO_RECEIVERS)
                LedgerEntry.objects.create(
                    supplier=supplier,
                    date=today - timedelta(days=random.randint(0, 25)),
                    entry_type=LedgerEntry.EntryType.PAYMENT,
                    amount=-payment_amount,
                    description="دفعة للمورد",
                    receipt_no=f"RC-{random.randint(1000, 9999)}",
                    payment_method=method,
                    bank_reference=bank_reference,
                    receiver_name=receiver_name,
                )
                balance -= payment_amount
                ledger_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"تم إنشاء البيانات التجريبية: {len(branches)} فروع، {len(suppliers)} موردين، "
            f"{sales_count} عملية بيع، {expenses_count} مصروف خلال آخر 30 يومًا"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"تم إنشاء {fabric_count} أقمشة، {ledger_count} قيد دفتر مورد، {items_count} صنف شراء"
        ))