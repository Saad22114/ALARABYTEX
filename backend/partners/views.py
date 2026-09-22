from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from reports.views import _export_generic_to_xlsx, _xlsx_response

from .models import Partner, PartnerOperation, PartnerMovement
from .serializers import (
    PartnerBriefSerializer,
    PartnerMovementReportSerializer,
    PartnerOperationReadSerializer,
    PartnerOperationWriteSerializer,
    PartnerSerializer,
)
from .services import signed_movement_amount


class PartnerViewSet(viewsets.ModelViewSet):
    permission_section = "partners"
    serializer_class = PartnerSerializer
    search_fields = ["name", "notes"]

    def get_queryset(self):
        from .models import PartnerMovement as PM
        return (
            Partner.objects.all()
            .order_by("name")
            .annotate(
                support=Sum(
                    "movements__amount",
                    filter=Q(movements__movement_type=PM.MovementType.SUPPORT),
                ),
                withdraw=Sum(
                    "movements__amount",
                    filter=Q(movements__movement_type=PM.MovementType.WITHDRAW),
                ),
            )
        )

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.movements.exists():
            return Response(
                {"detail": "لا يمكن حذف الشريك لوجود حركات مرتبطة بحسابه"},
                status=400,
            )
        obj.delete()
        return Response({"detail": settings.API_MESSAGES["deleted"]}, status=200)

    @action(detail=True, methods=["get"], url_path="movements")
    def movements(self, request, pk=None):
        partner = self.get_object()
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        qs = partner.movements.select_related("operation").all()
        if date_from:
            qs = qs.filter(operation__date__gte=date_from)
        if date_to:
            qs = qs.filter(operation__date__lte=date_to)
        qs = list(qs.order_by("operation__date", "created_at", "id"))

        opening = Decimal("0")
        if date_from:
            before = (
                partner.movements.filter(operation__date__lt=date_from)
                .select_related("operation")
                .all()
            )
            opening = sum((signed_movement_amount(m) for m in before), Decimal("0"))

        running = opening
        total_support = Decimal("0")
        total_withdraw = Decimal("0")
        for m in qs:
            signed = signed_movement_amount(m)
            running += signed
            m.running_balance = running
            if signed > 0:
                total_support += m.amount
            else:
                total_withdraw += m.amount

        export = request.query_params.get("export") == "xlsx"
        if export:
            headers = [
                "التاريخ", "رقم العملية", "النوع", "طريقة الدفع",
                "المبلغ", "الرصيد الجاري", "السبب", "ملاحظات",
            ]
            rows = [
                [
                    str(m.operation.date),
                    m.operation.number,
                    m.get_movement_type_display(),
                    m.operation.get_payment_method_display(),
                    float(m.amount),
                    float(m.running_balance),
                    m.operation.reason,
                    m.operation.notes,
                ]
                for m in qs
            ]
            wb = _export_generic_to_xlsx("حركات الشريك", headers, rows)
            if wb is not None:
                return _xlsx_response(wb, f"تقرير_حركات_{partner.name}")

        return Response({
            "partner": PartnerBriefSerializer(partner).data,
            "date_from": date_from,
            "date_to": date_to,
            "opening_balance": opening,
            "closing_balance": running,
            "movements": PartnerMovementReportSerializer(qs, many=True).data,
            "totals": {
                "total_support": total_support,
                "total_withdraw": total_withdraw,
                "net": total_support - total_withdraw,
            },
        })

    @action(detail=False, methods=["get"], url_path="distribution")
    def distribution(self, request):
        """تقرير حصة كل شريك مع احتساب التوزيع والإطفاء (تسوية الحسابات).

        يقارن الرصيد الفعلي لكل شريك مع نصيبه النظري حسب نسبة المشاركة، ويقترح
        التسوية المطلوبة (إضافة/سحب رصيد) لضبط الحسابات. يدعم تحديد الفترة عبر
        date_from/date_to فيقتصر الحساب على حركات الفترة المحددة.
        """
        from .models import PartnerMovement as PM

        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        period_filter = {}
        if date_from:
            period_filter["movements__operation__date__gte"] = date_from
        if date_to:
            period_filter["movements__operation__date__lte"] = date_to

        pm_filter = Q(**period_filter) if period_filter else Q()
        qs = (
            Partner.objects.filter(is_active=True)
            .annotate(
                support=Coalesce(
                    Sum(
                        "movements__amount",
                        filter=Q(movements__movement_type=PM.MovementType.SUPPORT) & pm_filter,
                    ),
                    Decimal("0"),
                ),
                withdraw=Coalesce(
                    Sum(
                        "movements__amount",
                        filter=Q(movements__movement_type=PM.MovementType.WITHDRAW) & pm_filter,
                    ),
                    Decimal("0"),
                ),
            )
            .order_by("name")
        )
        partners = list(qs)
        total_support = sum((p.support or Decimal("0") for p in partners), Decimal("0"))
        total_withdraw = sum((p.withdraw or Decimal("0") for p in partners), Decimal("0"))
        total_net = total_support - total_withdraw

        items = []
        for p in partners:
            support = p.support or Decimal("0")
            withdraw = p.withdraw or Decimal("0")
            actual_net = support - withdraw
            theoretical_share = total_net * p.share_percent / Decimal("100")
            difference = theoretical_share - actual_net
            if abs(difference) < Decimal("0.005"):
                settlement = "balanced"
            elif difference < 0:
                settlement = "withdraw"
            else:
                settlement = "add"
            items.append({
                "id": p.id,
                "name": p.name,
                "share_percent": p.share_percent,
                "total_support": support,
                "total_withdraw": withdraw,
                "actual_net": actual_net,
                "theoretical_share": theoretical_share,
                "difference": difference,
                "settlement": settlement,
                "settlement_amount": abs(difference),
            })

        export = request.query_params.get("export") == "xlsx"
        if export:
            headers = [
                "الشريك", "نسبة المشاركة %", "الدعم", "السحب",
                "الصافي الفعلي", "النصيب النظري", "الفرق (نظري - فعلي)", "التسوية المطلوبة",
            ]
            rows = [
                [
                    it["name"],
                    float(it["share_percent"]),
                    float(it["total_support"]),
                    float(it["total_withdraw"]),
                    float(it["actual_net"]),
                    float(it["theoretical_share"]),
                    float(it["difference"]),
                    {
                        "balanced": "متوازن",
                        "add": "إضافة (دعم)",
                        "withdraw": "سحب من الرصيد",
                    }[it["settlement"]],
                ]
                for it in items
            ]
            wb = _export_generic_to_xlsx(
                f"تقرير_حصص_الشركاء_{date_from or 'all'}_{date_to or 'all'}", headers, rows
            )
            if wb is not None:
                return _xlsx_response(wb, "تقرير_حصص_الشركاء")

        def _to_float(value):
            return float(value)

        return Response({
            "date_from": date_from,
            "date_to": date_to,
            "total_support": _to_float(total_support),
            "total_withdraw": _to_float(total_withdraw),
            "total_net": _to_float(total_net),
            "items": [
                {
                    "id": it["id"],
                    "name": it["name"],
                    "share_percent": _to_float(it["share_percent"]),
                    "total_support": _to_float(it["total_support"]),
                    "total_withdraw": _to_float(it["total_withdraw"]),
                    "actual_net": _to_float(it["actual_net"]),
                    "theoretical_share": _to_float(it["theoretical_share"]),
                    "difference": _to_float(it["difference"]),
                    "settlement": it["settlement"],
                    "settlement_amount": _to_float(it["settlement_amount"]),
                }
                for it in items
            ],
        })


class PartnerOperationViewSet(viewsets.ModelViewSet):
    permission_section = "partners"
    search_fields = ["number", "notes", "reason"]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return PartnerOperationReadSerializer
        return PartnerOperationWriteSerializer

    def get_queryset(self):
        qs = PartnerOperation.objects.prefetch_related("movements__partner").all()
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        partner_id = self.request.query_params.get("partner")
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        if partner_id:
            qs = qs.filter(partner_id=partner_id)
        return qs

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = self.get_queryset()
        agg = qs.aggregate(
            total_amount=Sum("amount"),
            support_amount=Sum(
                "amount", filter=Q(operation_type=PartnerOperation.OperationType.SUPPORT)
            ),
            withdraw_amount=Sum(
                "amount", filter=Q(operation_type=PartnerOperation.OperationType.WITHDRAW)
            ),
            support_count=Count(
                "id", filter=Q(operation_type=PartnerOperation.OperationType.SUPPORT)
            ),
            withdraw_count=Count(
                "id", filter=Q(operation_type=PartnerOperation.OperationType.WITHDRAW)
            ),
        )
        total_amount = agg["total_amount"] or Decimal("0")
        support_amount = agg["support_amount"] or Decimal("0")
        withdraw_amount = agg["withdraw_amount"] or Decimal("0")
        return Response({
            "count": qs.count(),
            "total_amount": float(total_amount),
            "support_count": agg["support_count"],
            "support_amount": float(support_amount),
            "withdraw_count": agg["withdraw_count"],
            "withdraw_amount": float(withdraw_amount),
            "net": float(support_amount - withdraw_amount),
        })

    def list(self, request, *args, **kwargs):
        export = request.query_params.get("export") == "xlsx"
        if export:
            qs = self.filter_queryset(self.get_queryset())
            headers = [
                "التاريخ", "رقم العملية", "الشريك", "النوع",
                "طريقة الدفع", "المبلغ", "السبب", "ملاحظات",
            ]
            rows = [
                [
                    str(op.date),
                    op.number,
                    op.partner.name if op.partner else "",
                    op.get_operation_type_display(),
                    op.get_payment_method_display(),
                    float(op.amount),
                    op.reason,
                    op.notes,
                ]
                for op in qs
            ]
            wb = _export_generic_to_xlsx("عمليات الشركاء", headers, rows)
            if wb is not None:
                return _xlsx_response(wb, "عمليات_الشركاء")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        try:
            from accounting.services import post_partner_operation
            post_partner_operation(instance)
        except Exception:
            pass
        return Response(
            PartnerOperationReadSerializer(instance, context=self.get_serializer_context()).data,
            status=201,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        obj = self.get_object()
        serializer = self.get_serializer(obj, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            from accounting.models import JournalEntry
            from accounting.services import post_partner_operation, unpost_source
            from .services import refresh_partner_movement
            unpost_source(JournalEntry.Source.PARTNER, obj.pk)
            obj.movements.all().delete()
            instance = serializer.save()
            refresh_partner_movement(instance)
            try:
                post_partner_operation(instance)
            except Exception:
                pass
        return Response(
            PartnerOperationReadSerializer(instance, context=self.get_serializer_context()).data,
            status=200,
        )

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        try:
            from accounting.models import JournalEntry
            from accounting.services import unpost_source
            unpost_source(JournalEntry.Source.PARTNER, obj.pk)
        except Exception:
            pass
        obj.delete()
        return Response({"detail": settings.API_MESSAGES["deleted"]}, status=200)