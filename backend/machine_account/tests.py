"""اختبارات حساب ماكينة البطاقات: الرصيد = مبيعات البطاقة - الدفعات المستلمة."""

from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from branches.models import Branch
from core.testsupport import authenticate_admin
from machine_account.models import MachineCollection
from sales.models import DailySale


class MachineAccountTest(TestCase):
    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.branch = Branch.objects.create(name="B", code="B")
        self.algo = Branch.objects.create(name="ALGO", code="ALGO")

    def _sale(self, branch, card=0, date_str="2026-03-05"):
        return DailySale.objects.create(
            branch=branch, date=date.fromisoformat(date_str),
            total_sales=card, cash_amount=0, transfer_amount=0,
            card_amount=card, other_amount=0,
        )

    def _collection(self, amount, branch=None, date_str="2026-03-25", **kw):
        data = {
            "branch": branch.id if branch else None,
            "date": date_str,
            "amount": amount,
            "method": "transfer",
            "reference": "REF-1",
        }
        data.update(kw)
        return self.c.post("/api/machine-account/collections/", data, format="json")

    def test_summary_balance_is_card_sales_minus_received(self):
        self._sale(self.branch, card=1000)
        self._sale(self.algo, card=500)  # خارج الفترة إذا حددنا فرعاً
        self._collection(400, branch=self.branch)

        r = self.c.get("/api/machine-account/", {
            "date_from": "2026-03-01",
            "date_to": "2026-03-31",
        })
        self.assertEqual(r.status_code, 200)
        t = r.data["totals"]
        self.assertEqual(t["card_sales"], 1500.0)
        self.assertEqual(t["received"], 400.0)
        self.assertEqual(t["balance"], 1100.0)

    def test_summary_scoped_to_branch(self):
        self._sale(self.branch, card=1000)
        self._sale(self.algo, card=500)
        r = self.c.get("/api/machine-account/", {
            "date_from": "2026-03-01",
            "date_to": "2026-03-31",
            "branch": self.branch.id,
        })
        self.assertEqual(r.data["totals"]["card_sales"], 1000.0)
        self.assertEqual(r.data["totals"]["balance"], 1000.0)

    def test_recording_collection_reduces_balance(self):
        self._sale(self.branch, card=1000)
        self._collection(600, branch=self.branch)
        r = self.c.get("/api/machine-account/", {
            "date_from": "2026-03-01",
            "date_to": "2026-03-31",
            "branch": self.branch.id,
        })
        self.assertEqual(r.data["totals"]["received"], 600.0)
        self.assertEqual(r.data["totals"]["balance"], 400.0)

    def test_collection_rejected_when_not_positive(self):
        r = self._collection(0)
        self.assertEqual(r.status_code, 400)

    def test_collections_crud(self):
        r = self._collection(300)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["amount"], 300.0)
        cid = r.data["id"]

        lst = self.c.get("/api/machine-account/collections/")
        self.assertEqual(lst.data["count"], 1)

        r2 = self.c.delete(f"/api/machine-account/collections/{cid}/")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(MachineCollection.objects.count(), 0)

    def test_recent_collections_in_summary(self):
        self._sale(self.branch, card=1000)
        self._collection(250, branch=self.branch)
        r = self.c.get("/api/machine-account/")
        self.assertEqual(r.status_code, 200)
        recent = r.data["recent_collections"]
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["amount"], 250.0)

    def test_monthly_trend(self):
        self._sale(self.branch, card=800, date_str="2026-03-10")
        self._collection(200, branch=self.branch, date_str="2026-03-20")
        self._sale(self.branch, card=500, date_str="2026-04-10")

        r = self.c.get("/api/machine-account/", {
            "date_from": "2026-03-01",
            "date_to": "2026-04-30",
            "branch": self.branch.id,
        })
        months = {m["month"]: m for m in r.data["months"]}
        self.assertEqual(months["2026-03"]["card_sales"], 800.0)
        self.assertEqual(months["2026-03"]["received"], 200.0)
        self.assertEqual(months["2026-04"]["card_sales"], 500.0)
        # 2026-03 .. 2026-04 كلاهما ضمن الفترة ويظهران في الاتجاه.
        self.assertIn("2026-04", months)