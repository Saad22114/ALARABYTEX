from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from core.testsupport import authenticate_admin

from appsettings.models import AppSettings
from branches.models import Branch
from sale_sessions.models import Employee
from suppliers.models import Fabric
from warehouses.models import FabricRoll, StockMovement, Warehouse
from sales.models import DailySaleItem


class DailySaleAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="B", code="B")
        self.today = date.today().isoformat()

    def _sale(self, **overrides):
        data = {
            "branch": self.branch.id,
            "date": self.today,
            "total_sales": 100,
            "cash_amount": 50,
            "transfer_amount": 30,
            "card_amount": 20,
            "other_amount": 0,
        }
        data.update(overrides)
        return self.c.post("/api/sales/", data, format="json")

    def test_create_balanced_sale(self):
        r = self._sale()
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data["mismatch"])
        self.assertEqual(r.data["payment_total"], "100.00")

    def test_reject_mismatch(self):
        r = self._sale(cash_amount=10, transfer_amount=10)
        self.assertEqual(r.status_code, 400)

    def test_unique_branch_date(self):
        self._sale()
        r = self._sale()
        self.assertEqual(r.status_code, 400)

    def test_list_sales(self):
        self._sale()
        r = self.c.get("/api/sales/")
        self.assertEqual(r.data["count"], 1)

    def test_filter_by_branch(self):
        b2 = Branch.objects.create(name="B2", code="B2")
        self._sale()
        self.c.post("/api/sales/", {
            "branch": b2.id,
            "date": self.today,
            "total_sales": 200,
            "cash_amount": 200,
        }, format="json")
        r = self.c.get("/api/sales/", {"branch": self.branch.id})
        self.assertEqual(r.data["count"], 1)

    def test_update_sale(self):
        r = self._sale()
        sid = r.data["id"]
        r = self.c.put(f"/api/sales/{sid}/", {
            "branch": self.branch.id,
            "date": self.today,
            "total_sales": 200,
            "cash_amount": 200,
            "transfer_amount": 0,
            "card_amount": 0,
            "other_amount": 0,
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_sales"], "200.00")

    def test_delete_sale(self):
        r = self._sale()
        sid = r.data["id"]
        r = self.c.delete(f"/api/sales/{sid}/")
        self.assertEqual(r.status_code, 200)

    def test_summary_endpoint(self):
        self._sale()
        r = self.c.get("/api/sales/summary/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_sales"], 100.0)
        self.assertEqual(r.data["cash"], 50.0)
        self.assertEqual(r.data["transfer"], 30.0)
        self.assertEqual(r.data["card"], 20.0)
        self.assertEqual(r.data["sales_count"], 1)
        self.assertEqual(r.data["days_count"], 1)

    def test_summary_respects_branch_filter(self):
        b2 = Branch.objects.create(name="B2", code="B2")
        self._sale()
        self.c.post("/api/sales/", {
            "branch": b2.id, "date": self.today,
            "total_sales": 200, "cash_amount": 200,
        }, format="json")
        r = self.c.get(f"/api/sales/summary/?branch={self.branch.id}")
        self.assertEqual(r.data["total_sales"], 100.0)
        self.assertEqual(r.data["sales_count"], 1)

    def test_export_xlsx(self):
        self._sale()
        r = self.c.get("/api/sales/", {"export": "xlsx"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


class SaleStockDeductionTest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="B", code="B")
        self.wh = Warehouse.objects.create(name="فرع: B", code="BR-B", branch=self.branch)
        self.fabric = Fabric.objects.create(name="قماش", code="C1", sale_price_yard=2)
        FabricRoll.objects.create(warehouse=self.wh, fabric=self.fabric, yards=50, remaining_yards=50)
        self.today = date.today().isoformat()

    def _sale_with_items(self, yards=20):
        return self.c.post("/api/sales/", {
            "branch": self.branch.id,
            "date": self.today,
            "total_sales": 100,
            "cash_amount": 100,
            "items": [{"fabric": self.fabric.id, "yards": yards}],
        }, format="json")

    def test_sale_with_items_deducts_stock(self):
        r = self._sale_with_items(20)
        self.assertEqual(r.status_code, 201, r.data)
        rolls = FabricRoll.objects.get(fabric=self.fabric)
        self.assertEqual(Decimal(str(rolls.remaining_yards)), Decimal("30"))
        movements = StockMovement.objects.filter(movement_type=StockMovement.Type.SALE)
        self.assertEqual(movements.count(), 1)
        self.assertEqual(Decimal(str(movements[0].quantity)), Decimal("-20"))
        self.assertEqual(Decimal(str(movements[0].balance_before)), Decimal("50"))
        self.assertEqual(Decimal(str(movements[0].balance_after)), Decimal("30"))
        r2 = self.c.get("/api/sales/")
        self.assertEqual(r2.data["count"], 1)
        r3 = self.c.get(f"/api/sales/{r.data['id']}/")
        self.assertEqual(len(r3.data["items"]), 1, r3.data)
        self.assertEqual(Decimal(str(r3.data["items"][0]["yards"])), Decimal("20"))
        self.assertEqual(r3.data["items"][0]["fabric_unit"], "yard")

    def test_sale_insufficient_stock_rejected(self):
        r = self._sale_with_items(200)
        self.assertEqual(r.status_code, 400)
        rolls = FabricRoll.objects.get(fabric=self.fabric)
        self.assertEqual(Decimal(str(rolls.remaining_yards)), Decimal("50"))

    def test_sale_rejected_even_when_negative_stock_setting_on(self):
        s = AppSettings.load()
        s.allow_negative_stock = True
        s.save()
        r = self._sale_with_items(200)
        self.assertEqual(r.status_code, 400, r.data)
        rolls = FabricRoll.objects.get(fabric=self.fabric)
        self.assertEqual(Decimal(str(rolls.remaining_yards)), Decimal("50"))
        self.assertEqual(StockMovement.objects.filter(movement_type=StockMovement.Type.SALE).count(), 0)

    def test_sale_without_items_unchanged(self):
        r = self.c.post("/api/sales/", {
            "branch": self.branch.id, "date": self.today,
            "total_sales": 100, "cash_amount": 100,
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(StockMovement.objects.filter(movement_type=StockMovement.Type.SALE).count(), 0)

    def test_sale_update_with_items_reconciles_stock(self):
        r = self._sale_with_items(20)
        sid = r.data["id"]
        r2 = self.c.put(f"/api/sales/{sid}/", {
            "branch": self.branch.id, "date": self.today,
            "total_sales": 100, "cash_amount": 100,
            "items": [{"fabric": self.fabric.id, "yards": 30}],
        }, format="json")
        self.assertEqual(r2.status_code, 200, r2.data)
        rolls = FabricRoll.objects.get(fabric=self.fabric)
        self.assertEqual(Decimal(str(rolls.remaining_yards)), Decimal("20"))
        r3 = self.c.get(f"/api/sales/{sid}/")
        self.assertEqual(len(r3.data["items"]), 1)
        self.assertEqual(Decimal(str(r3.data["items"][0]["yards"])), Decimal("30"))

    def test_sale_update_removes_items(self):
        r = self._sale_with_items(20)
        sid = r.data["id"]
        r2 = self.c.put(f"/api/sales/{sid}/", {
            "branch": self.branch.id, "date": self.today,
            "total_sales": 100, "cash_amount": 100,
            "items": [],
        }, format="json")
        self.assertEqual(r2.status_code, 200, r2.data)
        rolls = FabricRoll.objects.get(fabric=self.fabric)
        self.assertEqual(Decimal(str(rolls.remaining_yards)), Decimal("50"))
        self.assertEqual(DailySaleItem.objects.filter(sale_id=sid).count(), 0)
        self.assertEqual(StockMovement.objects.filter(movement_type=StockMovement.Type.SALE).count(), 0)

    def test_sale_update_insufficient_stock_keeps_original(self):
        r = self._sale_with_items(20)
        sid = r.data["id"]
        r2 = self.c.put(f"/api/sales/{sid}/", {
            "branch": self.branch.id, "date": self.today,
            "total_sales": 100, "cash_amount": 100,
            "items": [{"fabric": self.fabric.id, "yards": 60}],
        }, format="json")
        self.assertEqual(r2.status_code, 400)
        rolls = FabricRoll.objects.get(fabric=self.fabric)
        self.assertEqual(Decimal(str(rolls.remaining_yards)), Decimal("30"))
        r3 = self.c.get(f"/api/sales/{sid}/")
        self.assertEqual(len(r3.data["items"]), 1)
        self.assertEqual(Decimal(str(r3.data["items"][0]["yards"])), Decimal("20"))

    def test_stock_hints_endpoint(self):
        r = self.c.get(f"/api/sales/stock/?branch={self.branch.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Decimal(str(r.data["items"][0]["yards"])), Decimal("50"))


class SalesByEmployeeTest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="B", code="B")
        self.today = date.today().isoformat()
        self.e1 = Employee.objects.create(name="أحمد", branch=self.branch)
        self.e2 = Employee.objects.create(name="محمد", branch=self.branch)

    def _sale(self, **overrides):
        data = {
            "branch": self.branch.id,
            "date": self.today,
            "total_sales": 100,
            "cash_amount": 100,
            "transfer_amount": 0,
            "card_amount": 0,
            "other_amount": 0,
        }
        data.update(overrides)
        return self.c.post("/api/sales/", data, format="json")

    def test_assign_employee_to_sale(self):
        r = self._sale(employee=self.e1.id)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["employee"], self.e1.id)
        self.assertEqual(r.data["employee_name"], "أحمد")

    def test_reject_employee_from_other_branch(self):
        other = Branch.objects.create(name="B2", code="B2")
        e3 = Employee.objects.create(name="علي", branch=other)
        r = self._sale(employee=e3.id)
        self.assertEqual(r.status_code, 400)

    def test_by_employee_aggregation(self):
        self._sale(employee=self.e1.id, total_sales=100, cash_amount=100, date="2026-09-01")
        self._sale(employee=self.e1.id, total_sales=50, cash_amount=50, date="2026-09-02")
        self._sale(employee=self.e2.id, total_sales=30, cash_amount=30, date="2026-09-03")
        self._sale(total_sales=20, cash_amount=20, date="2026-09-04")
        r = self.c.get(f"/api/sales/by-employee/?branch={self.branch.id}")
        self.assertEqual(r.status_code, 200)
        by_name = {i["employee_name"]: i for i in r.data["items"]}
        self.assertEqual(by_name["أحمد"]["total_sales"], 150.0)
        self.assertEqual(by_name["أحمد"]["sales_count"], 2)
        self.assertEqual(by_name["محمد"]["total_sales"], 30.0)
        self.assertEqual(r.data["unassigned_total"], 20.0)
        self.assertEqual(r.data["grand_total"], 200.0)

    def test_by_employee_requires_employee_branch_match(self):
        r = self.c.get(f"/api/sales/by-employee/?branch={self.branch.id}&date_from={self.today}&date_to={self.today}")
        self.assertEqual(r.status_code, 200)

    def test_by_employee_includes_quantities(self):
        wh = Warehouse.objects.create(name="W", code="W", branch=self.branch)
        fabric = Fabric.objects.create(name="قطن", code="C1", sale_price_yard=5)
        FabricRoll.objects.create(warehouse=wh, fabric=fabric, yards=100, remaining_yards=100)
        self._sale(
            employee=self.e1.id, total_sales=50, cash_amount=50,
            items=[{"fabric": fabric.id, "yards": 10, "unit_price": 5}],
        )
        r = self.c.get(f"/api/sales/by-employee/?branch={self.branch.id}")
        self.assertEqual(r.status_code, 200)
        row = {i["employee_name"]: i for i in r.data["items"]}["أحمد"]
        self.assertEqual(row["items_count"], 1)
        self.assertEqual(row["yards_total"], 10.0)
