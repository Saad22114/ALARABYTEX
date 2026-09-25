from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from core.testsupport import authenticate_admin

from branches.models import Branch
from suppliers.models import Fabric, LedgerEntry, PurchaseItem, Supplier
from warehouses.models import FabricRoll, GoodsReceipt, Warehouse


class SupplierAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)

    def test_create_supplier(self):
        r = self.c.post("/api/suppliers/", {"name": "Acme"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["name"], "Acme")
        self.assertTrue(r.data["is_active"])

    def test_list_suppliers(self):
        self.c.post("/api/suppliers/", {"name": "A"})
        self.c.post("/api/suppliers/", {"name": "B"})
        r = self.c.get("/api/suppliers/")
        self.assertEqual(r.data["count"], 2)

    def test_retrieve_supplier(self):
        r = self.c.post("/api/suppliers/", {"name": "X"})
        sid = r.data["id"]
        r = self.c.get(f"/api/suppliers/{sid}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "X")

    def test_update_supplier(self):
        r = self.c.post("/api/suppliers/", {"name": "Old"})
        sid = r.data["id"]
        r = self.c.put(f"/api/suppliers/{sid}/", {"name": "New"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "New")

    def test_delete_supplier(self):
        r = self.c.post("/api/suppliers/", {"name": "Del"})
        sid = r.data["id"]
        r = self.c.delete(f"/api/suppliers/{sid}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Supplier.objects.count(), 0)

    def test_optional_fields(self):
        r = self.c.post("/api/suppliers/", {
            "name": "Full",
            "company_name": "Corp",
            "phone": "+96891234567",
            "email": "a@b.com",
            "city": "Muscat",
            "country": "Oman",
            "tax_number": "12345",
        })
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["company_name"], "Corp")
        self.assertEqual(r.data["tax_number"], "12345")


class FabricAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)

    def test_create_fabric(self):
        r = self.c.post("/api/fabrics/", {
            "name": "قطن", "unit": "yard", "sale_price_yard": 3.5, "yards_per_roll": 50,
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["name"], "قطن")
        self.assertEqual(r.data["yards_per_roll"], "50.00")
        self.assertTrue(r.data["is_active"])

    def test_fabric_yards_per_roll_optional(self):
        r = self.c.post("/api/fabrics/", {"name": "حرير", "unit": "yard"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(r.data["yards_per_roll"])

    def test_create_fabric_requires_name(self):
        r = self.c.post("/api/fabrics/", {"name": "  "}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_piece_price_divides_into_yard_price(self):
        r = self.c.post(
            "/api/fabrics/", {"name": "كريب", "unit": "yard", "piece_price": "70"}, format="json"
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(r.data["piece_price"]), Decimal("70.000"))
        self.assertEqual(Decimal(r.data["sale_price_yard"]), Decimal("20.000"))

    def test_explicit_yard_price_wins_over_piece_price(self):
        r = self.c.post(
            "/api/fabrics/",
            {"name": "كريب", "unit": "yard", "piece_price": "70", "sale_price_yard": "22.5"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(r.data["sale_price_yard"]), Decimal("22.500"))

    def test_update_piece_price_only_recomputes_yard_price(self):
        r = self.c.post(
            "/api/fabrics/", {"name": "كريب", "unit": "yard", "sale_price_yard": "20"}, format="json"
        )
        fid = r.data["id"]
        r = self.c.patch(f"/api/fabrics/{fid}/", {"piece_price": "140.25"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(r.data["sale_price_yard"]), Decimal("40.071"))
        # تعديل صريح لسعر الياردة يبقى كما هو
        r = self.c.patch(f"/api/fabrics/{fid}/", {"sale_price_yard": "45"}, format="json")
        self.assertEqual(Decimal(r.data["sale_price_yard"]), Decimal("45.000"))

    def test_fabric_without_piece_price_keeps_prices(self):
        r = self.c.post(
            "/api/fabrics/", {"name": "شيفون", "unit": "yard", "sale_price_yard": "9"}, format="json"
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data["piece_price"])
        self.assertEqual(Decimal(r.data["sale_price_yard"]), Decimal("9.000"))

    def test_list_fabrics(self):
        self.c.post("/api/fabrics/", {"name": "A"}, format="json")
        r = self.c.get("/api/fabrics/")
        self.assertEqual(r.data["count"], 1)

    def test_retrieve_fabric(self):
        r = self.c.post("/api/fabrics/", {"name": "X"}, format="json")
        fid = r.data["id"]
        r = self.c.get(f"/api/fabrics/{fid}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "X")

    def test_update_fabric(self):
        r = self.c.post("/api/fabrics/", {"name": "Old"}, format="json")
        fid = r.data["id"]
        r = self.c.put(f"/api/fabrics/{fid}/", {"name": "New"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "New")

    def test_delete_fabric(self):
        r = self.c.post("/api/fabrics/", {"name": "Del"}, format="json")
        fid = r.data["id"]
        r = self.c.delete(f"/api/fabrics/{fid}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Fabric.objects.count(), 0)

    def test_delete_fabric_with_roll_blocked_with_clear_message(self):
        r = self.c.post("/api/fabrics/", {"name": "قطن محمي"}, format="json")
        fid = r.data["id"]
        wh = Warehouse.objects.create(name="مخزن", code="WH-TEST")
        FabricRoll.objects.create(
            warehouse=wh, fabric_id=fid, yards=10, remaining_yards=10, unit_cost=2
        )
        r = self.c.delete(f"/api/fabrics/{fid}/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("لا يمكن حذف القماش", r.data["detail"])
        self.assertTrue(Fabric.objects.filter(pk=fid).exists())

    def test_fabric_sold_count(self):
        from branches.models import Branch
        from sale_sessions.models import Employee, SaleSession, SaleSessionItem

        f1 = self.c.post("/api/fabrics/", {"name": "أول", "code": "F1"}, format="json").data["id"]
        f2 = self.c.post("/api/fabrics/", {"name": "ثاني", "code": "F2"}, format="json").data["id"]
        branch = Branch.objects.create(name="فرع", code="BR-X")
        emp = Employee.objects.create(name="موظف", branch=branch)
        session = SaleSession.objects.create(employee=emp, branch=branch)
        for fabric in (f1,):  # f1 مُباع مرة واحدة، f2 لم يُبع
            SaleSessionItem.objects.create(
                session=session, fabric_id=fabric, sale_type="yard",
                quantity=5, unit_price="10", total="50", sale_date="2026-09-10",
            )
        r = self.c.get("/api/fabrics/")
        counts = {item["name"]: item["sold_count"] for item in r.data["results"]}
        self.assertEqual(counts["أول"], 1)
        self.assertEqual(counts["ثاني"], 0)


class FabricAdvancedTests(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)

    def test_create_with_full_details(self):
        r = self.c.post("/api/fabrics/", {
            "name": "اكسفورد", "unit": "yard", "barcode": "6281-0001",
            "fabric_type": "منسوج", "color": "أزرق", "composition": "قطن 100%",
            "width_cm": 150, "weight_gsm": 240, "origin": "الصين", "manufacturer": "شركة النسيج",
            "sale_price_yard": 5, "purchase_price": 3, "yards_per_roll": 25,
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["barcode"], "6281-0001")
        self.assertEqual(r.data["color"], "أزرق")

    def test_roll_price_computed(self):
        r = self.c.post("/api/fabrics/", {
            "name": "قماش", "unit": "yard", "sale_price_yard": 4, "yards_per_roll": 25,
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(float(r.data["sale_price_roll_display"]), 100.0)

    def test_roll_price_override(self):
        r = self.c.post("/api/fabrics/", {
            "name": "قماش", "unit": "yard", "sale_price_yard": 4,
            "sale_price_roll": 90, "yards_per_roll": 25,
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(float(r.data["sale_price_roll_display"]), 90.0)

    def test_min_roll_price_computed(self):
        r = self.c.post("/api/fabrics/", {
            "name": "قماش", "unit": "yard", "min_sale_yard": 3, "yards_per_roll": 25,
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(float(r.data["min_sale_roll_display"]), 75.0)

    def test_min_above_sale_rejected(self):
        r = self.c.post("/api/fabrics/", {
            "name": "قماش", "unit": "yard", "sale_price_yard": 4, "min_sale_yard": 5,
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_min_roll_above_sale_roll_rejected(self):
        r = self.c.post("/api/fabrics/", {
            "name": "قماش", "unit": "yard", "sale_price_roll": 90, "min_sale_roll": 95,
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_profit_fields(self):
        r = self.c.post("/api/fabrics/", {
            "name": "قماش", "unit": "yard", "sale_price_yard": 5, "purchase_price": 3,
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(float(r.data["profit_yard"]), 2.0)
        self.assertGreater(float(r.data["profit_margin_pct"]), 39.9)

    def test_summary(self):
        self.c.post("/api/fabrics/", {
            "name": "قماش1", "unit": "yard", "sale_price_yard": 5, "min_stock": 10,
        }, format="json")
        r = self.c.get("/api/fabrics/summary/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["fabric_count"], 1)
        self.assertEqual(r.data["active_count"], 1)
        self.assertEqual(r.data["low_stock_count"], 1)

    def test_stock_endpoint(self):
        f = Fabric.objects.create(name="قماش", code="F1", sale_price_yard=5, min_stock=5)
        wh = Warehouse.objects.create(name="مخزن", code="W1")
        FabricRoll.objects.create(
            warehouse=wh, fabric=f, yards=20, remaining_yards=15, unit_cost=2
        )
        r = self.c.get(f"/api/fabrics/{f.id}/stock/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["totals"]["rolls"], 1)
        self.assertEqual(float(r.data["totals"]["yards"]), 15.0)
        self.assertEqual(float(r.data["totals"]["cost_value"]), 30.0)
        self.assertEqual(r.data["items"][0]["warehouse_name"], "مخزن")

    def test_list_export_xlsx(self):
        self.c.post("/api/fabrics/", {
            "name": "اكسفورد", "unit": "yard", "sale_price_yard": 5, "yards_per_roll": 25,
        }, format="json")
        r = self.c.get("/api/fabrics/?export=xlsx")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


class SupplierLedgerAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        from accounting.chart_of_accounts import ensure_seeded
        ensure_seeded()
        self.supplier = Supplier.objects.create(name="مورد تجريبي")
        self.f1 = Fabric.objects.create(name="قطن", code="FAB-01", unit="yard", sale_price_yard=3)
        self.f2 = Fabric.objects.create(name="حرير", code="FAB-02", unit="yard", sale_price_yard=5)
        self.today = date.today().isoformat()

    def _ledger(self, data, supplier=None):
        sid = supplier.id if supplier else self.supplier.id
        return self.c.post(f"/api/suppliers/{sid}/ledger/", data, format="json")

    def test_opening_balance(self):
        r = self._ledger({"entry_type": "opening", "date": self.today, "amount": 100})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["amount"], "100.00")

    def test_purchase_with_items(self):
        r = self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "items": [
                {"fabric": self.f1.id, "quantity_yards": 10, "unit_price": 3},
                {"fabric": self.f2.id, "quantity_yards": 20, "unit_price": 5},
            ],
        })
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["amount"], "130.00")
        self.assertEqual(len(r.data["items"]), 2)
        r = self.c.get(f"/api/suppliers/{self.supplier.id}/ledger/")
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["running_balance"], 130.0)
        self.assertEqual(r.data["results"][0]["items"][0]["fabric_name"], "قطن")

    def test_purchase_requires_total(self):
        r = self._ledger({"entry_type": "purchase", "date": self.today})
        self.assertEqual(r.status_code, 400)

    def test_payment_is_negative(self):
        self._ledger({"entry_type": "opening", "date": self.today, "amount": 100})
        r = self._ledger({
            "entry_type": "payment", "date": self.today,
            "amount": 40, "payment_method": "cash",
        })
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["amount"], "-40.00")

    def test_payment_requires_method(self):
        r = self._ledger({"entry_type": "payment", "date": self.today, "amount": 40})
        self.assertEqual(r.status_code, 400)

    def test_return_is_negative(self):
        self._ledger({"entry_type": "opening", "date": self.today, "amount": 100})
        r = self._ledger({"entry_type": "return", "date": self.today, "amount": 30})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["amount"], "-30.00")

    def test_purchase_with_immediate_payment(self):
        r = self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "payment_amount": 40,
            "payment_method": "cash",
            "receipt_no": "INV-77",
            "items": [{"fabric": self.f1.id, "quantity_yards": 10, "unit_price": 5}],
        })
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["amount"], "50.00")
        self.assertEqual(LedgerEntry.objects.filter(entry_type="payment").count(), 1)
        payment = LedgerEntry.objects.get(entry_type="payment")
        self.assertEqual(payment.amount, -40)
        self.assertEqual(payment.receipt_no, "INV-77")
        self.assertEqual(payment.description, "سداد فوري - INV-77")

    def test_running_balance_accumulates(self):
        self._ledger({"entry_type": "opening", "date": self.today, "amount": 100})
        self._ledger({
            "entry_type": "payment", "date": self.today,
            "amount": 40, "payment_method": "cash",
        })
        r = self.c.get(f"/api/suppliers/{self.supplier.id}/ledger/")
        balances = [e["running_balance"] for e in r.data["results"]]
        self.assertEqual(balances, [100.0, 60.0])

    def test_summary(self):
        self._ledger({"entry_type": "opening", "date": self.today, "amount": 100})
        self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "items": [{"fabric": self.f2.id, "quantity_yards": 40, "unit_price": 5}],
        })
        self._ledger({
            "entry_type": "payment", "date": self.today,
            "amount": 50, "payment_method": "bank_transfer", "bank_reference": "TR123",
        })
        self._ledger({"entry_type": "return", "date": self.today, "amount": 30})
        r = self.c.get(f"/api/suppliers/{self.supplier.id}/summary/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["opening_balance"], 100.0)
        self.assertEqual(r.data["total_purchases"], 200.0)
        self.assertEqual(r.data["total_payments"], 50.0)
        self.assertEqual(r.data["total_returns"], 30.0)
        self.assertEqual(r.data["balance"], 220.0)
        self.assertEqual(r.data["purchases_count"], 1)
        self.assertEqual(r.data["payments_count"], 1)
        self.assertEqual(r.data["returns_count"], 1)

    def test_cash_payment_receiver_name(self):
        r = self._ledger({
            "entry_type": "payment", "date": self.today,
            "amount": 50, "payment_method": "cash", "receiver_name": "خالد",
        })
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["receiver_name"], "خالد")
        entry = LedgerEntry.objects.get(pk=r.data["id"])
        self.assertEqual(entry.receiver_name, "خالد")
        r = self.c.get(f"/api/suppliers/{self.supplier.id}/ledger/")
        self.assertEqual(r.data["results"][0]["receiver_name"], "خالد")

    def test_immediate_cash_payment_receiver_name(self):
        r = self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "payment_amount": 30,
            "payment_method": "cash",
            "receiver_name": "أحمد",
            "items": [{"fabric": self.f1.id, "quantity_yards": 10, "unit_price": 5}],
        })
        self.assertEqual(r.status_code, 201)
        payment = LedgerEntry.objects.get(entry_type="payment")
        self.assertEqual(payment.receiver_name, "أحمد")

    def test_fractional_rolls(self):
        r = self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "items": [{"fabric": self.f1.id, "quantity_yards": 150, "rolls": 3.5, "unit_price": 5}],
        })
        self.assertEqual(r.status_code, 201)
        item = r.data["items"][0]
        self.assertEqual(item["rolls"], "3.50")

    def test_delete_ledger_entry(self):
        r = self._ledger({"entry_type": "opening", "date": self.today, "amount": 100})
        eid = r.data["id"]
        r = self.c.delete(f"/api/suppliers/{self.supplier.id}/ledger/{eid}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(LedgerEntry.objects.count(), 0)

    def test_delete_purchase_removes_immediate_payment(self):
        r = self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "payment_amount": 40,
            "payment_method": "cash",
            "receipt_no": "INV-DEL",
            "items": [{"fabric": self.f1.id, "quantity_yards": 10, "unit_price": 5}],
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(LedgerEntry.objects.filter(entry_type="payment").count(), 1)
        from accounting.models import JournalEntry
        self.assertTrue(
            JournalEntry.objects.filter(source=JournalEntry.Source.PURCHASE).exists()
        )
        r = self.c.delete(f"/api/suppliers/{self.supplier.id}/ledger/{r.data['id']}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(LedgerEntry.objects.count(), 0)
        self.assertFalse(
            JournalEntry.objects.filter(source=JournalEntry.Source.PURCHASE).exists()
        )

    def test_standalone_payment_delete_keeps_purchase(self):
        self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "receipt_no": "INV-STD",
            "items": [{"fabric": self.f1.id, "quantity_yards": 10, "unit_price": 5}],
        })
        payment = LedgerEntry.objects.create(
            supplier=self.supplier,
            date=date.today(),
            entry_type=LedgerEntry.EntryType.PAYMENT,
            amount=-20,
            payment_method=LedgerEntry.PaymentMethod.CASH,
            description="دفعة عادية",
        )
        r = self.c.delete(f"/api/suppliers/{self.supplier.id}/ledger/{payment.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(LedgerEntry.objects.filter(entry_type="payment").count(), 0)
        self.assertEqual(LedgerEntry.objects.filter(entry_type="purchase").count(), 1)

    def test_adjustment_posted_to_opening_offset_not_inventory(self):
        r = self._ledger({
            "entry_type": "adjustment", "date": self.today, "amount": 50,
        })
        self.assertEqual(r.status_code, 201, r.data)
        from accounting.models import JournalEntry
        entry = JournalEntry.objects.filter(
            source=JournalEntry.Source.PURCHASE, source_id=r.data["id"]
        ).first()
        self.assertIsNotNone(entry)
        from accounting.chart_of_accounts import ensure_seeded
        ensure_seeded()
        from accounting.models import Account
        opening = Account.objects.get(source_key="OPENING_OFFSET")
        inv = Account.objects.get(source_key="INVENTORY")
        self.assertTrue(entry.lines.filter(account__source_key="OPENING_OFFSET").exists())
        self.assertFalse(entry.lines.filter(account__source_key="INVENTORY").exists())
        self.assertEqual(entry.lines.filter(account=opening).count(), 1)
        self.assertEqual(entry.lines.filter(account=inv).count(), 0)

    def test_supplier_current_balance(self):
        self._ledger({"entry_type": "opening", "date": self.today, "amount": 100})
        self._ledger({
            "entry_type": "payment", "date": self.today,
            "amount": 40, "payment_method": "cash",
        })
        r = self.c.get("/api/suppliers/")
        sup = next(s for s in r.data["results"] if s["id"] == self.supplier.id)
        self.assertEqual(sup["current_balance"], "60.00")

    def test_purchase_to_warehouse_adds_stock(self):
        wh = Warehouse.objects.create(name="مخزن أ", code="WH-A")
        r = self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "warehouse": wh.id,
            "receipt_no": "INV-1",
            "items": [{"fabric": self.f1.id, "quantity_yards": 10, "rolls": 2, "unit_price": 3}],
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["warehouse_name"], "مخزن أ")
        self.assertEqual(r.data["destination_type"], "warehouse")
        grs = GoodsReceipt.objects.filter(purchase_entry_id=r.data["id"])
        self.assertEqual(grs.count(), 1)
        self.assertEqual(grs.first().status, "posted")
        rolls = FabricRoll.objects.filter(warehouse=wh, fabric=self.f1, status="available")
        self.assertEqual(rolls.count(), 2)
        self.assertEqual(sum(x.remaining_yards for x in rolls), 10)

    def test_purchase_to_branch_adds_stock(self):
        br = Branch.objects.create(name="فرع الاختبار", code="BX-1")
        r = self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "branch": br.id,
            "items": [{"fabric": self.f1.id, "quantity_yards": 25, "rolls": 1, "unit_price": 3}],
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["destination_type"], "branch")
        self.assertEqual(r.data["branch_name"], "فرع الاختبار")
        self.assertEqual(r.data["goods_receipt_number"], GoodsReceipt.objects.get().number)
        bwh = Warehouse.objects.get(branch=br)
        self.assertTrue(bwh.is_branch_stock)
        rolls = FabricRoll.objects.filter(warehouse=bwh, fabric=self.f1, status="available")
        self.assertEqual(sum(x.remaining_yards for x in rolls), 25)

    def test_purchase_two_destinations_rejected(self):
        wh = Warehouse.objects.create(name="مخزن أ", code="WH-A")
        br = Branch.objects.create(name="فرع الاختبار", code="BX-1")
        r = self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "warehouse": wh.id,
            "branch": br.id,
            "items": [{"fabric": self.f1.id, "quantity_yards": 10, "unit_price": 3}],
        })
        self.assertEqual(r.status_code, 400)
        self.assertEqual(GoodsReceipt.objects.count(), 0)

    def test_purchase_without_destination_no_stock(self):
        r = self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "items": [{"fabric": self.f1.id, "quantity_yards": 10, "unit_price": 3}],
        })
        self.assertEqual(r.status_code, 201)
        self.assertEqual(GoodsReceipt.objects.count(), 0)
        self.assertEqual(FabricRoll.objects.count(), 0)

    def test_purchase_item_warehouse_destination(self):
        wh = Warehouse.objects.create(name="مخزن المواد", code="WH-M")
        r = self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "items": [
                {
                    "fabric": self.f1.id, "quantity_yards": 10, "rolls": 1,
                    "unit_price": 3, "warehouse": wh.id,
                }
            ],
        })
        self.assertEqual(r.status_code, 201, r.data)
        item = r.data["items"][0]
        self.assertEqual(item["warehouse_name"], "مخزن المواد")
        self.assertEqual(item["destination_type"], "warehouse")
        self.assertEqual(r.data["destination_name"], "مخزن المواد")
        gr = GoodsReceipt.objects.get()
        self.assertEqual(gr.warehouse_id, wh.id)
        self.assertEqual(gr.status, "posted")
        self.assertEqual(sum(x.remaining_yards for x in FabricRoll.objects.filter(warehouse=wh, fabric=self.f1)), 10)

    def test_purchase_item_branch_destination(self):
        br = Branch.objects.create(name="فرع السيب", code="BX-S")
        r = self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "items": [
                {
                    "fabric": self.f1.id, "quantity_yards": 20, "rolls": 1,
                    "unit_price": 3, "branch": br.id,
                }
            ],
        })
        self.assertEqual(r.status_code, 201, r.data)
        item = r.data["items"][0]
        self.assertEqual(item["branch_name"], "فرع السيب")
        self.assertEqual(item["destination_type"], "branch")
        bwh = Warehouse.objects.get(branch=br)
        self.assertEqual(sum(x.remaining_yards for x in FabricRoll.objects.filter(warehouse=bwh, fabric=self.f1)), 20)

    def test_purchase_items_split_across_destinations(self):
        wh = Warehouse.objects.create(name="مخزن المواد", code="WH-M")
        br = Branch.objects.create(name="فرع السيب", code="BX-S")
        r = self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "items": [
                {
                    "fabric": self.f1.id, "quantity_yards": 10, "rolls": 1,
                    "unit_price": 3, "warehouse": wh.id,
                },
                {
                    "fabric": self.f1.id, "quantity_yards": 10, "rolls": 1,
                    "unit_price": 3, "branch": br.id,
                },
                {
                    "fabric": self.f2.id, "quantity_yards": 5, "rolls": 1,
                    "unit_price": 4,
                },
            ],
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(GoodsReceipt.objects.count(), 2)
        bwh = Warehouse.objects.get(branch=br)
        self.assertEqual(sum(x.remaining_yards for x in FabricRoll.objects.filter(warehouse=wh, fabric=self.f1)), 10)
        self.assertEqual(sum(x.remaining_yards for x in FabricRoll.objects.filter(warehouse=bwh, fabric=self.f1)), 10)
        self.assertEqual(
            FabricRoll.objects.filter(fabric=self.f2, warehouse__isnull=False).count(), 0
        )
        self.assertNotEqual(r.data["destination_type"], "")
        self.assertEqual(r.data["destination_name"], "مخزن المواد، فرع السيب")

    def test_purchase_item_two_destinations_rejected(self):
        wh = Warehouse.objects.create(name="مخزن أ", code="WH-A")
        br = Branch.objects.create(name="فرع الاختبار", code="BX-1")
        r = self._ledger({
            "entry_type": "purchase",
            "date": self.today,
            "items": [
                {
                    "fabric": self.f1.id, "quantity_yards": 10, "unit_price": 3,
                    "warehouse": wh.id, "branch": br.id,
                }
            ],
        })
        self.assertEqual(r.status_code, 400)
        self.assertEqual(GoodsReceipt.objects.count(), 0)

    def test_receive_action_creates_receipt(self):
        wh = Warehouse.objects.create(name="مخزن أ", code="WH-A")
        entry = LedgerEntry.objects.create(
            supplier=self.supplier, date=date.today(), entry_type="purchase",
            amount=30, receipt_no="INV-9", warehouse=wh,
        )
        PurchaseItem.objects.create(
            entry=entry, fabric=self.f1, quantity_yards=10, rolls=1,
            unit_price=3, total=30,
        )
        r = self.c.post(f"/api/suppliers/{self.supplier.id}/ledger/{entry.id}/receive/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["goods_receipt_number"], GoodsReceipt.objects.get().number)
        rolls = FabricRoll.objects.filter(warehouse=wh, fabric=self.f1)
        self.assertEqual(sum(x.remaining_yards for x in rolls), 10)
        # استلام ثانٍ مرفوض
        r = self.c.post(f"/api/suppliers/{self.supplier.id}/ledger/{entry.id}/receive/")
        self.assertEqual(r.status_code, 400)

    def test_receive_action_requires_destination(self):
        entry = LedgerEntry.objects.create(
            supplier=self.supplier, date=date.today(), entry_type="purchase",
            amount=30, receipt_no="INV-10",
        )
        PurchaseItem.objects.create(
            entry=entry, fabric=self.f1, quantity_yards=10, rolls=1,
            unit_price=3, total=30,
        )
        r = self.c.post(f"/api/suppliers/{self.supplier.id}/ledger/{entry.id}/receive/")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(GoodsReceipt.objects.count(), 0)

    def test_overview_summary(self):
        s2 = Supplier.objects.create(name="مورد آخر", is_active=False)
        self._ledger({
            "entry_type": "purchase", "date": self.today,
            "items": [{"fabric": self.f1.id, "quantity_yards": 10, "unit_price": 5}],
        })
        self._ledger({
            "entry_type": "payment", "date": self.today,
            "amount": 20, "payment_method": "cash",
        })
        LedgerEntry.objects.create(
            supplier=s2, date=date.today(), entry_type="opening", amount=50,
        )
        r = self.c.get("/api/suppliers/summary/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_suppliers"], 2)
        self.assertEqual(r.data["active_count"], 1)
        self.assertEqual(r.data["total_purchases"], 50.0)
        self.assertEqual(r.data["total_payments"], 20.0)
        self.assertEqual(r.data["purchases_count"], 1)
        self.assertEqual(r.data["payments_count"], 1)
        self.assertEqual(r.data["outstanding_debit"], 80.0)
        self.assertEqual(r.data["owing_count"], 2)
        self.assertEqual(len(r.data["top_suppliers"]), 2)
        self.assertEqual(r.data["top_suppliers"][0]["name"], "مورد آخر")
