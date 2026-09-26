from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounting.models import JournalEntry, JournalLine
from branches.models import Branch
from core.testsupport import authenticate_admin
from payroll.models import (
    AdvanceInstallment,
    Payslip,
    PayrollRun,
    SalaryAdvance,
    SalaryStructure,
)
from payroll.services import month_bounds, salary_snapshot
from sale_sessions.models import Employee, SaleSession


class PayrollTestBase(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.user, self.admin = authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="فرع payroll", code="PRL")
        self.emp = Employee.objects.create(name="موظف رواتب", branch=self.branch, base_salary=1000)
        self.month = month_bounds("2026-03")[0]
        self.month_str = self.month.isoformat()

    def _structure(self, **kwargs):
        data = {
            "employee": self.emp.id,
            "base_salary": "2000",
            "housing_allowance": "300",
            "transport_allowance": "200",
            "other_allowance": "0",
            "effective_from": "2026-01-01",
        }
        data.update(kwargs)
        return self.c.post("/api/payroll/salary-structures/", data, format="json")

    def _advance(self, amount="500", **kwargs):
        data = {
            "employee": self.emp.id,
            "amount": amount,
            "date": "2026-03-05",
            "method": "cash",
            "reason": "سلفة اختبار",
        }
        data.update(kwargs)
        return self.c.post("/api/payroll/advances/", data, format="json")


    def _advance_id(self, amount="500", **kwargs):
        r = self._advance(amount, **kwargs)
        self.assertEqual(r.status_code, 201, r.data)
        return r.data["id"]

    def _payslip(self, run_id):
        return Payslip.objects.get(run_id=run_id, employee=self.emp)

    def _row(self, response):
        return next(r for r in response["rows"] if r["employee"] == self.emp.id)


class SalaryStructureTests(PayrollTestBase):
    def test_create_structure_and_snapshot(self):
        r = self._structure()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(str(r.data["gross"])), Decimal("2500.00"))
        self.assertEqual(Decimal(str(r.data["total_allowances"])), Decimal("500.00"))
        snap = salary_snapshot(self.emp, date(2026, 3, 1))
        self.assertEqual(snap["base_salary"], Decimal("2000.00"))
        self.assertTrue(snap["has_structure"])

    def test_snapshot_falls_back_to_employee_base_salary(self):
        snap = salary_snapshot(self.emp, date(2026, 3, 1))
        self.assertEqual(snap["base_salary"], Decimal("1000.00"))
        self.assertFalse(snap["has_structure"])

    def test_latest_effective_structure_wins(self):
        self._structure(base_salary="2000", effective_from="2026-01-01")
        self._structure(base_salary="3000", effective_from="2026-03-01")
        snap = salary_snapshot(self.emp, date(2026, 3, 15))
        self.assertEqual(snap["base_salary"], Decimal("3000.00"))

    def test_duplicate_effective_date_rejected(self):
        self._structure(effective_from="2026-01-01")
        r = self._structure(effective_from="2026-01-01")
        self.assertEqual(r.status_code, 400)

    def test_inactive_employee_rejected(self):
        self.emp.is_active = False
        self.emp.save(update_fields=["is_active"])
        r = self._structure()
        self.assertEqual(r.status_code, 400)


class AdvanceTests(PayrollTestBase):
    def test_create_and_approve_posts_journal(self):
        r = self._advance()
        self.assertEqual(r.status_code, 201, r.data)
        aid = r.data["id"]
        self.assertEqual(SalaryAdvance.objects.get(id=aid).status, SalaryAdvance.Status.PENDING)

        r = self.c.post(f"/api/payroll/advances/{aid}/approve/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], SalaryAdvance.Status.APPROVED)

        entry = JournalEntry.objects.filter(
            source=JournalEntry.Source.SALARY_ADVANCE, source_id=aid
        ).first()
        self.assertIsNotNone(entry)
        lines = JournalLine.objects.filter(entry=entry)
        debit = sum(l.debit for l in lines)
        credit = sum(l.credit for l in lines)
        self.assertEqual(debit, credit)
        self.assertEqual(debit, Decimal("500.00"))

    def test_partial_and_full_repayment(self):
        aid = self._advance_id("500")
        self.c.post(f"/api/payroll/advances/{aid}/approve/", {}, format="json")

        r = self.c.post(
            f"/api/payroll/advances/{aid}/repay/",
            {"amount": "200", "method": "cash"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        advance = SalaryAdvance.objects.get(id=aid)
        self.assertEqual(advance.remaining_amount, Decimal("300.00"))
        self.assertEqual(advance.recovered_amount, Decimal("200.00"))

        self.c.post(
            f"/api/payroll/advances/{aid}/repay/",
            {"amount": "300", "method": "transfer"},
            format="json",
        )
        advance.refresh_from_db()
        self.assertEqual(advance.remaining_amount, Decimal("0.00"))
        self.assertTrue(advance.is_settled)
        self.assertEqual(advance.status, SalaryAdvance.Status.SETTLED)

    def test_repay_more_than_remaining_is_capped(self):
        aid = self._advance_id("500")
        self.c.post(f"/api/payroll/advances/{aid}/approve/", {}, format="json")
        r = self.c.post(
            f"/api/payroll/advances/{aid}/repay/", {"amount": "900"}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(str(r.data["advance"]["remaining_amount"])), Decimal("0.00"))

    def test_reject_unposts_journal(self):
        aid = self._advance_id()
        self.c.post(f"/api/payroll/advances/{aid}/approve/", {}, format="json")
        self.c.post(f"/api/payroll/advances/{aid}/reject/", {}, format="json")
        self.assertEqual(
            JournalEntry.objects.filter(
                source=JournalEntry.Source.SALARY_ADVANCE, source_id=aid
            ).count(),
            0,
        )
        self.assertEqual(SalaryAdvance.objects.get(id=aid).status, SalaryAdvance.Status.REJECTED)

    def test_delete_with_installments_blocked(self):
        aid = self._advance_id()
        self.c.post(f"/api/payroll/advances/{aid}/approve/", {}, format="json")
        self.c.post(f"/api/payroll/advances/{aid}/repay/", {"amount": "100"}, format="json")
        r = self.c.delete(f"/api/payroll/advances/{aid}/")
        self.assertEqual(r.status_code, 400)

    def test_zero_amount_rejected(self):
        r = self._advance(amount="0")
        self.assertEqual(r.status_code, 400)

    def test_status_cannot_be_changed_directly(self):
        aid = self._advance_id()
        r = self.c.patch(
            f"/api/payroll/advances/{aid}/", {"status": "approved"}, format="json"
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(SalaryAdvance.objects.get(id=aid).status, SalaryAdvance.Status.PENDING)

    def test_outstanding_filter(self):
        self._advance("300")
        self.c.post("/api/payroll/advances/", {
            "employee": self.emp.id, "amount": "100", "date": "2026-03-06",
        }, format="json")
        r = self.c.get("/api/payroll/advances/", {"outstanding": "1"})
        self.assertEqual(r.data["count"], 2)
        aid = r.data["results"][0]["id"]
        self.c.post(f"/api/payroll/advances/{aid}/approve/", {}, format="json")
        self.c.post(f"/api/payroll/advances/{aid}/repay/", {"amount": "100"}, format="json")
        r = self.c.get("/api/payroll/advances/", {"outstanding": "1"})
        self.assertEqual(r.data["count"], 1)


class PayrollRunTests(PayrollTestBase):
    def _closed_session(self, commission="150"):
        session = SaleSession.objects.create(
            employee=self.emp,
            branch=self.branch,
            status=SaleSession.Status.CLOSED,
            closed_at=date(2026, 3, 10),
            session_date=date(2026, 3, 10),
            commission_amount=Decimal(commission),
        )
        return session

    def test_preview_includes_structure_commission_and_advances(self):
        self._structure()
        self._closed_session("150")
        aid = self._advance_id("500")
        self.c.post(f"/api/payroll/advances/{aid}/approve/", {}, format="json")
        r = self.c.get("/api/payroll/preview/", {"month": self.month_str})
        self.assertEqual(r.status_code, 200)
        row = self._row(r.data)
        self.assertEqual(row["employee_name"], "موظف رواتب")
        self.assertEqual(row["commission_amount"], 150.0)
        self.assertEqual(row["advances_total"], 500.0)
        self.assertEqual(row["gross"], 2500.0)

    def test_preview_ignores_pending_advance(self):
        self._structure()
        self._advance("500")
        r = self.c.get("/api/payroll/preview/", {"month": self.month_str})
        self.assertEqual(self._row(r.data)["advances_total"], 0.0)

    def test_generate_run_creates_payslips(self):
        self._structure()
        self._closed_session("150")
        r = self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        run = PayrollRun.objects.get(id=r.data["id"])
        payslip = self._payslip(run.id)
        self.assertEqual(payslip.base_salary, Decimal("2000.00"))
        self.assertEqual(payslip.commission_amount, Decimal("150.00"))
        self.assertEqual(payslip.gross, Decimal("2650.00"))

    def test_duplicate_run_rejected(self):
        self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json")
        r = self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_approve_settles_advances(self):
        self._structure()
        aid = self._advance_id("500")
        self.c.post(f"/api/payroll/advances/{aid}/approve/", {}, format="json")
        run_id = self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json").data["id"]

        r = self.c.post(f"/api/payroll/runs/{run_id}/approve/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], PayrollRun.Status.APPROVED)

        payslip = self._payslip(run_id)
        self.assertEqual(payslip.advance_deduction, Decimal("500.00"))
        self.assertEqual(payslip.net_pay, Decimal("2000.00"))
        self.assertEqual(AdvanceInstallment.objects.filter(payslip=payslip).count(), 1)
        advance = SalaryAdvance.objects.get(id=aid)
        self.assertEqual(advance.remaining_amount, Decimal("0.00"))
        self.assertTrue(advance.is_settled)

    def test_cancel_restores_settled_advance(self):
        self._structure()
        aid = self._advance_id("500")
        self.c.post(f"/api/payroll/advances/{aid}/approve/", {}, format="json")
        run_id = self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json").data["id"]
        self.c.post(f"/api/payroll/runs/{run_id}/approve/", {}, format="json")
        self.assertEqual(SalaryAdvance.objects.get(id=aid).status, SalaryAdvance.Status.SETTLED)

        self.c.post(f"/api/payroll/runs/{run_id}/cancel/", {}, format="json")
        advance = SalaryAdvance.objects.get(id=aid)
        self.assertEqual(advance.status, SalaryAdvance.Status.APPROVED)
        self.assertEqual(advance.remaining_amount, Decimal("500.00"))
        self.assertIsNone(advance.settled_at)

    def test_pay_run_journal_balances_with_advance_deduction(self):
        self._structure()
        aid = self._advance_id("500")
        self.c.post(f"/api/payroll/advances/{aid}/approve/", {}, format="json")
        run_id = self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json").data["id"]
        r = self.c.post(f"/api/payroll/runs/{run_id}/pay/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.data)

        entry = JournalEntry.objects.filter(
            source=JournalEntry.Source.PAYROLL, source_id=run_id
        ).first()
        self.assertIsNotNone(entry)
        lines = list(JournalLine.objects.filter(entry=entry))
        debit = sum(l.debit for l in lines)
        credit = sum(l.credit for l in lines)
        self.assertEqual(debit, credit)
        self.assertEqual(debit, Decimal("2500.00"))

    def test_pay_run_marks_paid_and_posts_journal(self):
        self._structure()
        run_id = self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json").data["id"]
        r = self.c.post(
            f"/api/payroll/runs/{run_id}/pay/", {"payment_method": "cash"}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], PayrollRun.Status.PAID)
        self.assertTrue(self._payslip(run_id).is_paid)

        entry = JournalEntry.objects.filter(
            source=JournalEntry.Source.PAYROLL, source_id=run_id
        ).first()
        self.assertIsNotNone(entry)
        lines = JournalLine.objects.filter(entry=entry)
        self.assertEqual(
            sum(l.debit for l in lines), sum(l.credit for l in lines)
        )
        self.assertEqual(sum(l.debit for l in lines), Decimal("2500.00"))

    def test_cancel_deletes_payslips(self):
        self._structure()
        run_id = self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json").data["id"]
        r = self.c.post(f"/api/payroll/runs/{run_id}/cancel/", {}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Payslip.objects.filter(run_id=run_id).count(), 0)
        self.assertEqual(PayrollRun.objects.get(id=run_id).status, PayrollRun.Status.CANCELLED)

    def test_cannot_pay_cancelled_run(self):
        self._structure()
        run_id = self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json").data["id"]
        self.c.post(f"/api/payroll/runs/{run_id}/cancel/", {}, format="json")
        r = self.c.post(f"/api/payroll/runs/{run_id}/pay/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_payslip_edit_blocked_after_approval(self):
        self._structure()
        run_id = self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json").data["id"]
        self.c.post(f"/api/payroll/runs/{run_id}/approve/", {}, format="json")
        payslip = self._payslip(run_id)
        r = self.c.patch(
            f"/api/payroll/payslips/{payslip.id}/", {"bonus": "100"}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_payslip_editable_in_draft(self):
        self._structure()
        run_id = self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json").data["id"]
        payslip = self._payslip(run_id)
        r = self.c.patch(
            f"/api/payroll/payslips/{payslip.id}/", {"bonus": "100", "absence_days": "2"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        # 2500 + 100 مكافأة - (يومان × 76.92)
        self.assertEqual(Decimal(str(r.data["absence_deduction"])), Decimal("153.84"))
        self.assertEqual(Decimal(str(r.data["net_pay"])), Decimal("2446.16"))

    def test_overtime_computed_from_rate(self):
        self._structure(overtime_hour_rate="10")
        run_id = self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json").data["id"]
        payslip = self._payslip(run_id)
        r = self.c.patch(
            f"/api/payroll/payslips/{payslip.id}/", {"overtime_hours": "5"}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(str(r.data["overtime_amount"])), Decimal("50.00"))
        self.assertEqual(Decimal(str(r.data["net_pay"])), Decimal("2550.00"))

    def test_summary_endpoint(self):
        self._structure()
        self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json")
        r = self.c.get("/api/payroll/summary/", {"month": self.month_str})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["gross"], 2500.0)
        self.assertEqual(r.data["runs"], 1)
        self.assertEqual(r.data["pending_runs"], 1)
        self.assertNotIn(self.emp.id, r.data["missing_structures"])

    def test_employees_endpoint_snapshot(self):
        self._structure()
        r = self.c.get("/api/payroll/employees/", {"month": self.month_str})
        self.assertEqual(r.status_code, 200)
        row = self._row(r.data)
        self.assertEqual(row["gross"], 2500.0)
        self.assertTrue(row["has_structure"])

    def test_run_export_xlsx(self):
        self._structure()
        run_id = self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json").data["id"]
        r = self.c.get(f"/api/payroll/runs/{run_id}/export/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])

    def test_advances_export_xlsx(self):
        self._advance("100")
        r = self.c.get("/api/payroll/export/advances/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])

    def test_statement_endpoint(self):
        self._structure()
        self._advance("300")
        run_id = self.c.post("/api/payroll/runs/", {"month": self.month_str}, format="json").data["id"]
        self.c.post(f"/api/payroll/runs/{run_id}/pay/", {}, format="json")
        r = self.c.get(
            f"/api/payroll/employees/{self.emp.id}/statement/",
            {"date_from": "2026-01-01", "date_to": "2026-12-31"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Decimal(str(r.data["totals"]["net_paid"])), Decimal("2500.00"))
        self.assertEqual(Decimal(str(r.data["totals"]["advances"])), Decimal("300.00"))


class PayrollPermissionTests(PayrollTestBase):
    def test_viewer_can_view_but_not_pay(self):
        from django.contrib.auth.models import User

        user = User.objects.create_user(username="viewer_pr", password="pass1234")
        emp = Employee.objects.create(name="مشاهد رواتب", user=user, branch=self.branch)
        emp.apply_role_preset(Employee.Role.VIEWER)
        emp.save()
        self.c.force_authenticate(user=user)

        r = self.c.get("/api/payroll/advances/")
        self.assertEqual(r.status_code, 200)
        r = self.c.post("/api/payroll/advances/", {
            "employee": self.emp.id, "amount": "100", "date": "2026-03-05",
        }, format="json")
        self.assertEqual(r.status_code, 403)

    def test_section_hidden_without_permission(self):
        from django.contrib.auth.models import User

        user = User.objects.create_user(username="sales_pr", password="pass1234")
        emp = Employee.objects.create(name="مندوب رواتب", user=user, branch=self.branch)
        emp.apply_role_preset(Employee.Role.SALES)
        emp.save()
        self.c.force_authenticate(user=user)
        r = self.c.get("/api/payroll/advances/")
        self.assertEqual(r.status_code, 403)

    def test_branch_scope_limits_runs(self):
        from django.contrib.auth.models import User

        other = Branch.objects.create(name="فرع آخر", code="PRL2")
        self.c.post("/api/payroll/runs/", {"month": self.month_str, "branch": other.id}, format="json")
        user = User.objects.create_user(username="scoped_pr", password="pass1234")
        emp = Employee.objects.create(name="محدود الفرع", user=user, branch=self.branch)
        emp.apply_role_preset(Employee.Role.ADMIN)
        emp.save()
        emp.role = Employee.Role.VIEWER
        emp.permissions["payroll"]["view"] = True
        emp.permissions["payroll"]["create"] = False
        emp.save()
        self.c.force_authenticate(user=user)
        r = self.c.get("/api/payroll/runs/")
        self.assertEqual(r.data["count"], 0)

    def test_statement_outside_branch_scope_is_hidden(self):
        from django.contrib.auth.models import User

        other = Branch.objects.create(name="فرع كشف", code="PRL3")
        outsider = Employee.objects.create(name="موظف فرع آخر", branch=other)
        user = User.objects.create_user(username="stmt_pr", password="pass1234")
        emp = Employee.objects.create(name="مشاهد كشف", user=user, branch=self.branch)
        emp.apply_role_preset(Employee.Role.VIEWER)
        emp.save()
        self.c.force_authenticate(user=user)
        r = self.c.get(f"/api/payroll/employees/{outsider.id}/statement/")
        self.assertEqual(r.status_code, 404)
        r = self.c.get(f"/api/payroll/export/statement/{self.emp.id}/")
        self.assertEqual(r.status_code, 200)
