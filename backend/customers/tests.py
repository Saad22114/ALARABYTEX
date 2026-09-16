from django.test import TestCase
from django.urls import reverse

from branches.models import Branch
from core.models import TimeStampedModel
from .models import Customer


class CustomerModelTests(TestCase):
    def test_create_customer(self):
        c = Customer.objects.create(name="أحمد العلي", phone="0500000000")
        self.assertEqual(str(c), "أحمد العلي")
        self.assertTrue(c.is_active)
        self.assertIsInstance(c, TimeStampedModel)

    def test_phone_optional(self):
        c = Customer.objects.create(name="بدون رقم")
        self.assertIsNone(c.phone)

    def test_duplicate_phone_rejected_at_model(self):
        Customer.objects.create(name="أ", phone="0599999999")
        with self.assertRaises(Exception):
            Customer.objects.create(name="ب", phone="0599999999")

    def test_customer_ordering(self):
        Customer.objects.create(name="زيد", phone="051")
        Customer.objects.create(name="أحمد", phone="052")
        names = list(Customer.objects.values_list("name", flat=True))
        self.assertEqual(names, ["أحمد", "زيد"])


class CustomerApiTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="الفرع الرئيسي", code="BR-MAIN")
        self.list_url = reverse("customer-list")
        self.payload = {
            "name": "سارة محمد",
            "phone": "0551234567",
            "branch": self.branch.pk,
            "address": "الرياض",
            "notes": "زبون دائم",
        }

    def _url(self, pk):
        return reverse("customer-detail", kwargs={"pk": pk})

    def test_list_returns_paginated(self):
        Customer.objects.create(name="سارة محمد", phone="0551234567")
        res = self.client.get(self.list_url)
        self.assertEqual(res.status_code, 200)
        self.assertIn("results", res.json())

    def test_create_customer(self):
        res = self.client.post(self.list_url, self.payload, content_type="application/json")
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["name"], "سارة محمد")
        self.assertEqual(data["phone"], "0551234567")
        self.assertEqual(data["branch_name"], self.branch.name)

    def test_create_requires_name(self):
        res = self.client.post(self.list_url, {"phone": "0550000000"}, content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("name", res.json())

    def test_create_blank_phone_normalized_to_null(self):
        res = self.client.post(self.list_url, {"name": "بلا هاتف", "phone": "   "}, content_type="application/json")
        self.assertEqual(res.status_code, 201)
        self.assertIsNone(res.json()["phone"])

    def test_duplicate_phone_rejected_by_api(self):
        Customer.objects.create(name="أ", phone="0551234567")
        res = self.client.post(self.list_url, self.payload, content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("phone", res.json())

    def test_update_customer(self):
        c = Customer.objects.create(name="قديم", phone="0559999999")
        res = self.client.put(
            self._url(c.pk),
            {"id": c.pk, "name": "جديد", "phone": "0559999999"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.name, "جديد")

    def test_delete_customer(self):
        c = Customer.objects.create(name="مؤقت", phone="0558888888")
        res = self.client.delete(self._url(c.pk))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Customer.objects.filter(pk=c.pk).exists())

    def test_search_by_name_and_phone(self):
        Customer.objects.create(name="خالد", phone="0561111111")
        Customer.objects.create(name="ماجد", phone="0562222222")
        by_name = self.client.get(self.list_url, {"search": "خالد"})
        self.assertEqual(by_name.json()["count"], 1)
        by_phone = self.client.get(self.list_url, {"search": "2222222"})
        self.assertEqual(by_phone.json()["count"], 1)

    def test_lookup_phone_found(self):
        c = Customer.objects.create(name="منى", phone="0565555555", branch=self.branch)
        res = self.client.get(reverse("customer-lookup"), {"phone": "0565555555"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["found"])
        self.assertEqual(data["customer"]["id"], c.pk)
        self.assertEqual(data["customer"]["name"], "منى")

    def test_lookup_phone_not_found(self):
        res = self.client.get(reverse("customer-lookup"), {"phone": "0567777777"})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["found"])

    def test_lookup_requires_phone(self):
        res = self.client.get(reverse("customer-lookup"))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["found"])

    def test_filter_by_branch(self):
        b2 = Branch.objects.create(name="فرع ثانٍ", code="BR-SEC")
        Customer.objects.create(name="أ", phone="051", branch=self.branch)
        Customer.objects.create(name="ب", phone="052", branch=b2)
        res = self.client.get(self.list_url, {"branch": self.branch.pk})
        self.assertEqual(res.json()["count"], 1)

    def test_filter_by_active(self):
        Customer.objects.create(name="أ", phone="053", is_active=False)
        res = self.client.get(self.list_url, {"is_active": "false"})
        self.assertEqual(res.json()["count"], 1)