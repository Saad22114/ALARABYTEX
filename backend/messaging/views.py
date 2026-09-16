from collections import defaultdict

from django.db.models import Max
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from sale_sessions.models import Employee

from .models import Message
from .serializers import MessageSerializer

# نافذة الحذف/التعديل بعد الإرسال (بالدقائق)
EDIT_WINDOW_MINUTES = 30


def _within_window(msg, now=None):
    now = now or timezone.now()
    return now - msg.created_at <= timezone.timedelta(minutes=EDIT_WINDOW_MINUTES)


class ConversationListView(APIView):
    """قائمة المحادثات: كل الموظفين النشطين مع آخر رسالة وعدد غير المقروء.

    Query params:
      employee  — معرف الموظف الحالي.
      q         — اختياري: فلترة بالاسم.
    """

    def get(self, request):
        employee_id = request.query_params.get("employee")
        if not employee_id:
            return Response({"detail": "معرف الموظف مطلوب"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            me = Employee.objects.get(pk=employee_id)
        except Employee.DoesNotExist:
            return Response({"detail": "الموظف غير موجود"}, status=status.HTTP_404_NOT_FOUND)

        # عدد غير المقروء لكل مرسل
        unread = defaultdict(int)
        for msg in Message.objects.filter(receiver=me, read_at__isnull=True):
            unread[msg.sender_id] += 1

        employees = Employee.objects.filter(is_active=True).exclude(pk=me.pk).order_by("name")
        q = (request.query_params.get("q") or "").strip()
        if q:
            employees = employees.filter(name__icontains=q)

        contacts = []
        for emp in employees:
            # آخر رسالة نصية مع هذا النظير (أحدث واحدة)
            last = (
                Message.objects.filter(
                    sender__in=[me, emp],
                    receiver__in=[me, emp],
                )
                .order_by("-created_at", "-id")
                .first()
            )
            contacts.append({
                "employee": {
                    "id": emp.pk,
                    "name": emp.name,
                    "phone": emp.phone,
                    "role_label": emp.get_role_display(),
                    "branch_name": emp.branch.name if emp.branch_id else "",
                },
                "last_message": "تم حذف رسالة" if (last and last.is_deleted) else (last.body if last else ""),
                "last_message_from_me": bool(last and last.sender_id == me.pk),
                "last_at": str(last.created_at) if last else "",
                "unread": unread.get(emp.pk, 0),
            })

        contacts.sort(key=lambda c: c["last_at"], reverse=True)
        return Response({
            "me": {"id": me.pk, "name": me.name},
            "conversations": contacts,
            "unread_total": sum(unread.values()),
        })


class MessageThreadView(APIView):
    """سلسلة الرسائل بين الموظف الحالي ونظيره؛ يعلّم الواردة كمقروءة.

    Query params: employee (الحالي), partner (النظير), after_id (اختياري للاستطلاع),
      q (اختياري للبحث داخل السلسلة — بدون تحديث مقروءة عند البحث).
    """

    def get(self, request):
        employee_id = request.query_params.get("employee")
        partner_id = request.query_params.get("partner")
        if not employee_id or not partner_id:
            return Response({"detail": "employee و partner مطلوبان"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            me = Employee.objects.get(pk=employee_id)
            partner = Employee.objects.get(pk=partner_id)
        except Employee.DoesNotExist:
            return Response({"detail": "موظف غير موجود"}, status=status.HTTP_404_NOT_FOUND)

        qs = Message.objects.filter(
            sender__in=[me, partner],
            receiver__in=[me, partner],
        )
        after_id = request.query_params.get("after_id")
        if after_id:
            qs = qs.filter(pk__gt=after_id)
        search = (request.query_params.get("q") or "").strip()
        if search:
            qs = qs.filter(body__icontains=search)
        messages = list(qs.order_by("created_at", "id"))

        # تحديد رسائل المستلمة غير المقروءة كمقروءة (فقط عند التصفح العادي لا البحث)
        if not search:
            incoming_ids = [m.pk for m in messages if m.receiver_id == me.pk and m.read_at is None]
            if incoming_ids:
                now = timezone.now()
                Message.objects.filter(pk__in=incoming_ids).update(read_at=now)
                for m in messages:
                    if m.pk in incoming_ids:
                        m.read_at = now

        return Response({
            "with_employee": {
                "id": partner.pk,
                "name": partner.name,
                "branch_name": partner.branch.name if partner.branch_id else "",
                "role_label": partner.get_role_display(),
            },
            "messages": MessageSerializer(messages, many=True).data,
        })


class SendMessageView(APIView):
    def post(self, request):
        sender = request.data.get("sender")
        receiver = request.data.get("receiver")
        body = request.data.get("body", "")
        reply_to = request.data.get("reply_to")
        if not sender or not receiver:
            return Response({"detail": "sender و receiver مطلوبان"}, status=status.HTTP_400_BAD_REQUEST)
        if not str(body).strip():
            return Response({"detail": "لا يمكن إرسال رسالة فارغة"}, status=status.HTTP_400_BAD_REQUEST)
        if int(sender) == int(receiver):
            return Response({"detail": "لا يمكنك إرسال رسالة لنفسك"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            s = Employee.objects.get(pk=sender)
            r = Employee.objects.get(pk=receiver)
        except Employee.DoesNotExist:
            return Response({"detail": "موظف غير موجود"}, status=status.HTTP_404_NOT_FOUND)

        reply_body = ""
        if reply_to:
            try:
                replied = Message.objects.get(pk=int(reply_to))
                if replied.receiver not in (s, r) or replied.sender not in (s, r):
                    return Response({"detail": "لا يمكن الرد على هذه الرسالة"}, status=status.HTTP_400_BAD_REQUEST)
                reply_body = "تم حذف رسالة" if replied.is_deleted else replied.body
            except (Message.DoesNotExist, ValueError, TypeError):
                return Response({"detail": "الرسالة المُركّب عليها غير موجودة"}, status=status.HTTP_400_BAD_REQUEST)

        msg = Message.objects.create(
            sender=s,
            receiver=r,
            body=str(body).strip(),
            reply_to=replied if reply_to else None,
            reply_to_body=reply_body,
        )
        return Response(MessageSerializer(msg).data, status=status.HTTP_201_CREATED)


class EditMessageView(APIView):
    """تعديل نص رسالتي خلال 30 دقيقة — للمرسل فقط."""

    def post(self, request, pk):
        body = request.data.get("body", "")
        actor = request.data.get("employee")
        if not str(body).strip():
            return Response({"detail": "لا يمكن أن يكون نص الرسالة فارغاً"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            msg = Message.objects.get(pk=pk)
            me = Employee.objects.get(pk=actor) if actor else None
        except (Message.DoesNotExist, Employee.DoesNotExist):
            return Response({"detail": "الرسالة غير موجودة"}, status=status.HTTP_404_NOT_FOUND)

        if msg.sender_id != me.pk:
            return Response({"detail": "يمكن للمرسل فقط تعديل الرسالة"}, status=status.HTTP_403_FORBIDDEN)
        if msg.is_deleted:
            return Response({"detail": "لا يمكن تعديل رسالة محذوفة"}, status=status.HTTP_400_BAD_REQUEST)
        if not _within_window(msg):
            return Response(
                {"detail": f"لا يمكن التعديل بعد مرور {EDIT_WINDOW_MINUTES} دقيقة على الإرسال"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        msg.body = str(body).strip()
        msg.edited_at = timezone.now()
        msg.save(update_fields=["body", "edited_at"])
        return Response(MessageSerializer(msg).data)


class DeleteMessageView(APIView):
    """حذف الرسالة من الطرفين خلال 30 دقيقة — للمرسل فقط (تظهر «تم حذف رسالة»)."""

    def post(self, request, pk):
        actor = request.data.get("employee")
        try:
            msg = Message.objects.get(pk=pk)
            me = Employee.objects.get(pk=actor) if actor else None
        except (Message.DoesNotExist, Employee.DoesNotExist):
            return Response({"detail": "الرسالة غير موجودة"}, status=status.HTTP_404_NOT_FOUND)

        if msg.sender_id != me.pk:
            return Response({"detail": "يمكن للمرسل فقط حذف الرسالة"}, status=status.HTTP_403_FORBIDDEN)
        if msg.is_deleted:
            return Response({"detail": "الرسالة محذوفة بالفعل"}, status=status.HTTP_400_BAD_REQUEST)
        if not _within_window(msg):
            return Response(
                {"detail": f"لا يمكن الحذف بعد مرور {EDIT_WINDOW_MINUTES} دقيقة على الإرسال"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        msg.deleted_at = timezone.now()
        msg.body = ""
        msg.save(update_fields=["deleted_at", "body"])
        return Response(MessageSerializer(msg).data)


class UnreadCountView(APIView):
    """عدد الرسائل غير المقروءة لموظف — لشارة الجرس."""

    def get(self, request):
        employee_id = request.query_params.get("employee")
        if not employee_id:
            return Response({"count": 0})
        qs = Message.objects.filter(receiver_id=employee_id, read_at__isnull=True)
        return Response({"count": qs.count()})