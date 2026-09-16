from django.test import TestCase
from rest_framework.test import APIClient

from branches.models import Branch
from sales.models import DailySale
from suppliers.models import Fabric
from warehouses.models import Warehouse


class BranchAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()

    def test_create_branch(self):
        r = self.c.post("/api/branches/", {"name": "Muscat", "code": "MUS-01"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["name"], "Muscat")
        self.assertEqual(r.data["code"], "MUS-01")
        self.assertTrue(r.data["is_active"])

    def test_create_branch_auto_creates_stock_warehouse(self):
        r = self.c.post("/api/branches/", {"name": "Seeb", "code": "SEB-1"})
        self.assertEqual(r.status_code, 201)
        wh = Warehouse.objects.get(branch_id=r.data["id"])
        self.assertEqual(wh.name, "فرع: Seeb")
        self.assertEqual(wh.code, "BR-SEB-1")
        self.assertTrue(wh.is_active)

    def test_duplicate_code_rejected(self):
        self.c.post("/api/branches/", {"name": "A", "code": "X"})
        r = self.c.post("/api/branches/", {"name": "B", "code": "X"})
        self.assertEqual(r.status_code, 400)

    def test_list_branches(self):
        self.c.post("/api/branches/", {"name": "A", "code": "A"})
        self.c.post("/api/branches/", {"name": "B", "code": "B"})
        r = self.c.get("/api/branches/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 2)

    def test_retrieve_branch(self):
        r = self.c.post("/api/branches/", {"name": "X", "code": "X"})
        bid = r.data["id"]
        r = self.c.get(f"/api/branches/{bid}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "X")

    def test_update_branch(self):
        r = self.c.post("/api/branches/", {"name": "Old", "code": "O"})
        bid = r.data["id"]
        r = self.c.put(f"/api/branches/{bid}/", {"name": "New", "code": "O"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "New")

    def test_delete_branch_without_records(self):
        r = self.c.post("/api/branches/", {"name": "Del", "code": "DEL"})
        bid = r.data["id"]
        r = self.c.delete(f"/api/branches/{bid}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Branch.objects.count(), 0)

    def test_search(self):
        self.c.post("/api/branches/", {"name": "Al Khuwair", "code": "KH"})
        self.c.post("/api/branches/", {"name": "Salalah", "code": "SL"})
        r = self.c.get("/api/branches/", {"search": "Khuwair"})
        self.assertEqual(r.data["count"], 1)


class BranchTargetAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.branch = Branch.objects.create(
            name="Muscat", code="MUS-01", monthly_sales_target=50000
        )

    def test_monthly_sales_and_progress(self):
        from datetime import date

        DailySale.objects.create(
            branch=self.branch, date=date.today(),
            total_sales=10000, cash_amount=10000,
        )
        r = self.c.get(f"/api/branches/{self.branch.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["monthly_sales"], 10000.0)
        self.assertEqual(r.data["target_progress_pct"], 20.0)

    def test_target_zero_gives_null_progress(self):
        Branch.objects.filter(pk=self.branch.pk).update(monthly_sales_target=0)
        r = self.c.get(f"/api/branches/{self.branch.id}/")
        self.assertIsNone(r.data["target_progress_pct"])


class FabricBranchPriceAPITest(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.branch = Branch.objects.create(name="Muscat", code="MUS-01")
        self.fabric = Fabric.objects.create(
            name="قطن", code="FAB-1", sale_price_yard=5, sale_price_roll=50, yards_per_roll=11
        )

    def test_create_price(self):
        r = self.c.post("/api/branch-prices/", {
            "branch": self.branch.id,
            "fabric": self.fabric.id,
            "sale_price_yard": "6",
            "min_sale_yard": "5.5",
        })
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["fabric_name"], "قطن")
        self.assertEqual(r.data["branch_name"], "Muscat")
        self.assertEqual(r.data["global_sale_price_yard"], "5.000")

    def test_duplicate_price_rejected(self):
        self.c.post("/api/branch-prices/", {
            "branch": self.branch.id, "fabric": self.fabric.id, "sale_price_yard": "6",
        })
        r = self.c.post("/api/branch-prices/", {
            "branch": self.branch.id, "fabric": self.fabric.id, "sale_price_yard": "7",
        })
        self.assertEqual(r.status_code, 400)

    def test_filter_by_branch(self):
        other = Branch.objects.create(name="Seeb", code="SEB-1")
        self.c.post("/api/branch-prices/", {
            "branch": self.branch.id, "fabric": self.fabric.id, "sale_price_yard": "6",
        })
        r = self.c.get("/api/branch-prices/", {"branch": other.id})
        self.assertEqual(r.data["count"], 0)
        r = self.c.get("/api/branch-prices/", {"branch": self.branch.id})
        self.assertEqual(r.data["count"], 1)
