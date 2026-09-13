from django.test import TestCase
from rest_framework.test import APIClient

from branches.models import Branch
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
