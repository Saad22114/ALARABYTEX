from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from branches.models import Branch
from core.models import TimeStampedModel
from core.testsupport import authenticate_admin
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
        self.client = APIClient()
        authenticate_admin(self.client)
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

    def _phones(self, term):
        res = self.client.get(self.list_url, {"search": term, "page_size": 50})
        self.assertEqual(res.status_code, 200)
        return [row["phone"] for row in res.json()["results"]]

    def test_partial_phone_search_shows_similar_numbers(self):
        """الطلب: يظهر المتشابه فوراً على حسب البحث، بلا انتظار الرقم كاملاً.

        الترتيب بالاسم كان يخلط المتشابهين، فيبدو البحث كأنه لا يستجيب
        حتى يكتب المستخدم الرقم كله.
        """
        Customer.objects.create(name="أ", phone="0561000000")
        Customer.objects.create(name="ب", phone="0562000000")
        Customer.objects.create(name="ج", phone="0561000009")
        Customer.objects.create(name="د", phone="971234567")

        # أربعة أرقام من أصل ثمانية: يجب أن يُرى المتشابهان الآن.
        self.assertEqual(self._phones("0561"), ["0561000000", "0561000009"])
        # التطابق التام في الصدارة، لا في منتصف القائمة.
        self.assertEqual(self._phones("0561000009"), ["0561000009"])
        # ذيل الرقم: من يكتب آخر أربعة أرقام يعرف صاحبه بلا تردد.
        self.assertEqual(self._phones("0009"), ["0561000009"])

    def test_phone_search_ignores_separators_he_types(self):
        """«0561 000009» و«0561000009» رقم واحد، والمستخدم يكتبه بالطريقة الأولى."""
        Customer.objects.create(name="أ", phone="0561000009")
        self.assertEqual(self._phones("0561 000009"), ["0561000009"])
        self.assertEqual(self._phones("0561-000009"), ["0561000009"])

    def test_search_by_name_still_finds_phone_matches(self):
        Customer.objects.create(name="خالد", phone="0561111111")
        Customer.objects.create(name="ماجد", phone="0562222222")
        self.assertEqual(self._phones("خالد"), ["0561111111"])

    def test_empty_search_stays_in_name_order(self):
        for index, name in enumerate(("زينب", "أحمد", "سعيد")):
            Customer.objects.create(name=name, phone=f"0561000{index:03d}")
        res = self.client.get(self.list_url, {"page_size": 50})
        self.assertEqual(
            [row["name"] for row in res.json()["results"]], ["أحمد", "زينب", "سعيد"]
        )

    def test_lookup_phone_found(self):
        c = Customer.objects.create(name="منى", phone="0565555555", branch=self.branch)
        res = self.client.get(reverse("customer-lookup"), {"phone": "0565555555"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["found"])
        self.assertEqual(data["customer"]["id"], c.pk)
        self.assertEqual(data["customer"]["name"], "منى")

    def test_lookup_returns_last_purchase_date(self):
        from sale_sessions.models import Employee, SaleSession, SaleSessionItem
        from suppliers.models import Fabric

        customer = Customer.objects.create(name="منى", phone="0565555555", branch=self.branch)
        emp = Employee.objects.create(name="موظف", branch=self.branch)
        fabric = Fabric.objects.create(name="قماش اختبار")
        session = SaleSession.objects.create(employee=emp, branch=self.branch)
        SaleSessionItem.objects.create(
            session=session,
            fabric=fabric,
            sale_type="yard",
            quantity=5,
            unit_price="10",
            total="50",
            sale_date="2026-09-10",
            customer_name="منى",
            customer_phone="0565555555",
        )
        res = self.client.get(reverse("customer-lookup"), {"phone": "0565555555"})
        self.assertEqual(res.status_code, 200)
        data = res.json()["customer"]
        self.assertEqual(data["last_purchase_date"], "2026-09-10")

    def test_lookup_last_purchase_null_when_no_purchases(self):
        Customer.objects.create(name="منى", phone="0565555555", branch=self.branch)
        res = self.client.get(reverse("customer-lookup"), {"phone": "0565555555"})
        self.assertIsNone(res.json()["customer"]["last_purchase_date"])

    def test_lookup_phone_not_found(self):
        res = self.client.get(reverse("customer-lookup"), {"phone": "0567777777"})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["found"])

    def test_lookup_finds_customer_by_normalized_phone(self):
        """الرقمُ واحد، والرسم واحد، والذي كتبه قراره يحتفظ الزبون.

        الشاشة ستقول «غيرُ مسجَّل» لكل رقم لم يطابق تماماً، فإذا أخبر
        زبوناً موجوداً بالمئة أن يُقال «مسجَّل» والذي سجلّناً برقمن واحد.
        """
        customer = Customer.objects.create(
            name="منى", phone="0565-555-555", branch=self.branch
        )
        for typed in ("0565555555", "0565 555 555", "0565-555-555"):
            with self.subTest(typed=typed):
                res = self.client.get(reverse("customer-lookup"), {"phone": typed})
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertTrue(data["found"], typed)
                self.assertEqual(data["customer"]["id"], customer.pk)

    def test_lookup_still_says_no_for_a_number_that_does_not_exist(self):
        """تنويه الرقم ليس الفاصل إلا إنه يُقابل على رقم آخر مُسجَّل، فيحاسب على عدم المتابعة.

        لولا أصاب «أقرب» أن يُحسّن البحث إلى أقرب أخر ويُقال إليه أنّه
        المحصوص عناد، وأنّ الأصول أحرً من الذي كتبه الشاشة.
        """
        Customer.objects.create(name="منى", phone="0561111111", branch=self.branch)
        for typed in ("0567777777", "9999", "0561", "0561111112"):
            with self.subTest(typed=typed):
                res = self.client.get(reverse("customer-lookup"), {"phone": typed})
                self.assertEqual(res.status_code, 200)
                self.assertFalse(res.json()["found"], typed)

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

    def test_filter_by_created_date_range(self):
        old = Customer.objects.create(name="قديم", phone="0571111111", branch=self.branch)
        recent = Customer.objects.create(name="جديد", phone="0572222222", branch=self.branch)
        Customer.objects.filter(pk=old.pk).update(created_at="2026-01-05T10:00:00+04:00")
        Customer.objects.filter(pk=recent.pk).update(created_at="2026-09-18T10:00:00+04:00")
        res = self.client.get(self.list_url, {"date_from": "2026-09-01", "date_to": "2026-09-30"})
        self.assertEqual(res.json()["count"], 1)
        self.assertEqual(res.json()["results"][0]["id"], recent.pk)

    # ------------------------------------------------- الرقم واحدٌ برسمين

    def test_create_rejects_the_same_digits_in_another_drawing(self):
        """«0565-555-555» و«0565555555» سطران في الجدول، ورقمٌ واحد عند الناس.

        وقاعدةُ البيانات لا ترى ذلك: ``unique=True`` يقارن النصّ حرفاً بحرف.
        فلو سقط الفحصُ على مقارنة الرسم، لكُتب الرقم مرّتين، وصار في المحل
        زبونان يقرآن الرقمَ نفسَه فيتّهم كلٌّ منهما الآخر.
        """
        Customer.objects.create(name="منى", phone="0565-555-555", branch=self.branch)
        for typed in ("0565555555", "0565 555 555", "05-65-555-555"):
            with self.subTest(typed=typed):
                res = self.client.post(
                    self.list_url,
                    {"name": "مكرر", "phone": typed, "branch": self.branch.pk},
                    content_type="application/json",
                )
                self.assertEqual(res.status_code, 400)
                self.assertIn("منى", str(res.json()["phone"]))

    def test_create_rejects_the_twin_in_the_other_direction(self):
        """الاتجاهُ المعاكس هو المهمّ: المسجَّل بلا فواصل، والمكتوب بفاصل."""
        Customer.objects.create(name="سالم", phone="0565555555", branch=self.branch)
        res = self.client.post(
            self.list_url,
            {"name": "مكرر", "phone": "0565-555-555", "branch": self.branch.pk},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("سالم", str(res.json()["phone"]))

    def test_short_numbers_are_checked_too(self):
        """الرقمُ القصيرُ أرجحُ خطأٍ منه رقماً صحيحاً، فالفحصُ عليه أوجب.

        وهنا الفحصُ بسقفٍ منخفض مقصود: في البحث نرفض أقلَّ من سبعة أرقام لأنّ
        السؤال «هل أعرفه؟»، أمّا هنا فالسؤال «هل واحدٌ مرّتين؟» — وفيه الرقمُ
        القصيرُ نفسه هو الدليل.
        """
        Customer.objects.create(name="قديم", phone="05-05", branch=self.branch)
        res = self.client.post(
            self.list_url,
            {"name": "مكرر", "phone": "0505", "branch": self.branch.pk},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("phone", res.json())

    def test_update_keeps_its_own_phone(self):
        """من يحفظ رقمه هو ليس مكرِّراً لأحد — وإلا استحال التعديل أصلاً."""
        c = Customer.objects.create(name="قديم", phone="0565555555", branch=self.branch)
        res = self.client.put(
            self._url(c.pk),
            {"id": c.pk, "name": "جديد", "phone": "0565555555", "branch": self.branch.pk},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.name, "جديد")

    def test_update_cannot_take_another_customers_number(self):
        Customer.objects.create(name="منى", phone="0565555555", branch=self.branch)
        other = Customer.objects.create(name="سالم", phone="0566666666", branch=self.branch)
        res = self.client.patch(
            self._url(other.pk),
            {"phone": "0565-555-555"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        other.refresh_from_db()
        self.assertEqual(other.phone, "0566666666")

    # ------------------------------------------------------------ الترتيب

    def _names(self, params):
        res = self.client.get(self.list_url, {"page_size": 50, **params})
        self.assertEqual(res.status_code, 200)
        return [row["name"] for row in res.json()["results"]]

    def _age(self, customer, when):
        Customer.objects.filter(pk=customer.pk).update(created_at=when)

    def test_order_newest_and_oldest_first(self):
        first = Customer.objects.create(name="أول", phone="0581111111")
        middle = Customer.objects.create(name="ثانٍ", phone="0582222222")
        last = Customer.objects.create(name="ثالث", phone="0583333333")
        self._age(first, "2026-01-05T10:00:00+04:00")
        self._age(middle, "2026-05-05T10:00:00+04:00")
        self._age(last, "2026-09-05T10:00:00+04:00")
        self.assertEqual(self._names({"ordering": "newest"}), ["ثالث", "ثانٍ", "أول"])
        self.assertEqual(self._names({"ordering": "oldest"}), ["أول", "ثانٍ", "ثالث"])

    def test_order_by_price_sorts_by_what_they_bought(self):
        """«السعر الأعلى» مبلغٌ في جدول البنود، لا عمودٌ في جدول الزبائن.

        والترتيبُ به لا يعمل إن حُسب بعد التقسيم إلى صفحات، لأن الصفحة الثانية
        لا تعرف أرقامَ الأولى — فالحسابُ لازمٌ داخل الاستعلام.
        """
        small = Customer.objects.create(name="صغير", phone="0591111111")
        big = Customer.objects.create(name="كبير", phone="0592222222")
        middle = Customer.objects.create(name="وسط", phone="0593333333")
        self._buy(small, "10")
        self._buy(middle, "100")
        self._buy(big, "1000")
        self.assertEqual(
            self._names({"ordering": "top"}), ["كبير", "وسط", "صغير"]
        )
        self.assertEqual(
            self._names({"ordering": "bottom"}), ["صغير", "وسط", "كبير"]
        )

    def test_price_order_ignores_customers_who_bought_nothing(self):
        """من لم يشترِ ليس «صفراً في آخر القائمة» بل لا معنى لمقارنته بالمبلغ.

        إنه يأخذ مكانه في النهاية حين يُرتَّب تنازلياً، ويبدأ القائمة حين يُرتَّب
        تصاعدياً — فلا يختفي زبونٌ لم يشترِ من الشاشة أبداً.
        """
        silent = Customer.objects.create(name="صامت", phone="0599111111")
        buyer = Customer.objects.create(name="مشترٍ", phone="0599222222")
        self._buy(buyer, "50")
        self.assertEqual(self._names({"ordering": "bottom"}), ["صامت", "مشترٍ"])
        self.assertEqual(self._names({"ordering": "top"}), ["مشترٍ", "صامت"])
        self.assertIsNotNone(silent.pk)

    def test_price_order_sums_a_number_written_with_spaces(self):
        """«0561 000009» و«0561000009» رقمٌ واحد، والمبلغُ يجب أن يُحسب مرّةً واحدة."""
        spaced = Customer.objects.create(name="بمسافات", phone="0561 000009")
        plain = Customer.objects.create(name="بلا مسافات", phone="0599333333")
        self._buy(spaced, "40")
        self._buy(spaced, "2")  # نفس الرقم، رسمٌ آخر: يجب أن يُجمَع معه
        self._buy(plain, "30")
        self.assertEqual(self._names({"ordering": "top"}), ["بمسافات", "بلا مسافات"])

    def test_search_keeps_closeness_first_and_the_chosen_order_after(self):
        """البحثُ يقدّم الأقرب، والترتيبُ الذي اختاره الزائر يفصل بين المتساويين."""
        old = Customer.objects.create(name="قديم", phone="0561000001")
        recent = Customer.objects.create(name="حديث", phone="0561000002")
        self._age(old, "2026-01-05T10:00:00+04:00")
        self._age(recent, "2026-09-05T10:00:00+04:00")
        # كلاهما يبدأ بالرقم المكتوب، فيتساويان في القرب — والفاصل هو التاريخ.
        self.assertEqual(
            self._names({"search": "0561", "ordering": "newest"}), ["حديث", "قديم"]
        )
        self.assertEqual(
            self._names({"search": "0561", "ordering": "oldest"}), ["قديم", "حديث"]
        )

    def _buy(self, customer, total):
        """سطرُ بيعٍ واحد باسم هذا الزبون — ليس أكثر، فالمبلغُ المطلوب هو المجموع."""
        from sale_sessions.models import Employee, SaleSession, SaleSessionItem
        from suppliers.models import Fabric

        if not hasattr(self, "_buyer"):
            self._fabric = Fabric.objects.create(name="قماش اختبار")
            self._buyer = Employee.objects.create(name="بائع", branch=self.branch)
        session = SaleSession.objects.create(employee=self._buyer, branch=self.branch)
        SaleSessionItem.objects.create(
            session=session,
            fabric=self._fabric,
            sale_type="yard",
            quantity=1,
            unit_price=total,
            total=total,
            sale_date="2026-09-10",
            customer_name=customer.name,
            customer_phone=customer.phone,
        )