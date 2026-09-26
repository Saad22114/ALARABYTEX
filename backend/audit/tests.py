"""اختبارات سجل التدقيق: تغطية الإشارات، الأحداث التشغيلية، الاستعلامات، والصلاحيات."""

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditLog
from audit.services import log_activity
from core.request_state import suppress_audit
from core.testsupport import authenticate_admin, make_admin_user
from payroll.models import PayrollRun, SalaryStructure
from sale_sessions.models import Employee
from suppliers.models import Fabric, Supplier


class AuditSignalTests(TestCase):
    def test_create_is_logged(self):
        supplier = Supplier.objects.create(name="مورد التدقيق")
        entry = AuditLog.objects.filter(model_name=Supplier._meta.label, object_id=supplier.pk).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.action, AuditLog.Action.CREATE)
        self.assertEqual(entry.section, "suppliers")
        self.assertEqual(entry.object_repr, "مورد التدقيق")

    def test_update_logs_only_changed_fields(self):
        supplier = Supplier.objects.create(name="قبل", phone="111")
        supplier.name = "بعد"
        supplier.save()
        entry = (
            AuditLog.objects.filter(model_name=Supplier._meta.label, action=AuditLog.Action.UPDATE)
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(entry)
        self.assertIn("name", entry.changes)
        self.assertEqual(entry.changes["name"]["old"], "قبل")
        self.assertEqual(entry.changes["name"]["new"], "بعد")
        self.assertNotIn("phone", entry.changes)

    def test_save_without_changes_logs_nothing(self):
        supplier = Supplier.objects.create(name="ثابت")
        before = AuditLog.objects.count()
        supplier.save()
        self.assertEqual(AuditLog.objects.count(), before)

    def test_delete_is_logged(self):
        fabric = Fabric.objects.create(name="قماش محذوف", code="DEL-1")
        fabric.delete()
        entry = AuditLog.objects.filter(model_name=Fabric._meta.label, action=AuditLog.Action.DELETE).first()
        self.assertIsNotNone(entry)

    def test_suppress_audit_silences_signals(self):
        with suppress_audit():
            Supplier.objects.create(name="مورد صامت")
        self.assertFalse(AuditLog.objects.filter(object_repr="مورد صامت").exists())

    def test_payroll_models_are_tracked(self):
        employee = Employee.objects.create(name="موظف التدقيق")
        SalaryStructure.objects.create(employee=employee, base_salary=Decimal("500.00"))
        entry = (
            AuditLog.objects.filter(model_name=SalaryStructure._meta.label, section="payroll")
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.action, AuditLog.Action.CREATE)

    def test_untracked_model_is_ignored(self):
        run = PayrollRun.objects.create(month="2026-01-01")
        self.assertTrue(
            AuditLog.objects.filter(
                model_name=PayrollRun._meta.label, action=AuditLog.Action.CREATE
            ).exists()
        )
        self.assertEqual(str(run.month), "2026-01-01")


class LogActivityTests(TestCase):
    def test_activity_records_event_and_details(self):
        run = PayrollRun.objects.create(month="2026-02-01")
        log_activity("payroll", "صرف مسيّر رواتب", run, details={"method": "cash"})
        entry = AuditLog.objects.filter(model_name=PayrollRun._meta.label).order_by("-id").first()
        self.assertEqual(entry.action, AuditLog.Action.OTHER)
        self.assertEqual(entry.changes["event"], "صرف مسيّر رواتب")
        self.assertEqual(entry.changes["details"]["method"], "cash")
        self.assertIn("صرف مسيّر رواتب", entry.object_repr)

    def test_activity_without_instance_uses_event_as_repr(self):
        log_activity("system", "فحص دوري", employee=None, request=None)
        entry = AuditLog.objects.order_by("-id").first()
        self.assertEqual(entry.object_repr, "فحص دوري")
        self.assertEqual(entry.model_name, "فحص دوري")


class AuditLogApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user, self.employee = authenticate_admin(self.client)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/audit/").status_code, 401)

    def test_denied_without_audit_permission(self):
        self.employee.permissions = {**self.employee.permissions, "audit": {"view": False}}
        self.employee.save(update_fields=["permissions"])
        self.assertEqual(self.client.get("/api/audit/").status_code, 403)

    def test_admin_preset_grants_audit_access(self):
        self.assertTrue(self.employee.has_permission("audit", "view"))
        self.assertEqual(self.client.get("/api/audit/").status_code, 200)

    def test_list_returns_newest_first(self):
        first = Supplier.objects.create(name="مورد أقدم")
        second = Fabric.objects.create(name="قماش أحدث", code="NEW-1")
        response = self.client.get("/api/audit/")
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertTrue(any(r["object_repr"] == "مورد أقدم" for r in results))
        self.assertTrue(any(r["object_repr"] == "قماش أحدث" for r in results))
        newest = results[0]
        self.assertEqual(newest["section"], "fabrics")
        self.assertEqual(newest["object_id"], second.pk)
        # السجلات المنشأة خارج طلب HTTP لا تملك منفّذاً مسجّلاً.
        self.assertIsNone(newest["employee_name"])

    def test_entries_created_through_request_record_actor(self):
        response = self.client.post(
            "/api/suppliers/", {"name": "مورد عبر الطلب"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        log = AuditLog.objects.filter(
            model_name=Supplier._meta.label,
            object_id=response.json()["id"],
            action=AuditLog.Action.CREATE,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.employee_id, self.employee.pk)
        self.assertEqual(log.section, "suppliers")
        self.assertEqual(log.method, "POST")
        self.assertTrue(log.path.endswith("/api/suppliers/"))

    def test_updated_entry_exposes_change_payload(self):
        supplier = Supplier.objects.create(name="قبل")
        supplier.city = "دمشق"
        supplier.save()
        response = self.client.get("/api/audit/?action=update")
        row = response.json()["results"][0]
        self.assertIn("city", row["changes"])
        self.assertEqual(row["changes"]["city"]["new"], "دمشق")

    def test_filter_by_section_and_action(self):
        Supplier.objects.create(name="مورد مفلتر")
        response = self.client.get("/api/audit/?section=suppliers&action=create")
        self.assertEqual(response.status_code, 200)
        for row in response.json()["results"]:
            self.assertEqual(row["section"], "suppliers")
            self.assertEqual(row["action"], "create")

    def test_filter_by_employee_and_search_term(self):
        Supplier.objects.create(name="مورد البحث الخاص")
        response = self.client.get("/api/audit/?q=البحث الخاص")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["object_repr"], "مورد البحث الخاص")

    def test_filter_by_model_and_date_range(self):
        Supplier.objects.create(name="مورد النموذج")
        response = self.client.get("/api/audit/?model=suppliers.Supplier")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["count"], 1)

        empty = self.client.get("/api/audit/?from=1990-01-01&to=1990-01-02")
        self.assertEqual(empty.json()["count"], 0)

    def test_pagination_metadata_present(self):
        response = self.client.get("/api/audit/?limit=1")
        payload = response.json()
        self.assertIn("count", payload)
        self.assertIn("next", payload)
        self.assertIn("previous", payload)
        self.assertLessEqual(len(payload["results"]), 1)


class AuditLoginTests(TestCase):
    def test_login_and_logout_are_logged(self):
        client = APIClient()
        user, employee = make_admin_user()
        client.force_authenticate(user=user)
        client.post("/api/auth/logout/")
        self.assertTrue(
            AuditLog.objects.filter(
                employee=employee, action=AuditLog.Action.LOGOUT, section="auth"
            ).exists()
        )
