from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from sale_sessions.models import Employee


class Command(BaseCommand):
    help = "تعيين اسم مستخدم وكلمة مرور لموظف لتسجيل الدخول إلى النظام"

    def add_arguments(self, parser):
        parser.add_argument("employee", type=str, help="معرّف الموظف أو اسم المستخدم أو اسم الموظف")
        parser.add_argument("username", type=str, help="اسم المستخدم الجديد")
        parser.add_argument("password", type=str, help="كلمة المرور الجديدة")

    def handle(self, *args, **opts):
        target = opts["employee"].strip().lower()
        employee = (
            Employee.objects.filter(pk__iexact=target).first()
            or Employee.objects.filter(username__iexact=target).first()
            or Employee.objects.filter(name__iexact=target).first()
        )
        if not employee:
            raise CommandError("لم يتم العثور على الموظف")

        username = opts["username"].strip().lower()
        if not username:
            raise CommandError("اسم المستخدم لا يمكن أن يكون فارغاً")
        if Employee.objects.exclude(pk=employee.pk).filter(username__iexact=username).exists():
            raise CommandError("اسم المستخدم مستخدم بالفعل")

        if not opts["password"]:
            raise CommandError("كلمة المرور لا يمكن أن تكون فارغة")

        employee.username = username
        employee.password = make_password(opts["password"])
        employee.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"تم تعيين بيانات الدخول للموظف «{employee.name}» — اسم المستخدم: {username}"
            )
        )