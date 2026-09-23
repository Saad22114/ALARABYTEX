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


def _me(request):
    return request.user.employee


def _employee_contact(emp):
    return {
        "id": emp.pk,
        "name": emp.name,
        "avatar": emp.avatar,
        "phone": emp.phone,
        "role_label": emp.get_role_display(),
        "branch_name": emp.branch.name if emp.branch_id else "",
        "is_online": _is_online(emp),
    }


ONLINE_MINUTES = 2


def _is_online(emp):
    if not emp.last_seen_at:
        return False
    return timezone.now() - emp.last_seen_at <= timezone.timedelta(minutes=ONLINE_MINUTES)


class EmployeeContactListView(APIView):
    """كل الموظفين النشطين لبدء محادثة جديدة (بدون صلاحية الموظفين)."""

    permission_section = "messages"

    def get(self, request):
        me = _me(request)
        employees = (
            Employee.objects.filter(is_active=True)
            .exclude(pk=me.pk)
            .order_by("name")
        )
        return Response({
            "me": {"id": me.pk, "name": me.name, "avatar": me.avatar, "role_label": me.get_role_display()},
            "employees": [_employee_contact(e) for e in employees],
        })


class ConversationListView(APIView):
    """قائمة المحادثات: كل الموظفين النشطين مع آخر رسالة وعدد غير المقروء.

    Query params:
      q — اختياري: فلترة بالاسم.
    """

    permission_section = "messages"

    def get(self, request):
        me = _me(request)

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
                "employee": _employee_contact(emp),
                "last_message": "تم حذف رسالة" if (last and last.is_deleted) else (last.body if last else ""),
                "last_message_from_me": bool(last and last.sender_id == me.pk),
                "last_at": str(last.created_at) if last else "",
                "unread": unread.get(emp.pk, 0),
            })

        contacts.sort(key=lambda c: c["last_at"], reverse=True)
        return Response({
            "me": {"id": me.pk, "name": me.name, "avatar": me.avatar, "role_label": me.get_role_display()},
            "conversations": contacts,
            "unread_total": sum(unread.values()),
        })


class MessageThreadView(APIView):
    """سلسلة الرسائل بين الموظف الحالي ونظيره؛ يعلّم الواردة كمقروءة.

    Query params: partner (النظير), after_id (اختياري للاستطلاع),
      q (اختياري للبحث داخل السلسلة — بدون تحديث مقروءة عند البحث).
    """

    permission_section = "messages"

    def get(self, request):
        me = _me(request)
        partner_id = request.query_params.get("partner")
        if not partner_id:
            return Response({"detail": "حدّد النظير (partner)"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            partner = Employee.objects.get(pk=partner_id)
        except Employee.DoesNotExist:
            return Response({"detail": "الموظف غير موجود"}, status=status.HTTP_404_NOT_FOUND)

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
            "with_employee": _employee_contact(partner),
            "messages": MessageSerializer(messages, many=True).data,
        })


class SendMessageView(APIView):
    permission_section = "messages"

    def post(self, request):
        sender = _me(request)
        receiver = request.data.get("receiver")
        body = request.data.get("body", "")
        reply_to = request.data.get("reply_to")
        if not receiver:
            return Response({"detail": "receiver مطلوب"}, status=status.HTTP_400_BAD_REQUEST)
        if not str(body).strip():
            return Response({"detail": "لا يمكن إرسال رسالة فارغة"}, status=status.HTTP_400_BAD_REQUEST)
        if sender.pk == int(receiver):
            return Response({"detail": "لا يمكنك إرسال رسالة لنفسك"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            r = Employee.objects.get(pk=receiver)
        except Employee.DoesNotExist:
            return Response({"detail": "الموظف غير موجود"}, status=status.HTTP_404_NOT_FOUND)

        replied = None
        reply_body = ""
        if reply_to:
            try:
                replied = Message.objects.get(pk=int(reply_to))
                if replied.receiver not in (sender, r) or replied.sender not in (sender, r):
                    return Response({"detail": "لا يمكن الرد على هذه الرسالة"}, status=status.HTTP_400_BAD_REQUEST)
                reply_body = "تم حذف رسالة" if replied.is_deleted else replied.body
            except (Message.DoesNotExist, ValueError, TypeError):
                return Response({"detail": "الرسالة المُركّب عليها غير موجودة"}, status=status.HTTP_400_BAD_REQUEST)

        msg = Message.objects.create(
            sender=sender,
            receiver=r,
            body=str(body).strip(),
            reply_to=replied,
            reply_to_body=reply_body,
        )
        return Response(MessageSerializer(msg).data, status=status.HTTP_201_CREATED)


class EditMessageView(APIView):
    """تعديل نص رسالتي خلال 30 دقيقة — للمرسل فقط."""

    permission_section = "messages"

    def post(self, request, pk):
        body = request.data.get("body", "")
        me = _me(request)
        if not str(body).strip():
            return Response({"detail": "لا يمكن أن يكون نص الرسالة فارغاً"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            msg = Message.objects.get(pk=pk)
        except Message.DoesNotExist:
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

    permission_section = "messages"

    def post(self, request, pk):
        me = _me(request)
        try:
            msg = Message.objects.get(pk=pk)
        except Message.DoesNotExist:
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


class MessageSearchView(APIView):
    """بحث شامل في كل محادثاتي عن نص مطابق — مجموعاً حسب النظير."""

    permission_section = "messages"

    def get(self, request):
        me = _me(request)
        q = (request.query_params.get("q") or "").strip()
        if not q:
            return Response({"detail": "اكتب كلمة البحث"}, status=status.HTTP_400_BAD_REQUEST)
        sent_ids = Message.objects.filter(sender=me).values_list("receiver_id", flat=True)
        recv_ids = Message.objects.filter(receiver=me).values_list("sender_id", flat=True)
        partner_ids = set(sent_ids) | set(recv_ids)
        partners = Employee.objects.filter(pk__in=partner_ids, is_active=True)

        groups = []
        for p in partners:
            msgs = list(
                Message.objects.filter(
                    sender__in=[me, p],
                    receiver__in=[me, p],
                    body__icontains=q,
                ).order_by("created_at", "id")
            )
            if not msgs:
                continue
            groups.append({
                "employee": _employee_contact(p),
                "matches": MessageSerializer(msgs[-50:], many=True).data,
                "last_at": str(msgs[-1].created_at),
            })
        groups.sort(key=lambda g: g["last_at"], reverse=True)
        return Response({"q": q, "groups": groups})


class ForwardMessageView(APIView):
    """إعادة توجيه رسالة من محادثاتي إلى زميل آخر."""

    permission_section = "messages"

    def post(self, request):
        me = _me(request)
        receiver = request.data.get("receiver")
        message_id = request.data.get("message_id")
        if not receiver:
            return Response({"detail": "اختر المستلم (receiver)"}, status=status.HTTP_400_BAD_REQUEST)
        if not message_id:
            return Response({"detail": "message_id مطلوب"}, status=status.HTTP_400_BAD_REQUEST)
        if me.pk == int(receiver):
            return Response({"detail": "لا يمكنك إرسال رسالة لنفسك"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            target = Employee.objects.get(pk=receiver)
        except Employee.DoesNotExist:
            return Response({"detail": "الموظف غير موجود"}, status=status.HTTP_404_NOT_FOUND)
        try:
            msg = Message.objects.get(pk=message_id)
        except Message.DoesNotExist:
            return Response({"detail": "الرسالة غير موجودة"}, status=status.HTTP_404_NOT_FOUND)
        if not (msg.sender_id == me.pk or msg.receiver_id == me.pk):
            return Response({"detail": "لا يمكن إعادة توجيه هذه الرسالة"}, status=status.HTTP_403_FORBIDDEN)
        if msg.is_deleted:
            return Response({"detail": "لا يمكن إعادة توجيه رسالة محذوفة"}, status=status.HTTP_400_BAD_REQUEST)

        new_msg = Message.objects.create(
            sender=me,
            receiver=target,
            body=msg.body,
        )
        return Response(MessageSerializer(new_msg).data, status=status.HTTP_201_CREATED)


class UnreadCountView(APIView):
    """عدد الرسائل غير المقروءة — لشارة الجرس."""

    permission_section = "messages"

    def get(self, request):
        qs = Message.objects.filter(receiver_id=request.user.employee.pk, read_at__isnull=True)
        return Response({"count": qs.count()})