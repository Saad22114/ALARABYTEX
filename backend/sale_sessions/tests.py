from datetime import date, time, timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from core.testsupport import authenticate_admin

from branches.models import Branch, FabricBranchPrice
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

    def test_configurable_cutoff_hour(self):
        from appsettings.models import AppSettings

        settings = AppSettings.load()
        settings.previous_day_cutoff_hour = 5
        settings.save(update_fields=["previous_day_cutoff_hour"])
        d = date(2026, 9, 12)
        early = timezone.make_aware(timezone.datetime.combine(d, time(4, 30)))
        late = timezone.make_aware(timezone.datetime.combine(d, time(6, 0)))
        self.assertEqual(effective_sale_date(early), d - timedelta(days=1))
        self.assertEqual(effective_sale_date(late), d)


class EmployeeAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
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

    def test_create_employee_defaults_to_admin_role_with_permissions(self):
        r = self.c.post("/api/employees/", {"name": "زينب", "branch": self.branch.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["role"], "admin")
        self.assertTrue(r.data["permissions"]["sales"]["create"])
        self.assertTrue(r.data["permissions"]["sales"]["delete"])

    def test_create_employee_with_sales_role_gets_preset(self):
        r = self.c.post("/api/employees/", {"name": "سارة", "branch": self.branch.id, "role": "sales"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["role"], "sales")
        self.assertTrue(r.data["permissions"]["sales"]["view"])
        self.assertFalse(r.data["permissions"]["settings"]["view"])
        self.assertIn("employees", r.data["hidden_sections"])

    def test_update_employee_role_reapplies_preset(self):
        r = self.c.post("/api/employees/", {"name": "خالد", "branch": self.branch.id, "role": "sales"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        emp = r.data
        r = self.c.patch(f"/api/employees/{emp['id']}/", {"role": "viewer"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["role"], "viewer")
        self.assertTrue(r.data["permissions"]["sales"]["view"])
        self.assertFalse(r.data["permissions"]["sales"]["edit"])

    def test_custom_role_permissions_saved(self):
        perms = {"sales": {"view": True, "create": False, "edit": False, "delete": False}}
        r = self.c.post("/api/employees/", {
            "name": "نور", "branch": self.branch.id, "role": "custom",
            "permissions": perms, "hidden_sections": ["reports"],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["role"], "custom")
        self.assertTrue(r.data["permissions"]["sales"]["view"])
        self.assertFalse(r.data["permissions"]["sales"]["edit"])
        self.assertIn("reports", r.data["hidden_sections"])

    def test_update_permissions_only_via_put_succeeds(self):
        r = self.c.post("/api/employees/", {"name": "ليلى", "branch": self.branch.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        emp_id = r.data["id"]
        perms = {"sales": {"view": True, "create": True, "edit": False, "delete": False}}
        r = self.c.put(f"/api/employees/{emp_id}/", {
            "role": "custom",
            "permissions": perms,
            "hidden_sections": ["reports"],
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["role"], "custom")
        self.assertEqual(r.data["name"], "ليلى")
        self.assertTrue(r.data["permissions"]["sales"]["create"])
        self.assertFalse(r.data["permissions"]["sales"]["edit"])
        self.assertIn("reports", r.data["hidden_sections"])

    def test_update_employee_username_and_password(self):
        r = self.c.post("/api/employees/", {
            "name": "أحمد", "branch": self.branch.id,
            "username": "ahmed", "password": "OldPass@123",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        emp_id = r.data["id"]
        r = self.c.patch(f"/api/employees/{emp_id}/", {
            "username": "ahmed_new", "password": "NewPass@456",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["username"], "ahmed_new")
        user = Employee.objects.get(id=emp_id).user
        self.assertEqual(user.username, "ahmed_new")
        self.assertTrue(user.check_password("NewPass@456"))

    def test_update_employee_blank_password_keeps_current(self):
        r = self.c.post("/api/employees/", {
            "name": "مريم", "branch": self.branch.id,
            "username": "mariam", "password": "KeepMe@123",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        emp_id = r.data["id"]
        r = self.c.patch(f"/api/employees/{emp_id}/", {"password": ""}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(Employee.objects.get(id=emp_id).user.check_password("KeepMe@123"))

    def test_update_employee_rejects_conflicting_username(self):
        r1 = self.c.post("/api/employees/", {
            "name": "أول", "branch": self.branch.id, "username": "taken",
        }, format="json")
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self.c.post("/api/employees/", {
            "name": "ثاني", "branch": self.branch.id, "username": "other",
        }, format="json")
        self.assertEqual(r2.status_code, 201, r2.data)
        r = self.c.patch(f"/api/employees/{r2.data['id']}/", {"username": "taken"}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(Employee.objects.get(id=r2.data["id"]).user.username, "other")

    def test_create_employees_with_blank_employee_code(self):
        for i in range(2):
            r = self.c.post("/api/employees/", {
                "name": f"بلا كود {i}",
                "branch": self.branch.id,
                "employee_code": "",
            }, format="json")
            self.assertEqual(r.status_code, 201, r.data)
            self.assertIsNone(r.data["employee_code"])

    def test_duplicate_employee_code_rejected(self):
        r1 = self.c.post("/api/employees/", {
            "name": "الأول", "branch": self.branch.id, "employee_code": "EMP-100",
        }, format="json")
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self.c.post("/api/employees/", {
            "name": "الثاني", "branch": self.branch.id, "employee_code": "EMP-100",
        }, format="json")
        self.assertEqual(r2.status_code, 400)
        self.assertIn("employee_code", r2.data)

    def test_update_duplicate_employee_code_rejected(self):
        e1 = Employee.objects.create(name="الأول", branch=self.branch, employee_code="EMP-1")
        e2 = Employee.objects.create(name="الثاني", branch=self.branch, employee_code="EMP-2")
        r = self.c.patch(f"/api/employees/{e2.id}/", {"employee_code": "EMP-1"}, format="json")
        self.assertEqual(r.status_code, 400)
        e2.refresh_from_db()
        self.assertEqual(e2.employee_code, "EMP-2")

    def test_update_own_employee_code_unchanged(self):
        e1 = Employee.objects.create(name="الأول", branch=self.branch, employee_code="EMP-1")
        r = self.c.patch(f"/api/employees/{e1.id}/", {"employee_code": "EMP-1"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["employee_code"], "EMP-1")

    def test_rejected_create_leaves_no_orphan_user(self):
        from django.contrib.auth.models import User

        r1 = self.c.post("/api/employees/", {
            "name": "الأول", "branch": self.branch.id, "employee_code": "EMP-999",
        }, format="json")
        self.assertEqual(r1.status_code, 201, r1.data)
        r = self.c.post("/api/employees/", {
            "name": "المكرر", "branch": self.branch.id, "employee_code": "EMP-999",
            "username": "dupcode",
        }, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(User.objects.filter(username="dupcode").exists())


class SectionsAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)

    def test_sections_endpoint_returns_sections_and_roles(self):
        r = self.c.get("/api/sections/")
        self.assertEqual(r.status_code, 200)
        keys = {s["key"] for s in r.data["sections"]}
        for expect in ("sales", "warehouses", "employees", "settings", "dashboard"):
            self.assertIn(expect, keys)
        self.assertIn("admin", r.data["roles"])
        self.assertIn("custom", r.data["roles"])

    def test_role_presets_have_permission_fields_matching_actions(self):
        r = self.c.get("/api/sections/")
        actions = self.c.get("/api/sections/").data["sections"][0]["actions"]
        for role_key, role in r.data["roles"].items():
            for section in r.data["sections"]:
                if section["key"] in role["permissions"]:
                    for action in actions:
                        self.assertIn(action, role["permissions"][section["key"]])


class SaleSessionAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
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
        if data.get("payment_method") == "card" and "card_type" not in data:
            data["card_type"] = "credit"
        return self.c.post(f"/api/sale-sessions/{sid}/items/", data, format="json")

    def test_open_session_uses_employee_branch(self):
        d = self._open_session()
        self.assertEqual(d["branch"], self.branch.id)
        self.assertEqual(d["status"], "open")

    def test_second_open_session_rejected(self):
        self._open_session()
        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_open_reopens_same_day_closed_session(self):
        sid = self._open_session()["id"]
        self._add_item(sid, quantity=10)
        self.assertEqual(self.c.post(f"/api/sale-sessions/{sid}/close/").status_code, 200)
        # بعد إغلاق وردية الصباح للاستراحة، يُعيد فتح نفس الوردية بدل إنشاء وردية جديدة
        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["id"], sid)
        self.assertTrue(r.data.get("reopened"))
        self.assertEqual(r.data["status"], "open")
        # البنود القديمة ما زالت محفوظة في نفس الوردية
        self.assertEqual(len(r.data["items"]), 1)

    def test_open_same_day_reopen_keeps_same_session_record(self):
        sid = self._open_session()["id"]
        self._add_item(sid, quantity=20)
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["id"], sid)
        self.assertEqual(SaleSession.objects.filter(id=sid).count(), 1)
        self.assertEqual(SaleSessionItem.objects.filter(session_id=sid).count(), 1)
        self.roll.refresh_from_db()
        # المخزون عاد متاحاً بعد إعادة الفتح (عكس الاستهلاك عند الإغلاق)
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("500"))

    def test_add_yard_item_auto_price(self):
        sid = self._open_session()["id"]
        r = self._add_item(sid, quantity=10)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(str(r.data["unit_price"])), Decimal("5"))
        self.assertEqual(Decimal(str(r.data["total"])), Decimal("50"))

    def test_add_yard_item_uses_branch_price_when_set(self):
        FabricBranchPrice.objects.create(
            branch=self.branch, fabric=self.fabric, sale_price_yard=8, min_sale_yard=0,
        )
        sid = self._open_session()["id"]
        r = self._add_item(sid, quantity=10)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(str(r.data["unit_price"])), Decimal("8"))

    def test_branch_min_price_enforced(self):
        FabricBranchPrice.objects.create(
            branch=self.branch, fabric=self.fabric, sale_price_yard=8, min_sale_yard=7,
        )
        sid = self._open_session()["id"]
        r = self._add_item(sid, quantity=10, unit_price=6)
        self.assertEqual(r.status_code, 400)

    def test_add_item_custom_price(self):
        sid = self._open_session()["id"]
        r = self._add_item(sid, quantity=10, unit_price=7)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Decimal(str(r.data["total"])), Decimal("70"))

    def test_item_without_price_rejected(self):
        f2 = Fabric.objects.create(name="بلا سعر", code="C9", sale_price_yard=0)
        FabricRoll.objects.create(warehouse=self.wh, fabric=f2, yards=50, remaining_yards=50)
        sid = self._open_session()["id"]
        r = self.c.post(
            f"/api/sale-sessions/{sid}/items/",
            {"fabric": f2.id, "sale_type": "yard", "quantity": 1, "payment_method": "cash"},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.data)

    def test_item_without_auto_price_accepts_custom_price(self):
        f2 = Fabric.objects.create(name="بلا سعر 2", code="C10", sale_price_yard=0)
        FabricRoll.objects.create(warehouse=self.wh, fabric=f2, yards=50, remaining_yards=50)
        sid = self._open_session()["id"]
        r = self.c.post(
            f"/api/sale-sessions/{sid}/items/",
            {"fabric": f2.id, "sale_type": "yard", "quantity": 1, "unit_price": 7, "payment_method": "cash"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)

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

    def test_cumulative_session_items_exceeding_stock_rejected(self):
        # رصيد المخزن 500 — بنود الوردية المعلّقة تُخصم من المتاح عند إضافة أي بند
        sid = self._open_session()["id"]
        r1 = self._add_item(sid, quantity=300)
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self._add_item(sid, quantity=250)  # 300 + 250 = 550 > 500 → مرفوض
        self.assertEqual(r2.status_code, 400, r2.data)
        r3 = self._add_item(sid, quantity=200)  # 300 + 200 = 500 بالضبط → مقبول
        self.assertEqual(r3.status_code, 201, r3.data)
        r4 = self._add_item(sid, quantity=1)  # 500 + 1 = 501 > 500 → مرفوض
        self.assertEqual(r4.status_code, 400, r4.data)

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

    def _bulk_items(self, sid, items):
        return self.c.post(
            f"/api/sale-sessions/{sid}/items/bulk/",
            {"items": items},
            format="json",
        )

    def test_bulk_add_items(self):
        sid = self._open_session()["id"]
        r = self._bulk_items(
            sid,
            [
                {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10, "payment_method": "cash"},
                {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 5, "payment_method": "card", "card_type": "credit"},
                {"fabric": self.fabric.id, "sale_type": "roll", "quantity": 1, "payment_method": "transfer"},
            ],
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(r.data), 3)
        session = SaleSession.objects.get(pk=sid)
        self.assertEqual(session.items.count(), 3)
        self.assertEqual(
            Decimal(str(session.items.aggregate(total=Sum("total"))["total"])),
            Decimal("325"),  # 10*5 + 5*5 + 1*250
        )

    def test_bulk_add_stores_customer_phone(self):
        sid = self._open_session()["id"]
        r = self._bulk_items(
            sid,
            [
                {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10, "payment_method": "cash", "customer_name": "أحمد العلي", "customer_phone": "0501234567"},
                {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 5, "payment_method": "card", "card_type": "credit"},
            ],
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data[0]["customer_name"], "أحمد العلي")
        self.assertEqual(r.data[0]["customer_phone"], "0501234567")
        self.assertEqual(r.data[1]["customer_name"], "")
        self.assertEqual(r.data[1]["customer_phone"], "")
        # ترتيب البنود في الجلسة هو -id: first() = الأحدث id
        items = list(SaleSession.objects.get(pk=sid).items.all())
        self.assertEqual(items[1].customer_name, "أحمد العلي")
        self.assertEqual(items[1].customer_phone, "0501234567")
        self.assertEqual(items[0].customer_name, "")
        self.assertEqual(items[0].customer_phone, "")

    def test_bulk_add_shared_sale_group(self):
        sid = self._open_session()["id"]
        r = self._bulk_items(
            sid,
            [
                {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10, "payment_method": "cash"},
                {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 5, "payment_method": "card", "card_type": "credit"},
            ],
        )
        self.assertEqual(r.status_code, 201, r.data)
        groups = {it["sale_group"] for it in r.data}
        self.assertEqual(len(groups), 1)
        self.assertTrue(r.data[0]["sale_group"])
        # بنود من عمليتين منفصلتين لا تشارك نفس المعرّف
        r2 = self._bulk_items(
            sid,
            [{"fabric": self.fabric.id, "sale_type": "yard", "quantity": 3, "payment_method": "cash"}],
        )
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertNotEqual(r2.data[0]["sale_group"], r.data[0]["sale_group"])

    def test_single_add_stores_customer_phone(self):
        sid = self._open_session()["id"]
        r = self._add_item(sid, quantity=5, customer_name="سارة", customer_phone="0559876543")
        self.assertEqual(r.status_code, 201, r.data)
        item = SaleSession.objects.get(pk=sid).items.first()
        self.assertEqual(item.customer_name, "سارة")
        self.assertEqual(item.customer_phone, "0559876543")

    def test_bulk_add_requires_items_list(self):
        sid = self._open_session()["id"]
        r = self.c.post(f"/api/sale-sessions/{sid}/items/bulk/", {}, format="json")
        self.assertEqual(r.status_code, 400)
        r2 = self.c.post(f"/api/sale-sessions/{sid}/items/bulk/", {"items": []}, format="json")
        self.assertEqual(r2.status_code, 400)

    def test_bulk_add_all_or_nothing(self):
        f2 = Fabric.objects.create(name="كمية قليلة", code="C9", sale_price_yard=5)
        FabricRoll.objects.create(
            warehouse=self.wh, fabric=f2, yards=10, remaining_yards=10
        )
        sid = self._open_session()["id"]
        # البند الثاني يتجاوز المخزون المتوفر → تُرفض العملية كلها ولا يُحفظ أي بند
        r = self._bulk_items(
            sid,
            [
                {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10, "payment_method": "cash"},
                {"fabric": f2.id, "sale_type": "yard", "quantity": 15, "payment_method": "cash"},
            ],
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(SaleSession.objects.get(pk=sid).items.count(), 0)

    def test_bulk_add_after_close_rejected(self):
        sid = self._open_session()["id"]
        self._add_item(sid, quantity=5)
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        r = self._bulk_items(
            sid,
            [{"fabric": self.fabric.id, "sale_type": "yard", "quantity": 3, "payment_method": "cash"}],
        )
        self.assertEqual(r.status_code, 400)

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


class ManualSessionAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="B", code="B")
        self.wh = Warehouse.objects.create(name="فرع: B", code="BR-B", branch=self.branch)
        self.emp = Employee.objects.create(name="علي", branch=self.branch)
        self.fabric = Fabric.objects.create(name="قطن", code="C1", sale_price_yard=5, yards_per_roll=50)
        self.roll = FabricRoll.objects.create(
            warehouse=self.wh, fabric=self.fabric, yards=500, remaining_yards=500
        )

    def _manual(self, **overrides):
        data = {
            "employee": self.emp.id,
            "date": "2026-09-12",
            "cash": "100.00",
            "transfer": "50.00",
            "card": "25.00",
            "notes": "مجموع يدوي",
        }
        data.update(overrides)
        return self.c.post("/api/sale-sessions/manual/", data, format="json")

    def test_creates_closed_manual_session_and_daily_sale(self):
        r = self._manual()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["is_manual"])
        self.assertEqual(r.data["status"], "closed")
        self.assertEqual(r.data["items"], [])
        self.assertEqual(r.data["totals"]["cash"], 100.0)
        self.assertEqual(r.data["totals"]["transfer"], 50.0)
        self.assertEqual(r.data["totals"]["card"], 25.0)
        self.assertEqual(r.data["totals"]["total"], 175.0)
        sale = DailySale.objects.get(branch=self.branch, date=date(2026, 9, 12))
        self.assertEqual(sale.total_sales, Decimal("175.00"))
        self.assertEqual(sale.cash_amount, Decimal("100.00"))
        self.assertEqual(sale.transfer_amount, Decimal("50.00"))
        self.assertEqual(sale.card_amount, Decimal("25.00"))

    def test_does_not_deduct_stock(self):
        self._manual()
        self.roll.refresh_from_db()
        self.assertEqual(self.roll.remaining_yards, Decimal("500"))
        self.assertFalse(StockMovement.objects.exists())

    def test_rejects_zero_total(self):
        r = self._manual(cash="0", transfer="0", card="0")
        self.assertEqual(r.status_code, 400, r.data)

    def test_rejects_negative_amount(self):
        r = self._manual(cash="-5")
        self.assertEqual(r.status_code, 400, r.data)

    def test_rejects_employee_of_other_branch(self):
        branch2 = Branch.objects.create(name="B2", code="B2")
        r = self._manual(branch=branch2.id)
        self.assertEqual(r.status_code, 400, r.data)

    def test_delete_reverses_daily_sale(self):
        sid = self._manual().data["id"]
        r = self.c.delete(f"/api/sale-sessions/{sid}/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(DailySale.objects.filter(branch=self.branch, date=date(2026, 9, 12)).exists())

    def test_cannot_reopen_manual_session(self):
        sid = self._manual().data["id"]
        r = self.c.post(f"/api/sale-sessions/{sid}/reopen/")
        self.assertEqual(r.status_code, 400, r.data)

    def test_adds_to_existing_daily_sale(self):
        DailySale.objects.create(
            branch=self.branch, employee=self.emp, date=date(2026, 9, 12),
            total_sales=Decimal("30"), cash_amount=Decimal("30"),
        )
        self._manual(cash="20", transfer="0", card="0")
        sale = DailySale.objects.get(branch=self.branch, date=date(2026, 9, 12))
        self.assertEqual(sale.total_sales, Decimal("50.00"))
        self.assertEqual(sale.cash_amount, Decimal("50.00"))

    def test_manual_commission_applied(self):
        self.emp.commission_active = True
        self.emp.commission_percent = Decimal("10")
        self.emp.save(update_fields=["commission_active", "commission_percent"])
        r = self._manual()
        self.assertEqual(Decimal(str(r.data["commission_amount"])), Decimal("17.50"))

    def test_closed_range_filter_uses_manual_date(self):
        self._manual(date="2026-09-10")
        r = self.c.get("/api/sale-sessions/?status=closed&closed_from=2026-09-10&closed_to=2026-09-10")
        self.assertEqual(r.data["count"], 1)
        r2 = self.c.get("/api/sale-sessions/?status=closed&closed_from=2026-09-11&closed_to=2026-09-11")
        self.assertEqual(r2.data["count"], 0)


class ClosedSessionEditDeleteTest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
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
                     "payment_method": "card", "card_type": "credit"}, format="json")
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

    def test_update_open_session_notes_and_employee(self):
        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        sid = r.data["id"]
        emp2 = Employee.objects.create(name="محمود", branch=self.branch)
        r = self.c.patch(f"/api/sale-sessions/{sid}/",
                         {"notes": "ثبات", "employee": emp2.id}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["notes"], "ثبات")
        self.assertEqual(r.data["employee_name"], "محمود")

    def test_update_session_employee_from_other_branch_rejected(self):
        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        sid = r.data["id"]
        branch2 = Branch.objects.create(name="فرع ثاني", code="B2")
        emp2 = Employee.objects.create(name="محمود", branch=branch2)
        r = self.c.patch(f"/api/sale-sessions/{sid}/", {"employee": emp2.id}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_update_close_session_branch_rejected(self):
        sid = self._closed_session()
        branch2 = Branch.objects.create(name="فرع ثاني", code="B2")
        r = self.c.patch(f"/api/sale-sessions/{sid}/", {"branch": branch2.id}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_delete_closed_session_restores_daily_sale_and_stock(self):
        sid = self._closed_session()
        sale_date = effective_sale_date()
        r = self.c.delete(f"/api/sale-sessions/{sid}/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(SaleSession.objects.filter(pk=sid).exists())
        self.assertFalse(DailySale.objects.filter(branch=self.branch, date=sale_date).exists())
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("500"))
        self.assertEqual(
            StockMovement.objects.filter(movement_type=StockMovement.Type.SALE).count(), 0
        )

    def test_delete_open_session_no_stock_touch(self):
        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        sid = r.data["id"]
        self.c.post(f"/api/sale-sessions/{sid}/items/",
                    {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 20,
                     "payment_method": "cash"}, format="json")
        r = self.c.delete(f"/api/sale-sessions/{sid}/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(SaleSession.objects.filter(pk=sid).exists())
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("500"))
        self.assertEqual(
            StockMovement.objects.filter(movement_type=StockMovement.Type.SALE).count(), 0
        )

    def test_reopen_closed_session_restores_stock(self):
        sid = self._closed_session()
        sale_date = effective_sale_date()
        r = self.c.post(f"/api/sale-sessions/{sid}/reopen/")
        self.assertEqual(r.status_code, 200, r.data)
        session = SaleSession.objects.get(pk=sid)
        self.assertEqual(session.status, SaleSession.Status.OPEN)
        self.assertIsNone(session.closed_at)
        self.assertFalse(DailySale.objects.filter(branch=self.branch, date=sale_date).exists())
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("500"))
        self.assertEqual(
            StockMovement.objects.filter(movement_type=StockMovement.Type.SALE).count(), 0
        )

    def test_reopen_then_add_item_and_close(self):
        sid = self._closed_session()
        self.assertEqual(self.c.post(f"/api/sale-sessions/{sid}/reopen/").status_code, 200)
        r = self.c.post(f"/api/sale-sessions/{sid}/items/",
                        {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 25,
                         "payment_method": "cash"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        r2 = self.c.post(f"/api/sale-sessions/{sid}/close/")
        self.assertEqual(r2.status_code, 200, r2.data)
        sale_date = effective_sale_date()
        sale = DailySale.objects.get(branch=self.branch, date=sale_date)
        # القديمة 20 + 10 + الجديدة 25 = 55 * 5 = 275
        self.assertEqual(Decimal(str(sale.total_sales)), Decimal("275"))
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("445"))

    def test_reopen_open_session_rejected(self):
        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        sid = r.data["id"]
        r = self.c.post(f"/api/sale-sessions/{sid}/reopen/")
        self.assertEqual(r.status_code, 400)


class SessionItemExtrasTest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="B", code="B")
        self.wh = Warehouse.objects.create(name="فرع: B", code="BR-B", branch=self.branch)
        self.emp = Employee.objects.create(name="علي", branch=self.branch)
        self.fabric = Fabric.objects.create(name="قطن", code="C1", sale_price_yard=5, yards_per_roll=50)
        self.roll = FabricRoll.objects.create(
            warehouse=self.wh, fabric=self.fabric, yards=500, remaining_yards=500
        )

    def _open(self, emp=None):
        r = self.c.post("/api/sale-sessions/", {"employee": (emp or self.emp).id}, format="json")
        return r.data["id"]

    def test_discount_applied_on_create(self):
        sid = self._open()
        r = self.c.post(f"/api/sale-sessions/{sid}/items/",
                        {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
                         "unit_price": 5, "discount_amount": 7, "payment_method": "cash"},
                        format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(str(r.data["total"])), Decimal("43"))
        self.assertEqual(Decimal(str(r.data["discount_amount"])), Decimal("7"))

    def test_discount_less_than_total_rejected(self):
        sid = self._open()
        r = self.c.post(f"/api/sale-sessions/{sid}/items/",
                        {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 3,
                         "unit_price": 5, "discount_amount": 20}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_close_reflects_discount(self):
        sid = self._open()
        self.c.post(f"/api/sale-sessions/{sid}/items/",
                    {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
                     "unit_price": 5, "discount_amount": 5, "payment_method": "cash"}, format="json")
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        sale_date = effective_sale_date()
        sale = DailySale.objects.get(branch=self.branch, date=sale_date)
        self.assertEqual(Decimal(str(sale.total_sales)), Decimal("45"))
        self.assertEqual(Decimal(str(sale.cash_amount)), Decimal("45"))
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("490"))

    def test_edit_adds_discount(self):
        sid = self._open()
        item = self.c.post(f"/api/sale-sessions/{sid}/items/",
                           {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
                            "unit_price": 5, "payment_method": "cash"}, format="json").data
        r = self.c.patch(f"/api/sale-sessions/{sid}/items/{item['id']}/",
                         {"discount_amount": 8}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(str(r.data["total"])), Decimal("42"))

    def test_discount_beyond_max_percent_rejected(self):
        from appsettings.models import AppSettings

        settings = AppSettings.load()
        settings.discount_max_percent = Decimal("50")
        settings.save(update_fields=["discount_max_percent"])
        sid = self._open()
        base = {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
                "unit_price": 5, "payment_method": "cash"}
        # الحد 50% من 50 = 25 — خصم 26 مرفوض و 25 مقبول
        bad = self.c.post(f"/api/sale-sessions/{sid}/items/",
                          {**base, "discount_amount": 26}, format="json")
        self.assertEqual(bad.status_code, 400)
        ok = self.c.post(f"/api/sale-sessions/{sid}/items/",
                         {**base, "discount_amount": 25}, format="json")
        self.assertEqual(ok.status_code, 201, ok.data)
        self.assertEqual(Decimal(str(ok.data["total"])), Decimal("25"))

    def test_move_item_between_sessions(self):
        sid1 = self._open()
        sid2 = self._open(Employee.objects.create(name="محمود", branch=self.branch))
        item = self.c.post(f"/api/sale-sessions/{sid1}/items/",
                           {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 6,
                            "unit_price": 6, "payment_method": "card", "card_type": "debit"}, format="json").data
        r = self.c.post(f"/api/sale-sessions/{sid1}/move-item/{item['id']}/",
                        {"target_session": sid2}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(str(r.data["total"])), Decimal("36"))
        self.assertEqual(Decimal(str(r.data["discount_amount"])), Decimal("0"))
        self.assertEqual(SaleSessionItem.objects.get(pk=item["id"]).session_id, sid2)
        self.assertEqual(SaleSessionItem.objects.filter(session_id=sid1).count(), 0)
        self.assertEqual(SaleSessionItem.objects.filter(session_id=sid2).count(), 1)

    def test_move_item_target_closed_rejected(self):
        sid1 = self._open()
        item = self.c.post(f"/api/sale-sessions/{sid1}/items/",
                           {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 6,
                            "unit_price": 6}, format="json").data
        emp2 = Employee.objects.create(name="محمود", branch=self.branch)
        sid2 = self._open(emp2)
        self.c.post(f"/api/sale-sessions/{sid2}/close/")
        r = self.c.post(f"/api/sale-sessions/{sid1}/move-item/{item['id']}/",
                        {"target_session": sid2}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_move_item_insufficient_stock_at_target_rejected(self):
        branch2 = Branch.objects.create(name="فرع ثاني", code="B2")
        Warehouse.objects.create(name="فرع: B2", code="BR-B2", branch=branch2)
        emp2 = Employee.objects.create(name="سعيد", branch=branch2)
        sid1 = self._open()
        sid2 = self._open(emp2)
        item = self.c.post(f"/api/sale-sessions/{sid1}/items/",
                           {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 100,
                            "unit_price": 6}, format="json").data
        r = self.c.post(f"/api/sale-sessions/{sid1}/move-item/{item['id']}/",
                        {"target_session": sid2}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_clear_session_items(self):
        sid = self._open()
        self.c.post(f"/api/sale-sessions/{sid}/items/",
                    {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 2}, format="json")
        self.c.post(f"/api/sale-sessions/{sid}/items/",
                    {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 3}, format="json")
        r = self.c.post(f"/api/sale-sessions/{sid}/clear/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SaleSessionItem.objects.filter(session_id=sid).count(), 0)

    def test_reopen_preserves_discount(self):
        sid = self._open()
        self.c.post(f"/api/sale-sessions/{sid}/items/",
                    {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
                     "unit_price": 5, "discount_amount": 5, "payment_method": "cash"}, format="json")
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        self.assertEqual(self.c.post(f"/api/sale-sessions/{sid}/reopen/").status_code, 200)
        item = SaleSessionItem.objects.get(session_id=sid)
        self.assertEqual(Decimal(str(item.total)), Decimal("45"))
        self.assertEqual(Decimal(str(item.discount_amount)), Decimal("5"))


class CommissionAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="B", code="B")
        self.wh = Warehouse.objects.create(name="فرع: B", code="BR-B", branch=self.branch)
        self.emp = Employee.objects.create(
            name="محمد", branch=self.branch,
            commission_active=True, commission_percent=5,
        )
        self.fabric = Fabric.objects.create(name="قطن", code="CM1", sale_price_yard=10, yards_per_roll=50)
        self.roll = FabricRoll.objects.create(
            warehouse=self.wh, fabric=self.fabric, yards=500, remaining_yards=500
        )

    def _open(self):
        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data["id"]

    def _add(self, sid, qty=20):
        return self.c.post(f"/api/sale-sessions/{sid}/items/",
                           {"fabric": self.fabric.id, "sale_type": "yard", "quantity": qty,
                            "payment_method": "cash"}, format="json")

    def test_employee_serializer_includes_commission(self):
        r = self.c.get(f"/api/employees/{self.emp.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Decimal(str(r.data["commission_percent"])), Decimal("5"))
        self.assertTrue(r.data["commission_active"])

    def test_close_session_computes_commission(self):
        sid = self._open()
        self._add(sid, qty=20)  # 20 × 10 = 200 ثم عمولة 5% = 10
        r = self.c.post(f"/api/sale-sessions/{sid}/close/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(str(r.data["commission_amount"])), Decimal("10.00"))

    def test_no_commission_when_inactive(self):
        emp2 = Employee.objects.create(name="سالم", branch=self.branch, commission_active=False)
        r = self.c.post("/api/sale-sessions/", {"employee": emp2.id}, format="json")
        sid = r.data["id"]
        self._add(sid, qty=20)
        r = self.c.post(f"/api/sale-sessions/{sid}/close/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(str(r.data["commission_amount"])), Decimal("0"))

    def test_commission_recomputed_on_closed_edit(self):
        sid = self._open()
        self._add(sid, qty=20)
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        item = SaleSessionItem.objects.get(session_id=sid)
        r = self.c.put(f"/api/sale-sessions/{sid}/items/{item.id}/",
                       {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 40,
                        "unit_price": 10, "payment_method": "cash"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        session = self.c.get(f"/api/sale-sessions/{sid}/").data
        self.assertEqual(Decimal(str(session["commission_amount"])), Decimal("20.00"))

    def test_reopen_resets_commission(self):
        sid = self._open()
        self._add(sid, qty=20)
        r = self.c.post(f"/api/sale-sessions/{sid}/close/")
        self.assertEqual(Decimal(str(r.data["commission_amount"])), Decimal("10.00"))
        self.c.post(f"/api/sale-sessions/{sid}/reopen/")
        session = self.c.get(f"/api/sale-sessions/{sid}/").data
        self.assertEqual(Decimal(str(session["commission_amount"])), Decimal("0"))


class SessionOpeningPermissionTest(TestCase):
    """فتح الوردية مقصور على الموظف نفسه — المدير فقط يفتح لأي موظف."""

    User = get_user_model()

    def setUp(self):
        self.branch_a = Branch.objects.create(name="فرع أ", code="A")
        self.branch_b = Branch.objects.create(name="فرع ب", code="B")
        self.other_branch = Branch.objects.create(name="فرع آخر", code="C")
        self.emp_a = self._employee("مندوب أ", Employee.Role.SALES, self.branch_a)
        self.emp_b = self._employee("مندوب ب", Employee.Role.SALES, self.branch_a)
        self.branchless = self._employee("بلا فرع", Employee.Role.SALES, None)
        self.admin_emp = self._employee("مشرف النظام", Employee.Role.ADMIN, self.branch_a)

    def _employee(self, name, role, branch):
        user = self.User.objects.create_user(username=f"t_{uuid4().hex[:8]}", password="pass1234")
        emp = Employee(name=name, branch=branch, user=user)
        emp.apply_role_preset(role)
        emp.save()
        return emp

    def _login(self, employee):
        client = APIClient()
        client.force_authenticate(user=employee.user)
        return client

    def test_sales_opens_own_session(self):
        c = self._login(self.emp_a)
        r = c.post("/api/sale-sessions/", {"employee": self.emp_a.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["branch"], self.branch_a.id)

    def test_sales_cannot_open_session_for_other(self):
        c = self._login(self.emp_a)
        r = c.post("/api/sale-sessions/", {"employee": self.emp_b.id}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("باسمك", str(r.data))

    def test_manager_opens_session_for_any_employee(self):
        c = self._login(self.admin_emp)
        r = c.post("/api/sale-sessions/", {"employee": self.emp_b.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["branch"], self.branch_a.id)

    def test_manager_opening_branchless_employee_friendly_error(self):
        c = self._login(self.admin_emp)
        r = c.post("/api/sale-sessions/", {"employee": self.branchless.id}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("غير مرتبط بفرع", str(r.data))

    def test_sales_manual_only_for_self(self):
        c = self._login(self.emp_a)
        ok = c.post("/api/sale-sessions/manual/", {"employee": self.emp_a.id, "date": "2026-09-21", "cash": 100}, format="json")
        self.assertEqual(ok.status_code, 201, ok.data)
        r = c.post("/api/sale-sessions/manual/", {"employee": self.emp_b.id, "date": "2026-09-21", "cash": 50}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("باسمك", str(r.data))

    def test_sales_cannot_reassign_or_move_own_session(self):
        c = self._login(self.emp_a)
        sid = c.post("/api/sale-sessions/", {"employee": self.emp_a.id}, format="json").data["id"]
        r = c.patch(f"/api/sale-sessions/{sid}/", {"employee": self.emp_b.id}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("موظف الوردية", str(r.data))
        r = c.patch(f"/api/sale-sessions/{sid}/", {"branch": self.other_branch.id}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("فرع آخر", str(r.data))
        r = c.patch(f"/api/sale-sessions/{sid}/", {"notes": "ملاحظة"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)

    def test_sales_branches_list_scoped_to_own_branch(self):
        c = self._login(self.emp_a)
        r = c.get("/api/branches/")
        self.assertEqual(r.status_code, 200)
        ids = [b["id"] for b in r.data["results"]]
        self.assertEqual(ids, [self.branch_a.id])

    def test_sales_employees_list_forbidden(self):
        c = self._login(self.emp_a)
        r = c.get("/api/employees/")
        self.assertEqual(r.status_code, 403)


class AvatarAndProfileAPITest(TestCase):
    """الأفاتارات الجاهزة + بطاقة معلومات الموظف."""

    def setUp(self):
        self.c = APIClient()
        self.user, self.emp = authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="فرع أ", code="AVBR")

    def test_avatar_roundtrip_via_employees_endpoint(self):
        r = self.c.post("/api/employees/", {
            "name": "علي", "branch": self.branch.id, "avatar": "🦁",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["avatar"], "🦁")

    def test_user_can_change_own_avatar(self):
        r = self.c.patch("/api/account/avatar/", {"avatar": "🐼"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["employee"]["avatar"], "🐼")
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.avatar, "🐼")

    def test_user_cannot_set_arbitrary_avatar(self):
        r = self.c.patch("/api/account/avatar/", {"avatar": "😀"}, format="json")
        self.assertEqual(r.status_code, 400, r.data)

    def test_avatar_in_me_payload(self):
        self.emp.avatar = "🦄"
        self.emp.save(update_fields=["avatar"])
        r = self.c.get("/api/auth/me/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["employee"]["avatar"], "🦄")

    def test_profile_card_returns_safe_fields(self):
        other = Employee.objects.create(branch=self.branch, name="زيد", phone="055")
        other.department = "قسم المبيعات"
        other.position = "بائع"
        other.email = "z@example.com"
        other.avatar = "🐯"
        other.save()
        r = self.c.get(f"/api/account/profile/?employee_id={other.id}")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["name"], "زيد")
        self.assertEqual(r.data["position"], "بائع")
        self.assertEqual(r.data["avatar"], "🐯")
        self.assertEqual(r.data["branch_name"], "فرع أ")

    def test_profile_requires_id_and_404(self):
        self.assertEqual(self.c.get("/api/account/profile/").status_code, 400)
        self.assertEqual(self.c.get("/api/account/profile/?employee_id=999999").status_code, 404)

    def test_profile_also_in_messaging_contacts(self):
        other = Employee.objects.create(branch=self.branch, name="هند", avatar="🐸")
        r = self.c.get("/api/messaging/contacts/")
        emp = next(e for e in r.data["employees"] if e["id"] == other.id)
        self.assertEqual(emp["avatar"], "🐸")


class ReturnAndRollOverrideTest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="B", code="B")
        self.wh = Warehouse.objects.create(name="فرع: B", code="BR-B", branch=self.branch)
        self.emp = Employee.objects.create(name="علي", branch=self.branch)
        self.fabric = Fabric.objects.create(name="قطن", code="C1", sale_price_yard=5, yards_per_roll=50)
        self.roll = FabricRoll.objects.create(
            warehouse=self.wh, fabric=self.fabric, yards=500, remaining_yards=500
        )

    def _open_session(self):
        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        return r.data["id"]

    def _add_item(self, sid, quantity=10, payment_method="cash", phone="055000"):
        data = {"fabric": self.fabric.id, "sale_type": "yard", "quantity": quantity,
                "payment_method": payment_method, "customer_phone": phone}
        if payment_method == "card":
            data["card_type"] = "credit"
        return self.c.post(f"/api/sale-sessions/{sid}/items/", data, format="json")

    def test_roll_override_blocks_branch_when_global_allows(self):
        self.fabric.roll_sale_overrides = {str(self.branch.id): False}
        self.fabric.save(update_fields=["roll_sale_overrides"])
        sid = self._open_session()
        r = self.c.post(
            f"/api/sale-sessions/{sid}/items/",
            {"fabric": self.fabric.id, "sale_type": "roll", "quantity": 1,
             "payment_method": "cash"},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("البيع بالطاقة", str(r.data))

    def test_roll_override_allows_branch_when_global_blocked(self):
        self.fabric.allow_roll_sale = False
        self.fabric.roll_sale_overrides = {str(self.branch.id): True}
        self.fabric.save(update_fields=["allow_roll_sale", "roll_sale_overrides"])
        sid = self._open_session()
        r = self.c.post(
            f"/api/sale-sessions/{sid}/items/",
            {"fabric": self.fabric.id, "sale_type": "roll", "quantity": 1,
             "payment_method": "cash"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)

    def test_roll_blocked_follows_global_when_not_in_overrides(self):
        # override مكتوب لفرع آخر؛ فرع الوردية غير مذكور فيتبع العام المسموح
        other = Branch.objects.create(name="فرع ثاني", code="B2")
        self.fabric.roll_sale_overrides = {str(other.id): False}
        self.fabric.save(update_fields=["roll_sale_overrides"])
        sid = self._open_session()
        r = self.c.post(
            f"/api/sale-sessions/{sid}/items/",
            {"fabric": self.fabric.id, "sale_type": "roll", "quantity": 1,
             "payment_method": "cash"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)

    def test_customer_sales_lists_open_and_closed_items(self):
        sid1 = self._open_session()
        self._add_item(sid1, quantity=10, phone="055111")
        self.c.post(f"/api/sale-sessions/{sid1}/close/")
        emp2 = Employee.objects.create(name="محمود", branch=self.branch)
        sid2 = self.c.post("/api/sale-sessions/", {"employee": emp2.id}, format="json").data["id"]
        self._add_item(sid2, quantity=5, phone="055111")
        self._add_item(sid2, quantity=3, phone="055999")
        r = self.c.get("/api/sale-sessions/customer-sales/", {"phone": "055111"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["totals"]["count"], 2)
        closed_row = [i for i in r.data["items"] if i["session_closed"]]
        open_row = [i for i in r.data["items"] if not i["session_closed"]]
        self.assertEqual(len(closed_row), 1)
        self.assertEqual(len(open_row), 1)
        self.assertEqual(r.data["totals"]["total"], 75.0)

    def test_customer_sales_requires_phone(self):
        r = self.c.get("/api/sale-sessions/customer-sales/")
        self.assertEqual(r.status_code, 400)

    def test_return_closed_item_restores_stock_and_daily_sale(self):
        sid = self._open_session()
        self._add_item(sid, quantity=20, payment_method="cash", phone="055222")
        self._add_item(sid, quantity=10, payment_method="card", phone="055222")
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        sale_date = effective_sale_date()
        sale = DailySale.objects.get(branch=self.branch, date=sale_date)
        self.assertEqual(Decimal(str(sale.total_sales)), Decimal("150"))
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("470"))

        items = list(SaleSessionItem.objects.filter(session_id=sid).order_by("id"))
        r = self.c.post("/api/sale-sessions/return-items/",
                        {"item_ids": [items[0].id], "reason": "مقاس خاطئ"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)

        sale.refresh_from_db()
        # بقيت 10*5 = 50 فقط
        self.assertEqual(Decimal(str(sale.total_sales)), Decimal("50"))
        self.roll.refresh_from_db()
        # عادت 20 ياردة → 500 - 10 = 490
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("490"))

        items[0].refresh_from_db()
        self.assertTrue(items[0].is_returned)
        self.assertIsNotNone(items[0].returned_at)
        self.assertEqual(items[0].return_reason, "مقاس خاطئ")
        items[1].refresh_from_db()
        self.assertFalse(items[1].is_returned)

    def test_return_all_closed_items_deletes_daily_sale(self):
        sid = self._open_session()
        self._add_item(sid, quantity=10, phone="055333")
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        item = SaleSessionItem.objects.get(session_id=sid)
        r = self.c.post("/api/sale-sessions/return-items/",
                        {"item_ids": [item.id]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        sale_date = effective_sale_date()
        self.assertFalse(DailySale.objects.filter(branch=self.branch, date=sale_date).exists())
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("500"))
        item.refresh_from_db()
        self.assertTrue(item.is_returned)

    def test_return_open_item_only_marks_no_stock_touch(self):
        sid = self._open_session()
        self._add_item(sid, quantity=20, phone="055444")
        item = SaleSessionItem.objects.get(session_id=sid)
        r = self.c.post("/api/sale-sessions/return-items/",
                        {"item_ids": [item.id]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        item.refresh_from_db()
        self.assertTrue(item.is_returned)
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("500"))

    def test_return_then_close_excludes_returned_from_daily(self):
        sid = self._open_session()
        self._add_item(sid, quantity=20, payment_method="cash", phone="055555")
        self._add_item(sid, quantity=10, payment_method="card", phone="055555")
        items = list(SaleSessionItem.objects.filter(session_id=sid).order_by("id"))
        self.c.post("/api/sale-sessions/return-items/",
                    {"item_ids": [items[0].id]}, format="json")
        r = self.c.post(f"/api/sale-sessions/{sid}/close/")
        self.assertEqual(r.status_code, 200, r.data)
        sale_date = effective_sale_date()
        sale = DailySale.objects.get(branch=self.branch, date=sale_date)
        self.assertEqual(Decimal(str(sale.total_sales)), Decimal("50"))
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("490"))

    def test_reopen_after_return_does_not_double_reverse(self):
        sid = self._open_session()
        self._add_item(sid, quantity=20, payment_method="cash", phone="055666")
        self._add_item(sid, quantity=10, payment_method="card", phone="055666")
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        items = list(SaleSessionItem.objects.filter(session_id=sid).order_by("id"))
        r = self.c.post("/api/sale-sessions/return-items/",
                        {"item_ids": [items[0].id]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.c.post(f"/api/sale-sessions/{sid}/reopen/")
        self.roll.refresh_from_db()
        # لا يجب أن يُتراجع عن البند المسترجع مرة أخرى؛ رصيد بعد الاسترجاع 490 عاد كاملاً عند إعادة الفتح
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("500"))

    def test_returned_item_cannot_be_edited_or_deleted(self):
        sid = self._open_session()
        self._add_item(sid, quantity=10, phone="055777")
        item = SaleSessionItem.objects.get(session_id=sid)
        self.c.post("/api/sale-sessions/return-items/", {"item_ids": [item.id]}, format="json")
        r = self.c.delete(f"/api/sale-sessions/{sid}/items/{item.id}/")
        self.assertEqual(r.status_code, 400, r.data)
        r = self.c.put(f"/api/sale-sessions/{sid}/items/{item.id}/",
                       {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 3},
                       format="json")
        self.assertEqual(r.status_code, 400, r.data)

    def test_return_items_requires_single_session_and_existing(self):
        sid1 = self._open_session()
        self._add_item(sid1, quantity=10, phone="055888")
        emp2 = Employee.objects.create(name="محمود", branch=self.branch)
        r = self.c.post("/api/sale-sessions/", {"employee": emp2.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        sid2 = r.data["id"]
        self._add_item(sid2, quantity=10, phone="055888")
        i1 = SaleSessionItem.objects.filter(session_id=sid1).first().id
        i2 = SaleSessionItem.objects.filter(session_id=sid2).first().id
        r = self.c.post("/api/sale-sessions/return-items/", {"item_ids": [i1, i2]}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        r = self.c.post("/api/sale-sessions/return-items/", {"item_ids": [i1, 999999]}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        r = self.c.post("/api/sale-sessions/return-items/", {"item_ids": [999999]}, format="json")
        self.assertEqual(r.status_code, 400, r.data)


class CardMachineFeeTest(TestCase):
    """عمولة الماكينة: نوع البطاقة (إئتماني/خصم مباشر) ونسبة كل نوع من الإعدادات."""

    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="B", code="B")
        self.wh = Warehouse.objects.create(name="فرع: B", code="BR-B", branch=self.branch)
        self.emp = Employee.objects.create(name="علي", branch=self.branch)
        self.fabric = Fabric.objects.create(name="قطن", code="C1", sale_price_yard=5, yards_per_roll=50)
        self.roll = FabricRoll.objects.create(
            warehouse=self.wh, fabric=self.fabric, yards=500, remaining_yards=500
        )
        from appsettings.models import AppSettings

        s = AppSettings.load()
        s.card_credit_fee_percent = Decimal("2")
        s.card_debit_fee_percent = Decimal("5")
        s.save(update_fields=["card_credit_fee_percent", "card_debit_fee_percent"])

    def _session(self):
        return self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json").data["id"]

    def test_card_requires_card_type(self):
        sid = self._session()
        r = self.c.post(f"/api/sale-sessions/{sid}/items/",
                        {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
                         "unit_price": 10, "payment_method": "card"}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("card_type", r.data)

    def test_credit_fee_computed_and_net_recorded_on_close(self):
        sid = self._session()
        r = self.c.post(f"/api/sale-sessions/{sid}/items/",
                        {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
                         "unit_price": 10, "payment_method": "card", "card_type": "credit"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        # إجمالي 100، عمولة 2% = 2 → صافي 98
        self.assertEqual(Decimal(str(r.data["card_fee_amount"])), Decimal("2.00"))
        self.assertEqual(Decimal(str(r.data["net_total"])), Decimal("98.00"))
        self.assertEqual(r.data["card_type"], "credit")
        self.assertEqual(r.data["card_type_label"], "إئتماني / Credit")
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        sale = DailySale.objects.get(branch=self.branch, date=effective_sale_date())
        self.assertEqual(Decimal(str(sale.card_amount)), Decimal("98.00"))
        self.assertEqual(Decimal(str(sale.total_sales)), Decimal("98.00"))

    def test_debit_uses_its_own_percent(self):
        sid = self._session()
        r = self.c.post(f"/api/sale-sessions/{sid}/items/",
                        {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
                         "unit_price": 10, "payment_method": "card", "card_type": "debit"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        # عمولة 5% من 100 = 5 → صافي 95
        self.assertEqual(Decimal(str(r.data["card_fee_amount"])), Decimal("5.00"))
        self.assertEqual(Decimal(str(r.data["net_total"])), Decimal("95.00"))

    def test_cash_and_transfer_have_no_fee(self):
        sid = self._session()
        r = self.c.post(f"/api/sale-sessions/{sid}/items/",
                        {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
                         "unit_price": 10, "payment_method": "cash"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["card_type"], "")
        self.assertEqual(Decimal(str(r.data["card_fee_amount"])), Decimal("0.00"))
        self.assertEqual(Decimal(str(r.data["net_total"])), Decimal("100.00"))

    def test_edit_card_type_recomputes_fee(self):
        sid = self._session()
        item = self.c.post(f"/api/sale-sessions/{sid}/items/",
                           {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
                            "unit_price": 10, "payment_method": "card", "card_type": "credit"}, format="json").data
        r = self.c.patch(f"/api/sale-sessions/{sid}/items/{item['id']}/",
                         {"card_type": "debit"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(str(r.data["card_fee_amount"])), Decimal("5.00"))
        self.assertEqual(Decimal(str(r.data["net_total"])), Decimal("95.00"))

    def test_edit_card_to_cash_resets_fee(self):
        sid = self._session()
        item = self.c.post(f"/api/sale-sessions/{sid}/items/",
                           {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
                            "unit_price": 10, "payment_method": "card", "card_type": "credit"}, format="json").data
        r = self.c.patch(f"/api/sale-sessions/{sid}/items/{item['id']}/",
                         {"payment_method": "cash"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["card_type"], "")
        self.assertEqual(Decimal(str(r.data["card_fee_amount"])), Decimal("0.00"))
        self.assertEqual(Decimal(str(r.data["net_total"])), Decimal("100.00"))

    def test_zero_fee_percent_keeps_gross(self):
        from appsettings.models import AppSettings

        s = AppSettings.load()
        s.card_credit_fee_percent = Decimal("0")
        s.save(update_fields=["card_credit_fee_percent"])
        sid = self._session()
        r = self.c.post(f"/api/sale-sessions/{sid}/items/",
                        {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
                         "unit_price": 10, "payment_method": "card", "card_type": "credit"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(str(r.data["card_fee_amount"])), Decimal("0.00"))
        self.assertEqual(Decimal(str(r.data["net_total"])), Decimal("100.00"))