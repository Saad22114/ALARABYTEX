"""بحث شامل عبر كيانات النظام لواجهة الأوامر السريعة (Ctrl+K).

المبدأ: كل نوع بحث مرتبط بقسم صلاحيات، ولا يظهر أي نوع لا يملك المستخدم صلاحية
رؤيته — حتى لا يكشف البحث أسماء موردين أو موظفين لا يحق للمستخدم الاطلاع عليهم.
كما تُقيَّد النتائج بنطاق الفرع عبر ``scope_queryset``when يملك النموذج فرعاً.
"""

from dataclasses import dataclass, field
from typing import Callable

from django.db.models import Q

from branches.models import Branch
from core.branch_scope import scope_queryset
from core.permissions import section_view_allowed
from customers.models import Customer
from expenses.models import ExpenseCategory
from partners.models import Partner
from rest_framework.response import Response
from rest_framework.views import APIView
from sale_sessions.models import Employee
from suppliers.models import Fabric, Supplier
from warehouses.models import Warehouse

MIN_QUERY_LENGTH = 2
MAX_QUERY_LENGTH = 100
DEFAULT_PER_TYPE = 5
MAX_PER_TYPE = 20


@dataclass(frozen=True)
class SearchSpec:
    key: str
    label: str
    singular: str
    section: str
    icon: str
    href: str
    model: object
    fields: tuple
    title_field: str = "name"
    branch_field: str | None = "branch"
    subtitle: Callable | None = None
    weight: int = 0
    extra: Callable = field(default=lambda obj: {})


def _first(*values):
    for v in values:
        if v not in (None, "", []):
            return v
    return ""


SPECS = (
    SearchSpec(
        key="supplier",
        label="الموردون",
        singular="مورد",
        section="suppliers",
        icon="truck",
        href="/suppliers",
        model=Supplier,
        fields=("name", "company_name", "phone", "email", "city", "tax_number"),
        branch_field=None,
        subtitle=lambda o: _first(o.company_name, o.city, o.phone, o.email),
    ),
    SearchSpec(
        key="fabric",
        label="الأقمشة",
        singular="قماش",
        section="fabrics",
        icon="layers",
        href="/fabrics",
        model=Fabric,
        fields=("name", "code", "barcode", "fabric_type", "color", "composition", "manufacturer"),
        branch_field=None,
        subtitle=lambda o: _first(o.code, o.color, o.fabric_type, o.composition),
    ),
    SearchSpec(
        key="customer",
        label="الزبائن",
        singular="زبون",
        section="customers",
        icon="users",
        href="/customers",
        model=Customer,
        fields=("name", "phone", "email", "address", "notes"),
        subtitle=lambda o: _first(o.phone, o.email, o.address),
    ),
    SearchSpec(
        key="employee",
        label="الموظفون",
        singular="موظف",
        section="employees",
        icon="user",
        href="/employees",
        model=Employee,
        fields=("name", "phone", "department", "email"),
        subtitle=lambda o: _first(o.department, o.phone, o.email),
    ),
    SearchSpec(
        key="partner",
        label="الشركاء",
        singular="شريك",
        section="partners",
        icon="handshake",
        href="/partners",
        model=Partner,
        fields=("name", "notes"),
        branch_field=None,
        subtitle=lambda o: _first(o.notes),
    ),
    SearchSpec(
        key="warehouse",
        label="المخازن",
        singular="مخزن",
        section="warehouses",
        icon="warehouse",
        href="/warehouses",
        model=Warehouse,
        fields=("name", "code", "location", "phone", "manager_name"),
        subtitle=lambda o: _first(o.code, o.location, o.manager_name),
    ),
    SearchSpec(
        key="branch",
        label="الفروع",
        singular="فرع",
        section="branches",
        icon="building",
        href="/branches",
        model=Branch,
        fields=("name", "code", "phone", "city", "address"),
        branch_field="id",
        subtitle=lambda o: _first(o.code, o.city, o.phone),
    ),
    SearchSpec(
        key="expense_category",
        label="تصنيفات المصاريف",
        singular="تصنيف",
        section="expenses",
        icon="tag",
        href="/expenses?tab=categories",
        model=ExpenseCategory,
        fields=("name", "code", "notes"),
        branch_field=None,
        subtitle=lambda o: _first(o.code, o.notes),
    ),
)

SPECS_BY_KEY = {s.key: s for s in SPECS}


def _rank(spec, query):
    """ترتيب بالأولوية: تطابق تام ← بادئة ← يحتوي، ثم أبجدياً."""
    lowered = query.lower()

    def score(obj):
        title = str(getattr(obj, spec.title_field, "") or "").lower()
        if title == lowered:
            return 0
        if title.startswith(lowered):
            return 1
        return 2

    return score


def _matches(spec, query):
    condition = Q()
    for field_name in spec.fields:
        condition |= Q(**{f"{field_name}__icontains": query})
    return condition


def _row(spec, obj):
    return {
        "type": spec.key,
        "type_label": spec.singular,
        "group_label": spec.label,
        "icon": spec.icon,
        "id": obj.pk,
        "title": str(getattr(obj, spec.title_field, "") or "").strip() or f"#{obj.pk}",
        "subtitle": str(spec.subtitle(obj) if spec.subtitle else "").strip(),
        "href": spec.href,
        "extra": spec.extra(obj) if spec.extra else {},
    }


class GlobalSearchView(APIView):
    permission_section = "@search"

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if len(query) < MIN_QUERY_LENGTH:
            return Response(
                {
                    "query": query,
                    "total": 0,
                    "groups": [],
                    "results": [],
                    "min_length": MIN_QUERY_LENGTH,
                }
            )

        query = query[:MAX_QUERY_LENGTH]
        per_type = request.query_params.get("limit")
        try:
            limit = int(per_type) if per_type else DEFAULT_PER_TYPE
        except (TypeError, ValueError):
            limit = DEFAULT_PER_TYPE
        limit = max(1, min(limit, MAX_PER_TYPE))

        requested = (request.query_params.get("types") or "").strip()
        wanted = [t.strip() for t in requested.split(",") if t.strip()]

        groups = []
        flat = []
        for spec in SPECS:
            if wanted and spec.key not in wanted:
                continue
            if not section_view_allowed(request, spec.section):
                continue
            rows = self._search(request, spec, query, limit)
            if not rows:
                continue
            groups.append(
                {
                    "key": spec.key,
                    "label": spec.label,
                    "icon": spec.icon,
                    "count": len(rows),
                    "results": rows,
                }
            )
            flat.extend(rows)

        return Response(
            {
                "query": query,
                "total": len(flat),
                "groups": groups,
                "results": flat,
            }
        )

    def _search(self, request, spec, query, limit):
        qs = spec.model.objects.filter(_matches(spec, query))
        if spec.branch_field:
            qs = scope_queryset(request, qs, spec.branch_field)
        rows = list(qs[: limit * 4])
        rows.sort(key=_rank(spec, query))
        return [_row(spec, obj) for obj in rows[:limit]]
