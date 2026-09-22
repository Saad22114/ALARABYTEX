from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from branches.models import Branch
from sale_sessions.models import Employee


class Command(BaseCommand):
    help = "إنشاء حساب مدير نظام (موظف + مستخدم) فوراً للدخول على خادم جديد"

    def add_arguments(self, parser):
        parser.add_argument("--username", default="Saad22114", help="اسم المستخدم")
        parser.add_argument("--password", default="Saad22114@#", help="كلمة المرور")
        parser.add_argument("--name", default="مدير النظام", help="اسم الموظف")
        parser.add_argument("--phone", default="", help="رقم الهاتف")
        parser.add_argument("--branch", type=int, default=None, help="معرف الفرع (اختياري)")
        parser.add_argument("--force-name", action="store_true", help="السماح بتكرار اسم الموظف")

    def handle(self, *args, **options):
        username = (options.get("username") or "Saad22114").strip()
        password = options.get("password") or "Saad22114@#"
        name = (options.get("name") or "مدير النظام").strip()
        phone = (options.get("phone") or "").strip()
        branch_id = options.get("branch")
        force_name = options.get("force_name")

        if not username or not password:
            raise CommandError("اسم المستخدم وكلمة المرور مطلوبان")

        with transaction.atomic():
            user = User.objects.filter(username=username).first()
            if user is None:
                user = User.objects.create_user(username=username, password=password, is_active=True)
                created_user = True
            else:
                user.set_password(password)
                user.is_active = True
                user.save()
                created_user = False

            employee = Employee.objects.filter(user=user).first()
            if employee is None and phone:
                employee = Employee.objects.filter(phone=phone).first()

            if employee is None:
                employee = Employee.objects.filter(name=name).first()
                if employee is not None and not force_name:
                    raise CommandError(
                        f"يوجد موظف بنفس الاسم «{name}» — استخدم --force-name لربط الحساب به أو --name لاسم آخر"
                    )

            branch = None
            if branch_id is not None:
                branch = Branch.objects.filter(pk=branch_id).first()
                if branch is None:
                    raise CommandError(f"لا يوجد فرع بالمعرف {branch_id}")

            if employee is None:
                employee = Employee(name=name, phone=phone, branch=branch)
            else:
                if not employee.branch_id and branch:
                    employee.branch = branch
                if phone and employee.phone != phone:
                    employee.phone = phone

            employee.user = user
            employee.is_active = True
            employee.apply_role_preset(Employee.Role.ADMIN)
            employee.save()

        action = "تم التحديث" if not created_user else "تم الإنشاء"
        self.stdout.write(self.style.SUCCESS(
            f"{action}: الموظف «{employee.name}» (id={employee.pk}) — الدخول باسم «{username}» وكلمة المرور المحددة."
        ))
        self.stdout.write(self.style.WARNING(
            "تسجيل الدخول عبر /api/auth/login/ (اسم المستخدم + كلمة المرور)."
        ))