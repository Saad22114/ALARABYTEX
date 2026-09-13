from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Partner, PartnerOperation, PartnerMovement


class PartnerCRUDTests(APITestCase):
    def setUp(self):
        self.p1 = Partner.objects.create(name="أحمد", share_percent=Decimal("60.00"))
        self.p2 = Partner.objects.create(name="محمد", share_percent=Decimal("40.00"))

    def _create(self, **overrides):
        return self.client.post(
            "/api/partners/",
            {"name": "شريك جديد", "share_percent": 50, **overrides},
            format="json",
        )

    def test_create(self):
        resp = self._create()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        self.assertEqual(resp.data["name"], "شريك جديد")
        self.assertEqual(float(resp.data["share_percent"]), 50.0)
        self.assertEqual(resp.data["total_support"], 0.0)
        self.assertEqual(resp.data["net_balance"], 0.0)

    def test_list(self):
        resp = self.client.get("/api/partners/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 2)

    def test_retrieve(self):
        resp = self.client.get(f"/api/partners/{self.p1.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["name"], "أحمد")

    def test_update(self):
        resp = self.client.patch(
            f"/api/partners/{self.p1.id}/",
            {"share_percent": 55},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(float(resp.data["share_percent"]), 55.0)

    def test_delete_no_movements(self):
        p = Partner.objects.create(name="مؤقت", share_percent=50)
        resp = self.client.delete(f"/api/partners/{p.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Partner.objects.filter(pk=p.pk).exists())

    def test_delete_guarded_with_movements(self):
        op = PartnerOperation.objects.create(
            number="TRP-2026-9999", date=date.today(),
            partner=self.p1, operation_type="support", amount=100,
        )
        PartnerMovement.objects.create(
            operation=op, partner=self.p1, movement_type="support", amount=100
        )
        resp = self.client.delete(f"/api/partners/{self.p1.id}/")
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(Partner.objects.filter(pk=self.p1.pk).exists())

    def test_share_validation(self):
        resp = self._create(share_percent=0)
        self.assertEqual(resp.status_code, 400)
        resp = self._create(share_percent=101)
        self.assertEqual(resp.status_code, 400)


class PartnerOperationTests(APITestCase):
    def setUp(self):
        self.p1 = Partner.objects.create(name="شريك أول", share_percent=50)
        self.p2 = Partner.objects.create(name="شريك ثاني", share_percent=50)

    def _create_op(self, partner=None, **overrides):
        payload = {
            "partner": partner.id if partner else self.p1.id,
            "date": str(timezone.localdate()),
            "operation_type": "support",
            "amount": 1000,
        }
        payload.update(overrides)
        return self.client.post(
            "/api/partner-operations/",
            payload,
            format="json",
        )

    def test_create_required_partner(self):
        resp = self.client.post(
            "/api/partner-operations/",
            {"date": str(timezone.localdate()), "operation_type": "support", "amount": 100},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_support_single_movement_for_partner(self):
        resp = self._create_op(amount=1000)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        self.assertEqual(resp.data["operation_type"], "support")
        self.assertEqual(resp.data["partner"], self.p1.id)
        self.assertEqual(resp.data["partner_name"], "شريك أول")
        self.assertEqual(float(resp.data["amount"]), 1000.0)
        movements = resp.data["movements"]
        self.assertEqual(len(movements), 1)
        self.assertEqual(movements[0]["partner"], self.p1.id)
        self.assertEqual(movements[0]["movement_type"], "support")
        self.assertEqual(movements[0]["movement_type_label"], "دعم")
        self.assertEqual(float(movements[0]["amount"]), 1000.0)
        self.assertEqual(PartnerOperation.objects.count(), 1)

    def test_create_withdraw_single_movement_for_partner(self):
        resp = self._create_op(operation_type="withdraw", amount=500)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        movements = resp.data["movements"]
        self.assertEqual(len(movements), 1)
        self.assertEqual(movements[0]["partner"], self.p1.id)
        self.assertEqual(movements[0]["movement_type"], "withdraw")
        self.assertEqual(resp.data["operation_type"], "withdraw")

    def test_number_sequential(self):
        r1 = self._create_op(amount=500)
        r2 = self._create_op(amount=300)
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r1.data["number"], "TRP-2026-0001")
        self.assertEqual(r2.data["number"], "TRP-2026-0002")

    def test_list_operations(self):
        self._create_op()
        resp = self.client.get("/api/partner-operations/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(len(resp.data["results"][0]["movements"]), 1)

    def test_filter_by_date(self):
        old = date.today() - timedelta(days=30)
        op1 = PartnerOperation.objects.create(
            number="TRP-2026-1111", date=old, partner=self.p1,
            operation_type="withdraw", amount=200,
        )
        PartnerMovement.objects.bulk_create([
            PartnerMovement(operation=op1, partner=p, movement_type="withdraw", amount=200)
            for p in [self.p1, self.p2]
        ])
        op2 = PartnerOperation.objects.create(
            number="TRP-2026-2222", date=date.today(), partner=self.p1,
            operation_type="support", amount=500,
        )
        PartnerMovement.objects.bulk_create([
            PartnerMovement(operation=op2, partner=p, movement_type="support", amount=500)
            for p in [self.p1, self.p2]
        ])
        resp = self.client.get(f"/api/partner-operations/?date_from={old}&date_to={old}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["operation_type"], "withdraw")

    def test_delete_operation(self):
        r = self._create_op()
        op_id = r.data["id"]
        self.assertEqual(PartnerMovement.objects.count(), 1)
        resp = self.client.delete(f"/api/partner-operations/{op_id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(PartnerOperation.objects.filter(pk=op_id).exists())
        self.assertEqual(PartnerMovement.objects.count(), 0)

    def test_balance_annotations(self):
        self._create_op(amount=1000)
        self._create_op(operation_type="withdraw", amount=300)
        resp1 = self.client.get(f"/api/partners/{self.p1.id}/")
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.data["total_support"], 1000.0)
        self.assertEqual(resp1.data["total_withdraw"], 300.0)
        self.assertEqual(resp1.data["net_balance"], 700.0)
        resp2 = self.client.get(f"/api/partners/{self.p2.id}/")
        self.assertEqual(resp2.data["total_support"], 0.0)
        self.assertEqual(resp2.data["total_withdraw"], 0.0)
        self.assertEqual(resp2.data["net_balance"], 0.0)

    def test_create_rejects_inactive_partner(self):
        self.p2.is_active = False
        self.p2.save()
        resp = self._create_op(partner=self.p2)
        self.assertEqual(resp.status_code, 400)

    def test_operations_summary(self):
        self._create_op(amount=1000)
        self._create_op(operation_type="withdraw", amount=300)
        resp = self.client.get("/api/partner-operations/summary/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 2)
        self.assertEqual(float(resp.data["total_amount"]), 1300.0)
        self.assertEqual(resp.data["support_count"], 1)
        self.assertEqual(float(resp.data["support_amount"]), 1000.0)
        self.assertEqual(resp.data["withdraw_count"], 1)
        self.assertEqual(float(resp.data["withdraw_amount"]), 300.0)
        self.assertEqual(float(resp.data["net"]), 700.0)
        today = str(timezone.localdate())
        resp = self.client.get(f"/api/partner-operations/summary/?partner={self.p1.id}&date_from={today}&date_to={today}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 2)

    def test_operations_list_export_xlsx(self):
        self._create_op(amount=500)
        resp = self.client.get("/api/partner-operations/?export=xlsx")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml.sheet", resp.headers["Content-Type"])

    def test_operations_filter_by_partner(self):
        self._create_op(partner=self.p1, amount=500)
        resp = self.client.get(f"/api/partner-operations/?partner={self.p2.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 0)

    def test_create_rejects_zero_amount(self):
        resp = self._create_op(amount=0)
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_negative_amount(self):
        resp = self._create_op(amount=-50)
        self.assertEqual(resp.status_code, 400)

    def test_create_with_payment_method_and_reason(self):
        resp = self._create_op(
            amount=800,
            payment_method="transfer",
            reason="سداد راتب للموظفين",
            notes="ملاحظة إضافية",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["payment_method"], "transfer")
        self.assertEqual(resp.data["payment_method_label"], "تحويل بنكي")
        self.assertEqual(resp.data["reason"], "سداد راتب للموظفين")
        self.assertEqual(resp.data["notes"], "ملاحظة إضافية")
        self.assertEqual(float(resp.data["amount"]), 800.0)


class PartnerMovementReportTests(APITestCase):
    def setUp(self):
        self.p1 = Partner.objects.create(name="شريك أول", share_percent=50)
        self.p2 = Partner.objects.create(name="شريك ثاني", share_percent=50)

    def _op(self, partner, date, op_type, amount, **extra):
        resp = self.client.post(
            "/api/partner-operations/",
            {"partner": partner.id, "date": str(date), "operation_type": op_type, "amount": amount, **extra},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        return resp.data["id"]

    def test_movements_running_balance(self):
        self._op(self.p1, date.today() - timedelta(days=20), "support", 500)
        self._op(self.p1, date.today() - timedelta(days=10), "support", 500)
        self._op(self.p1, date.today(), "withdraw", 300)
        resp = self.client.get(f"/api/partners/{self.p1.id}/movements/")
        self.assertEqual(resp.status_code, 200)
        moves = resp.data["movements"]
        self.assertEqual(len(moves), 3)
        self.assertEqual(float(moves[0]["running_balance"]), 500.0)
        self.assertEqual(float(moves[1]["running_balance"]), 1000.0)
        self.assertEqual(float(moves[2]["running_balance"]), 700.0)
        self.assertEqual(float(resp.data["opening_balance"]), 0.0)
        self.assertEqual(float(resp.data["closing_balance"]), 700.0)
        self.assertEqual(float(resp.data["totals"]["total_support"]), 1000.0)
        self.assertEqual(float(resp.data["totals"]["total_withdraw"]), 300.0)
        self.assertEqual(float(resp.data["totals"]["net"]), 700.0)
        self.assertEqual(resp.data["partner"]["name"], "شريك أول")

    def test_other_partner_has_no_movement(self):
        self._op(self.p1, date.today(), "withdraw", 300)
        r2 = self.client.get(f"/api/partners/{self.p2.id}/movements/")
        self.assertEqual(r2.data["movements"], [])
        self.assertEqual(float(r2.data["closing_balance"]), 0.0)
        r1 = self.client.get(f"/api/partners/{self.p1.id}/movements/")
        self.assertEqual(len(r1.data["movements"]), 1)
        self.assertEqual(r1.data["movements"][0]["movement_type"], "withdraw")
        self.assertEqual(float(r1.data["movements"][0]["running_balance"]), -300.0)
        self.assertEqual(float(r1.data["closing_balance"]), -300.0)

    def test_movements_openings_and_date_filter(self):
        self._op(self.p1, date.today() - timedelta(days=40), "support", 1000)
        self._op(self.p1, date.today() - timedelta(days=5), "support", 400)
        self._op(self.p1, date.today(), "withdraw", 100)
        from_d = date.today() - timedelta(days=10)
        resp = self.client.get(
            f"/api/partners/{self.p1.id}/movements/?date_from={from_d}"
        )
        self.assertEqual(resp.status_code, 200)
        moves = resp.data["movements"]
        self.assertEqual(len(moves), 2)
        self.assertEqual(float(resp.data["opening_balance"]), 1000.0)
        self.assertEqual(float(moves[0]["running_balance"]), 1400.0)
        self.assertEqual(float(moves[1]["running_balance"]), 1300.0)
        self.assertEqual(float(resp.data["totals"]["total_support"]), 400.0)
        self.assertEqual(float(resp.data["totals"]["net"]), 300.0)

    def test_movements_include_method_and_reason(self):
        self._op(self.p1, date.today(), "withdraw", 250, payment_method="transfer", reason="شراء خامات")
        resp = self.client.get(f"/api/partners/{self.p1.id}/movements/")
        move = resp.data["movements"][0]
        self.assertEqual(move["payment_method"], "transfer")
        self.assertEqual(move["payment_method_label"], "تحويل بنكي")
        self.assertEqual(move["reason"], "شراء خامات")

    def test_movements_export_xlsx(self):
        self._op(self.p1, date.today(), "support", 300)
        r = self.client.get(f"/api/partners/{self.p1.id}/movements/?export=xlsx")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml.sheet", r.headers["Content-Type"])


class PartnerDistributionTests(APITestCase):
    def setUp(self):
        self.p1 = Partner.objects.create(name="شريك أول", share_percent=60)
        self.p2 = Partner.objects.create(name="شريك ثاني", share_percent=40)

    def _op(self, partner, op_type, amount):
        return self.client.post(
            "/api/partner-operations/",
            {"partner": partner.id, "date": str(timezone.localdate()), "operation_type": op_type, "amount": amount},
            format="json",
        )

    def test_distribution_matches_shares(self):
        self._op(self.p1, "support", 6000)
        self._op(self.p2, "support", 4000)
        resp = self.client.get("/api/partners/distribution/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(float(resp.data["total_net"]), 10000.0)
        items = {it["id"]: it for it in resp.data["items"]}
        p1 = items[self.p1.id]
        p2 = items[self.p2.id]
        self.assertEqual(p1["share_percent"], 60.0)
        self.assertEqual(p1["actual_net"], 6000.0)
        self.assertEqual(p1["theoretical_share"], 6000.0)
        self.assertEqual(p1["difference"], 0.0)
        self.assertEqual(p2["actual_net"], 4000.0)
        self.assertEqual(p2["theoretical_share"], 4000.0)
        self.assertEqual(p2["difference"], 0.0)

    def test_distribution_shows_variance_when_unbalanced(self):
        self._op(self.p1, "support", 9000)
        self._op(self.p2, "support", 1000)
        resp = self.client.get("/api/partners/distribution/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(float(resp.data["total_net"]), 10000.0)
        items = {it["id"]: it for it in resp.data["items"]}
        p1 = items[self.p1.id]
        p2 = items[self.p2.id]
        self.assertEqual(float(p1["theoretical_share"]), 6000.0)
        self.assertEqual(float(p1["difference"]), -3000.0)
        self.assertEqual(float(p2["theoretical_share"]), 4000.0)
        self.assertEqual(float(p2["difference"]), 3000.0)

    def test_distribution_excludes_inactive(self):
        self._op(self.p1, "support", 5000)
        inactive = Partner.objects.create(name="منسحب", share_percent=25, is_active=False)
        resp = self.client.get("/api/partners/distribution/")
        ids = [it["id"] for it in resp.data["items"]]
        self.assertNotIn(inactive.id, ids)
        self.assertEqual(float(resp.data["total_net"]), 5000.0)

    def test_distribution_export_xlsx(self):
        self._op(self.p1, "support", 3000)
        resp = self.client.get("/api/partners/distribution/?export=xlsx")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml.sheet", resp.headers["Content-Type"])