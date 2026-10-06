from django.conf import settings
import re
from decimal import Decimal

from django.db.models import (
    Case,
    Count,
    DecimalField,
    IntegerField,
    Max,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Replace
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from core.daterange import resolve_range
from core.branch_scope import scope_queryset
from core.phones import find_by_phone, normalize_phone

from sale_sessions.models import SaleSessionItem

from .models import Customer
from .serializers import CustomerSerializer
from .whatsapp import send_customer_welcome

class CustomerViewSet(viewsets.ModelViewSet):
    permission_section = "customers"
    queryset = Customer.objects.select_related("branch").order_by("name")
    serializer_class = CustomerSerializer
    search_fields = ["name", "phone", "email", "address"]
    ordering_fields = ["name", "phone", "created_at", "is_active", "purchase_total"]
    #: «الأحدث أولاً» و«الأعلى سعراً» اسمان يطلبهما الموظف بلغته، لا أسماء
    #: أعمدة يعرفها الخادم وحده. فنرتّب فقط حين يُطلب الترتيب، فلا نُحمّل
    #: كل استعلامٍ بلا فائدة استعلاماً فرعياً على كل سطرٍ فيه.
    ordering_labels = {
        "newest": "-created_at",
        "oldest": "created_at",
        "top": "-purchase_total",
        "bottom": "purchase_total",
    }
    #: أعمدةُ الترتيب التي اختارها الزائر لهذا الطلب، لتبقى فاصلاً بعد القرب
    #: في البحث. تُصفَّر كلَّ طلب في ``_requested_ordering``.
    _order_columns = ()
    #: ما يريده المستخدم من البحث ليس «الاسم أبجدياً» بل «الأقرب إلى ما
    #: كتبه». فنرتّب قرب المطابقة بأنفسنا في ``_search`` —لأن ذلك يتطلّب ذلك
    #: تجريد الرقم من فواصله، ولا يفعل ``SearchFilter`` ذلك — ونترك
    #: ``OrderingFilter`` يعمل إن طلبه العميل صراحةً.
    filter_backends = [OrderingFilter]

    def perform_create(self, serializer):
        customer = serializer.save()
        send_customer_welcome(customer)

    def get_queryset(self):
        qs = super().get_queryset()
        qs = scope_queryset(self.request, qs)
        params = self.request.query_params
        branch = params.get("branch")
        if branch:
            qs = qs.filter(branch_id=branch)
        is_active = params.get("is_active")
        if is_active in ("true", "1"):
            qs = qs.filter(is_active=True)
        elif is_active in ("false", "0"):
            qs = qs.filter(is_active=False)
        date_from = params.get("date_from")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        date_to = params.get("date_to")
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        qs = self._requested_ordering(qs, params.get("ordering"))
        return self._search(qs, params.get("search"), tiebreak=self._order_columns)

    def _requested_ordering(self, qs, requested):
        """يترجم اسماً مختصراً للترتيب إلى عمودٍ حقيقي، ويضيفه إن كان عموداً محسوباً.

        «الأحدث أولاً» و«الأعلى سعراً» اسمان يطلبهما الموظف بلغته، لا أسماء
        أعمدة يعرفها الخادم وحده. فنترجمهما إلى ``created_at`` و
        ``purchase_total``، ولا نضيف استعلاماً فرعياً إلا إن طُلب ترتيبٌ
        بالمبلغ فعلاً — وخلاف ذلك فالحسابُ على كل استعلام بلا فائدة.
        """
        self._order_columns = ()
        if not requested:
            return qs
        columns = tuple(
            self.ordering_labels.get(part.strip(), part.strip())
            for part in str(requested).split(",")
            if part.strip()
        )
        if not columns:
            return qs
        if any(col.lstrip("-") == "purchase_total" for col in columns):
            qs = self._annotate_purchase_total(qs)
        self._order_columns = columns
        return qs.order_by(*columns)

    def _annotate_purchase_total(self, qs):
        """يربط «مجموع مشتريات الزبون» بالسجلّ نفسِه، ليصير ترتيباً لا زينة.

        المجموعُ يُحسب مرّتين برسمين: كما سُجِّل، وبلا مسافات — فمن كتب
        الرقم مرّتين مختلفَ الرسم لا يلتقي مَن يقرأه. نجمعهما معاً أوّلاً
        ثم نربط، تماماً كما يفعل ``_purchase_stats`` في الذاكرة.
        """
        items = scope_queryset(
            self.request,
            SaleSessionItem.objects.all(),
            branch_field="session__branch",
        ).filter(
            Q(customer_phone=OuterRef("phone"))
            | Q(customer_phone=Replace(OuterRef("phone"), Value(" "), Value("")))
        )
        total = Subquery(
            items.values("customer_phone").annotate(t=Sum("total")).values("t"),
            output_field=DecimalField(max_digits=15, decimal_places=2),
        )
        return qs.annotate(purchase_total=Coalesce(total, Value(Decimal("0"))))

    def _search(self, qs, term, tiebreak=()):
        """يبحث بالاسم أو برقم الهاتف، ويرتّب من الأقرب إلى الأبعد.

        ما يريده المستخدم من البحث ليس «الاسم أبجدياً» بل «الأقرب إلى ما
        كتبه»: يكتب رقماً جزئياً فيبحث به عن صاحب الرقم، فيقرأ «هذا هو»
        أولاً. والترتيب بالاسم يخلط المتشابهين في صفحات مختلفة، فيبدو
        البحث كأنه لا يستجيب حتى يُكتب الرقم كاملاً.

        الترتيب: رقم مطابق تماماً ← يبدأ بالرقم ← يحتوي الرقم ← الاسم يبدأ
        بالكلمة ← الاسم يحتويها.

        closeness comes first and the requested sort is only the tie-break:
        فلو غلب الترتيبُ المطلوب على القرب، عاد البحثُ إلى ما كان عليه قبل
        أن يُصلحه: متشابهون متباعدون. أمّا بلا بحثٍ أصلاً فالترتيبُ المطلوب
        هو كلُّ ما بقي — وهذا ما كان يضيع لأنّ ``order_by("name")`` هنا كان
        يبتلع كلَّ اختيارٍ للزائر.
        """
        needle = normalize_phone(term)
        if not needle:
            return qs.order_by(*(tiebreak or ("name",)))

        if needle.isdigit():
            # الهاتف مخزَّن كما سُجّل، فقد يكون بمسافات. فنطابق على ما
            # خُزّن وعلى تجريده معاً، وإلا اختفت نتيجة البحث بالكامل
            # لمجرد أن المستخدم كتب الرقم بنفس الطريقة التي رآه.
            qs = qs.filter(
                Q(phone__icontains=term)
                | Q(phone__icontains=needle)
                | Q(name__icontains=needle)
            )
            steps = [
                When(phone=needle, then=0),
                When(phone__startswith=needle, then=1),
                When(phone__contains=needle, then=2),
            ]
        else:
            qs = qs.filter(
                Q(name__icontains=needle)
                | Q(phone__icontains=needle)
                | Q(email__icontains=needle)
                | Q(address__icontains=needle)
            )
            steps = []

        base = len(steps)
        steps += [
            When(name__istartswith=needle, then=base),
            When(name__icontains=needle, then=base + 1),
        ]
        rank = Case(*steps, default=99, output_field=IntegerField())
        return qs.annotate(_match_rank=rank).order_by("_match_rank", *(tiebreak or ()), "name")

    def _phone_variants(self, phones):
        out = set()
        for p in phones:
            if not p:
                continue
            out.add(p)
            out.add(re.sub(r"\s", "", p))
        return out

    def _purchase_stats(self, phones):
        """إجمالي المشتريات وعددها وآخر تاريخ شراء لكل رقم هاتف."""
        stats = {}
        if not phones:
            return stats
        rows = (
            scope_queryset(
                self.request,
                SaleSessionItem.objects.filter(customer_phone__in=phones),
                branch_field="session__branch",
            )
            .values("customer_phone")
            .annotate(
                total=Sum("total"),
                count=Count("id"),
                last=Max("sale_date"),
            )
        )
        for r in rows:
            stats[r["customer_phone"]] = r
        return stats

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        customers = response.data.get("results") or []
        phones = self._phone_variants([c.get("phone") for c in customers])
        stats = self._purchase_stats(phones)
        for c in customers:
            variants = self._phone_variants([c.get("phone")])
            total = sum(float(stats.get(v, {}).get("total") or 0) for v in variants)
            count = sum(int(stats.get(v, {}).get("count") or 0) for v in variants)
            last = None
            for v in variants:
                v_last = stats.get(v, {}).get("last")
                if v_last and (last is None or v_last > last):
                    last = v_last
            c["purchase_total"] = total
            c["purchase_count"] = count
            c["last_purchase_date"] = last.isoformat() if last else None
        return response

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = self.get_queryset()
        start_date, end_date, _ = resolve_range(request.query_params, default_period="month")
        return Response({
            "total_customers": qs.count(),
            "active_count": qs.filter(is_active=True).count(),
            "new_count": qs.filter(
                created_at__date__gte=start_date, created_at__date__lte=end_date
            ).count(),
            "with_phone_count": qs.exclude(phone__isnull=True).exclude(phone="").count(),
        })

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        """هل هذا الرقم مسجَّل؟ سؤالٌ له جوابٌ واحد، فلا يُترك فراغاً.

        الشاشة تعرض «لا يوجد زبون مسجَّل بهذا الرقم» على هذا الجواب، فيصير
        الرقمُ الخطأُ حكماً على زبونٍ مسجَّلٍ فعلاً، فيُطلب من المحاسب أن
        يضيفه من جديد — وهو ليس جديداً، ويأخذ عرضَ زبونٍ آخر واسمَه.
        """
        phone = (request.query_params.get("phone") or "").strip()
        if not phone:
            return Response({"found": False, "customer": None})
        customer = self._find_by_phone(request, phone)
        if customer is None:
            return Response({"found": False, "customer": None})
        data = CustomerSerializer(customer).data
        data["last_purchase_date"] = self._last_purchase_date(request, phone)
        return Response({"found": True, "customer": data})

    def _find_by_phone(self, request, phone):
        return find_by_phone(
            scope_queryset(request, Customer.objects.all()), phone
        ).first()

    @staticmethod
    def _last_purchase_date(request, phone):
        phones = {phone, re.sub(r"\s", "", phone)} if phone else {phone}
        return (
            scope_queryset(
                request,
                SaleSessionItem.objects.filter(customer_phone__in=phones),
                branch_field="session__branch",
            )
            .order_by("-sale_date")
            .values_list("sale_date", flat=True)
            .first()
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": settings.API_MESSAGES["deleted"]},
            status=status.HTTP_200_OK,
        )
