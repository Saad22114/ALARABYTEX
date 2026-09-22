from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from branches.models import Branch
from sale_sessions.models import Employee

from .models import Message

User = get_user_model()


class MessagingSetup(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("admin", password="pass1234")
        cls.partner_user = User.objects.create_user("partner", password="pass1234")
        cls.branch = Branch.objects.create(name="فرع 1", code="BR1")
        cls.me = Employee(branch=cls.branch, user=cls.user, name="أحمد")
        cls.me.apply_role_preset(Employee.Role.ADMIN)
        cls.me.save()
        cls.partner = Employee(branch=cls.branch, user=cls.partner_user, name="محمد")
        cls.partner.apply_role_preset(Employee.Role.ADMIN)
        cls.partner.save()
        cls.silent = Employee.objects.create(name="خالد", branch=cls.branch)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)


class SendMessageTests(MessagingSetup):
    def test_send_message(self):
        res = self.client.post(
            "/api/messaging/send/",
            {"sender": self.me.pk, "receiver": self.partner.pk, "body": "مرحباً"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Message.objects.filter(sender=self.me, receiver=self.partner).exists())

    def test_send_requires_employee_ids(self):
        res = self.client.post(
            "/api/messaging/send/", {"sender": self.me.pk, "body": "بدون مستلم"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_rejects_self(self):
        res = self.client.post(
            "/api/messaging/send/",
            {"sender": self.me.pk, "receiver": self.me.pk, "body": "مرحباً"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_rejects_empty_body(self):
        res = self.client.post(
            "/api/messaging/send/",
            {"sender": self.me.pk, "receiver": self.partner.pk, "body": "   "},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class ConversationListTests(MessagingSetup):
    def test_conversations_include_all_employees(self):
        res = self.client.get(f"/api/messaging/conversations/?employee={self.me.pk}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        names = {c["employee"]["name"] for c in res.data["conversations"]}
        self.assertIn("محمد", names)
        self.assertIn("خالد", names)
        self.assertNotIn("أحمد", names)  # not self

    def test_unread_counts(self):
        Message.objects.create(sender=self.partner, receiver=self.me, body="رسالة 1")
        Message.objects.create(sender=self.partner, receiver=self.me, body="رسالة 2")
        Message.objects.create(sender=self.silent, receiver=self.partner, body="لأحمد؟ لا")
        res = self.client.get(f"/api/messaging/conversations/?employee={self.me.pk}")
        by_name = {c["employee"]["name"]: c for c in res.data["conversations"]}
        self.assertEqual(by_name["محمد"]["unread"], 2)
        self.assertEqual(by_name["خالد"]["unread"], 0)
        self.assertEqual(res.data["unread_total"], 2)

    def test_last_message_preview_and_sort(self):
        Message.objects.create(sender=self.me, receiver=self.partner, body="أول رسالة")
        Message.objects.create(sender=self.partner, receiver=self.me, body="الرد الأخير")
        res = self.client.get(f"/api/messaging/conversations/?employee={self.me.pk}")
        by_name = {c["employee"]["name"]: c for c in res.data["conversations"]}
        self.assertEqual(by_name["محمد"]["last_message"], "الرد الأخير")
        self.assertFalse(by_name["محمد"]["last_message_from_me"])
        # محمد يسبق خالد بلا محادثة
        self.assertEqual(res.data["conversations"][0]["employee"]["name"], "محمد")

    def test_requires_employee(self):
        res = self.client.get("/api/messaging/conversations/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["me"]["id"], self.me.pk)


class MessageThreadTests(MessagingSetup):
    def test_thread_and_mark_read(self):
        m1 = Message.objects.create(sender=self.partner, receiver=self.me, body="مرحباً")
        m2 = Message.objects.create(sender=self.me, receiver=self.partner, body="أهلاً")
        res = self.client.get(
            f"/api/messaging/messages/?employee={self.me.pk}&partner={self.partner.pk}"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [m["id"] for m in res.data["messages"]]
        self.assertEqual(ids, [m1.pk, m2.pk])  # بترتيب زمني
        m1.refresh_from_db()
        self.assertIsNotNone(m1.read_at)  # رسالة الواردة أصبحت مقروءة

    def test_after_id_incremental(self):
        Message.objects.create(sender=self.partner, receiver=self.me, body="قديم")
        newest = Message.objects.create(sender=self.partner, receiver=self.me, body="جديد")
        res = self.client.get(
            f"/api/messaging/messages/?employee={self.me.pk}&partner={self.partner.pk}"
        )
        last_id = res.data["messages"][-1]["id"]
        res2 = self.client.get(
            f"/api/messaging/messages/?employee={self.me.pk}&partner={self.partner.pk}&after_id={last_id}"
        )
        self.assertEqual(len(res2.data["messages"]), 0)
        res3 = self.client.get(
            f"/api/messaging/messages/?employee={self.me.pk}&partner={self.partner.pk}&after_id={newest.pk}"
        )
        self.assertEqual(len(res3.data["messages"]), 0)

    def test_only_thread_partners(self):
        Message.objects.create(sender=self.silent, receiver=self.me, body="من خالد")
        res = self.client.get(
            f"/api/messaging/messages/?employee={self.me.pk}&partner={self.partner.pk}"
        )
        self.assertEqual(res.data["messages"], [])


class UnreadCountTests(MessagingSetup):
    def test_unread_total(self):
        Message.objects.create(sender=self.partner, receiver=self.me, body="1")
        Message.objects.create(sender=self.partner, receiver=self.me, body="2")
        Message.objects.create(sender=self.silent, receiver=self.me, body="3")
        res = self.client.get(f"/api/messaging/unread/?employee={self.me.pk}")
        self.assertEqual(res.data["count"], 3)

    def test_unread_clears_after_thread_read(self):
        Message.objects.create(sender=self.partner, receiver=self.me, body="1")
        self.client.get(f"/api/messaging/messages/?employee={self.me.pk}&partner={self.partner.pk}")
        res = self.client.get(f"/api/messaging/unread/?employee={self.me.pk}")
        self.assertEqual(res.data["count"], 0)

    def test_unread_without_employee(self):
        res = self.client.get("/api/messaging/unread/")
        self.assertEqual(res.data["count"], 0)


class DeleteMessageTests(MessagingSetup):
    def test_sender_deletes_for_both(self):
        msg = Message.objects.create(sender=self.me, receiver=self.partner, body="أرسلها ثم حذفها")
        res = self.client.post(
            f"/api/messaging/messages/{msg.pk}/delete/",
            {"employee": self.me.pk},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["is_deleted"])
        self.assertEqual(res.data["body"], "")
        # جهة منظوري (أحمد): تظهر الرسالة كمحذوفة مع محمد
        conv = self.client.get("/api/messaging/conversations/").data
        by_name = {c["employee"]["name"]: c for c in conv["conversations"]}
        self.assertEqual(by_name["محمد"]["last_message"], "تم حذف رسالة")

    def test_receiver_cannot_delete(self):
        msg = Message.objects.create(sender=self.me, receiver=self.partner, body="رسالة")
        self.client.force_authenticate(user=self.partner_user)
        res = self.client.post(
            f"/api/messaging/messages/{msg.pk}/delete/",
            {"employee": self.partner.pk},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_delete_after_window(self):
        from datetime import timedelta
        from django.utils import timezone as tz

        msg = Message.objects.create(sender=self.me, receiver=self.partner, body="قديمة")
        Message.objects.filter(pk=msg.pk).update(created_at=tz.now() - timedelta(minutes=31))
        res = self.client.post(
            f"/api/messaging/messages/{msg.pk}/delete/",
            {"employee": self.me.pk},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class EditMessageTests(MessagingSetup):
    def test_sender_edits_within_window(self):
        msg = Message.objects.create(sender=self.me, receiver=self.partner, body="النص الأصلي")
        res = self.client.post(
            f"/api/messaging/messages/{msg.pk}/edit/",
            {"employee": self.me.pk, "body": "النص المعدل"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["body"], "النص المعدل")
        self.assertIsNotNone(res.data["edited_at"])

    def test_receiver_cannot_edit(self):
        msg = Message.objects.create(sender=self.me, receiver=self.partner, body="نص")
        self.client.force_authenticate(user=self.partner_user)
        res = self.client.post(
            f"/api/messaging/messages/{msg.pk}/edit/",
            {"employee": self.partner.pk, "body": "تعديل"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_edit_deleted_message(self):
        msg = Message.objects.create(sender=self.me, receiver=self.partner, body="نص")
        self.client.post(
            f"/api/messaging/messages/{msg.pk}/delete/",
            {"employee": self.me.pk},
            format="json",
        )
        res = self.client.post(
            f"/api/messaging/messages/{msg.pk}/edit/",
            {"employee": self.me.pk, "body": "تعديل بعد حذف"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class ReplyAndSearchTests(MessagingSetup):
    def test_send_with_reply(self):
        original = Message.objects.create(sender=self.partner, receiver=self.me, body="السؤال")
        res = self.client.post(
            "/api/messaging/send/",
            {
                "sender": self.me.pk,
                "receiver": self.partner.pk,
                "body": "الجواب",
                "reply_to": original.pk,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["reply_to_id"], original.pk)
        self.assertEqual(res.data["reply_to_body"], "السؤال")

    def test_reply_to_deleted_shows_placeholder(self):
        original = Message.objects.create(sender=self.partner, receiver=self.me, body="سيُحذف")
        self.client.force_authenticate(user=self.partner_user)
        self.client.post(
            f"/api/messaging/messages/{original.pk}/delete/",
            {"employee": self.partner.pk},
            format="json",
        )
        self.client.force_authenticate(user=self.user)
        res = self.client.post(
            "/api/messaging/send/",
            {
                "sender": self.me.pk,
                "receiver": self.partner.pk,
                "body": "الجواب",
                "reply_to": original.pk,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["reply_to_body"], "تم حذف رسالة")

    def test_thread_search(self):
        Message.objects.create(sender=self.me, receiver=self.partner, body="رسالة عادية")
        Message.objects.create(sender=self.partner, receiver=self.me, body="الكمية المطلوبة")
        res = self.client.get(
            f"/api/messaging/messages/?employee={self.me.pk}&partner={self.partner.pk}&q=المطلوبة"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["messages"]), 1)
        self.assertEqual(res.data["messages"][0]["body"], "الكمية المطلوبة")

    def test_conversation_search_by_name(self):
        res = self.client.get(
            f"/api/messaging/conversations/?employee={self.me.pk}&q=محمد"
        )
        names = {c["employee"]["name"] for c in res.data["conversations"]}
        self.assertEqual(names, {"محمد"})


class ContactsListTests(MessagingSetup):
    def test_lists_active_employees_excluding_self(self):
        res = self.client.get("/api/messaging/contacts/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = {e["id"] for e in res.data["employees"]}
        self.assertIn(self.partner.pk, ids)
        self.assertIn(self.silent.pk, ids)
        self.assertNotIn(self.me.pk, ids)

    def test_sales_employee_can_list_contacts(self):
        sales_user = User.objects.create_user("sales1", password="pass1234")
        sales_emp = Employee(branch=self.branch, user=sales_user, name="مندوب")
        sales_emp.apply_role_preset(Employee.Role.SALES)
        sales_emp.save()
        client = APIClient()
        client.force_authenticate(user=sales_user)
        res = client.get("/api/messaging/contacts/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = {e["id"] for e in res.data["employees"]}
        self.assertIn(self.me.pk, ids)  # me هو أحمد الآن من منظوري المندوب

    def test_inactive_employees_excluded(self):
        self.silent.is_active = False
        self.silent.save(update_fields=["is_active"])
        res = self.client.get("/api/messaging/contacts/")
        ids = {e["id"] for e in res.data["employees"]}
        self.assertNotIn(self.silent.pk, ids)

    def test_contacts_requires_messages_permission(self):
        restricted_user = User.objects.create_user("viewer1", password="pass1234")
        restricted_emp = Employee(branch=self.branch, user=restricted_user, name="مشاهد")
        restricted_emp.apply_role_preset(Employee.Role.CUSTOM)
        restricted_emp.permissions["messages"] = {"view": False, "create": False}
        restricted_emp.save()
        client = APIClient()
        client.force_authenticate(user=restricted_user)
        res = client.get("/api/messaging/contacts/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class MessageSearchTests(MessagingSetup):
    def test_searches_my_conversations_only(self):
        Message.objects.create(sender=self.me, receiver=self.partner, body="مناقشة الكمية")
        Message.objects.create(sender=self.partner, receiver=self.me, body="أقصى كمية")
        # لا ينبغي أن تظهر محادثة لا تشملني حتى لو تطابق النص
        Message.objects.create(sender=self.silent, receiver=self.partner, body="كمية بينهما")
        res = self.client.get("/api/messaging/search/?q=كمية")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        partners = {g["employee"]["id"] for g in res.data["groups"]}
        self.assertEqual(partners, {self.partner.pk})
        bodies = [m["body"] for g in res.data["groups"] for m in g["matches"]]
        self.assertIn("الكمية", "".join(bodies))

    def test_groups_sorted_by_latest_match(self):
        Message.objects.create(sender=self.me, receiver=self.silent, body="ملف قديم")
        Message.objects.create(sender=self.me, receiver=self.partner, body="ملف حديث")
        res = self.client.get("/api/messaging/search/?q=ملف")
        names = [g["employee"]["name"] for g in res.data["groups"]]
        self.assertEqual(names[0], "محمد")

    def test_requires_query(self):
        res = self.client.get("/api/messaging/search/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_thread_search_highlights_only_matching(self):
        Message.objects.create(sender=self.me, receiver=self.partner, body="المطلوب: قماش")
        Message.objects.create(sender=self.me, receiver=self.partner, body="لا يطابق")
        res = self.client.get(
            f"/api/messaging/messages/?employee={self.me.pk}&partner={self.partner.pk}&q=قماش"
        )
        self.assertEqual(len(res.data["messages"]), 1)
        self.assertEqual(res.data["messages"][0]["body"], "المطلوب: قماش")


class ForwardMessageTests(MessagingSetup):
    def test_forward_received_message(self):
        msg = Message.objects.create(sender=self.partner, receiver=self.me, body="نص أصلي")
        res = self.client.post(
            "/api/messaging/forward/",
            {"receiver": self.silent.pk, "message_id": msg.pk},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["sender"], self.me.pk)
        self.assertEqual(res.data["receiver"], self.silent.pk)
        self.assertEqual(res.data["body"], "نص أصلي")

    def test_forward_rejects_message_outside_my_threads(self):
        msg = Message.objects.create(sender=self.silent, receiver=self.partner, body="غير متعلق بي")
        res = self.client.post(
            "/api/messaging/forward/",
            {"receiver": self.partner.pk, "message_id": msg.pk},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_forward_rejects_self(self):
        msg = Message.objects.create(sender=self.partner, receiver=self.me, body="نص")
        res = self.client.post(
            "/api/messaging/forward/",
            {"receiver": self.me.pk, "message_id": msg.pk},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_forward_rejects_deleted_message(self):
        msg = Message.objects.create(sender=self.partner, receiver=self.me, body="نص")
        self.client.force_authenticate(user=self.partner_user)
        self.client.post(
            f"/api/messaging/messages/{msg.pk}/delete/",
            {"employee": self.partner.pk},
            format="json",
        )
        self.client.force_authenticate(user=self.user)
        res = self.client.post(
            "/api/messaging/forward/",
            {"receiver": self.silent.pk, "message_id": msg.pk},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)