import secrets

from django.contrib.auth.models import User
from django.core.management.base import CommandError
from django.db import transaction

from branches.models import Branch
from core.management.base import ArabicSafeCommand
from sale_sessions.models import Employee

#: أقل طول نقبله لكلمة مرور المدير — أقصر من ذلك يسهل تخمينه.
MIN_PASSWORD_LENGTH = 12


class Command(ArabicSafeCommand):
    help = "إنشاء حساب مدير نظام (موظف + مستخدم) فوراً للدخول على خادم جديد"

    def add_arguments(self, parser):
        # لا قيم افتراضية لاسم المستخدم أو كلمة المرور: أي قيمة افتراضية
        # مثبّتة في الكود تعني أن كل نسخة من هذا المشروع تحمل حساباً بالاسم
        # وكلمة المرور نفسها. كان `--password` مثبّتاً هنا، فأي شخص اطّلع على
        # المستودع كان يستطيع الدخول كمدير على أي خادم لم يغيّر كلمة مروره.
        parser.add_argument("--username", required=True, help="اسم المستخدم (مطلوب)")
        parser.add_argument(
            "--password",
            default=None,
            help="كلمة المرور. إن تُركت تُولَّد كلمة عشوائية قوية وتُطبع مرة واحدة",
        )
        parser.add_argument("--name", default="مدير النظام", help="اسم الموظف")
        parser.add_argument("--phone", default="", help="رقم الهاتف")
        parser.add_argument("--branch", type=int, default=None, help="معرف الفرع (اختياري)")
        parser.add_argument("--force-name", action="store_true", help="السماح بتكرار اسم الموظف")

    def handle(self, *args, **options):
        username = (options.get("username") or "").strip()
        name = (options.get("name") or "مدير النظام").strip()
        phone = (options.get("phone") or "").strip()
        branch_id = options.get("branch")
        force_name = options.get("force_name")

        if not username:
            raise CommandError("اسم المستخدم مطلوب — مرّره بـ --username")

        # كلمة المرور تأتي من المُشغّل أو تُولَّد عشوائياً — بلا قيم ثابتة.
        generated = False
        password = options.get("password")
        if not password:
            password = secrets.token_urlsafe(18)
            generated = True
        elif len(password) < MIN_PASSWORD_LENGTH:
            raise CommandError(
                f"كلمة المرور قصيرة جداً — استخدم {MIN_PASSWORD_LENGTH} حرفاً على الأقل"
            )

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
        self.write_line(
            f"{action}: الموظف «{employee.name}» (id={employee.pk}) — الدخول باسم «{username}».",
            self.style.SUCCESS,
        )
        if generated:
            # نطبعها مرة واحدة فقط ولا تُخزَّن إلا مُجزّأة، فهذه فرصته الوحيدة.
            self.write_line(
                f"كلمة المرور المُولَّدة: {password}",
                self.style.SUCCESS,
            )
            self.write_line(
                "احفظها الآن — لن تظهر مرة أخرى ولا يمكن استرجاعها.",
                self.style.WARNING,
            )
        self.write_line(
            "تسجيل الدخول عبر /api/auth/login/ (اسم المستخدم + كلمة المرور).",
            self.style.WARNING,
        )