from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from branches.models import Branch
from suppliers.models import Fabric, Supplier

from .models import FabricRoll, GoodsReceipt, StockMovement, StockTransfer, Warehouse


def create_fabric(name="قماش"):
    return Fabric.objects.create(name=name, code=f"C-{name}xxx", sale_price_yard=2)


class WarehouseAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()

    def test_create_warehouse(self):
        r = self.c.post("/api/warehouses/", {"name": "مخزن رئيسي", "code": "WH1"})
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["is_active"])

    def test_cannot_delete_warehouse_with_rolls(self):
        wh = Warehouse.objects.create(name="مخزن", code="W1")
        fabric = create_fabric()
        FabricRoll.objects.create(warehouse=wh, fabric=fabric, yards=10, remaining_yards=10)
        r = self.c.delete(f"/api/warehouses/{wh.pk}/")
        self.assertEqual(r.status_code, 400)

    def test_warehouse_summary(self):
        wh = Warehouse.objects.create(name="مخزن", code="W2")
        fabric = create_fabric()
        FabricRoll.objects.create(warehouse=wh, fabric=fabric, yards=10, remaining_yards=6)
        r = self.c.get(f"/api/warehouses/{wh.pk}/summary/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data[0]["total_yards"], 6)


class GoodsReceiptAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.wh = Warehouse.objects.create(name="مخزن", code="W-R")
        self.supplier = Supplier.objects.create(name="مورد")
        self.fabric = create_fabric()

    def test_create_and_post_receipt(self):
        r = self.c.post("/api/warehouses/receipts/", {
            "warehouse": self.wh.pk,
            "supplier": self.supplier.pk,
            "date": date.today().isoformat(),
            "items": [{"fabric": self.fabric.pk, "rolls_count": 2, "yards": 100, "unit_price": 3}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        receipt_id = r.data["id"]
        self.assertTrue(r.data["number"].startswith("GR-"))
        self.assertEqual(r.data["status"], "draft")

        r = self.c.post(f"/api/warehouses/receipts/{receipt_id}/post/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "posted")

        rolls = FabricRoll.objects.filter(warehouse=self.wh, fabric=self.fabric)
        self.assertEqual(rolls.count(), 2)
        self.assertEqual(sum(x.remaining_yards for x in rolls), 100)
        self.assertEqual(StockMovement.objects.count(), 2)

    def test_receipt_post_twice_rejected(self):
        r = self.c.post("/api/warehouses/receipts/", {
            "warehouse": self.wh.pk, "date": date.today().isoformat(),
            "items": [{"fabric": self.fabric.pk, "rolls_count": 1, "yards": 10, "unit_price": 1}],
        }, format="json")
        rid = r.data["id"]
        self.c.post(f"/api/warehouses/receipts/{rid}/post/")
        r2 = self.c.post(f"/api/warehouses/receipts/{rid}/post/")
        self.assertGreaterEqual(r2.status_code, 400)

    def test_delete_posted_receipt_rejected(self):
        r = self.c.post("/api/warehouses/receipts/", {
            "warehouse": self.wh.pk, "date": date.today().isoformat(),
            "items": [{"fabric": self.fabric.pk, "rolls_count": 1, "yards": 10, "unit_price": 1}],
        }, format="json")
        rid = r.data["id"]
        self.c.post(f"/api/warehouses/receipts/{rid}/post/")
        r = self.c.delete(f"/api/warehouses/receipts/{rid}/")
        self.assertEqual(r.status_code, 400)


class StockTransferAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.src = Warehouse.objects.create(name="مخزن أ", code="W-A")
        self.dst = Warehouse.objects.create(name="مخزن ب", code="W-B")
        self.fabric = create_fabric()
        FabricRoll.objects.create(warehouse=self.src, fabric=self.fabric, yards=100, remaining_yards=100)

    def _transfer_payload(self):
        return {
            "from_warehouse": self.src.pk,
            "to_warehouse": self.dst.pk,
            "date": date.today().isoformat(),
            "requested_by": "محمد",
            "items": [{"fabric": self.fabric.pk, "yards": 40, "rolls_count": 1}],
        }

    def test_workflow(self):
        r = self.c.post("/api/warehouses/transfers/", self._transfer_payload(), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        tid = r.data["id"]
        self.assertTrue(r.data["number"].startswith("TR-"))
        self.assertEqual(r.data["status"], "draft")

        r = self.c.post(f"/api/warehouses/transfers/{tid}/request/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "requested")

        # approve requires requested state
        r = self.c.post(f"/api/warehouses/transfers/{tid}/approve/", {"approved_by": "المدير"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "approved")

        r = self.c.post(f"/api/warehouses/transfers/{tid}/complete/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "completed")

        src_avail = FabricRoll.objects.filter(warehouse=self.src, status=FabricRoll.Status.AVAILABLE)
        dst_avail = FabricRoll.objects.filter(warehouse=self.dst, status=FabricRoll.Status.AVAILABLE)
        self.assertEqual(sum(x.remaining_yards for x in src_avail), 60)
        self.assertEqual(sum(x.remaining_yards for x in dst_avail), 40)
        self.assertEqual(StockMovement.objects.filter(movement_type=StockMovement.Type.TRANSFER_OUT).count(), 1)
        self.assertEqual(StockMovement.objects.filter(movement_type=StockMovement.Type.TRANSFER_IN).count(), 1)

    def test_transfer_insufficient_stock(self):
        r = self.c.post("/api/warehouses/transfers/", {
            "from_warehouse": self.src.pk, "to_warehouse": self.dst.pk,
            "date": date.today().isoformat(),
            "items": [{"fabric": self.fabric.pk, "yards": 500}],
        }, format="json")
        tid = r.data["id"]
        self.c.post(f"/api/warehouses/transfers/{tid}/approve/")
        r = self.c.post(f"/api/warehouses/transfers/{tid}/complete/")
        self.assertGreaterEqual(r.status_code, 400)
        self.assertEqual(FabricRoll.objects.filter(warehouse=self.dst).count(), 0)

    def test_transfer_same_warehouse_rejected(self):
        r = self.c.post("/api/warehouses/transfers/", {
            "from_warehouse": self.src.pk, "to_warehouse": self.src.pk,
            "date": date.today().isoformat(),
            "items": [{"fabric": self.fabric.pk, "yards": 10}],
        }, format="json")
        self.assertGreaterEqual(r.status_code, 400)

    def test_approve_before_request_rejected(self):
        r = self.c.post("/api/warehouses/transfers/", self._transfer_payload(), format="json")
        tid = r.data["id"]
        r = self.c.post(f"/api/warehouses/transfers/{tid}/approve/")
        self.assertGreaterEqual(r.status_code, 400)

    def test_reject_workflow(self):
        r = self.c.post("/api/warehouses/transfers/", self._transfer_payload(), format="json")
        tid = r.data["id"]
        self.c.post(f"/api/warehouses/transfers/{tid}/request/")
        r = self.c.post(f"/api/warehouses/transfers/{tid}/reject/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "rejected")

    def test_transfer_to_branch_by_yards(self):
        branch = Branch.objects.create(name="فرع الرياض", code="R-01")
        rid = self.c.post("/api/warehouses/receipts/", {
            "warehouse": self.src.pk, "date": date.today().isoformat(),
            "items": [{"fabric": self.fabric.pk, "rolls_count": 2, "yards": 100, "unit_price": 2}],
        }, format="json").data["id"]
        self.c.post(f"/api/warehouses/receipts/{rid}/post/")

        r = self.c.post("/api/warehouses/transfers/", {
            "from_warehouse": self.src.pk, "to_branch": branch.pk,
            "date": date.today().isoformat(),
            "items": [{"fabric": self.fabric.pk, "yards": 40}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["dest_type"], "branch")
        self.assertEqual(r.data["dest_name"], "فرع الرياض")
        tid = r.data["id"]
        self.c.post(f"/api/warehouses/transfers/{tid}/request/")
        self.c.post(f"/api/warehouses/transfers/{tid}/approve/")
        r = self.c.post(f"/api/warehouses/transfers/{tid}/complete/")
        self.assertEqual(r.status_code, 200, r.data)

        branch_wh = Warehouse.objects.get(branch=branch)
        self.assertEqual(branch_wh.name, "فرع: فرع الرياض")
        self.assertTrue(branch_wh.is_branch_stock)
        avail = FabricRoll.objects.filter(warehouse=branch_wh, status=FabricRoll.Status.AVAILABLE)
        self.assertEqual(sum(x.remaining_yards for x in avail), 40)
        src_avail = FabricRoll.objects.filter(warehouse=self.src, status=FabricRoll.Status.AVAILABLE)
        # 100 لفة setUp + 100 وصول - 40 نقل = 160
        self.assertEqual(sum(x.remaining_yards for x in src_avail), 160)

    def test_transfer_by_rolls(self):
        rid = self.c.post("/api/warehouses/receipts/", {
            "warehouse": self.src.pk, "date": date.today().isoformat(),
            "items": [{"fabric": self.fabric.pk, "rolls_count": 3, "yards": 150, "unit_price": 2}],
        }, format="json").data["id"]
        self.c.post(f"/api/warehouses/receipts/{rid}/post/")

        r = self.c.post("/api/warehouses/transfers/", {
            "from_warehouse": self.src.pk, "to_warehouse": self.dst.pk,
            "date": date.today().isoformat(),
            "items": [{"fabric": self.fabric.pk, "quantity_mode": "roll", "rolls_count": 2}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        tid = r.data["id"]
        self.c.post(f"/api/warehouses/transfers/{tid}/request/")
        self.c.post(f"/api/warehouses/transfers/{tid}/approve/")
        r = self.c.post(f"/api/warehouses/transfers/{tid}/complete/")
        self.assertEqual(r.status_code, 200, r.data)
        # أول لفتين (أقدم اللفات) نفقلتا كاملتين: لفة 100 من setUp + أول لفة 50
        dst_rolls = FabricRoll.objects.filter(warehouse=self.dst, status=FabricRoll.Status.AVAILABLE)
        self.assertEqual(dst_rolls.count(), 2)
        self.assertEqual(sum(x.remaining_yards for x in dst_rolls), 150)
        self.assertEqual(r.data["total_yards"], 150)

    def test_transfer_to_branch_requires_destination(self):
        r = self.c.post("/api/warehouses/transfers/", {
            "from_warehouse": self.src.pk, "date": date.today().isoformat(),
            "items": [{"fabric": self.fabric.pk, "yards": 10}],
        }, format="json")
        self.assertGreaterEqual(r.status_code, 400)

    def test_transfer_rolls_insufficient(self):
        r = self.c.post("/api/warehouses/transfers/", {
            "from_warehouse": self.src.pk, "to_warehouse": self.dst.pk,
            "date": date.today().isoformat(),
            "items": [{"fabric": self.fabric.pk, "quantity_mode": "roll", "rolls_count": 5}],
        }, format="json")
        tid = r.data["id"]
        self.c.post(f"/api/warehouses/transfers/{tid}/approve/")
        r = self.c.post(f"/api/warehouses/transfers/{tid}/complete/")
        self.assertGreaterEqual(r.status_code, 400)


class StockAdjustmentAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.wh = Warehouse.objects.create(name="مخزن", code="W-ADJ")
        self.fabric = create_fabric()

    def test_adjustment_in(self):
        r = self.c.post("/api/warehouses/adjustments/", {
            "warehouse": self.wh.pk, "date": date.today().isoformat(),
            "direction": "in", "reason": "gain",
            "items": [{"fabric": self.fabric.pk, "yards": 25, "rolls_count": 1}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["number"].startswith("ADJ-"))
        self.assertEqual(FabricRoll.objects.filter(warehouse=self.wh).count(), 1)
        self.assertEqual(StockMovement.objects.filter(movement_type=StockMovement.Type.ADJUSTMENT_IN).count(), 1)

    def test_adjustment_out_insufficient(self):
        r = self.c.post("/api/warehouses/adjustments/", {
            "warehouse": self.wh.pk, "date": date.today().isoformat(),
            "direction": "out", "items": [{"fabric": self.fabric.pk, "yards": 50}],
        }, format="json")
        self.assertGreaterEqual(r.status_code, 400)


class StockCountAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.wh = Warehouse.objects.create(name="مخزن", code="W-CNT")
        self.fabric = create_fabric()
        FabricRoll.objects.create(warehouse=self.wh, fabric=self.fabric, yards=30, remaining_yards=30)

    def test_count_workflow(self):
        r = self.c.post("/api/warehouses/counts/", {
            "warehouse": self.wh.pk, "date": date.today().isoformat(),
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        cid = r.data["id"]
        self.assertTrue(r.data["number"].startswith("CNT-"))
        self.assertEqual(len(r.data["items"]), 1)
        self.assertEqual(Decimal(str(r.data["items"][0]["system_yards"])), Decimal("30"))

        # إدخال الرصيد الفعلي
        r = self.c.patch(
            f"/api/warehouses/counts/{cid}/items/",
            {"items": [{"fabric": self.fabric.pk, "counted_yards": 25}]},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)

        r = self.c.post(f"/api/warehouses/counts/{cid}/post/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "posted")
        self.assertEqual(StockMovement.objects.filter(movement_type=StockMovement.Type.COUNT).count(), 1)
        avail = FabricRoll.objects.filter(warehouse=self.wh, status=FabricRoll.Status.AVAILABLE)
        self.assertEqual(sum(x.remaining_yards for x in avail), 25)

    def test_post_without_counts_rejected(self):
        r = self.c.post("/api/warehouses/counts/", {
            "warehouse": self.wh.pk, "date": date.today().isoformat(),
        }, format="json")
        cid = r.data["id"]
        r = self.c.post(f"/api/warehouses/counts/{cid}/post/")
        self.assertGreaterEqual(r.status_code, 400)


class FabricRollAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.wh = Warehouse.objects.create(name="مخزن", code="W-RL")
        self.fabric = create_fabric()

    def test_create_roll_auto_code(self):
        r = self.c.post("/api/warehouses/rolls/", {
            "warehouse": self.wh.pk, "fabric": self.fabric.pk, "yards": 50,
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["code"].startswith("RL-"))
        self.assertEqual(Decimal(str(r.data["remaining_yards"])), Decimal("50"))

    def test_same_warehouse_filter(self):
        self.c.post("/api/warehouses/rolls/", {
            "warehouse": self.wh.pk, "fabric": self.fabric.pk, "yards": 10,
        }, format="json")
        r = self.c.get(f"/api/warehouses/rolls/?warehouse={self.wh.pk}")
        self.assertEqual(r.data["count"], 1)


class MovementsTest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.wh = Warehouse.objects.create(name="مخزن", code="W-MV")
        self.fabric = create_fabric()

    def test_movements_list_and_filters(self):
        self.c.post("/api/warehouses/adjustments/", {
            "warehouse": self.wh.pk, "date": date.today().isoformat(),
            "direction": "in", "items": [{"fabric": self.fabric.pk, "yards": 5}],
        }, format="json")
        r = self.c.get("/api/warehouses/movements/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)
        r = self.c.get(f"/api/warehouses/movements/?warehouse={self.wh.pk}&movement_type=adjustment_in")
        self.assertEqual(r.data["count"], 1)


class OpeningBalanceAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.wh = Warehouse.objects.create(name="مخزن", code="W-OPN")
        self.fabric = create_fabric()

    def _payload(self):
        return {
            "warehouse": self.wh.pk,
            "date": date.today().isoformat(),
            "items": [{"fabric": self.fabric.pk, "yards": 100, "rolls_count": 2, "unit_price": 3}],
        }

    def test_create_opening_posts_immediately(self):
        r = self.c.post("/api/warehouses/openings/", self._payload(), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["number"].startswith("OPN-"))
        rolls = FabricRoll.objects.filter(warehouse=self.wh, fabric=self.fabric)
        self.assertEqual(rolls.count(), 2)
        self.assertEqual(sum(x.remaining_yards for x in rolls), 100)
        movements = list(StockMovement.objects.filter(movement_type=StockMovement.Type.OPENING).order_by("id"))
        self.assertEqual(len(movements), 2)
        self.assertEqual(Decimal(str(movements[0].balance_before)), Decimal("0"))
        self.assertEqual(Decimal(str(movements[0].balance_after)), Decimal("50"))
        self.assertEqual(Decimal(str(movements[1].balance_before)), Decimal("50"))
        self.assertEqual(Decimal(str(movements[1].balance_after)), Decimal("100"))

    def test_duplicate_opening_rejected(self):
        self.c.post("/api/warehouses/openings/", self._payload(), format="json")
        r = self.c.post("/api/warehouses/openings/", self._payload(), format="json")
        self.assertGreaterEqual(r.status_code, 400)

    def test_empty_items_rejected(self):
        r = self.c.post("/api/warehouses/openings/", {
            "warehouse": self.wh.pk, "date": date.today().isoformat(),
        }, format="json")
        self.assertGreaterEqual(r.status_code, 400)


class StockBalanceAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.wh = Warehouse.objects.create(name="مخزن", code="W-SB")
        self.fabric = Fabric.objects.create(name="قماش الصيف", code="C-SB", sale_price_yard=2, min_stock=10)

    def test_stock_endpoint_with_low_stock(self):
        self.c.post("/api/warehouses/adjustments/", {
            "warehouse": self.wh.pk, "date": date.today().isoformat(),
            "direction": "in", "items": [{"fabric": self.fabric.pk, "yards": 5}],
        }, format="json")
        r = self.c.get("/api/warehouses/stock/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["totals"]["total_yards"], 5)
        self.assertEqual(r.data["totals"]["low_stock_count"], 1)
        self.assertTrue(r.data["items"][0]["low_stock"])

    def test_stock_endpoint_search(self):
        self.c.post("/api/warehouses/adjustments/", {
            "warehouse": self.wh.pk, "date": date.today().isoformat(),
            "direction": "in", "items": [{"fabric": self.fabric.pk, "yards": 50}],
        }, format="json")
        r = self.c.get("/api/warehouses/stock/", {"search": "الصيف"})
        self.assertEqual(r.data["totals"]["total_yards"], 50)

    def test_movements_have_balance_columns(self):
        self.c.post("/api/warehouses/adjustments/", {
            "warehouse": self.wh.pk, "date": date.today().isoformat(),
            "direction": "in", "items": [{"fabric": self.fabric.pk, "yards": 25}],
        }, format="json")
        self.c.post("/api/warehouses/adjustments/", {
            "warehouse": self.wh.pk, "date": date.today().isoformat(),
            "direction": "out", "items": [{"fabric": self.fabric.pk, "yards": 10}],
        }, format="json")
        r = self.c.get("/api/warehouses/movements/")
        self.assertEqual(r.data["count"], 2)
        ins = [m for m in r.data["results"] if Decimal(str(m["quantity"])) > 0][0]
        outs = [m for m in r.data["results"] if Decimal(str(m["quantity"])) < 0][0]
        self.assertEqual(Decimal(ins["balance_before"]), Decimal("0"))
        self.assertEqual(Decimal(ins["balance_after"]), Decimal("25"))
        self.assertEqual(Decimal(outs["balance_before"]), Decimal("25"))
        self.assertEqual(Decimal(outs["balance_after"]), Decimal("15"))


class StockBalanceSetAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.wh1 = Warehouse.objects.create(name="مخزن أ", code="W-SET1")
        self.wh2 = Warehouse.objects.create(name="مخزن ب", code="W-SET2")
        self.fabric = Fabric.objects.create(name="قماش الشتاء", code="F-SET", sale_price_yard=3, min_stock=10)

    def _set(self, items, fabric=None):
        return self.c.post("/api/warehouses/stock/set/", {
            "fabric": fabric or self.fabric.pk, "items": items,
        }, format="json")

    def test_set_increases_stock(self):
        r = self._set([{"warehouse": self.wh1.pk, "yards": 5}])
        self.assertEqual(r.status_code, 200)
        bal = self.c.get("/api/warehouses/stock/").data
        self.assertEqual(bal["totals"]["total_yards"], 5)

    def test_set_decreases_stock(self):
        self._set([{"warehouse": self.wh1.pk, "yards": 30}])
        bal = self.c.get("/api/warehouses/stock/").data
        self.assertEqual(bal["totals"]["total_yards"], 30)
        self._set([{"warehouse": self.wh1.pk, "yards": 10}])
        bal = self.c.get("/api/warehouses/stock/").data
        self.assertEqual(bal["totals"]["total_yards"], 10)
        self.assertEqual(bal["items"][0]["warehouses"][0]["total_yards"], 10)

    def test_set_multiple_warehouses(self):
        self._set([{"warehouse": self.wh1.pk, "yards": 7}, {"warehouse": self.wh2.pk, "yards": 3}])
        bal = self.c.get("/api/warehouses/stock/").data
        self.assertEqual(bal["totals"]["total_yards"], 10)
        self.assertEqual(len(bal["items"][0]["warehouses"]), 2)

    def test_set_delete_zeroes_out_empty_row(self):
        self._set([{"warehouse": self.wh1.pk, "yards": 8}])
        r = self._set([{"warehouse": self.wh1.pk, "yards": 0}])
        self.assertEqual(r.status_code, 200)
        items = self.c.get("/api/warehouses/stock/").data["items"]
        self.assertTrue(all(it["fabric"] != self.fabric.pk for it in items))

    def test_set_rejects_negative(self):
        r = self._set([{"warehouse": self.wh1.pk, "yards": -5}])
        self.assertEqual(r.status_code, 400)

    def test_set_rejects_empty_items(self):
        r = self._set([])
        self.assertEqual(r.status_code, 400)

    def test_set_rejects_duplicate_warehouse(self):
        r = self._set([{"warehouse": self.wh1.pk, "yards": 1}, {"warehouse": self.wh1.pk, "yards": 2}])
        self.assertEqual(r.status_code, 400)

    def test_set_creates_adjustment_documents(self):
        self._set([{"warehouse": self.wh1.pk, "yards": 20}])
        r = self.c.get("/api/warehouses/adjustments/")
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["direction"], "in")
        self._set([{"warehouse": self.wh1.pk, "yards": 5}])
        r = self.c.get("/api/warehouses/adjustments/")
        self.assertEqual(r.data["count"], 2)
        self.assertEqual(r.data["results"][0]["direction"], "out")