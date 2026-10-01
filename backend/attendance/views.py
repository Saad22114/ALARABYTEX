# -*- coding: utf-8 -*-
"""نقاط قسم الحضور: ورقة اليوم، الملخص، التصدير، وسياسة الضبط."""

from datetime import date, datetime, timedelta

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core import excel
from sale_sessions.models import Employee

from .models import AttendancePolicy, AttendanceRecord
from .serializers import (
    AttendancePolicySerializer,
    AttendanceRecordSerializer,
    AttendanceRecordWriteSerializer,
)
from .services import (
    day_sheet,
    is_working_day,
    record_login,
    record_logout,
    recompute,
    summarize,
)

#: ترويسات الورقة. ترتيبها هو ترتيب الأعمدة في ``data_rows`` بالضبط؛
#: فأي عمود يُزاد بلا ترويسة يُكتب تحت قيمة عمودٍ لا يعرفه القارئ، والترتيب
#: يمرّ في الصمت.
HEADERS = (
    "الموظف",
    "وقت الدخول",
    "وقت الخروج",
    "ساعات العمل",
    "التأخير",
    "الانصراف المبكر",
    "الإضافي",
    "الحالة",
    "المبرر",
    "يوم عمل",
    "المصدر",
    "ملاحظات",
)

#: نوع كل عمود: الدقائق أعداد لا نقود، والحالة نصّ. بلا هذا يستنتج
#: :func:`core.excel.infer_columns` من الأرقام فيحتسب «ساعات العمل» مبلغاً
#: لاصقاً ويُعرض بمنزلتين عشريتين لا كعدد صحيح.
TYPES = ("text", "text", "text", "number", "number", "number",
         "number", "text", "text", "text", "text", "text")


def parse_day(value):
    """يحوّل نصّاً إلى تاريخ، أو ``None`` إن لم يكن شكل تاريخٍ معروفاً.

    لا نُسقط القيمة على اليوم الحالي صامتة: تاريخٌ يُعرض في جدول حضور
    خطأً يُقرأ كحقيقة. فالسقوط يُرجع ``None`` ليتخذه صاحبه قراراً.
    """
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def clock(value):
    """وقتٌ بصيغة ساعتين ودقيقتين، أو فراغ.

    الثانية لا تُعرض: دقّتان تكفيان لقراءة وقتِ دخول، والثانية تجعل عموداً
    من عمودين بلا فائدة.
    """
    if value is None:
        return ""
    local = timezone.localtime(value)
    return local.strftime("%H:%M")


def active_employees():
    return Employee.objects.filter(is_active=True).order_by("name")


class AttendancePolicyView(APIView):
    """سياسة الضبط: صفٌّ واحد، يُقرأ ويُحفظ على عنوانٍ واحد بلا معرّف.

    ليس هذا مساراً بمعرّف زائد: السياسة ليست مجموعة سياسات يُختار منها
    واحد، بل إعدادٌ واحد لكل النظام. ``<pk>`` يجعل منها سياساتٍ متعدّدة،
    فتُنسى السياساتُ وتُترك على قيمتها الأولى.

    وليس على الراوتر: الراوتر يمنح مسار المجموعة فعلاً واحداً (GET)،
    فيسقط PATCH بـ 405 لأن بايثون يوقف عند أول نمطٍ يطابق المسار ولا
    يبحث عن نمطٍ يقبل الطريقة.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(AttendancePolicySerializer(AttendancePolicy.load()).data)

    def put(self, request):
        return self._save(request)

    def patch(self, request):
        return self._save(request)

    def _save(self, request):
        policy = AttendancePolicy.load()
        serializer = AttendancePolicySerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # بعد تعديل النوافذ، الأرقام المشتقّة في السجلات القديمة صارت على
        # أساسٍ قديم. نعيد اشتقاقها كلها الآن حتى لا يقرأ أحد رقماً حُسب
        # على سياسةٍ غُيّرت: نسبةٌ إلى نافذةِ الدخول لم تعد تعني شيئاً.
        for record in AttendanceRecord.objects.exclude(login_at=None).iterator():
            recompute(record, policy)
        return Response(serializer.data)


class AttendanceRecordViewSet(viewsets.ModelViewSet):
    queryset = AttendanceRecord.objects.all().select_related("employee")
    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        # الكتابة لا تقبل ``status``: الحالة مُشتقّة، ولو سمحنا بإرسالها
        # لأرسلها كاتبٌ لا يعرف النافذة، فصار الحقل يُكتب مرّتين.
        if self.action in ("update", "partial_update"):
            return AttendanceRecordWriteSerializer
        return AttendanceRecordSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        employee_id = params.get("employee")
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        status_param = params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        start = parse_day(params.get("start"))
        end = parse_day(params.get("end"))
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        return qs

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = AttendanceRecordWriteSerializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        instance.source = AttendanceRecord.Source.MANUAL
        recompute(instance)
        return Response(AttendanceRecordSerializer(instance).data)

    def create(self, request, *args, **kwargs):
        """سطرٌ يدويّ ليومٍ وموظف، لمن أُغاب سهواً أو نسي النظام تسجيله."""
        data = dict(request.data)
        employee = Employee.objects.filter(pk=data.pop("employee", None)).first()
        if employee is None:
            return Response(
                {"detail": "اختر موظفاً أولاً"}, status=status.HTTP_400_BAD_REQUEST
            )
        record = AttendanceRecord(
            employee=employee,
            source=AttendanceRecord.Source.MANUAL,
        )
        serializer = AttendanceRecordWriteSerializer(record, data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record.working_day = is_working_day(record.date, AttendancePolicy.load())
        recompute(record)
        return Response(
            AttendanceRecordSerializer(record).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        """الحذف ممنوع: سجلّ الحضور هو الدليل، والحذف يمحو الدليل."""
        return Response(
            {"detail": "لا يمكن حذف سجل الحضور"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def _employee(self, request):
        return getattr(request.user, "employee", None)

    @action(detail=False, methods=["post"])
    def check_in(self, request):
        """فتح سطر اليوم — للمستخدم نفسه."""
        employee = self._employee(request)
        if employee is None:
            return Response(
                {"detail": "لا يوجد موظف مرتبط بهذا الحساب"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record = record_login(employee, when=timezone.now())
        if record is None:
            return Response(
                {"detail": "تسجيل الحضور غير مفعّل"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(AttendanceRecordSerializer(record).data)

    @action(detail=False, methods=["post"])
    def check_out(self, request):
        """إغلاق سطر اليوم — للمستخدم نفسه."""
        employee = self._employee(request)
        if employee is None:
            return Response(
                {"detail": "لا يوجد موظف مرتبط بهذا الحساب"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record = record_logout(employee, when=timezone.now())
        if record is None:
            return Response(
                {"detail": "لا يوجد سجل دخول مفتوح لهذا اليوم"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(AttendanceRecordSerializer(record).data)

    @action(detail=False, methods=["get"])
    def sheet(self, request):
        """ورقة يومٍ واحد: صفٌّ لكل موظف، حاضراً كان أو غائباً."""
        policy = AttendancePolicy.load()
        day = parse_day(request.query_params.get("date")) or timezone.localdate()
        rows = day_sheet(day, active_employees(), policy)
        payload = AttendanceRecordSerializer(rows, many=True).data
        worked = sum(1 for r in rows if r.worked_minutes)
        return Response(
            {
                "date": day.isoformat(),
                "working_day": is_working_day(day, policy),
                "summary": summarize(rows, policy),
                "worked": worked,
                "rows": payload,
            }
        )

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """أرقامُ مدى زمني في سطر — الشاشة تملأ بطاقاتها منها."""
        policy = AttendancePolicy.load()
        params = self.request.query_params
        end = parse_day(params.get("end")) or timezone.localdate()
        start = parse_day(params.get("start")) or (end - timedelta(days=29))
        qs = self.get_queryset().filter(date__gte=start, date__lte=end)
        return Response(
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "summary": summarize(list(qs), policy),
            }
        )

    @action(detail=False, methods=["get"])
    def open_sessions(self, request):
        """من لم يخرج بعد: السطر المفتوح دليلُ حضورٍ لا دليلُ غياب."""
        qs = AttendanceRecord.objects.filter(
            login_at__isnull=False, logout_at__isnull=True
        ).select_related("employee")
        return Response(AttendanceRecordSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def export(self, request):
        """تصدير Excel — نفس مسّار كل تقارير المشروع بلا استثناء."""
        if not excel.available():
            return Response(
                {"detail": "مكتبة تصدير Excel غير مثبّتة على الخادم"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        policy = AttendancePolicy.load()
        params = self.request.query_params
        day = parse_day(params.get("date"))
        employee_id = params.get("employee")
        if day:
            rows = day_sheet(day, active_employees(), policy)
            subtitle = f"ورقة يوم {day:%Y-%m-%d}"
        else:
            end = parse_day(params.get("end")) or timezone.localdate()
            start = parse_day(params.get("start")) or (end - timedelta(days=29))
            rows = list(
                self.get_queryset().filter(date__gte=start, date__lte=end)
            )
            subtitle = f"من {start:%Y-%m-%d} إلى {end:%Y-%m-%d}"

        data_rows = [
            [
                r.employee.name if r.employee_id else "",
                clock(r.login_at),
                clock(r.logout_at),
                r.worked_minutes if r.worked_minutes is not None else "",
                r.late_minutes,
                r.early_leave_minutes,
                r.overtime_minutes,
                r.get_status_display(),
                r.get_excuse_display(),
                "نعم" if r.working_day else "لا",
                r.get_source_display(),
                r.note,
            ]
            for r in rows
        ]
        # صفّ الإجمالي يُكتشف من أول خلية فيه «الإجمالي»، فنضعه أولاً:
        # مجموعُ الدقائق في آخر ورقةٍ بعد مئة سطرٍ لا يُقرأ.
        totals = [
            "الإجمالي",
            "",
            "",
            sum(r.worked_minutes or 0 for r in rows),
            sum(r.late_minutes for r in rows),
            sum(r.early_leave_minutes for r in rows),
            sum(r.overtime_minutes for r in rows),
            "",
            "",
            "",
            "",
            "",
        ]
        if data_rows:
            data_rows.append(totals)

        workbook = excel.simple(
            "الحضور والانصراف",
            list(HEADERS),
            data_rows,
            types=list(TYPES),
            heading="سجل الحضور والانصراف",
            subtitle=subtitle,
        )
        return excel.xlsx_response(
            workbook,
            "الحضور-والانصراف",
            ascii_name="attendance",
        )
