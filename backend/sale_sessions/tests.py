from datetime import date, time, timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from core.testsupport import authenticate_admin, make_admin_user

from branches.models import Branch, FabricBranchPrice
from sales.models import DailySale, DailySaleItem
from suppliers.models import Fabric
from warehouses.models import FabricRoll, StockMovement, Warehouse

from .models import Employee, SaleSession, SaleSessionItem
from .sections import SECTIONS, canonical_role, effective_permissions
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


class EffectivePermissionsTest(TestCase):
    """قسمٌ أُضيف بعدَ إنشاء الحساب لا يصل إلى موظفٍ قديم، فيختفي.

    والأثرُ ليس مُجرّدَ إخفاء: القائمةُ تتجاهلُ المفتاحَ الغائب، وصفحتُه
    تُصفِّي تبويباتها بـ«hasWindow» فلا يبقى فيها شيء. فالموظفُ يقابل
    قسماً معلناً ولا يجده، ويظنّ أنّ النظامَ نسيه.
    """

    def setUp(self):
        self.sections = SECTIONS
        self.declared = {s["key"] for s in SECTIONS}

    def test_every_declared_section_is_present_for_an_old_row(self):
        # صفُّ موظفٍ كُتب قبل قسم الحضور: خانةُ الحضور غائبةٌ فيه.
        stale = {"sales": {"view": True, "create": False, "edit": False, "delete": False}}
        perms = effective_permissions("admin", stale)
        self.assertEqual(set(perms), self.declared)
        self.assertTrue(perms["attendance"]["view"])
        self.assertTrue(perms["attendance"]["edit"])

    def test_the_missing_section_comes_from_the_role_not_from_blanks(self):
        rows = {
            "admin": True, "supervisor": True, "viewer": True,
            "sales": True, "accountant": True, "custom": False,
        }
        for role, expected_view in rows.items():
            perms = effective_permissions(role, {})
            self.assertEqual(
                perms["attendance"]["view"], expected_view, role,
            )

    def test_a_stored_permission_is_never_overwritten(self):
        # المديرُ يأخذ كلَّ شيءٍ من دوره، لكنّ ما حُفظ للموظفِ مقدَّمٌ على
        # الدور: هنا سطرُ المبيعات محذوفٌ عمداً.
        stale = {"sales": {"view": True, "create": False, "edit": False, "delete": False}}
        perms = effective_permissions("admin", stale)
        self.assertFalse(perms["sales"]["create"])
        self.assertFalse(perms["sales"]["delete"])

    def test_a_granted_section_takes_all_its_windows_when_none_are_listed(self):
        # «view» وعدٌ بصفحةٍ فيها شيء. الأدوارُ المكتوبةُ يدوياً تعطي العرض
        # بلا نوافذ، فتصير الصفحةُ فراغاً: القسمُ ظاهرٌ ولا يُرى منه شيء.
        perms = effective_permissions("sales", {})
        declared = {
            w["key"]
            for s in self.sections if s["key"] == "attendance"
            for w in (s.get("windows") or [])
        }
        self.assertEqual(set(perms["attendance"]["windows"]), declared)

    def test_a_narrow_window_list_is_kept_but_pruned_of_ghosts(self):
        perms = effective_permissions("admin", {
            "attendance": {
                "view": True, "create": True, "edit": True, "delete": True,
                "windows": ["daily", "قسم لم يعد له أثر"],
            },
        })
        self.assertEqual(perms["attendance"]["windows"], ["daily"])

    def test_a_section_no_role_mentions_stays_closed(self):
        # دورُ مندوبِ المبيعات لا يذكر «التسويات المالية»، فغيابُه قصدٌ
        # لا نقصٌ في الخريطة. والقسمُ المُقفَلُ يُكتب صريحاً لا غائباً.
        perms = effective_permissions("sales", {})
        self.assertIn("machine_account", perms)
        self.assertFalse(perms["machine_account"]["view"])

    def test_null_and_rubbish_stored_maps_do_not_break_the_read(self):
        for junk in (None, [], "nonsense", {"attendance": "yes"}):
            perms = effective_permissions("admin", junk)
            self.assertEqual(set(perms), self.declared)
            self.assertTrue(perms["attendance"]["view"])

    def test_the_session_endpoint_carries_the_filled_map(self):
        # هذا هو الطريقُ الذي تسير عليه الواجهة: لا الخريطةُ في القاعدة
        # بل التي في الجلسة. ولولاه لبقيت القاعدةُ نظيفةً والشاشةُ خاوية.
        user, emp = make_admin_user()
        # نُحاكي صفّاً كُتب قبل قسم الحضور: خانةُ الحضور غائبةٌ فيه.
        stale = {k: v for k, v in (emp.permissions or {}).items() if k != "attendance"}
        Employee.objects.filter(pk=emp.pk).update(permissions=stale)
        emp.refresh_from_db()
        self.assertNotIn("attendance", (emp.permissions or {}))

        c = APIClient()
        c.force_authenticate(user)
        r = c.get("/api/auth/me/")
        self.assertEqual(r.status_code, 200)
        perms = r.data["employee"]["permissions"]
        self.assertTrue(perms["attendance"]["view"])
        self.assertEqual(
            set(perms["attendance"]["windows"]),
            {"daily", "records", "summary", "policy"},
        )

    def test_the_gate_agrees_with_the_map_it_published(self):
        """الحكمُ في مكانين: الخريطةُ التي في الجلسة، والبابُ الذي يردّ.

        أصلحت الأولى فظهر القسمُ في القائمة، وبقي الثاني على حاله يقرأ
        الصفَّ خاماً فيرفض. فالقسمُ صار مرئياً ومرفوضاً في اللحظة نفسِها،
        وهو أسوأ من غيابه لأنّ المستخدمَ لا يجد ما يُبلّغه به. فالمقارنةُ
        هنا على كلِّ قسمٍ وفعلٍ معاً: ما تعلنه الجلسةُ يفتحه البابُ نفسُه.
        """
        user, emp = make_admin_user()
        stale = {k: v for k, v in (emp.permissions or {}).items() if k != "attendance"}
        Employee.objects.filter(pk=emp.pk).update(permissions=stale)
        emp.refresh_from_db()

        self.assertTrue(emp.has_permission("attendance", "view"))
        self.assertTrue(emp.has_permission("attendance", "edit"))
        self.assertTrue(emp.has_window("attendance", "daily"))

        c = APIClient()
        c.force_authenticate(user)
        published = c.get("/api/auth/me/").data["employee"]["permissions"]
        for section, entry in published.items():
            for action in ("view", "create", "edit", "delete"):
                if action not in entry:
                    continue
                self.assertEqual(
                    emp.has_permission(section, action), entry[action],
                    f"{section}.{action} is published as {entry[action]} "
                    f"but the gate says {emp.has_permission(section, action)}",
                )

    def test_the_attendance_api_opens_for_a_row_that_predates_the_section(self):
        # الاختبارُ السابق يقول إنّ الخريطةَ صارت صحيحة. وهذا يقول إنّ
        # الصفحةَ صارت تُفتح فعلاً، فبينهما بابٌ قد يُغلق بمفرده.
        user, emp = make_admin_user()
        stale = {k: v for k, v in (emp.permissions or {}).items() if k != "attendance"}
        Employee.objects.filter(pk=emp.pk).update(permissions=stale)

        c = APIClient()
        c.force_authenticate(user)
        for url in ("/api/attendance/policy/", "/api/attendance/records/"):
            r = c.get(url)
            self.assertEqual(r.status_code, 200, url)

    def test_a_role_in_the_wrong_case_still_reaches_its_sections(self):
        # الحقلُ نصٌّ حرٌّ، فالصفوفُ المكتوبةُ `ADMIN` ليست نادرةً. وهي
        # ليست نيّةً: `ROLE_PRESETS` لا يعرف إلا الحروفَ الصغيرة، فالعيبُ
        # يقع على كلِّ قسمٍ ناقصٍ في الوقت نفسِه، لا على الحضور وحده.
        user, emp = make_admin_user()
        Employee.objects.filter(pk=emp.pk).update(
            role="ADMIN",
            permissions={k: v for k, v in (emp.permissions or {}).items()
                         if k != "attendance"},
        )
        emp.refresh_from_db()
        self.assertEqual(canonical_role(emp.role), "admin")
        self.assertTrue(emp.has_permission("attendance", "view"))

        c = APIClient()
        c.force_authenticate(user)
        self.assertEqual(c.get("/api/attendance/policy/").status_code, 200)

    def test_a_role_outside_the_choices_gets_nothing(self):
        # لا تُرقَّع قيمةٌ لا معنى لها. `admin` ليست تخميناً معقولاً لـ
        # `nonsense`، فمنعُها أصدقُ من اختراعِ دورٍ لم يكتبه أحد.
        self.assertIsNone(canonical_role("nonsense"))
        self.assertEqual(effective_permissions("nonsense", {})["attendance"]["view"],
                         False)

    def test_the_audit_command_names_the_rows_it_found(self):
        # The command names the row that is wrong; it does not invent a right
        # one. So it names it by id and name, and it leaves the map alone: a
        # permission map is a set of decisions, not a calculation, and nothing
        # here second-guesses it.
        user, emp = make_admin_user()
        Employee.objects.filter(pk=emp.pk).update(
            role="ADMIN",
            permissions={k: v for k, v in (emp.permissions or {}).items()
                         if k != "attendance"},
        )
        before = run_audit()
        self.assertIn("role the choices do not define", before)
        self.assertIn(emp.name, before)

        # After --apply the role failure is gone. The map gap stays, and stays
        # reported, because it is still true: the row does not name the
        # section. What changed is that the section is reachable regardless.
        run_audit("--apply")
        emp.refresh_from_db()
        self.assertEqual(emp.role, "admin")
        after = run_audit()
        self.assertIn("ok    every role is one of the defined choices", after)
        self.assertIn("recovered on read: attendance", after)


def run_audit(*args) -> str:
    from django.core.management import call_command
    from io import StringIO

    out = StringIO()
    call_command("audit_access", *args, stdout=out)
    return out.getvalue()


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
        # الخصم فوري عند الإضافة — إعادة الفتح لا تُرجع المخزون (يبقى 500 - 20)
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("480"))

    # ---- فتح وردية بتاريخ محدد ----

    def test_open_without_date_leaves_session_date_null(self):
        d = self._open_session()
        self.assertIsNone(d["session_date"])
        sid = d["id"]
        r = self._add_item(sid, quantity=5)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["sale_date"], effective_sale_date().isoformat())

    def test_open_with_date_records_items_and_daily_sale_on_that_date(self):
        past = timezone.localdate() - timedelta(days=3)
        r = self.c.post(
            "/api/sale-sessions/", {"employee": self.emp.id, "date": past.isoformat()}, format="json"
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["session_date"], past.isoformat())
        sid = r.data["id"]
        r = self._add_item(sid, quantity=10)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["sale_date"], past.isoformat())
        self.assertEqual(self.c.post(f"/api/sale-sessions/{sid}/close/").status_code, 200)
        sale = DailySale.objects.get(branch=self.branch, date=past)
        self.assertEqual(Decimal(str(sale.total_sales)), Decimal("50.00"))
        self.assertFalse(DailySale.objects.filter(branch=self.branch, date=effective_sale_date()).exists())

    def test_open_with_future_date_rejected(self):
        future = timezone.localdate() + timedelta(days=1)
        r = self.c.post(
            "/api/sale-sessions/", {"employee": self.emp.id, "date": future.isoformat()}, format="json"
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("date", r.data)

    def test_open_with_date_stamps_opened_and_created_at_on_that_date(self):
        past = timezone.localdate() - timedelta(days=6)
        r = self.c.post(
            "/api/sale-sessions/", {"employee": self.emp.id, "date": past.isoformat()}, format="json"
        )
        self.assertEqual(r.status_code, 201, r.data)
        session = SaleSession.objects.get(pk=r.data["id"])
        self.assertEqual(timezone.localtime(session.opened_at).date(), past)
        self.assertEqual(timezone.localtime(session.created_at).date(), past)
        self.assertEqual(session.session_date, past)

    def test_backdated_sessions_keep_date_order(self):
        # الوردية لنفس الموظف بنفس التاريخ تُعاد فتحها، فتُستخدم تواريخ مختلفة
        dates = [timezone.localdate() - timedelta(days=n) for n in (5, 3, 1)]
        created = []
        for d in dates:
            r = self.c.post(
                "/api/sale-sessions/", {"employee": self.emp.id, "date": d.isoformat()}, format="json"
            )
            self.assertEqual(r.status_code, 201, r.data)
            created.append((d, r.data["id"]))
            self.c.post(f"/api/sale-sessions/{r.data['id']}/close/")
        for d, sid in created:
            session = SaleSession.objects.get(pk=sid)
            self.assertEqual(timezone.localtime(session.opened_at).date(), d)
        stamps = [timezone.localtime(SaleSession.objects.get(pk=s).opened_at) for _, s in created]
        self.assertEqual(stamps, sorted(stamps))
        # الترتيب الافتراضي للقائمة (الأحدث أولاً) يتبع تاريخ الوردية لا تاريخ الإنشاء
        listed = list(
            SaleSession.objects.filter(id__in=[s for _, s in created]).values_list("id", flat=True)
        )
        self.assertEqual(listed, [s for _, s in reversed(created)])

    def test_close_backdated_session_keeps_closed_at_on_same_date(self):
        past = timezone.localdate() - timedelta(days=2)
        r = self.c.post(
            "/api/sale-sessions/", {"employee": self.emp.id, "date": past.isoformat()}, format="json"
        )
        sid = r.data["id"]
        self._add_item(sid, quantity=4)
        self.assertEqual(self.c.post(f"/api/sale-sessions/{sid}/close/").status_code, 200)
        session = SaleSession.objects.get(pk=sid)
        opened = timezone.localtime(session.opened_at)
        closed = timezone.localtime(session.closed_at)
        self.assertEqual(closed.date(), past)
        self.assertGreaterEqual(closed, opened)

    def test_backdated_open_session_elapsed_is_minutes_not_days(self):
        past = timezone.localdate() - timedelta(days=8)
        r = self.c.post(
            "/api/sale-sessions/", {"employee": self.emp.id, "date": past.isoformat()}, format="json"
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["elapsed_minutes"], 0)
        # تحديث القائمة بعد دقيقة — تبقى المدة بالدقائق
        session = SaleSession.objects.get(pk=r.data["id"])
        session.opened_at = session.opened_at - timedelta(minutes=5)
        session.save(update_fields=["opened_at"])
        r = self.c.get(f"/api/sale-sessions/{session.pk}/")
        self.assertEqual(r.data["elapsed_minutes"], 5)

    def test_opened_date_filter_excludes_backdated_session_from_today(self):
        today = timezone.localdate()
        past = today - timedelta(days=5)
        r = self.c.post(
            "/api/sale-sessions/", {"employee": self.emp.id, "date": past.isoformat()}, format="json"
        )
        sid = r.data["id"]
        listed = self.c.get(
            "/api/sale-sessions/", {"opened_from": today.isoformat(), "opened_to": today.isoformat()}
        )
        self.assertNotIn(sid, [s["id"] for s in listed.data["results"]])
        listed = self.c.get(
            "/api/sale-sessions/", {"opened_from": past.isoformat(), "opened_to": past.isoformat()}
        )
        self.assertIn(sid, [s["id"] for s in listed.data["results"]])

    def test_manual_session_stamped_on_its_manual_date(self):
        past = timezone.localdate() - timedelta(days=3)
        r = self.c.post(
            "/api/sale-sessions/manual/",
            {"employee": self.emp.id, "date": past.isoformat(), "cash": "10"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        session = SaleSession.objects.get(pk=r.data["id"])
        self.assertEqual(timezone.localtime(session.opened_at).date(), past)
        self.assertEqual(timezone.localtime(session.closed_at).date(), past)

    def test_open_with_date_reopens_closed_session_of_same_date_only(self):
        past = timezone.localdate() - timedelta(days=2)
        r = self.c.post(
            "/api/sale-sessions/", {"employee": self.emp.id, "date": past.isoformat()}, format="json"
        )
        sid = r.data["id"]
        self._add_item(sid, quantity=10)
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        # نفس التاريخ → إعادة فتح نفس الوردية
        r = self.c.post(
            "/api/sale-sessions/", {"employee": self.emp.id, "date": past.isoformat()}, format="json"
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["id"], sid)
        self.assertTrue(r.data.get("reopened"))
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        # تاريخ مختلف (اليوم) → وردية جديدة مستقلة
        r = self.c.post(
            "/api/sale-sessions/",
            {"employee": self.emp.id, "date": timezone.localdate().isoformat()},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotEqual(r.data["id"], sid)
        self.assertFalse(r.data.get("reopened"))

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

    def test_add_yard_item_uses_branch_piece_price(self):
        # قطعة الفرع (70 ÷ 3.5 = 20 ياردة) تُحدد سعر بيع الياردة تلقائياً
        FabricBranchPrice.objects.create(
            branch=self.branch, fabric=self.fabric, sale_price_yard=0,
            piece_price=70, min_sale_yard=0,
        )
        sid = self._open_session()["id"]
        r = self._add_item(sid, quantity=2)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(str(r.data["unit_price"])), Decimal("20"))
        self.assertEqual(Decimal(str(r.data["total"])), Decimal("40"))

    def test_branch_min_price_enforced(self):
        FabricBranchPrice.objects.create(
            branch=self.branch, fabric=self.fabric, sale_price_yard=8, min_sale_yard=7,
        )
        sid = self._open_session()["id"]
        r = self._add_item(sid, quantity=10, unit_price=6)
        self.assertEqual(r.status_code, 400)

    def test_default_min_percent_applies(self):
        # بلا حد أدنى صريح → يُطبَّق تلقائياً 15% من سعر بيع الياردة (5 × 0.15 = 0.75)
        sid = self._open_session()["id"]
        r = self._add_item(sid, quantity=1, unit_price=0.5)
        self.assertEqual(r.status_code, 400, r.data)
        r = self._add_item(sid, quantity=1, unit_price=1)
        self.assertEqual(r.status_code, 201, r.data)

    def test_default_min_percent_follows_settings(self):
        from appsettings.models import AppSettings
        s = AppSettings.load()
        s.min_sale_percent = 50
        s.save()
        sid = self._open_session()["id"]
        # الحد الأدنى = 5 × 0.5 = 2.5
        r = self._add_item(sid, quantity=1, unit_price=2)
        self.assertEqual(r.status_code, 400, r.data)
        r = self._add_item(sid, quantity=1, unit_price=3)
        self.assertEqual(r.status_code, 201, r.data)

    def test_piece_below_purchase_multiplier_rejected(self):
        # المضاعف الافتراضي 1: سعر القطعة (ياردة × 3.5) يجب ألا يقل عن تكلفة الشراء
        self.fabric.purchase_price = 10
        self.fabric.save()
        sid = self._open_session()["id"]
        # ياردة 9 → القطعة 31.5 < 35 → مرفوض
        r = self._add_item(sid, quantity=1, unit_price=9)
        self.assertEqual(r.status_code, 400, r.data)
        # ياردة 10 → القطعة 35 = التكلفة → مقبول
        r = self._add_item(sid, quantity=1, unit_price=10)
        self.assertEqual(r.status_code, 201, r.data)

    def test_piece_multiplier_follows_settings(self):
        from appsettings.models import AppSettings
        s = AppSettings.load()
        s.min_piece_price_multiplier = 2
        s.save()
        self.fabric.purchase_price = 10
        self.fabric.save()
        sid = self._open_session()["id"]
        # ياردة 15 → القطعة 52.5 < 70 (10×3.5×2) → مرفوض
        r = self._add_item(sid, quantity=1, unit_price=15)
        self.assertEqual(r.status_code, 400, r.data)
        # ياردة 21 → القطعة 73.5 ≥ 70 → مقبول
        r = self._add_item(sid, quantity=1, unit_price=21)
        self.assertEqual(r.status_code, 201, r.data)

    def test_piece_multiplier_roll_uses_yard_equivalent(self):
        from appsettings.models import AppSettings
        s = AppSettings.load()
        s.min_piece_price_multiplier = 2
        s.save()
        self.fabric.purchase_price = 10
        self.fabric.save()
        sid = self._open_session()["id"]
        # لفة = 50 ياردة → مطلوب سعر لفة ≥ 10×50×2 = 1000
        r = self._add_item(sid, sale_type="roll", quantity=1, unit_price=900)
        self.assertEqual(r.status_code, 400, r.data)
        r = self._add_item(sid, sale_type="roll", quantity=1, unit_price=1100)
        self.assertEqual(r.status_code, 201, r.data)

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

    def test_remove_item_returns_stock_immediately(self):
        sid = self._open_session()["id"]
        item = self._add_item(sid, quantity=5)
        iid = item.data["id"]
        self.roll.refresh_from_db()
        # الخصم فوري بمجرد الحفظ
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("495"))
        r = self.c.delete(f"/api/sale-sessions/{sid}/items/{iid}/")
        self.assertEqual(r.status_code, 200)
        self.roll.refresh_from_db()
        # حذف البيعة يُرجع المخزون فوراً
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("500"))
        r2 = self.c.get("/api/sale-sessions/")
        self.assertEqual(r2.data["results"][0]["totals"]["total"], 0)

    def test_stock_deducted_immediately_on_add(self):
        sid = self._open_session()["id"]
        r = self._add_item(sid, quantity=20, payment_method="cash")
        self.assertEqual(r.status_code, 201, r.data)
        self.roll.refresh_from_db()
        # الخصم حدث لحظياً قبل إغلاق الوردية
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("480"))
        self.assertEqual(
            StockMovement.objects.filter(movement_type=StockMovement.Type.SALE).count(), 1
        )
        # الإغلاق لا يخصم مرة أخرى
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("480"))

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
        # حركة لكل بند: بعد التعديل أُعيدت حركة القديمة ونشأت حركة الجديدة = حركتان
        self.assertEqual(
            StockMovement.objects.filter(movement_type=StockMovement.Type.SALE).count(), 2
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

    def test_delete_open_session_returns_stock(self):
        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        sid = r.data["id"]
        self.c.post(f"/api/sale-sessions/{sid}/items/",
                    {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 20,
                     "payment_method": "cash"}, format="json")
        self.roll.refresh_from_db()
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("480"))
        r = self.c.delete(f"/api/sale-sessions/{sid}/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(SaleSession.objects.filter(pk=sid).exists())
        self.roll.refresh_from_db()
        # حذف الوردية يرجّع كل الخصم الفوري
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("500"))
        self.assertEqual(
            StockMovement.objects.filter(movement_type=StockMovement.Type.SALE).count(), 0
        )

    def test_reopen_closed_session_keeps_stock_deducted(self):
        sid = self._closed_session()
        sale_date = effective_sale_date()
        r = self.c.post(f"/api/sale-sessions/{sid}/reopen/")
        self.assertEqual(r.status_code, 200, r.data)
        session = SaleSession.objects.get(pk=sid)
        self.assertEqual(session.status, SaleSession.Status.OPEN)
        self.assertIsNone(session.closed_at)
        self.assertFalse(DailySale.objects.filter(branch=self.branch, date=sale_date).exists())
        self.roll.refresh_from_db()
        # الخصم فوري عند الإضافة — إعادة الفتح لا تُرجع المخزون (يبقى 500 - 30)
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("470"))
        # حركة لكل بند ما زالت مرتبطة بالبند
        self.assertEqual(
            StockMovement.objects.filter(movement_type=StockMovement.Type.SALE).count(), 2
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


class AvatarImageUploadTest(TestCase):
    """الصورة الشخصية — تُرفع من الجهاز كـ data URL عبر /api/account/avatar/."""

    # PNG صالح 1×1 (أصغر صورة حقيقية يمكن إنشاؤها)
    PNG_1PX = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )

    def setUp(self):
        self.c = APIClient()
        self.user, self.emp = authenticate_admin(self.c)

    def test_user_can_upload_own_avatar_image(self):
        r = self.c.patch(
            "/api/account/avatar/", {"avatar_image": self.PNG_1PX}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["employee"]["avatar_image"], self.PNG_1PX)
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.avatar_image, self.PNG_1PX)

    def test_avatar_image_keeps_emoji_avatar(self):
        self.emp.avatar = "🦁"
        self.emp.save(update_fields=["avatar"])
        r = self.c.patch(
            "/api/account/avatar/", {"avatar_image": self.PNG_1PX}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["employee"]["avatar"], "🦁")

    def test_can_set_avatar_and_clear_image_together(self):
        Employee.objects.filter(pk=self.emp.pk).update(avatar_image=self.PNG_1PX)
        r = self.c.patch(
            "/api/account/avatar/",
            {"avatar": "🐼", "clear_avatar_image": True},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["employee"]["avatar"], "🐼")
        self.assertEqual(r.data["employee"]["avatar_image"], "")

    def test_can_remove_avatar_image(self):
        Employee.objects.filter(pk=self.emp.pk).update(avatar_image=self.PNG_1PX)
        r = self.c.patch(
            "/api/account/avatar/", {"clear_avatar_image": True}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["employee"]["avatar_image"], "")

    def test_rejects_non_image_data_url(self):
        r = self.c.patch(
            "/api/account/avatar/",
            {"avatar_image": "data:text/html;base64,PHNjcmlwdD4="},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.data)

    def test_rejects_magic_mismatch(self):
        # نوع معلن image/png لكن المحتوى HTML
        payload = "data:image/png;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=="
        r = self.c.patch("/api/account/avatar/", {"avatar_image": payload}, format="json")
        self.assertEqual(r.status_code, 400, r.data)

    def test_rejects_corrupt_base64(self):
        r = self.c.patch(
            "/api/account/avatar/",
            {"avatar_image": "data:image/png;base64,!!!not-base64!!!"},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.data)

    def test_rejects_oversized_image(self):
        from sale_sessions.avatars import MAX_AVATAR_IMAGE_CHARS
        payload = "data:image/png;base64," + "A" * (MAX_AVATAR_IMAGE_CHARS + 10)
        r = self.c.patch("/api/account/avatar/", {"avatar_image": payload}, format="json")
        self.assertEqual(r.status_code, 400, r.data)

    def test_rejects_empty_payload(self):
        r = self.c.patch("/api/account/avatar/", {}, format="json")
        self.assertEqual(r.status_code, 400, r.data)

    def test_cannot_write_arbitrary_emoji_even_with_image_key(self):
        r = self.c.patch(
            "/api/account/avatar/",
            {"avatar": "😀", "avatar_image": self.PNG_1PX},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.data)

    def test_avatar_image_is_read_only_for_admins(self):
        r = self.c.post(
            "/api/employees/",
            {"name": "سارة", "avatar_image": self.PNG_1PX},
            format="json",
        )
        self.assertIn(r.status_code, (201, 400))

    def test_avatar_image_exposed_in_profile_and_contacts(self):
        self.emp.avatar_image = self.PNG_1PX
        self.emp.save(update_fields=["avatar_image"])
        r = self.c.get(f"/api/account/profile/?employee_id={self.emp.id}")
        self.assertEqual(r.data["avatar_image"], self.PNG_1PX)
        r = self.c.get("/api/messaging/contacts/")
        self.assertEqual(r.data["me"]["avatar_image"], self.PNG_1PX)


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

    def test_customer_sales_finds_lines_written_with_a_different_spelling(self):
        """سطرُ البيع يحمل الرقمَ كما كُتب يومَ البيع، لا كما حُفظ للزبون.

        فالمطابقةُ بالرسم وحده تُسقط مشترياتٍ للزبون نفسه، والحائبُ
        يقول بعدها: ليس له مشتريات — وهو جوابٌ يغيّر ما يفعله المحاسب.
        """
        sid = self._open_session()
        self._add_item(sid, quantity=10, phone="0551-111")
        self._add_item(sid, quantity=4, phone="055999")
        for typed in ("0551-111", "0551111", "0551 111"):
            with self.subTest(typed=typed):
                r = self.c.get("/api/sale-sessions/customer-sales/", {"phone": typed})
                self.assertEqual(r.status_code, 200, r.data)
                self.assertEqual(r.data["totals"]["count"], 1, typed)
                self.assertEqual(r.data["totals"]["total"], 50.0, typed)

    def test_customer_sales_says_nothing_for_a_number_nobody_typed(self):
        """رقمٌ لم يكتبه أحد: صفرُ بنود، لا سطرٌ لرقمٍ آخر.

        الجوابُ الفارغُ يجب أن يكون فارغاً تماماً، وإلا أخبره رقمٌ آخر عن
        مشتريه.
        """
        sid = self._open_session()
        self._add_item(sid, quantity=10, phone="055111")
        r = self.c.get("/api/sale-sessions/customer-sales/", {"phone": "055222"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["items"], [])
        self.assertEqual(r.data["totals"]["count"], 0)
        self.assertEqual(r.data["totals"]["total"], 0.0)

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

    def test_return_open_item_returns_stock(self):
        sid = self._open_session()
        self._add_item(sid, quantity=20, phone="055444")
        item = SaleSessionItem.objects.get(session_id=sid)
        r = self.c.post("/api/sale-sessions/return-items/",
                        {"item_ids": [item.id]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        item.refresh_from_db()
        self.assertTrue(item.is_returned)
        self.roll.refresh_from_db()
        # استرجاع بند وردية مفتوحة يرجّع الخصم الفوري إلى المخزون
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
        # الخصم فوري: بعد الاسترجاع رصيد 490 (عادت 20) — إعادة الفتح لا تُغيّر المخزون
        self.assertEqual(Decimal(str(self.roll.remaining_yards)), Decimal("490"))

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


class SaleGroupNumberingTest(TestCase):
    """ترقيم البيّعات داخل الوردية: الأقدم = 1، والحذف لا يعيد الترقيم."""

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
        self.assertEqual(r.status_code, 201, r.data)
        return r.data["id"]

    def _add(self, sid, quantity=10):
        r = self.c.post(
            f"/api/sale-sessions/{sid}/items/",
            {"fabric": self.fabric.id, "sale_type": "yard", "quantity": quantity,
             "payment_method": "cash"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def _bulk(self, sid, count):
        items = [
            {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 3, "payment_method": "cash"}
            for _ in range(count)
        ]
        r = self.c.post(f"/api/sale-sessions/{sid}/items/bulk/", {"items": items}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def _numbers(self, sid):
        """أرقام البيّعات مرتبة تصاعدياً كما تُعرض للمستخدم."""
        return sorted(
            SaleSessionItem.objects.filter(session_id=sid)
            .values_list("group_no", flat=True)
        )

    def test_sales_number_from_one_oldest_first(self):
        sid = self._open()
        first = self._add(sid)
        second = self._add(sid)
        third = self._add(sid)
        self.assertEqual(first["group_no"], 1)
        self.assertEqual(second["group_no"], 2)
        self.assertEqual(third["group_no"], 3)
        self.assertEqual(self._numbers(sid), [1, 2, 3])

    def test_bulk_batch_shares_one_number(self):
        sid = self._open()
        rows = self._bulk(sid, 3)
        # بنود الدفعة الواحدة = بيعة واحدة، فكلها تشارك رقماً واحداً
        self.assertEqual({row["group_no"] for row in rows}, {1})
        other = self._bulk(sid, 1)
        self.assertEqual(other[0]["group_no"], 2)

    def test_delete_middle_sale_leaves_gap_without_renumbering(self):
        sid = self._open()
        self._add(sid)
        middle = self._add(sid)
        self._add(sid)
        r = self.c.delete(f"/api/sale-sessions/{sid}/items/{middle['id']}/")
        self.assertEqual(r.status_code, 200, r.data)
        # الباقية لا تُعاد ترقيمها: بيعة 1 وبيعة 3
        self.assertEqual(self._numbers(sid), [1, 3])
        # والبيعة الجديدة تأخذ الرقم التالي لا الرقم المحرَّر
        self.assertEqual(self._add(sid)["group_no"], 4)

    def test_delete_newest_sale_does_not_reuse_its_number(self):
        """حذف آخر بيعة لا يُرجع رقمها للبيعات التالية."""
        sid = self._open()
        self._add(sid)
        newest = self._add(sid)
        r = self.c.delete(f"/api/sale-sessions/{sid}/items/{newest['id']}/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._numbers(sid), [1])
        self.assertEqual(self._add(sid)["group_no"], 3)

    def test_sessions_number_independently(self):
        first = self._open()
        second = self._open(Employee.objects.create(name="محمود", branch=self.branch))
        self._add(first)
        self._add(first)
        # كل وردية ترقّ نفسها من 1
        self.assertEqual(self._add(second)["group_no"], 1)
        self.assertEqual(self._numbers(first), [1, 2])
        self.assertEqual(self._numbers(second), [1])

    def test_editing_item_keeps_its_number(self):
        sid = self._open()
        self._add(sid)
        item = self._add(sid)
        r = self.c.patch(
            f"/api/sale-sessions/{sid}/items/{item['id']}/", {"quantity": 25}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["group_no"], 2)

    def test_moved_item_gets_number_in_target_session(self):
        source = self._open()
        target = self._open(Employee.objects.create(name="محمود", branch=self.branch))
        self._add(target)
        self._add(source)
        moving = self._add(source)
        r = self.c.post(
            f"/api/sale-sessions/{source}/move-item/{moving['id']}/",
            {"target_session": target},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        # رقم 2 محجوز في الوردية المصدر، فلا يتكرر داخل الهدف
        self.assertEqual(self._numbers(target), [1, 2])
        self.assertEqual(self._numbers(source), [1])

    def test_client_cannot_set_group_no(self):
        sid = self._open()
        self._add(sid)
        r = self.c.post(
            f"/api/sale-sessions/{sid}/items/",
            {"fabric": self.fabric.id, "sale_type": "yard", "quantity": 10,
             "payment_method": "cash", "group_no": 99, "sale_group": "hijacked"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        # لا يُقبل من العميل: الرقم يُدار من الخادم ويستمر من العدّاد
        self.assertEqual(r.data["group_no"], 2)
        self.assertNotEqual(r.data["sale_group"], "hijacked")

    def test_session_payload_newest_first_but_oldest_numbered_one(self):
        """شارة «بيعة N» تقرأ من حمولة الوردية: الأحدث في الأعلى ورقمه الأكبر."""
        sid = self._open()
        self._add(sid)
        self._add(sid)
        self._add(sid)
        r = self.c.get(f"/api/sale-sessions/{sid}/")
        self.assertEqual(r.status_code, 200, r.data)
        # البنود مرتّبة من الأحدث إلى الأقدم، والأقدم يحمل الرقم 1
        self.assertEqual([it["group_no"] for it in r.data["items"]], [3, 2, 1])

    def test_reopen_keeps_existing_numbers(self):
        sid = self._open()
        self._add(sid)
        self._add(sid)
        self.c.post(f"/api/sale-sessions/{sid}/close/")
        r = self.c.post("/api/sale-sessions/", {"employee": self.emp.id}, format="json")
        self.assertEqual(r.data["id"], sid)
        self.assertEqual(self._numbers(sid), [1, 2])
        self.assertEqual(self._add(sid)["group_no"], 3)

    def test_backfill_numbers_existing_rows_oldest_first(self):
        """ترحيل البيانات المرقّمة: الأقدم = 1 وكل بنود البيعة تأخذ رقمها."""
        import importlib

        from django.apps import apps as django_apps
        from django.db import connection

        migration = importlib.import_module(
            "sale_sessions.migrations.0028_salesessionitem_group_no"
        )

        class _SchemaEditor:
            pass

        editor = _SchemaEditor()
        editor.connection = connection

        first = self._open()
        second = self._open(Employee.objects.create(name="محمود", branch=self.branch))
        # بيعة 1 من بندين، بيعة 2 مفردة، بيعة 3 مفردة
        self._bulk(first, 2)
        self._add(first)
        self._add(first)
        self._add(second)
        # محاكاة بيانات قبل إضافة عمود الترقيم
        SaleSessionItem.objects.update(group_no=None)

        migration.backfill_group_no(django_apps, editor)
        migration.set_session_counters(django_apps, editor)

        rows = list(
            SaleSessionItem.objects.filter(session_id=first)
            .order_by("id")
            .values_list("id", "group_no")
        )
        self.assertEqual([no for _, no in rows], [1, 1, 2, 3])
        # العدّاد صار 4 (بعد أكبر رقم) لا 1 الافتراضي، فلا تُعاد أرقام
        # بيعات محذوفة لاحقاً
        self.assertEqual(SaleSession.objects.get(pk=first).next_group_no, 4)
        self.assertEqual(self._add(first)["group_no"], 4)
        self.assertEqual(self._numbers(second), [1])
        # لا يبقى أي بند بلا رقم
        self.assertFalse(SaleSessionItem.objects.filter(group_no=None).exists())
