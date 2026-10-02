"""اختبارات قسم الجرد الاحترافي.

الجرد قياسٌ لا مطابقة: كل ما فيه صُمّم ليمنع العدّاد من مطابقة الدفتر.
وهذه أشياء لا تُكتشف إلا بكسرها عمداً، فمن لا يكسرها يجدها تحوّلت إلى
محرفٍ خطأ. فتُختبر هنا ثلاثة حدود: ما يراه العدّاد وما لا يراه، واتّساق
الملخّص مع النشر، وبقاء سبب الفرق في السجلّ الذي يُراجَع فعلاً.
"""

from datetime import date
from decimal import Decimal
from io import BytesIO

from django.test import TestCase
from rest_framework.test import APIClient

from core.testsupport import authenticate_admin
from reports.cogs import fabric_average_costs
from sale_sessions.models import Employee
from suppliers.models import Fabric

from .models import (
    FabricRoll,
    GoodsReceipt,
    GoodsReceiptItem,
    StockCount,
    StockCountItem,
    StockMovement,
    Warehouse,
)
from .services import VARIANCE_EPSILON, count_summary, public_summary

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None


def make_fabric(name, code):
    return Fabric.objects.create(name=name, code=code, sale_price_yard=2)


class CountTestCase(TestCase):
    """أرضية جاهزة: مخزنٌ فيه قماشٌ واحد برصيدٍ دفتريٍّ ثلاثين ياردة."""

    def setUp(self):
        self.c = APIClient()
        authenticate_admin(self.c)
        self.wh = Warehouse.objects.create(name="مخزن", code="W-CNT")
        self.fabric = make_fabric("قطن", "F-COTTON")
        self.book_stock(self.fabric, "30")

    def book_stock(self, fabric, yards):
        """يضع رصيداً دفترياً في المخزن: لفةٌ متاحةٌ لم تُستهلك."""
        return FabricRoll.objects.create(
            warehouse=self.wh, fabric=fabric,
            yards=Decimal(str(yards)), remaining_yards=Decimal(str(yards)),
        )

    def make_count(self, **extra):
        payload = {"warehouse": self.wh.pk, "date": date.today().isoformat()}
        payload.update(extra)
        r = self.c.post("/api/warehouses/counts/", payload, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def count_in(self, cid, **entries):
        r = self.c.patch(
            f"/api/warehouses/counts/{cid}/items/", {"items": [entries]},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def summary_of(self, cid):
        r = self.c.get(f"/api/warehouses/counts/{cid}/")
        self.assertEqual(r.status_code, 200, r.data)
        return r.data["summary"]

    def add_fabric(self, cid, fabric):
        r = self.c.post(
            f"/api/warehouses/counts/{cid}/add_fabric/",
            {"fabric": fabric.pk}, format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        return r.data


class BlindCountTests(CountTestCase):
    """الجرد المغلق: العدّاد يقيس ولا يطابق.

    وجود الرصيد الدفتري أمام العدّاد يجعله يعدّ ليطابق، فيمرّ الفارق
    صامتاً. فإخفاؤه ليس تشديداً في الحماية بل شرطُ صحّة الجرد.
    """

    def test_book_balance_is_withheld_from_a_blind_count(self):
        data = self.make_count(blind=True)
        self.assertTrue(data["blind"])
        self.assertTrue(data["hides_system"])
        for field in ("system_yards", "difference", "is_variance"):
            self.assertNotIn(field, data["items"][0])

    def test_counter_still_sees_what_to_count(self):
        """إخفاء الرقم لا يعني منع العدّ: لا بدّ من اسم الصنف ومدخل الرصيد."""
        item = self.make_count(blind=True)["items"][0]
        self.assertEqual(item["fabric_name"], "قطن")
        self.assertTrue(item["fabric_code"])
        self.assertIsNone(item["counted_yards"])
        self.assertFalse(item["counted"])

    def test_open_count_still_shows_the_book_balance(self):
        """الجرد المفتوح اختيارٌ مقصود: من يريده يرى الفرق وهو يعدّ."""
        data = self.make_count(blind=False)
        self.assertFalse(data["hides_system"])
        self.assertEqual(
            Decimal(str(data["items"][0]["system_yards"])), Decimal("30"),
        )

    def test_counting_works_while_the_balance_is_hidden(self):
        """السؤال الحاسم: هل يستطيع العدّاد أن يُدخل رقماً أصلاً؟"""
        data = self.make_count(blind=True)
        items = self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="27.5")
        self.assertEqual(Decimal(str(items[0]["counted_yards"])), Decimal("27.5"))
        self.assertTrue(items[0]["counted"])
        self.assertNotIn("system_yards", items[0])

    def test_posting_reveals_the_balance_and_the_difference(self):
        """المراجع يحتاج الرصيد والفرق معاً بعد النشر.

        لو بقي الرصيد مخفياً لان صار الجرد حساباً بلا مراجعة: أرقام فُرِقت
        ولم يعلم أحدٌ ما الذي فُرِق ولا مقابلَه.
        """
        data = self.make_count(blind=True)
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="25")
        r = self.c.post(f"/api/warehouses/counts/{data['id']}/post/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data["hides_system"])
        item = r.data["items"][0]
        self.assertEqual(Decimal(str(item["system_yards"])), Decimal("30"))
        self.assertEqual(Decimal(str(item["difference"])), Decimal("-5"))
        self.assertTrue(item["is_variance"])

    def test_cancelled_count_stops_hiding_the_balance(self):
        """القاعدة واحدة: الإخفاء أثناء العدّ فقط.

        جلسةٌ ملغاةٌ أو منشورةٌ لم يعد أحدٌ يعدّ، فإبقاء الرصيد مخفياً فيها
        لا يحمي عدّاً بل يحجب مراجعةَ جردٍ وُثِق.
        """
        data = self.make_count(blind=True)
        self.c.post(f"/api/warehouses/counts/{data['id']}/cancel/")
        r = self.c.get(f"/api/warehouses/counts/{data['id']}/")
        self.assertFalse(r.data["hides_system"])
        self.assertEqual(
            Decimal(str(r.data["items"][0]["system_yards"])), Decimal("30"),
        )

    def test_flag_is_remembered_on_the_stored_session(self):
        """الخيار يُحفظ مع الجلسة: الجرد المغلق ليس قناعاً مؤقتاً على الردّ."""
        data = self.make_count(blind=True)
        stored = StockCount.objects.get(pk=data["id"])
        self.assertTrue(stored.blind)

    def test_the_summary_does_not_give_away_the_variance(self):
        """إخفاءٌ سطراً سطراً ثم ملخّصٌ يجمعها = لا إخفاء.

        «فروقٌ في صنفين بخمس ياردات» هو الرصيدُ الدفتري مُجموعاً ومُقرَّباً،
        فينكشف بالضبط ما حميناه سطراً سطراً. ويبقى التقدّم ظاهراً لأنه ما
        يحتاجه العدّاد ليرفع رأسه.
        """
        data = self.make_count(blind=True)
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="25")
        summary = self.summary_of(data["id"])
        self.assertEqual(summary["variances"], 0)
        self.assertEqual(summary["net_yards"], 0.0)
        self.assertEqual(summary["value"], 0.0)
        self.assertEqual(summary["counted"], 1)
        self.assertTrue(summary["complete"])

    def test_the_service_still_computes_what_the_screen_hides(self):
        """الخدمة تُحسب كاملةً للنشر؛ المخفيّ على الشاشة وحده."""
        data = self.make_count(blind=True)
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="25")
        count = StockCount.objects.get(pk=data["id"])
        self.assertEqual(count_summary(count)["net_yards"], -5.0)
        self.assertEqual(public_summary(count)["net_yards"], 0.0)

    def test_publishing_reveals_the_summary_it_withheld(self):
        data = self.make_count(blind=True)
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="25")
        r = self.c.post(f"/api/warehouses/counts/{data['id']}/post/")
        self.assertEqual(r.data["summary"]["variances"], 1)
        self.assertEqual(r.data["summary"]["net_yards"], -5.0)

    def test_the_list_does_not_leak_it_either(self):
        """القائمة تُعرض قبل فتح الجلسة، فتسريبُها أفدأُ من تسريب الشاشة."""
        data = self.make_count(blind=True)
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="25")
        row = self.c.get("/api/warehouses/counts/").data["results"][0]
        self.assertEqual(row["summary"]["variances"], 0)
        self.assertEqual(row["summary"]["net_yards"], 0.0)


class SummaryTests(CountTestCase):
    """الملخّص هو ما يقرّر «هل انتهى الجرد» — فلا يجوز أن يكذب."""

    def test_fresh_count_is_pending_not_matched(self):
        """صنفٌ لم يُعدّ ليس مطابقاً: الفرق صفرٌ لسببٍ لا صفرٌ لقيمة."""
        summary = self.summary_of(self.make_count()["id"])
        self.assertEqual(summary["items"], 1)
        self.assertEqual(summary["counted"], 0)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["variances"], 0)
        self.assertFalse(summary["complete"])

    def test_matching_count_is_complete_with_no_variance(self):
        data = self.make_count()
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="30")
        summary = self.summary_of(data["id"])
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["variances"], 0)
        self.assertEqual(summary["net_yards"], 0.0)

    def test_variances_and_net_yards_are_reported(self):
        other = make_fabric("كتان", "F-LINEN")
        self.book_stock(other, "10")
        data = self.make_count()
        self.c.patch(
            f"/api/warehouses/counts/{data['id']}/items/",
            {"items": [
                {"fabric": self.fabric.pk, "counted_yards": "27"},
                {"fabric": other.pk, "counted_yards": "14"},
            ]},
            format="json",
        )
        summary = self.summary_of(data["id"])
        self.assertEqual(summary["variances"], 2)
        self.assertEqual(summary["net_yards"], 1.0)

    def test_uncounted_items_are_not_variances(self):
        """صنفٌ ناقص الرصد وصنفٌ بلا رصد: الأول فرق، والثاني لم يبدأ."""
        other = make_fabric("كتان", "F-LINEN")
        self.book_stock(other, "10")
        data = self.make_count()
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="25")
        summary = self.summary_of(data["id"])
        self.assertEqual(summary["variances"], 1)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["net_yards"], -5.0)

    def test_the_smallest_expressible_difference_is_a_variance(self):
        """حدّ الجرد قرارٌ لا مصادفة: أوّله فرقٌ يُحرّك المخزون نصفَ سنتيمتر.

        الحقل يحفظ منزلتين عشريتين، فأصغر فرقٍ ممكنٍ هو 0.01 — وهو فوق
        ``VARIANCE_EPSILON`` بقطره. فالفارق هنا ليس تفصيلاً: هو يقرّر هل
        يُحرَّك المخزون لأجل نصفِ سنتيمتر أم لا.
        """
        data = self.make_count()
        self.assertLess(VARIANCE_EPSILON, Decimal("0.01"))
        self.count_in(
            data["id"], fabric=self.fabric.pk, counted_yards="30.01",
        )
        summary = self.summary_of(data["id"])
        self.assertEqual(summary["variances"], 1)
        self.assertEqual(summary["net_yards"], 0.01)

    def test_an_uncounted_item_is_never_a_variance_however_small(self):
        """صفرٌ لسببٍ لا صفرٌ لقيمة: الفرقُ محسوبٌ للرصيدين، والرصدُ ناقص."""
        data = self.make_count()
        self.assertEqual(self.summary_of(data["id"])["variances"], 0)

    def test_empty_count_is_not_complete(self):
        empty = StockCount.objects.create(
            number="CNT-EMPTY", warehouse=self.wh, date=date.today(),
        )
        summary = count_summary(empty)
        self.assertEqual(summary["items"], 0)
        self.assertFalse(summary["complete"])

    def test_summary_is_stable_across_repeated_calls(self):
        """حالةٌ داخليةٌ مشتركة بين استدعاءين تجعل رقمين مختلفين للرقم نفسه."""
        data = self.make_count()
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="25")
        self.assertEqual(self.summary_of(data["id"]), self.summary_of(data["id"]))


class VarianceValueTests(CountTestCase):
    """فرقُ ياردتين بلا سعرٍ لا يُراجَع ولا يُسجَّل."""

    def setUp(self):
        super().setUp()
        self.costed = make_fabric("مُسعَّر", "F-COST")
        receipt = GoodsReceipt.objects.create(
            number="GR-COST", warehouse=self.wh, date=date.today(),
            status=GoodsReceipt.Status.POSTED,
        )
        GoodsReceiptItem.objects.create(
            receipt=receipt, fabric=self.costed, yards=Decimal("100"),
            unit_price=Decimal("10"), total=Decimal("1000"),
        )
        self.book_stock(self.costed, "100")

    def test_variance_value_uses_the_average_cost(self):
        """عشر يارداتٍ ناقصةٍ من قماشٍ تكلفته عشرة = مئة قيمة تُراجَع."""
        data = self.make_count()
        self.count_in(data["id"], fabric=self.costed.pk, counted_yards="90")
        summary = self.summary_of(data["id"])
        self.assertEqual(summary["variances"], 1)
        self.assertEqual(summary["value"], -100.0)

    def test_found_stock_is_valued_in_full(self):
        """قماشٌ وُجد على الرفّ بلا دفتر: فرقُه كامل القيمة."""
        stray = make_fabric("غريب", "F-STRAY")
        data = self.add_fabric(self.make_count()["id"], stray)
        self.count_in(data["id"], fabric=stray.pk, counted_yards="15")
        summary = self.summary_of(data["id"])
        self.assertEqual(summary["net_yards"], 15.0)
        self.assertEqual(summary["variances"], 1)

    def test_value_is_zero_when_no_cost_is_known(self):
        """لا سعر = لا قيمة. الصفر أصدق من تقديرٍ من عندنا."""
        data = self.make_count()
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="10")
        summary = self.summary_of(data["id"])
        self.assertEqual(summary["variances"], 1)
        self.assertEqual(summary["value"], 0.0)

    def test_summary_accepts_a_precomputed_cost_map(self):
        """من يحسب التكلفة مرةً لصفحةٍ فيها عدّة جلسات لا يدفع الثمن مرّتين."""
        data = self.make_count()
        self.count_in(data["id"], fabric=self.costed.pk, counted_yards="95")
        count = StockCount.objects.get(pk=data["id"])
        costs = fabric_average_costs([self.costed.pk])
        self.assertEqual(count_summary(count, costs=costs)["value"], -50.0)


class VarianceExpressionTests(CountTestCase):
    """تعبير الفرق في SQL: لا بدّ أن يجيب «لم يُعدّ» إجابةً صريحة."""

    def test_null_count_reads_as_zero_variance_not_as_missing(self):
        """طرحُ NULL يبتلع الصفّ، فيختفي الصنف من العدد كأنّه رُصد بلا فرق."""
        data = self.make_count()
        summary = self.summary_of(data["id"])
        self.assertEqual(summary["items"], 1)
        self.assertEqual(summary["counted"], 0)
        self.assertEqual(summary["variances"], 0)
        self.assertEqual(summary["net_yards"], 0.0)

    def test_two_items_are_aggregated_together(self):
        """جمعُ عمودٍ وتعبيرٍ في استعلامٍ واحد: إما يعملان أو يفشل كلّهما."""
        second = StockCountItem.objects.create(
            count=StockCount.objects.get(
                id=self.make_count()["id"],
            ),
            fabric=self.fabric, system_yards=Decimal("10"), counted_yards=Decimal("12"),
        )
        self.assertIsNotNone(second.pk)
        summary = self.summary_of(second.count_id)
        self.assertEqual(summary["items"], 2)
        self.assertEqual(summary["counted"], 1)
        self.assertEqual(summary["net_yards"], 2.0)


class FoundStockTests(CountTestCase):
    """القماش الذي وُجد بلا دفتر: أهمّ ما يكتشفه الجرد وأكثره إغفالاً."""

    def test_fabric_with_no_book_stock_can_be_added(self):
        stray = make_fabric("غريب", "F-STRAY")
        data = self.add_fabric(self.make_count()["id"], stray)
        self.assertEqual(len(data["items"]), 2)
        added = next(i for i in data["items"] if i["fabric_name"] == "غريب")
        self.assertEqual(Decimal(str(added["system_yards"])), Decimal("0"))

    def test_added_fabric_takes_its_real_book_balance(self):
        """رصيدٌ لاحقٌ في الدفتر لا صفرٌ مريح: يُقاس الفرق على الحقيقة.

        اللقطة تُبنى لحظة الفتح، فما بعده من حركات لا يظهر فيها. فمن أضاف
        قماشاً ورأى صفراً قد حسب فرقه على غير رصيده.
        """
        stranded = make_fabric("متبقٍّ", "F-LEFT")
        cid = self.make_count()["id"]
        self.book_stock(stranded, "7")
        data = self.add_fabric(cid, stranded)
        added = next(i for i in data["items"] if i["fabric_name"] == "متبقٍّ")
        self.assertEqual(Decimal(str(added["system_yards"])), Decimal("7"))

    def test_adding_the_same_fabric_twice_is_rejected(self):
        data = self.make_count()
        r = self.c.post(
            f"/api/warehouses/counts/{data['id']}/add_fabric/",
            {"fabric": self.fabric.pk}, format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("مرصود", str(r.data["detail"]))

    def test_a_mistaken_line_can_be_removed(self):
        stray = make_fabric("غريب", "F-STRAY")
        cid = self.make_count()["id"]
        self.add_fabric(cid, stray)
        item = StockCount.objects.get(pk=cid).items.get(fabric=stray)
        r = self.c.post(f"/api/warehouses/counts/{cid}/items/{item.pk}/remove/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data["items"]), 1)

    def test_a_line_from_another_session_cannot_be_removed(self):
        """معرّفٌ من جلسةٍ أخرى لا يُحذف منها: الحذفُ عبر الجلسة مقيَّدٌ بها."""
        other = StockCount.objects.create(
            number="CNT-OTHER", warehouse=self.wh, date=date.today(),
        )
        stray_item = StockCountItem.objects.create(
            count=other, fabric=self.fabric, system_yards=Decimal("5"),
        )
        cid = self.make_count()["id"]
        r = self.c.post(
            f"/api/warehouses/counts/{cid}/items/{stray_item.pk}/remove/",
        )
        self.assertEqual(r.status_code, 404)
        self.assertTrue(StockCountItem.objects.filter(pk=stray_item.pk).exists())

    def test_found_stock_becomes_real_stock_when_posted(self):
        """القماشُ الذي لم يكن له دفتر يصير رصيداً حقيقياً لا رقماً في تقرير."""
        stray = make_fabric("غريب", "F-STRAY")
        cid = self.make_count()["id"]
        self.add_fabric(cid, stray)
        self.count_in(cid, fabric=self.fabric.pk, counted_yards="30")
        self.count_in(cid, fabric=stray.pk, counted_yards="15")
        r = self.c.post(f"/api/warehouses/counts/{cid}/post/")
        self.assertEqual(r.status_code, 200, r.data)
        rolls = FabricRoll.objects.filter(
            warehouse=self.wh, fabric=stray, status=FabricRoll.Status.AVAILABLE,
        )
        self.assertEqual(sum(x.remaining_yards for x in rolls), Decimal("15"))

    def test_a_posted_count_takes_no_new_lines(self):
        data = self.make_count()
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="30")
        self.c.post(f"/api/warehouses/counts/{data['id']}/post/")
        r = self.c.post(
            f"/api/warehouses/counts/{data['id']}/add_fabric/",
            {"fabric": make_fabric("متأخر", "F-LATE").pk}, format="json",
        )
        self.assertEqual(r.status_code, 400)


class CountScopeTests(CountTestCase):
    """نطاق الجرد: صنفٌ واحد، أو أصناف مختارة، أو المخزن كله.

    الجردُ الكامل لمخزنٍ كبير يبدو فضيلةً، وهو في الحقيقة شرطُ تأخير: من
    يريد جردَ صنفٍ واحد عليه أن يعدّ فيه مئة صنفٍ أولاً. والجردُ الجزئيّ
    ليس ميزةً ناقصة، بل هو وحده ما يبقى ممكناً عند مستودعٍ فيه مئة صنف
    ومن عنده ساعة، فليس «الكل» هو الأصلَ والجزئيَّ هو الاستثناء.
    """

    def setUp(self):
        super().setUp()
        self.other = make_fabric("حرير", "F-SILK")
        self.book_stock(self.other, "12")

    def fabrics_in(self, cid):
        r = self.c.get(f"/api/warehouses/counts/{cid}/")
        self.assertEqual(r.status_code, 200)
        return sorted(line["fabric"] for line in r.data["items"])

    def test_the_scope_limits_the_session_to_the_fabrics_chosen(self):
        data = self.make_count(fabrics=[self.fabric.pk])
        self.assertEqual(self.fabrics_in(data["id"]), [self.fabric.pk])

    def test_several_fabrics_can_be_chosen_at_once(self):
        data = self.make_count(fabrics=[self.fabric.pk, self.other.pk])
        self.assertEqual(self.fabrics_in(data["id"]), sorted([self.fabric.pk, self.other.pk]))

    def test_no_scope_still_means_the_whole_warehouse(self):
        """غيابُ النطاق ليس نقصاً في الإرسال، بل هو «الكل» — كما كان قبله."""
        self.assertEqual(
            self.fabrics_in(self.make_count()["id"]),
            sorted([self.fabric.pk, self.other.pk]),
        )

    def test_an_empty_scope_does_not_mean_an_empty_count(self):
        """قائمةٌ فارغة ليست جردَ لا شيء، وإلا أدّت نقرةً واحدة إلى جلسةٍ فارغة."""
        self.assertEqual(
            self.fabrics_in(self.make_count(fabrics=[])["id"]),
            sorted([self.fabric.pk, self.other.pk]),
        )

    def test_a_chosen_fabric_with_no_stock_still_gets_a_line(self):
        """القماشُ المختار بلا رصيدٍ دفتري سطرٌ صفريّ لا غياب.

        أن يوجد على الرفّ بلا أن يكون في الدفتر هو الحالة التي برّها وُجد
        الجرد؛ فمن أسقطه من الجرد أسقط الدليلَ نفسه.
        """
        lonely = make_fabric("مخمل", "F-VELVET")
        data = self.make_count(fabrics=[lonely.pk])
        self.assertEqual(self.fabrics_in(data["id"]), [lonely.pk])
        line = self.c.get(f"/api/warehouses/counts/{data['id']}/").data["items"][0]
        self.assertEqual(Decimal(str(line["system_yards"])), Decimal("0"))

    def test_the_scope_reaches_the_book_balance_of_each_chosen_fabric(self):
        """النطاقُ يختار السطور، لا الأرصدة: كل سطرٍ يأخذ رصيده الحقيقي."""
        data = self.make_count(fabrics=[self.other.pk])
        line = self.c.get(f"/api/warehouses/counts/{data['id']}/").data["items"][0]
        self.assertEqual(Decimal(str(line["system_yards"])), Decimal("12"))


class VarianceNoteTests(CountTestCase):
    """سببُ الفرق: فرقٌ بلا سببٍ معروف يعود في الجرد القادم ولا يُعالَج أبداً."""

    def test_note_is_saved_with_the_counted_amount(self):
        items = self.count_in(
            self.make_count()["id"], fabric=self.fabric.pk,
            counted_yards="28", note="قصاصة في المخزن",
        )
        self.assertEqual(items[0]["note"], "قصاصة في المخزن")

    def test_note_reaches_the_stock_movement(self):
        """السبب المكتوب في جدولٍ موازٍ لا يقرأه أحد، وهو يضيع.

        حركةُ المخزون هي ما يفتحه المحاسب عند المراجعة، فهناك وحده يُكتب.
        """
        data = self.make_count()
        self.count_in(
            data["id"], fabric=self.fabric.pk, counted_yards="28",
            note="قصاصة في المخزن",
        )
        self.c.post(f"/api/warehouses/counts/{data['id']}/post/")
        movement = StockMovement.objects.filter(
            movement_type=StockMovement.Type.COUNT,
        ).first()
        self.assertIn("قصاصة في المخزن", movement.notes)
        self.assertIn("نقص", movement.notes)

    def test_omitting_the_note_keeps_the_previous_one(self):
        """تحديثُ الرصيد وحده لا يمحو سببَ الفرق المكتوب سلفاً."""
        data = self.make_count()
        self.count_in(
            data["id"], fabric=self.fabric.pk, counted_yards="28", note="تلف",
        )
        items = self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="27")
        self.assertEqual(items[0]["note"], "تلف")

    def test_movement_without_a_note_still_reads_as_a_count(self):
        """بلا سببٍ مكتوب تبقى الحركة مقروءة: «فارق جرد» أوضح من رقمَ صامت."""
        data = self.make_count()
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="28")
        self.c.post(f"/api/warehouses/counts/{data['id']}/post/")
        movement = StockMovement.objects.filter(
            movement_type=StockMovement.Type.COUNT,
        ).first()
        self.assertIn("فارق جرد", movement.notes)


class CounterTests(CountTestCase):
    """جردٌ بلا اسم يعني عملياً: لا أحد مسؤول."""

    def setUp(self):
        super().setUp()
        self.employee = Employee.objects.create(name="أمين المخزن")

    def test_counter_is_recorded_with_the_session(self):
        data = self.make_count(counted_by=self.employee.pk)
        self.assertEqual(data["counted_by"], self.employee.pk)
        self.assertEqual(data["counted_by_name"], "أمين المخزن")

    def test_session_without_a_counter_is_allowed(self):
        """فرضُ الاسم يمنع من لا يعرف الأسماء من تسجيل جردٍ أصلاً."""
        data = self.make_count()
        self.assertIsNone(data["counted_by"])
        self.assertEqual(data["counted_by_name"], "")

    def test_counter_can_be_found_by_search(self):
        self.make_count(counted_by=self.employee.pk)
        r = self.c.get("/api/warehouses/counts/?search=أمين")
        self.assertEqual(r.data["count"], 1)


class PostingTests(CountTestCase):
    """النشر: شرطُه ورفضُه ورسائلُه."""

    def test_pending_items_are_named_by_count(self):
        """«أدخل الرصيد» وحدها لا تُنجز: كم بقي؟"""
        other = make_fabric("كتان", "F-LINEN")
        self.book_stock(other, "10")
        data = self.make_count()
        self.c.patch(
            f"/api/warehouses/counts/{data['id']}/items/",
            {"items": [{"fabric": self.fabric.pk, "counted_yards": "30"}]},
            format="json",
        )
        r = self.c.post(f"/api/warehouses/counts/{data['id']}/post/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("بقي 1", str(r.data["detail"]))

    def test_error_detail_is_a_sentence_not_a_list(self):
        """الواجهة تعرض detail نصّاً، وقائمةً فيه تعرض «['نص']» للمستخدم."""
        data = self.make_count()
        r = self.c.post(f"/api/warehouses/counts/{data['id']}/post/")
        self.assertIsInstance(r.data["detail"], str)

    def test_matching_count_posts_without_touching_stock(self):
        data = self.make_count()
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="30")
        r = self.c.post(f"/api/warehouses/counts/{data['id']}/post/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(StockMovement.objects.filter(
            movement_type=StockMovement.Type.COUNT,
        ).exists())

    def test_posting_twice_is_refused(self):
        data = self.make_count()
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="30")
        self.c.post(f"/api/warehouses/counts/{data['id']}/post/")
        r = self.c.post(f"/api/warehouses/counts/{data['id']}/post/")
        self.assertEqual(r.status_code, 400)

    def test_a_posted_count_can_no_longer_be_edited(self):
        """ما بعد النشر فارقٌ موثَّق، وصحّتُه بتعديل حركة لا بإعادة الرصد."""
        data = self.make_count()
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="30")
        self.c.post(f"/api/warehouses/counts/{data['id']}/post/")
        r = self.c.patch(
            f"/api/warehouses/counts/{data['id']}/items/",
            {"items": [{"fabric": self.fabric.pk, "counted_yards": "10"}]},
            format="json",
        )
        self.assertGreaterEqual(r.status_code, 400)

    def test_blank_count_clears_a_previous_count(self):
        """إعادة الرصد إلى «لم يُعدّ» يجب أن تُمحى فعلاً، لا أن تُترك."""
        data = self.make_count()
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="30")
        items = self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="")
        self.assertIsNone(items[0]["counted_yards"])
        self.assertFalse(items[0]["counted"])


class ListEndpointTests(CountTestCase):
    """القائمة كانت تُحمّل أصنافَ كل جلسة لعرض خمسة أعمدة."""

    def test_list_omits_items_but_carries_the_summary(self):
        self.make_count()
        r = self.c.get("/api/warehouses/counts/")
        self.assertEqual(r.status_code, 200, r.data)
        row = r.data["results"][0]
        self.assertNotIn("items", row)
        self.assertIn("summary", row)
        self.assertEqual(row["summary"]["items"], 1)

    def test_list_summary_answers_progress(self):
        data = self.make_count()
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="25")
        row = self.c.get("/api/warehouses/counts/").data["results"][0]
        self.assertEqual(row["summary"]["counted"], 1)
        self.assertEqual(row["summary"]["variances"], 1)
        self.assertTrue(row["summary"]["complete"])


class ExportTests(CountTestCase):
    """ورقةُ الجرد تُملأ بيد، وورقةُ الفروق تُقرأ بالعين."""

    def setUp(self):
        super().setUp()
        if openpyxl is None:
            self.skipTest("openpyxl not installed")

    def export(self, cid):
        r = self.c.get(f"/api/warehouses/counts/{cid}/export/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml.sheet", r["Content-Type"])
        return openpyxl.load_workbook(BytesIO(r.content))

    def header_row(self, sheet, label):
        """موضع صفّ الرأس بالبحث عن عنوانه: التخطيطُ قرارٌ داخلي للمصنع."""
        for row in range(1, sheet.max_row + 1):
            if sheet.cell(row=row, column=1).value == label:
                return row
        raise AssertionError(f"لم يُعثر على العمود {label!r}")

    def cell_in(self, sheet, label, column):
        top = self.header_row(sheet, "القماش")
        return sheet.cell(
            row=top, column=[c.value for c in sheet[top]].index(label) + 1,
        )

    def data_cells(self, sheet, label):
        """قيمةُ العمود في كل سطر بيانات (تحت الرأس)."""
        top = self.header_row(sheet, "القماش")
        column = [c.value for c in sheet[top]].index(label) + 1
        return [
            sheet.cell(row=row, column=column).value
            for row in range(top + 1, sheet.max_row + 1)
        ]

    def test_export_is_formatted(self):
        ws = self.export(self.make_count()["id"]).active
        self.assertTrue(ws.sheet_view.rightToLeft)
        self.assertIsNotNone(ws.freeze_panes)

    def test_blind_export_writes_no_book_yardage(self):
        """الورقةُ المطبوعة تُقرأ على الرفّ، وتسريبُ الرصيد يُفسد الجرد.

        إخفاءُه في الشاشة لا يكفي: الملف الذي يحمله العدّاد إلى الرفّ هو
        التسريبُ نفسه.
        """
        ws = self.export(self.make_count(blind=True)["id"]).active
        self.assertIn("الرصيد الدفتري", [c.value for c in ws[self.header_row(ws, "القماش")]])
        self.assertEqual(self.data_cells(ws, "الرصيد الدفتري"), [None])
        self.assertEqual(self.data_cells(ws, "الفرق"), [None])

    def test_blind_export_has_no_variance_sheet(self):
        book = self.export(self.make_count(blind=True)["id"])
        self.assertEqual(book.sheetnames, ["جرد"])

    def test_a_blind_export_states_no_variance(self):
        """الملفُ المطبوع يُقرأ على الرفّ، فيجب أن يُسكت كما تسكت الشاشة.

        إخفاءُ عمود الرصيد لا يكفي إذا كان سطرُ العنوان يقول «فروق: صنف
        واحد — 5 ياردات». الملفُ يحمل التسريبَ نفسه إلى الرفّ.
        """
        data = self.make_count(blind=True)
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="25")
        subtitle = str(self.export(data["id"]).active.cell(row=2, column=1).value)
        self.assertNotIn("فروق:", subtitle)
        self.assertIn("جرد مغلق", subtitle)

    def test_open_export_writes_the_book_yardage_and_a_totals_row(self):
        data = self.make_count(blind=False)
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="25")
        ws = self.export(data["id"])["جرد"]
        self.assertEqual(self.data_cells(ws, "الرصيد الدفتري")[0], 30.0)
        self.assertEqual(self.data_cells(ws, "الفرق")[0], -5.0)
        self.assertIn("الإجمالي", self.data_cells(ws, "القماش"))

    def test_posted_count_gets_a_second_sheet_of_variances(self):
        data = self.make_count()
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="25")
        self.c.post(f"/api/warehouses/counts/{data['id']}/post/")
        book = self.export(data["id"])
        self.assertEqual(book.sheetnames, ["جرد", "فروق"])
        self.assertEqual(self.data_cells(book["فروق"], "الحالة"), ["فروق"])

    def test_variance_sheet_keeps_the_reason(self):
        """السبب بلا سطر فرقٍ لا يُقرأ: عمودُه فارغ في كل استعمال."""
        data = self.make_count()
        self.count_in(
            data["id"], fabric=self.fabric.pk, counted_yards="25",
            note="قصاصة",
        )
        self.c.post(f"/api/warehouses/counts/{data['id']}/post/")
        book = self.export(data["id"])
        self.assertEqual(self.data_cells(book["فروق"], "سبب الفرق"), ["قصاصة"])

    def test_matched_count_has_no_variance_sheet(self):
        data = self.make_count()
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="30")
        self.c.post(f"/api/warehouses/counts/{data['id']}/post/")
        self.assertEqual(self.export(data["id"]).sheetnames, ["جرد"])

    def test_subtitle_names_the_counter_and_the_progress(self):
        """من يفتح الملف بعد شهر يجب أن يعرف أيّ جردٍ هذا وكم بقي فيه."""
        employee = Employee.objects.create(name="أمين المخزن")
        data = self.make_count(counted_by=employee.pk)
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="25")
        subtitle = str(self.export(data["id"]).active.cell(row=2, column=1).value)
        self.assertIn("أمين المخزن", subtitle)
        self.assertIn("1 من 1", subtitle)
        self.assertIn("فروق", subtitle)

    def test_filename_is_ascii_with_an_arabic_form(self):
        data = self.make_count()
        r = self.c.get(f"/api/warehouses/counts/{data['id']}/export/")
        disposition = r["Content-Disposition"]
        self.assertTrue(disposition.isascii())
        self.assertIn('filename="stock-count.xlsx"', disposition)
        self.assertIn("filename*=UTF-8''", disposition)

    def test_the_sheet_carries_the_purchase_and_sale_price(self):
        """ورقةُ الجرد تُقرأ بالمتر وحده فتبقى بلا معنى للمال.

        ناقصُ قماشٍ خمسة ياردات جردٌ ناقص، لكن قيمته خمسون أو مئة بحسب
        سعره. فالسعران ليسا زينة: بهما يُثمن النقص والزيادة، لا مقدارهما
        وحده.
        """
        Fabric.objects.filter(pk=self.fabric.pk).update(
            purchase_price=Decimal("12.5"), sale_price_yard=Decimal("20"),
        )
        data = self.make_count(blind=False)
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="25")
        ws = self.export(data["id"])["جرد"]
        self.assertEqual(self.data_cells(ws, "سعر الشراء")[0], 12.5)
        self.assertEqual(self.data_cells(ws, "سعر البيع")[0], 20.0)

    def test_a_blind_sheet_prints_the_prices_and_still_hides_the_balance(self):
        """السعرُ معلومةٌ عن القماش، والرصيدُ جوابُ الجرد — فأولاهما يبقى وثانيهما يختفي."""
        Fabric.objects.filter(pk=self.fabric.pk).update(
            purchase_price=Decimal("12.5"), sale_price_yard=Decimal("20"),
        )
        data = self.make_count(blind=True)
        self.count_in(data["id"], fabric=self.fabric.pk, counted_yards="25")
        ws = self.export(data["id"]).active
        self.assertEqual(self.data_cells(ws, "سعر الشراء")[0], 12.5)
        self.assertEqual(self.data_cells(ws, "سعر البيع")[0], 20.0)
        self.assertEqual(self.data_cells(ws, "الرصيد الدفتري"), [None])

    def test_missing_openpyxl_gives_a_clear_error(self):
        from core import excel

        data = self.make_count()
        real = excel._lib
        excel._lib = lambda: None
        try:
            r = self.c.get(f"/api/warehouses/counts/{data['id']}/export/")
        finally:
            excel._lib = real
        self.assertEqual(r.status_code, 500)
        self.assertIn("openpyxl", str(r.data["detail"]))


class CountPriceTests(CountTestCase):
    """سعرا الشراء والبيع في ورقة الجرد: لا يُقاس النقص بالمتر وحده.

    ناقصُ قماشٍ خمسة ياردات جردٌ ناقص، لكن قيمته خمسون أو مئة أو ألف بحسب
    سعره. فعمودُ الأ yards يقول *كم* ضاع، ولا يقول *كم* ضاع من المال —
    وهذا هو السؤال الذي يُبنى عليه قرار التعويض.
    """

    def priced(self, purchase="12.5", sale="20"):
        Fabric.objects.filter(pk=self.fabric.pk).update(
            purchase_price=Decimal(purchase), sale_price_yard=Decimal(sale),
        )
        return self.fabric

    def line_of(self, cid):
        r = self.c.get(f"/api/warehouses/counts/{cid}/")
        self.assertEqual(r.status_code, 200)
        return r.data["items"][0]

    def test_the_counter_sees_both_prices(self):
        self.priced()
        line = self.line_of(self.make_count()["id"])
        self.assertEqual(Decimal(str(line["purchase_price"])), Decimal("12.5"))
        self.assertEqual(Decimal(str(line["sale_price"])), Decimal("20"))

    def test_a_blind_count_still_shows_the_prices(self):
        """السعرُ بياناتُ القماش، لا إجابةُ الجرد.

        الجردُ المغلق يُخفي الرصيد الدفتري والفرق لأنهما يجعلان العدّاد
        يطابق بدل أن يعدّ. أمّا السعرُ فمعلومةٌ ثابتة عن القماش تُقرأ
        في الورقةِ الدفترية أيضاً، وإخفاؤها تُحرم العدّاد من تقدير ما
        يعدّ بلا أن تكسر سرّيةَ الجرد.
        """
        self.priced()
        line = self.line_of(self.make_count(blind=True)["id"])
        self.assertEqual(Decimal(str(line["purchase_price"])), Decimal("12.5"))
        self.assertNotIn("system_yards", line)
        self.assertNotIn("difference", line)

    def test_prices_follow_the_fabric_not_the_old_line(self):
        """السعرُ يُقرأ لحظة العرض، فتغييرُ سعر القماش يغيّر ما يُعرض.

        لو خُزِّن السعرُ في سطر الجرد لتقادم مع القماش: يبقى الجردُّ
        القديم يثمن عيّنته بسعرٍ لم يبقِ له.
        """
        data = self.make_count()
        self.priced()
        self.assertEqual(Decimal(str(self.line_of(data["id"])["sale_price"])), Decimal("20"))
        self.priced(sale="25")
        self.assertEqual(Decimal(str(self.line_of(data["id"])["sale_price"])), Decimal("25"))
