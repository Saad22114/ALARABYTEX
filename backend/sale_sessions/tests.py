from datetime import date, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from branches.models import Branch
from sales.models import DailySale, DailySaleItem
from suppliers.models import Fabric
from warehouses.models import FabricRoll, StockMovement, Warehouse

from .models import Employee, SaleSession, SaleSessionItem
from .services import close_session, effective_sale_date


class EffectiveDateTest(TestCase):
    def test_before_2am_uses_previous_day(self):
        d = date(2026, 9, 12)
        now = timezone.make_aware(timezone.datetime.combine(d, time(1, 30)))
        self.assertEqual(effective_sale_date(now), d - timedelta(days=1))

    def test_at_2am_uses_same_day(self):
        d = date(2026, 9, 12)
        now = timezone.make_aware(timezone.datetime.combine(d, time(2, 0)))
        self.assertEqual(effective_sale_date(now), d)

    def test_during_day_uses_same_day(self):
        d = date(2026, 9, 12)
        now = timezone.make_aware(timezone.datetime.combine(d, time(14, 0)))
        self.assertEqual(effective_sale_date(now), d)


class EmployeeAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.branch = Branch.objects.create(name="B", code="B")

    def test_create_employee(self):
        r = self.c.post("/api/employees/", {"name": "علي", "branch": self.branch.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["branch_name"], "B")

    def test_delete_employee_with_sessions_rejected(self):
        emp = Employee.objects.create(name="علي", branch=self.branch)
        SaleSession.objects.create(employee=emp, branch=self.branch)
        r = self.c.delete(f"/api/employees/{emp.id}/")
        self.assertEqual(r.status_code, 400)

    def test_list_employees_filter_by_branch(self):
        branch2 = Branch.objects.create(name="فرع ثاني", code="B2")
        Employee.objects.create(name="علي", branch=self.branch)
        Employee.objects.create(name="محمود", branch=branch2)
        r = self.c.get(f"/api/employees/?branch={self.branch.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["name"], "علي")


class SaleSessionAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.branch = Branch.objects.create(name="B", code="B")
        self.wh = Warehouse.objects.create(name="فرع: B", code="BR-B", branch=self.branch)
        self.emp = Employee.objects.create(name="علي", branch=self.branch)
        self.fabric = Fabric.objects.create(name="قطن", code="C1", sale_price_yard=5, yards_per_roll=50)
        self.roll = FabricRoll.objects.create(
            warehouse=self.wh, fabric=self.fabric, yards=500, remaining_yards=500
        )

    def _open_session(self):
        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def _add_item(self, sid, **overrides):
        data = {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
                "payment_method": "cash"}
        data.update(overrides)
        return self.c.post(f"/api/sale-sessions/{sid}/items/", data, format="json")

    def test_open_session_uses_employee_branch(self):
        d = self._open_session()
        self.assertEqual(d["branch"], self.branch.id)
        self.assertEqual(d["status"], "open")

    def test_second_open_session_rejected(self):
        self._open_session()
        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_add_yard_item_auto_price(self):
        sid = self._open_session()["id"]
        r = self._add_item(sid, quantity=10)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(str(r.data["unit_price"])), Decimal("5"))
        self.assertEqual(Decimal(str(r.data["total"])), Decimal("50"))

    def test_add_item_custom_price(self):
        sid = self._open_session()["id"]
        r = self._add_item(sid, quantity=10, unit_price=7)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Decimal(str(r.data["total"])), Decimal("70"))

    def test_add_roll_item(self):
        sid = self._open_session()["id"]
        r = self._add_item(sid, sale_type="roll", quantity=2)
        self.assertEqual(r.status_code, 201, r.data)
        # سعر اللفة = ياردات اللفة × سعر الياردة
        self.assertEqual(Decimal(str(r.data["unit_price"])), Decimal("250"))
        self.assertEqual(Decimal(str(r.data["total"])), Decimal("500"))

    def test_roll_item_requires_yards_per_roll(self):
        f2 = Fabric.objects.create(name="حرير", code="C2", sale_price_yard=5)
        sid = self._open_session()["id"]
        r = self.c.post(f"/api/sale-sessions/{sid}/items/",
                        {"fabric": f2.id, "sale_type": "roll", "quantity": 1}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_add_item_unavailable_fabric_rejected(self):
        f2 = Fabric.objects.create(name="غير متوفر", code="C6", sale_price_yard=5)
        sid = self._open_session()["id"]
        r = self._add_item(sid, fabric=f2.id)
        self.assertEqual(r.status_code, 400)

    def test_add_item_insufficient_stock_rejected(self):
        f2 = Fabric.objects.create(name="كمية قليلة", code="C7", sale_price_yard=5)
        FabricRoll.objects.create(
            warehouse=self.wh, fabric=f2, yards=10, remaining_yards=10
        )
        sid = self._open_session()["id"]
        r = self._add_item(sid, fabric=f2.id, quantity=15)
        self.assertEqual(r.status_code, 400, r.data)
        r2 = self._add_item(sid, fabric=f2.id, quantity=10)
        self.assertEqual(r2.status_code, 201, r2.data)

    def test_add_roll_item_insufficient_stock_rejected(self):
        f2 = Fabric.objects.create(
            name="لفة قليلة", code="C8", sale_price_yard=5,
            yards_per_roll=50, sale_price_roll=250,
        )
        FabricRoll.objects.create(
            warehouse=self.wh, fabric=f2, yards=100, remaining_yards=100
        )
        sid = self._open_session()["id"]
        # لفتان = 100 ياردة، المتوفر 100 بالضبط → مطابق
        r = self.c.post(f"/api/sale-sessions/{sid}/items/",
                        {"fabric": f2.id, "sale_type": "roll", "quantity": 2,
                         "payment_method": "cash"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        # 3 لفات = 150 ياردة > المتوفر 100 → مرفوض
        r2 = self.c.post(f"/api/sale-sessions/{sid}/items/",
                         {"fabric": f2.id, "sale_type": "roll", "quantity": 3,
                          "payment_method": "cash"}, format="json")
        self.assertEqual(r2.status_code, 400)

    def test_roll_auto_price_uses_sale_price_roll(self):
        f2 = Fabric.objects.create(
            name="قماش لفة", code="C3", sale_price_yard=5,
            sale_price_roll=230, yards_per_roll=50,
        )
        FabricRoll.objects.create(warehouse=self.wh, fabric=f2, yards=100, remaining_yards=100)
        sid = self._open_session()["id"]
        r = self.c.post(f"/api/sale-sessions/{sid}/items/",
                        {"fabric": f2.id, "sale_type": "roll", "quantity": 1}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(str(r.data["unit_price"])), Decimal("230"))

    def test_min_price_yard_enforced(self):
        f2 = Fabric.objects.create(
            name="قماش حد", code="C4", sale_price_yard=5, min_sale_yard=6,
        )
        FabricRoll.objects.create(warehouse=self.wh, fabric=f2, yards=100, remaining_yards=100)
        sid = self._open_session()["id"]
        base = {"fabric": f2.id, "sale_type": "yard", "quantity": 1, "payment_method": "cash"}
        r = self.c.post(f"/api/sale-sessions/{sid}/items/",
                        {**base, "unit_price": 5}, format="json")
        self.assertEqual(r.status_code, 400)
        r2 = self.c.post(f"/api/sale-sessions/{sid}/items/",
                         {**base, "unit_price": 7}, format="json")
        self.assertEqual(r2.status_code, 201, r2.data)

    def test_min_roll_price_enforced(self):
        f2 = Fabric.objects.create(
            name="قماش لفة حد", code="C5", sale_price_yard=5,
            yards_per_roll=50, sale_price_roll=200, min_sale_roll=220,
        )
        FabricRoll.objects.create(warehouse=self.wh, fabric=f2, yards=200, remaining_yards=200)
        sid = self._open_session()["id"]
        r = self.c.post(f"/api/sale-sessions/{sid}/items/",
                        {"fabric": f2.id, "sale_type": "roll", "quantity": 1,
                         "payment_method": "cash"}, format="json")
        self.assertEqual(r.status_code, 400)  # السعر التلقائي 200 دون الحد الأدنى 220

    def test_add_after_close_rejected(self):
        sid = self._open_session()["id"]
        self._add_item(sid, quantity=5)
        r = self.c.post(f"/api/sale-sessions/{sid}/close/")
        self.assertEqual(r.status_code, 200)
        r2 = self._add_item(sid, quantity=3)
        self.assertEqual(r2.status_code, 400)

    def test_remove_item(self):
        sid = self._open_session()["id"]
        item = self._add_item(sid, quantity=5)
        iid = item.data["id"]
        r = self.c.delete(f"/api/sale-sessions/{sid}/items/{iid}/")
        self.assertEqual(r.status_code, 200)
        r2 = self.c.get("/api/sale-sessions/")
        self.assertEqual(r2.data["results"][0]["totals"]["total"], 0)

    def test_close_creates_daily_sale_and_deducts_stock(self):
        sid = self._open_session()["id"]
        self._add_item(sid, quantity=20, payment_method="cash")
        self._add_item(sid, quantity=10, payment_method="card")
        self._add_item(sid, sale_type="roll", quantity=1, payment_method="transfer")
        r = self.c.post(f"/api/sale-sessions/{sid}/close/")
        self.assertEqual(r.status_code, 200, r.data)

        session = SaleSession.objects.get(pk=sid)
        self.assertEqual(session.status, SaleSession.Status.CLOSED)
        self.assertIsNotNone(session.closed_at)

        sale_date = effective_sale_date()
        sale = DailySale.objects.get(branch=self.branch, date=sale_date)
        # 20*5 + 10*5 + 1*250 = 400
        self.assertEqual(Decimal(str(sale.total_sales)), Decimal("400"))
        self.assertEqual(Decimal(str(sale.cash_amount)), Decimal("100"))
        self.assertEqual(Decimal(str(sale.card_amount)), Decimal("50"))
        self.assertEqual(Decimal(str(sale.transfer_amount)), Decimal("250"))

        roll = FabricRoll.objects.get(fabric=self.fabric)
        # خصم: 20 + 10 + 50 = 80 من رصيد 500
        self.assertEqual(Decimal(str(roll.remaining_yards)), Decimal("420"))
        self.assertEqual(
            StockMovement.objects.filter(movement_type=StockMovement.Type.SALE).count(), 3
        )

    def test_close_merges_into_existing_daily_sale(self):
        sid1 = self._open_session()["id"]
        self._add_item(sid1, quantity=20)
        self.c.post(f"/api/sale-sessions/{sid1}/close/")

        emp2 = Employee.objects.create(name="محمود", branch=self.branch)
        sid2 = self.c.post("/api/sale-sessions/", {"employee": emp2.id}, format="json").data["id"]
        self._add_item(sid2, quantity=10)
        self.c.post(f"/api/sale-sessions/{sid2}/close/")

        sale_date = effective_sale_date()
        sale = DailySale.objects.get(branch=self.branch, date=sale_date)
        self.assertEqual(Decimal(str(sale.total_sales)), Decimal("150"))
        item = DailySaleItem.objects.get(sale=sale, fabric=self.fabric)
        self.assertEqual(Decimal(str(item.yards)), Decimal("30"))
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("470"))

    def test_close_twice_rejected(self):
        sid = self._open_session()["id"]
        self._add_item(sid, quantity=5)
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        r = self.c.post(f"/api/sale-sessions/{sid}/close/")
        self.assertEqual(r.status_code, 400)

    def test_open_session_list(self):
        self._open_session()
        r = self.c.get("/api/sale-sessions/", {"status": "open"})
        self.assertEqual(r.data["results"][0]["status"], "open")

    def test_close_empty_session(self):
        sid = self._open_session()["id"]
        r = self.c.post(f"/api/sale-sessions/{sid}/close/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(DailySale.objects.filter(branch=self.branch).exists())

    def test_session_totals_include_yards_and_elapsed(self):
        sid = self._open_session()["id"]
        self._add_item(sid, quantity=10)
        self._add_item(sid, sale_type="roll", quantity=2)
        r = self.c.get(f"/api/sale-sessions/{sid}/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["totals"]["total"], 550.0)
        self.assertEqual(r.data["totals"]["yards"], 110.0)
        self.assertIsNotNone(r.data["elapsed_minutes"])

    def test_closed_session_elapsed_none(self):
        sid = self._open_session()["id"]
        self._add_item(sid, quantity=5)
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        r = self.c.get(f"/api/sale-sessions/{sid}/")
        self.assertIsNone(r.data["elapsed_minutes"])

    def test_session_summary_endpoint(self):
        sid = self._open_session()["id"]
        self._add_item(sid, quantity=10)
        self._add_item(sid, quantity=5, payment_method="card")
        r = self.c.get("/api/sale-sessions/summary/?status=open")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["open_count"], 1)
        self.assertEqual(r.data["items_count"], 2)
        self.assertEqual(r.data["total"], 75.0)
        self.assertEqual(r.data["cash"], 50.0)
        self.assertEqual(r.data["card"], 25.0)
        self.assertEqual(r.data["yards"], 15.0)

    def test_session_summary_empty(self):
        r = self.c.get("/api/sale-sessions/summary/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 0)
        self.assertEqual(r.data["total"], 0.0)
        self.assertEqual(r.data["yards"], 0.0)

    def test_session_filter_by_employee_and_branch(self):
        emp2 = Employee.objects.create(name="محمود", branch=self.branch)
        self._open_session()
        self.c.post("/api/sale-sessions/", {"employee": emp2.id}, format="json")
        r = self.c.get(f"/api/sale-sessions/?employee={self.emp.id}")
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["employee_name"], "علي")
        r2 = self.c.get(f"/api/sale-sessions/?branch={self.branch.id}")
        self.assertEqual(r2.data["count"], 2)
        r3 = self.c.get("/api/sale-sessions/?opened_from=2999-01-01")
        self.assertEqual(r3.data["count"], 0)


class ClosedSessionEditDeleteTest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.branch = Branch.objects.create(name="B", code="B")
        self.wh = Warehouse.objects.create(name="فرع: B", code="BR-B", branch=self.branch)
        self.emp = Employee.objects.create(name="علي", branch=self.branch)
        self.fabric = Fabric.objects.create(name="قطن", code="C1", sale_price_yard=5, yards_per_roll=50)
        self.roll = FabricRoll.objects.create(
            warehouse=self.wh, fabric=self.fabric, yards=500, remaining_yards=500
        )

    def _closed_session(self):
        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        sid = r.data["id"]
        self.c.post(f"/api/sale-sessions/{sid}/items/",
                    {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 20,
                     "payment_method": "cash"}, format="json")
        self.c.post(f"/api/sale-sessions/{sid}/items/",
                    {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
                     "payment_method": "card"}, format="json")
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        return sid

    def test_edit_closed_item_updates_daily_sale_and_stock(self):
        sid = self._closed_session()
        sale_date = effective_sale_date()
        sale = DailySale.objects.get(branch=self.branch, date=sale_date)
        # الحصول على البند الأول (ياردات 20) وتعديله
        items = list(SaleSessionItem.objects.filter(session_id=sid).order_by("id"))
        r = self.c.put(f"/api/sale-sessions/{sid}/items/{items[0].id}/",
                       {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 15,
                        "unit_price": 5, "payment_method": "cash"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(str(r.data["quantity"])), Decimal("15"))
        # الإجمالي: 15*5 + 10*5 = 125 (كان 150)
        sale.refresh_from_db()
        self.assertEqual(Decimal(str(sale.total_sales)), Decimal("125"))
        item = SaleSessionItem.objects.get(pk=items[0].id)
        self.assertEqual(Decimal(str(item.total)), Decimal("75"))
        # المخزون: 500 - 25 = 475
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("475"))
        # حركات البيع أُعيد بناؤها (بند أجمد واحد بعد الدمج)
        self.assertEqual(
            StockMovement.objects.filter(movement_type=StockMovement.Type.SALE).count(), 1
        )

    def test_edit_closed_item_changes_payment_method(self):
        sid = self._closed_session()
        items = list(SaleSessionItem.objects.filter(session_id=sid).order_by("id"))
        r = self.c.patch(f"/api/sale-sessions/{sid}/items/{items[1].id}/",
                         {"payment_method": "transfer"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        sale_date = effective_sale_date()
        sale = DailySale.objects.get(branch=self.branch, date=sale_date)
        self.assertEqual(Decimal(str(sale.card_amount)), Decimal("0"))
        self.assertEqual(Decimal(str(sale.transfer_amount)), Decimal("50"))
        self.assertEqual(Decimal(str(sale.total_sales)), Decimal("150"))

    def test_edit_closed_item_quantity_zero_rolled_back_on_error(self):
        sid = self._closed_session()
        items = list(SaleSessionItem.objects.filter(session_id=sid).order_by("id"))
        # كمية سالبة → خطأ تحقق، لا يتغير شيء
        r = self.c.put(f"/api/sale-sessions/{sid}/items/{items[0].id}/",
                       {"fabric": self.fabric.id, "sale_type": "yard", "quantity": -5,
                        "unit_price": 5, "payment_method": "cash"}, format="json")
        self.assertEqual(r.status_code, 400)
        sale_date = effective_sale_date()
        sale = DailySale.objects.get(branch=self.branch, date=sale_date)
        self.assertEqual(Decimal(str(sale.total_sales)), Decimal("150"))

    def test_delete_closed_item_removes_from_daily_sale_and_restores_stock(self):
        sid = self._closed_session()
        items = list(SaleSessionItem.objects.filter(session_id=sid).order_by("id"))
        r = self.c.delete(f"/api/sale-sessions/{sid}/items/{items[0].id}/")
        self.assertEqual(r.status_code, 200)
        sale_date = effective_sale_date()
        sale = DailySale.objects.get(branch=self.branch, date=sale_date)
        # بند واحد متبقٍ: 10*5 = 50
        self.assertEqual(Decimal(str(sale.total_sales)), Decimal("50"))
        # المخزون عاد جزئياً: 500 - 10 = 490
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("490"))

    def test_delete_last_closed_item_deletes_daily_sale(self):
        sid = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json").data["id"]
        self.c.post(f"/api/sale-sessions/{sid}/items/",
                    {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 20,
                     "payment_method": "cash"}, format="json")
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        item = SaleSessionItem.objects.get(session_id=sid)
        r = self.c.delete(f"/api/sale-sessions/{sid}/items/{item.id}/")
        self.assertEqual(r.status_code, 200)
        sale_date = effective_sale_date()
        self.assertFalse(DailySale.objects.filter(branch=self.branch, date=sale_date).exists())
        # رصيد عاد كاملاً
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("500"))
        self.assertEqual(
            StockMovement.objects.filter(movement_type=StockMovement.Type.SALE).count(), 0
        )