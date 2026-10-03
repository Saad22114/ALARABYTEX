"""اختبارات حسابات التسوية: الرصيد = مبيعات القناة − الدفعات المستلمة.

القناتان المتتبَّعتان:
- ``machine``: مبيعات البطاقة (``card_amount``) — تنتظر تحويل شركة الماكينة.
- ``bank``: مبيعات التحويل (``transfer_amount``) — تصل إلى حسابنا البنكي.

النقدية تُستلم فوراً فلا حساب لها، و`other` غير متتبَّع هنا.
"""

from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from branches.models import Branch
from core.testsupport import authenticate_admin
from machine_account.models import MachineCollection
from sales.models import DailySale


class SettlementAccountTest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="B", code="B")
        self.algo = Branch.objects.create(name="ALGO", code="ALGO")
        self.range = {"date_from": "2026-03-01", "date_to": "2026-03-31"}

    def _sale(self, branch, card=0, transfer=0, date_str="2026-03-05"):
        return DailySale.objects.create(
            branch=branch,
            date=date.fromisoformat(date_str),
            total_sales=card + transfer,
            cash_amount=0,
            transfer_amount=transfer,
            card_amount=card,
            other_amount=0,
        )

    def _collection(self, amount, branch=None, date_str="2026-03-25", account="machine", **kw):
        data = {
            "branch": branch.id if branch else None,
            "date": date_str,
            "amount": amount,
            "method": "transfer",
            "reference": "REF-1",
            "account": account,
        }
        data.update(kw)
        return self.c.post("/api/machine-account/collections/", data, format="json")

    def _machine(self, response):
        return response.data["accounts"]["machine"]

    def _bank(self, response):
        return response.data["accounts"]["bank"]

    # ------------------------------------------------------------------ machine

    def test_machine_balance_is_card_sales_minus_received(self):
        self._sale(self.branch, card=1000)
        self._sale(self.algo, card=500)
        self._collection(400, branch=self.branch, account="machine")

        r = self.c.get("/api/machine-account/", self.range)
        self.assertEqual(r.status_code, 200)
        m = self._machine(r)
        self.assertEqual(m["sales"], 1500.0)
        self.assertEqual(m["received"], 400.0)
        self.assertEqual(m["balance"], 1100.0)

    def test_summary_scoped_to_branch(self):
        self._sale(self.branch, card=1000)
        self._sale(self.algo, card=500)
        r = self.c.get(
            "/api/machine-account/", {**self.range, "branch": self.branch.id}
        )
        self.assertEqual(self._machine(r)["sales"], 1000.0)
        self.assertEqual(self._machine(r)["balance"], 1000.0)
        # النطاق يقيّد البنك أيضاً
        self.assertEqual(self._bank(r)["sales"], 0.0)

    def test_recording_collection_reduces_balance(self):
        self._sale(self.branch, card=1000)
        self._collection(600, branch=self.branch, account="machine")
        r = self.c.get(
            "/api/machine-account/", {**self.range, "branch": self.branch.id}
        )
        self.assertEqual(self._machine(r)["received"], 600.0)
        self.assertEqual(self._machine(r)["balance"], 400.0)

    # --------------------------------------------------------------------- bank

    def test_bank_balance_is_transfer_sales_minus_received(self):
        self._sale(self.branch, transfer=700)
        self._collection(200, branch=self.branch, account="bank")

        r = self.c.get("/api/machine-account/", self.range)
        b = self._bank(r)
        self.assertEqual(b["sales"], 700.0)
        self.assertEqual(b["received"], 200.0)
        self.assertEqual(b["balance"], 500.0)

    def test_bank_and_machine_sales_do_not_mix(self):
        """تحويلٌ وبطاقة في نفس اليوم يُحسبان في حسابين منفصلين."""
        self._sale(self.branch, card=100, transfer=250)
        r = self.c.get("/api/machine-account/", self.range)
        self.assertEqual(self._machine(r)["sales"], 100.0)
        self.assertEqual(self._bank(r)["sales"], 250.0)

    def test_bank_collection_does_not_reduce_machine_balance(self):
        self._sale(self.branch, card=1000)
        self._collection(500, branch=self.branch, account="bank")

        r = self.c.get("/api/machine-account/", self.range)
        self.assertEqual(self._machine(r)["balance"], 1000.0)
        self.assertEqual(self._bank(r)["balance"], -500.0)

    def test_cash_sales_are_not_tracked_in_any_account(self):
        """النقدية تُستلم فوراً فلا تدخل حساب تسوية."""
        DailySale.objects.create(
            branch=self.branch,
            date=date(2026, 3, 5),
            total_sales=300,
            cash_amount=300,
            transfer_amount=0,
            card_amount=0,
            other_amount=0,
        )
        r = self.c.get("/api/machine-account/", self.range)
        self.assertEqual(self._machine(r)["sales"], 0.0)
        self.assertEqual(self._bank(r)["sales"], 0.0)

    # ----------------------------------------------------------------- combined

    def test_combined_sums_both_accounts(self):
        self._sale(self.branch, card=1000, transfer=300)
        self._collection(400, branch=self.branch, account="machine")
        self._collection(100, branch=self.branch, account="bank")

        r = self.c.get("/api/machine-account/", self.range)
        combined = r.data["combined"]
        self.assertEqual(combined["sales"], 1300.0)
        self.assertEqual(combined["received"], 500.0)
        self.assertEqual(combined["balance"], 800.0)

    def test_account_filter_narrows_the_response(self):
        self._sale(self.branch, card=1000, transfer=300)
        r = self.c.get("/api/machine-account/", {**self.range, "account": "bank"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.data["accounts"]), {"bank"})
        self.assertEqual(r.data["accounts"]["bank"]["sales"], 300.0)
        # الإجمالي المجمّع يبقى متسقاً مع الحساب المعروض وحده
        self.assertEqual(r.data["combined"]["sales"], 300.0)

    def test_unknown_account_is_rejected(self):
        r = self.c.get("/api/machine-account/", {**self.range, "account": "crypto"})
        self.assertEqual(r.status_code, 400)

    # -------------------------------------------------------------- collections

    def test_collection_rejected_when_not_positive(self):
        r = self._collection(0)
        self.assertEqual(r.status_code, 400)

    def test_collection_rejected_on_unknown_account(self):
        r = self._collection(100, account="crypto")
        self.assertEqual(r.status_code, 400)

    def test_collections_crud(self):
        r = self._collection(300)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["amount"], 300.0)
        self.assertEqual(r.data["account"], "machine")
        self.assertEqual(r.data["account_label"], "حساب الماكينة")
        cid = r.data["id"]

        lst = self.c.get("/api/machine-account/collections/")
        self.assertEqual(lst.data["count"], 1)

        r2 = self.c.delete(f"/api/machine-account/collections/{cid}/")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(MachineCollection.objects.count(), 0)

    def test_collections_filterable_by_account(self):
        self._collection(100, account="machine")
        self._collection(200, account="bank")

        machine = self.c.get("/api/machine-account/collections/", {"account": "machine"})
        self.assertEqual(machine.data["count"], 1)
        self.assertEqual(machine.data["results"][0]["amount"], 100.0)

        bank = self.c.get("/api/machine-account/collections/", {"account": "bank"})
        self.assertEqual(bank.data["count"], 1)
        self.assertEqual(bank.data["results"][0]["amount"], 200.0)

    def test_existing_rows_default_to_machine_account(self):
        """الدفعات القديمة بلا حساب تُحسب على الماكينة لا تُسقط من الأرصدة."""
        MachineCollection.objects.create(
            branch=self.branch, date=date(2026, 3, 25), amount=50, method="transfer"
        )
        self.assertEqual(MachineCollection.objects.get().account, "machine")

    def test_recent_collections_in_summary(self):
        self._sale(self.branch, card=1000)
        self._collection(250, branch=self.branch, account="machine")
        r = self.c.get("/api/machine-account/")
        self.assertEqual(r.status_code, 200)
        recent = r.data["recent_collections"]
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["amount"], 250.0)

    def test_recent_collections_respect_account_filter(self):
        self._collection(250, account="machine")
        self._collection(400, account="bank")
        r = self.c.get("/api/machine-account/", {"account": "bank"})
        recent = r.data["recent_collections"]
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["amount"], 400.0)

    # ------------------------------------------------------------------- trends

    def test_monthly_trend(self):
        self._sale(self.branch, card=800, date_str="2026-03-10")
        self._collection(200, branch=self.branch, date_str="2026-03-20", account="machine")
        self._sale(self.branch, card=500, date_str="2026-04-10")

        r = self.c.get(
            "/api/machine-account/",
            {"date_from": "2026-03-01", "date_to": "2026-04-30", "branch": self.branch.id},
        )
        months = {m["month"]: m for m in r.data["months"]}
        self.assertEqual(months["2026-03"]["accounts"]["machine"]["sales"], 800.0)
        self.assertEqual(months["2026-03"]["accounts"]["machine"]["received"], 200.0)
        self.assertEqual(months["2026-04"]["accounts"]["machine"]["sales"], 500.0)
        self.assertIn("2026-04", months)

    def test_monthly_trend_splits_both_accounts(self):
        self._sale(self.branch, card=800, transfer=400, date_str="2026-03-10")

        r = self.c.get("/api/machine-account/", self.range)
        months = {m["month"]: m for m in r.data["months"]}
        self.assertEqual(months["2026-03"]["accounts"]["machine"]["sales"], 800.0)
        self.assertEqual(months["2026-03"]["accounts"]["bank"]["sales"], 400.0)

    # ---------------------------------------------- تحويل من الماكينة إلى البنك

    def _transfer(self, amount, branch=None, date_str="2026-03-26", **kw):
        data = {
            "amount": amount,
            "branch": branch.id if branch else None,
            "date": date_str,
            "reference": "TRF-9",
        }
        data.update(kw)
        return self.c.post(
            "/api/machine-account/collections/transfer/", data, format="json"
        )

    def test_transfer_moves_money_out_of_the_machine(self):
        self._sale(self.branch, card=1000)
        r = self._transfer(400, branch=self.branch)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["transferred"], 400.0)
        self.assertEqual(r.data["machine_remaining"], 600.0)

        row = MachineCollection.objects.get()
        self.assertEqual(row.account, "machine")
        self.assertEqual(row.method, "transfer")
        self.assertEqual(row.reference, "TRF-9")

        # ثم يظهر في جدول الدفعات والرصيدُ ينقص كما ينقص أي إيداع.
        self.assertEqual(
            self.c.get("/api/machine-account/collections/").data["count"], 1
        )
        r2 = self.c.get("/api/machine-account/", {**self.range, "branch": self.branch.id})
        self.assertEqual(self._machine(r2)["balance"], 600.0)

    def test_transfer_cannot_exceed_what_the_machine_holds(self):
        """السقفُ ليس زينةً في الشاشة: هو ما في الماكينة فعلاً.

        ولو سمحنا بأكثر منه لأمكن تسجيل دفعةٍ لا تسدِّد شيئاً، فيبقى الرصيدُ
        موجباً كما لو أنّ المال لم يتحرّك — ويظنّ المحلّ أنّ ما في الماكينة
        أكبرُ ممّا هو فيه.
        """
        self._sale(self.branch, card=1000)
        r = self._transfer(1001, branch=self.branch)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["available"], 1000.0)
        self.assertEqual(MachineCollection.objects.count(), 0)

    def test_transfer_rejected_when_the_machine_is_empty(self):
        self._sale(self.branch, card=0)
        r = self._transfer(1, branch=self.branch)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(MachineCollection.objects.count(), 0)

    def test_transfer_limit_spans_older_sales(self):
        """السقفُ رصيدٌ متراكم، لا رصيدُ الشهر المعروض.

        الصندوقُ لا يُفرَّغ كلَّ شهر. فلو قِسناه بالفترة المعروضة لأمكن في
        فبراير تحويلُ مالَ يناير كلِّه ثم تحويلُه مرّةً أخرى في فبراير.
        """
        self._sale(self.branch, card=800, date_str="2026-01-10")
        self._sale(self.branch, card=500, date_str="2026-03-10")

        self.assertEqual(self._transfer(1300, branch=self.branch).status_code, 201)
        self.assertEqual(self._transfer(1, branch=self.branch).status_code, 400)

    def test_transfer_does_not_spend_another_branchs_money(self):
        self._sale(self.branch, card=1000)
        r = self._transfer(500, branch=self.algo)
        self.assertEqual(r.status_code, 400)
        r2 = self._transfer(500, branch=self.branch)
        self.assertEqual(r2.status_code, 201)

    def test_transfer_rejects_nonsense_amounts(self):
        self._sale(self.branch, card=1000)
        for bad in (0, -5, None, "abc"):
            with self.subTest(amount=bad):
                r = self._transfer(bad, branch=self.branch)
                self.assertEqual(r.status_code, 400)
        self.assertEqual(MachineCollection.objects.count(), 0)

    def test_transfer_falls_back_to_today_on_a_bad_date(self):
        self._sale(self.branch, card=1000)
        r = self._transfer(100, branch=self.branch, date_str="not-a-date")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(MachineCollection.objects.get().date, date.today())
