"""اختبارات مركز التنبيهات الذكية: القواعد، الترتيب، والصلاحيات."""

from datetime import date, timedelta
from decimal import Decimal

from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from appsettings.models import AppSettings
from branches.models import Branch
from core.testsupport import authenticate_admin, make_admin_user
from payroll.models import AdvanceInstallment, PayrollRun, SalaryAdvance, SalaryStructure
from sale_sessions.models import Employee, SaleSession
from suppliers.models import Fabric, LedgerEntry, Supplier
from warehouses.models import FabricRoll, Warehouse

from .alerts import build_alerts

_factory = RequestFactory()


def request_for(user):
    """طلب حقيقي من ``RequestFactory`` يحمل المستخدم — يمرّ بمسار الصلاحيات نفسه."""
    request = _factory.get("/api/dashboard/alerts-center/")
    request.user = user
    return request


def keys(alerts):
    return {a["key"] for a in alerts}


def alert_for(alerts, key):
    return next((a for a in alerts if a["key"] == key), None)


def titles_of(alerts, key):
    alert = alert_for(alerts, key)
    return [i["title"] for i in alert["items"]] if alert else []


class AlertsBase(TestCase):
    def setUp(self):
        self.user, self.employee = make_admin_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.request = request_for(self.user)
        self.branch = self.employee.branch
        self.warehouse = Warehouse.objects.create(name="مخزن رئيسي", code="W1", branch=self.branch)

    def alerts(self):
        return build_alerts(self.request)

    def _roll(self, fabric, yards):
        return FabricRoll.objects.create(
            fabric=fabric,
            warehouse=self.warehouse,
            status=FabricRoll.Status.AVAILABLE,
            yards=Decimal(str(yards)),
            remaining_yards=Decimal(str(yards)),
        )

    def _fabric(self, name, min_stock=0):
        return Fabric.objects.create(
            name=name, code=f"F{name[:5]}", min_stock=Decimal(str(min_stock))
        )

    def _employee(self, name="موظف"):
        return Employee.objects.create(name=name, branch=self.branch)


class AlertsShapeTests(AlertsBase):
    def test_every_alert_has_required_shape(self):
        self._roll(self._fabric("قماش", min_stock=10), 1)
        alerts = self.alerts()
        self.assertTrue(alerts)
        for alert in alerts:
            for key in ("key", "title", "severity", "section", "href", "hint", "count", "items"):
                self.assertIn(key, alert, alert.get("key"))
            self.assertIn(alert["severity"], ("critical", "warning", "info"))
            self.assertLessEqual(len(alert["items"]), 5)
            self.assertLessEqual(alert["count"], 50)

    def test_alerts_sorted_by_severity(self):
        order = {"critical": 0, "warning": 1, "info": 2}
        severities = [order[a["severity"]] for a in self.alerts()]
        self.assertEqual(severities, sorted(severities))

    def test_no_duplicate_keys(self):
        self._roll(self._fabric("مكرر", min_stock=5), 1)
        alert_keys = [a["key"] for a in self.alerts()]
        self.assertEqual(len(alert_keys), len(set(alert_keys)))


class StockAlertTests(AlertsBase):
    def test_out_of_stock_is_critical(self):
        self._roll(self._fabric("نفد رصيده", min_stock=5), 0)
        alert = alert_for(self.alerts(), "stock_out")
        self.assertIsNotNone(alert)
        self.assertEqual(alert["severity"], "critical")
        self.assertEqual(alert["items"][0]["title"], "نفد رصيده")

    def test_below_minimum_is_warning(self):
        self._roll(self._fabric("تحت الحد", min_stock=100), 40)
        alert = alert_for(self.alerts(), "stock_low")
        self.assertIsNotNone(alert)
        self.assertEqual(alert["severity"], "warning")
        self.assertIn("40", alert["items"][0]["detail"])
        self.assertIn("100", alert["items"][0]["detail"])

    def test_at_minimum_is_not_alerted(self):
        self._roll(self._fabric("كافٍ", min_stock=50), 50)
        self.assertNotIn("stock_low", keys(self.alerts()))

    def test_above_minimum_is_not_alerted(self):
        self._roll(self._fabric("وفير", min_stock=10), 500)
        self.assertNotIn("stock_low", keys(self.alerts()))

    def test_zero_minimum_does_not_alert(self):
        self._roll(self._fabric("بلا حد", min_stock=0), 5)
        alerts = keys(self.alerts())
        self.assertNotIn("stock_low", alerts)
        self.assertNotIn("stock_out", alerts)

    def test_stale_stock_detected(self):
        self._roll(self._fabric("راكد", min_stock=0), 300)
        alert = alert_for(self.alerts(), "stock_stale")
        self.assertIsNotNone(alert)
        self.assertEqual(alert["severity"], "info")
        self.assertIn("راكد", [i["title"] for i in alert["items"]])

    def test_stock_rules_respect_app_setting(self):
        self._roll(self._fabric("مفعّل", min_stock=10), 1)
        AppSettings.objects.all().delete()
        AppSettings.objects.create(low_stock_alert_enabled=False)
        alerts = keys(self.alerts())
        self.assertNotIn("stock_low", alerts)
        self.assertNotIn("stock_out", alerts)


class SessionAlertTests(AlertsBase):
    def _session(self, **kwargs):
        opened_at = kwargs.pop("opened_at", timezone.now() - timedelta(days=3))
        defaults = {
            "employee": self.employee,
            "branch": self.branch,
            "status": SaleSession.Status.OPEN,
        }
        defaults.update(kwargs)
        session = SaleSession.objects.create(**defaults)
        # opened_at حقل auto_now_add، فالتاريخ القديم يُكتب بعد الإنشاء
        SaleSession.objects.filter(pk=session.pk).update(opened_at=opened_at)
        session.refresh_from_db()
        return session

    def test_session_open_from_previous_day_alerts(self):
        self._session()
        alert = alert_for(self.alerts(), "sessions_open")
        self.assertIsNotNone(alert)
        self.assertEqual(alert["items"][0]["title"], self.employee.name)

    def test_session_open_today_is_not_alerted(self):
        self._session(opened_at=timezone.now())
        self.assertNotIn("sessions_open", keys(self.alerts()))

    def test_closed_old_session_is_not_alerted(self):
        self._session(
            status=SaleSession.Status.CLOSED, closed_at=timezone.now() - timedelta(days=2)
        )
        self.assertNotIn("sessions_open", keys(self.alerts()))


class PurchaseAlertTests(AlertsBase):
    def test_purchase_without_receipt_alerts(self):
        supplier = Supplier.objects.create(name="مورد معلّق")
        LedgerEntry.objects.create(
            supplier=supplier,
            date=date.today() - timedelta(days=2),
            entry_type=LedgerEntry.EntryType.PURCHASE,
            amount=Decimal("500"),
        )
        alert = alert_for(self.alerts(), "purchases_unreceived")
        self.assertIsNotNone(alert)
        self.assertEqual(alert["items"][0]["title"], "مورد معلّق")

    def test_no_purchases_means_no_alert(self):
        self.assertNotIn("purchases_unreceived", keys(self.alerts()))


class WarehouseAlertTests(AlertsBase):
    def test_requested_transfer_alerts(self):
        other = Branch.objects.create(name="فرع آخر", code="OB", is_active=False)
        target = Warehouse.objects.create(name="مخزن الهدف", code="W2", branch=other)
        from warehouses.models import StockTransfer

        StockTransfer.objects.create(
            number="TR-1",
            from_warehouse=self.warehouse,
            to_warehouse=target,
            date=date.today(),
            status=StockTransfer.Status.REQUESTED,
        )
        alert = alert_for(self.alerts(), "transfers_pending")
        self.assertIsNotNone(alert)
        self.assertEqual(alert["items"][0]["title"], "TR-1")

    def test_open_count_alerts(self):
        from warehouses.models import StockCount

        StockCount.objects.create(
            number="CNT-1", warehouse=self.warehouse, date=date.today(), status=StockCount.Status.OPEN
        )
        alert = alert_for(self.alerts(), "counts_open")
        self.assertIsNotNone(alert)
        self.assertEqual(alert["items"][0]["title"], "CNT-1")

    def test_posted_count_does_not_alert(self):
        from warehouses.models import StockCount

        StockCount.objects.create(
            number="CNT-2", warehouse=self.warehouse, date=date.today(), status=StockCount.Status.POSTED
        )
        self.assertNotIn("counts_open", keys(self.alerts()))


class PayrollAlertTests(AlertsBase):
    def test_draft_run_alerts(self):
        PayrollRun.objects.create(month=date(2026, 3, 1))
        alert = alert_for(self.alerts(), "payroll_draft")
        self.assertIsNotNone(alert)
        self.assertEqual(alert["items"][0]["title"], "2026-03")
        self.assertIn("كل الفروع", alert["items"][0]["detail"])

    def test_paid_run_does_not_alert(self):
        PayrollRun.objects.create(month=date(2026, 3, 1), status=PayrollRun.Status.PAID)
        self.assertNotIn("payroll_draft", keys(self.alerts()))

    def test_pending_advance_alerts(self):
        SalaryAdvance.objects.create(
            employee=self._employee("موظف سلفة"),
            amount=Decimal("300"),
            date=date.today(),
            status=SalaryAdvance.Status.PENDING,
        )
        alert = alert_for(self.alerts(), "advances_pending")
        self.assertIsNotNone(alert)
        self.assertEqual(alert["items"][0]["title"], "موظف سلفة")

    def test_overdue_advance_reports_remaining_and_age(self):
        advance = SalaryAdvance.objects.create(
            employee=self._employee("موظف متأخر"),
            amount=Decimal("1000"),
            date=date.today() - timedelta(days=90),
            status=SalaryAdvance.Status.APPROVED,
        )
        AdvanceInstallment.objects.create(
            advance=advance, amount=Decimal("250"), date=date.today() - timedelta(days=10)
        )
        alert = alert_for(self.alerts(), "advances_overdue")
        self.assertIsNotNone(alert)
        self.assertIn("750", alert["items"][0]["detail"])
        self.assertIn("90", alert["items"][0]["detail"])

    def test_fully_repaid_old_advance_does_not_alert(self):
        advance = SalaryAdvance.objects.create(
            employee=self._employee("موظف مسدد"),
            amount=Decimal("400"),
            date=date.today() - timedelta(days=90),
            status=SalaryAdvance.Status.APPROVED,
        )
        AdvanceInstallment.objects.create(
            advance=advance, amount=Decimal("400"), date=date.today()
        )
        self.assertNotIn("advances_overdue", keys(self.alerts()))

    def test_recent_approved_advance_does_not_alert(self):
        SalaryAdvance.objects.create(
            employee=self._employee("موظف حديث"),
            amount=Decimal("400"),
            date=date.today() - timedelta(days=2),
            status=SalaryAdvance.Status.APPROVED,
        )
        self.assertNotIn("advances_overdue", keys(self.alerts()))

    def test_employee_without_salary_alerts(self):
        self._employee("بلا راتب")
        self.assertIn("بلا راتب", titles_of(self.alerts(), "employees_no_salary"))

    def test_employee_with_structure_is_not_alerted(self):
        employee = self._employee("بهيكل")
        SalaryStructure.objects.create(employee=employee, base_salary=Decimal("1000"))
        self.assertNotIn("بهيكل", titles_of(self.alerts(), "employees_no_salary"))

    def test_employee_with_base_salary_is_not_alerted(self):
        Employee.objects.create(name="براتب", branch=self.branch, base_salary=Decimal("900"))
        self.assertNotIn("براتب", titles_of(self.alerts(), "employees_no_salary"))

    def test_inactive_employee_is_not_alerted(self):
        Employee.objects.create(name="معطّل", branch=self.branch, is_active=False)
        self.assertNotIn("معطّل", titles_of(self.alerts(), "employees_no_salary"))


class AlertsPermissionTests(AlertsBase):
    def _deny(self, section):
        perms = dict(self.employee.permissions or {})
        perms[section] = {"view": False}
        self.employee.permissions = perms
        self.employee.save(update_fields=["permissions"])

    def test_hides_sections_user_cannot_view(self):
        PayrollRun.objects.create(month=date(2026, 3, 1))
        self.assertIn("payroll_draft", keys(self.alerts()))
        self._deny("payroll")
        self.assertNotIn("payroll_draft", keys(self.alerts()))

    def test_other_sections_survive_permission_denial(self):
        PayrollRun.objects.create(month=date(2026, 3, 1))
        self._roll(self._fabric("مخزون", min_stock=10), 1)
        self._deny("payroll")
        self.assertIn("stock_low", keys(self.alerts()))


class AlertsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user, self.employee = authenticate_admin(self.client)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/dashboard/alerts-center/").status_code, 401)

    def test_returns_summary_and_alerts(self):
        response = self.client.get("/api/dashboard/alerts-center/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("summary", payload)
        self.assertIn("alerts", payload)
        self.assertEqual(payload["summary"]["total"], len(payload["alerts"]))

    def test_summary_counts_match_alerts(self):
        payload = self.client.get("/api/dashboard/alerts-center/").json()
        for level in ("critical", "warning", "info"):
            expected = sum(1 for a in payload["alerts"] if a["severity"] == level)
            self.assertEqual(payload["summary"][level], expected)
            self.assertIn(level, payload["summary"])

    def test_legacy_alerts_endpoint_still_works(self):
        response = self.client.get("/api/dashboard/alerts/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("low_stock_count", response.json())
