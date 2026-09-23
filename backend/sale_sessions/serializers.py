from decimal import Decimal
import os
import re
import uuid

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from branches.models import Branch, FabricBranchPrice
from core.branch_scope import MANAGER_ROLES
from core.permissions import get_request_employee
from suppliers.models import Fabric
from warehouses.models import FabricRoll, Warehouse

from .models import Employee, SaleSession, SaleSessionItem
from .services import effective_sale_date, create_manual_session

PAYMENT_METHODS = {m for m, _ in SaleSessionItem.PaymentMethod.choices}

DEFAULT_EMPLOYEE_PASSWORD = os.getenv("DEFAULT_EMPLOYEE_PASSWORD", "Qomash@123")


def unique_username(base):
    """يبني اسم مستخدم فريداً من أساس معيّن."""
    username = re.sub(r"\s+", "", base or "employee") or "employee"
    candidate = username
    n = 1
    while User.objects.filter(username=candidate).exists():
        candidate = f"{username}{n}"
        n += 1
    return candidate


class EmployeeSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    allowed_branches = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Branch.objects.all(), required=False
    )
    allowed_branches_names = serializers.SerializerMethodField()
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Employee
        fields = [
            "id", "name", "avatar", "phone", "branch", "branch_name",
            "allowed_branches", "allowed_branches_names",
            "notes", "is_active", "role", "role_label",
            "permissions", "hidden_sections",
            "commission_active", "commission_percent",
            "department", "position", "email", "employee_code",
            "multi_branch_access", "must_change_password",
            "birth_date", "civil_id", "address", "hire_date", "base_salary",
            "username", "password",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_employee_code(self, value):
        if value is None or not str(value).strip():
            return None
        code = str(value).strip()
        qs = Employee.objects.filter(employee_code=code)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "كود الموظف مستخدم من قبل — استخدم كوداً مختلفاً"
            )
        return code

    def validate(self, attrs):
        role = attrs.get("role") or getattr(self.instance, "role", None) or Employee.Role.ADMIN
        branch = attrs.get("branch", None)
        existing_branch = getattr(self.instance, "branch", None) if self.instance else None
        effective_branch = branch if branch is not None else existing_branch
        if role not in (Employee.Role.ADMIN, Employee.Role.SUPERVISOR):
            if effective_branch is None:
                raise serializers.ValidationError(
                    {"branch": "اختر الفرع — الفرع مطلوب لهذا الدور"}
                )
            if branch is None and existing_branch is not None:
                attrs["branch"] = existing_branch
        return attrs

    def _resolve_user(self, instance, username, password, is_active):
        """يُحدّث أو يُنشئ حساب Django المرتبط بالموظف ويعيده."""
        if instance.user_id:
            user = instance.user
            if username is not None and username.strip() and username.strip() != user.username:
                if User.objects.filter(username=username.strip()).exclude(pk=user.pk).exists():
                    raise serializers.ValidationError({"username": "اسم المستخدم محجوز بالفعل"})
                user.username = username.strip()
            if password:
                user.set_password(password)
            if is_active is not None:
                user.is_active = bool(is_active)
            user.save()
            return user
        if username is None or not username.strip():
            username = unique_username(instance.phone or instance.name)
        elif User.objects.filter(username=username.strip()).exists():
            username = unique_username(username.strip())
        user = User.objects.create_user(
            username=username.strip(),
            password=password or DEFAULT_EMPLOYEE_PASSWORD,
            is_active=is_active if is_active is not None else (instance.is_active if instance.pk else True),
        )
        return user

    def get_allowed_branches_names(self, obj):
        return list(
            obj.allowed_branches.order_by("name").values_list("name", flat=True)
        )

    def create(self, validated_data):
        allowed_branches = validated_data.pop("allowed_branches", [])
        username = validated_data.pop("username", None)
        password = validated_data.pop("password", None)
        role = validated_data.pop("role", Employee.Role.ADMIN)
        permissions = validated_data.pop("permissions", None)
        hidden_sections = validated_data.pop("hidden_sections", None)
        with transaction.atomic():
            employee = Employee(**validated_data)
            if permissions is not None and hidden_sections is not None:
                employee.role = role
                employee.permissions = permissions
                employee.hidden_sections = hidden_sections
            else:
                employee.apply_role_preset(role)
            employee.user = self._resolve_user(
                employee, username, password, validated_data.get("is_active", True)
            )
            employee.save()
            if allowed_branches:
                employee.allowed_branches.set(allowed_branches)
        return employee

    def update(self, instance, validated_data):
        allowed_branches = validated_data.pop("allowed_branches", None)
        username = validated_data.pop("username", None)
        password = validated_data.pop("password", None)
        requested_active = validated_data.get("is_active") if "is_active" in validated_data else None
        role = validated_data.pop("role", None)
        has_custom = "permissions" in validated_data or "hidden_sections" in validated_data
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if role is not None and not has_custom:
            instance.apply_role_preset(role)
        elif role is not None:
            instance.role = role
        if "permissions" in validated_data:
            instance.permissions = validated_data["permissions"]
        if "hidden_sections" in validated_data:
            instance.hidden_sections = validated_data["hidden_sections"]
        instance.user = self._resolve_user(instance, username, password, requested_active)
        instance.save()
        if allowed_branches is not None:
            instance.allowed_branches.set(allowed_branches)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["username"] = instance.user.username if instance.user_id else ""
        data["branch_name"] = instance.branch.name if instance.branch_id else None
        return data


class SaleSessionItemSerializer(serializers.ModelSerializer):
    fabric_name = serializers.CharField(source="fabric.name", read_only=True)
    fabric_code = serializers.CharField(source="fabric.code", read_only=True)
    fabric_unit = serializers.CharField(source="fabric.unit", read_only=True)
    sale_type_label = serializers.CharField(source="get_sale_type_display", read_only=True)
    payment_method_label = serializers.CharField(source="get_payment_method_display", read_only=True)
    yards_effective = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SaleSessionItem
        fields = [
            "id", "fabric", "fabric_name", "fabric_code", "fabric_unit",
            "sale_type", "sale_type_label",
            "quantity", "unit_price", "discount_amount", "payment_method", "payment_method_label",
            "total", "sale_date", "yards_effective",
            "customer_name", "customer_phone", "sale_group",
            "is_returned", "returned_at", "return_reason",
        ]


class SaleSessionUpdateSerializer(serializers.ModelSerializer):
    """تعديل بيانات الوردية: الموظف، الفرع، الملاحظات."""

    class Meta:
        model = SaleSession
        fields = ["employee", "branch", "notes"]

    def validate(self, attrs):
        employee = attrs.get("employee") or getattr(self.instance, "employee", None)
        branch = attrs.get("branch") or getattr(self.instance, "branch", None)
        requester = get_request_employee(self.context.get("request"))
        if requester is not None and requester.role not in MANAGER_ROLES:
            if attrs.get("branch") is not None and attrs["branch"] != requester.branch:
                raise serializers.ValidationError(
                    {"branch": "لا يمكنك نقل الوردية إلى فرع آخر — المدير فقط يمكنه ذلك"}
                )
        if employee and branch and employee.branch_id != branch.id:
            raise serializers.ValidationError(
                {"employee": "الموظف لا يتبع فرع الوردية — لا يمكن ربط موظف بفرع غير فرعه"}
            )
        return attrs

    def validate_branch(self, branch):
        session = self.instance
        if session and session.status == SaleSession.Status.CLOSED and branch.pk != session.branch_id:
            raise serializers.ValidationError("لا يمكن تغيير فرع وردية مغلقة")
        return branch

    def validate_employee(self, employee):
        session = self.instance
        qs = SaleSession.objects.filter(employee=employee, status=SaleSession.Status.OPEN)
        if session:
            qs = qs.exclude(pk=session.pk)
        if qs.exists():
            raise serializers.ValidationError("لهذا الموظف وردية مفتوحة بالفعل")
        requester = get_request_employee(self.context.get("request"))
        if (
            session
            and requester is not None
            and requester.role not in MANAGER_ROLES
            and employee.pk != session.employee_id
        ):
            raise serializers.ValidationError(
                "لا يمكنك تغيير موظف الوردية — المدير فقط يستطيع ذلك"
            )
        return employee


class SaleSessionReadSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    elapsed_minutes = serializers.SerializerMethodField()
    items = serializers.SerializerMethodField()
    totals = serializers.SerializerMethodField()

    class Meta:
        model = SaleSession
        fields = [
            "id", "employee", "employee_name", "branch", "branch_name",
            "status", "status_label", "opened_at", "closed_at", "notes",
            "commission_amount", "elapsed_minutes", "items", "totals",
            "is_manual", "manual_date", "manual_cash", "manual_transfer", "manual_card",
        ]

    def get_elapsed_minutes(self, obj):
        if obj.status == SaleSession.Status.CLOSED:
            return None
        if not obj.opened_at:
            return 0
        return max(0, int((timezone.now() - obj.opened_at).total_seconds() // 60))

    def get_items(self, obj):
        return SaleSessionItemSerializer(obj.items.all(), many=True).data

    def get_totals(self, obj):
        if obj.is_manual:
            cash = obj.manual_cash or Decimal("0")
            transfer = obj.manual_transfer or Decimal("0")
            card = obj.manual_card or Decimal("0")
            return {
                "cash": float(cash),
                "transfer": float(transfer),
                "card": float(card),
                "total": float(cash + transfer + card),
                "yards": 0.0,
            }
        agg = {m: Decimal("0") for m in PAYMENT_METHODS}
        yards = Decimal("0")
        for it in obj.items.filter(is_returned=False):
            agg[it.payment_method] += it.total
            yards += it.yards_effective
        return {
            "cash": float(agg["cash"]),
            "transfer": float(agg["transfer"]),
            "card": float(agg["card"]),
            "total": float(agg["cash"] + agg["transfer"] + agg["card"]),
            "yards": float(yards),
        }


class SaleSessionOpenSerializer(serializers.Serializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())

    def validate_employee(self, employee):
        if SaleSession.objects.filter(
            employee=employee, status=SaleSession.Status.OPEN
        ).exists():
            raise serializers.ValidationError("لهذا الموظف وردية مفتوحة بالفعل")
        requester = get_request_employee(self.context.get("request"))
        if requester is None:
            raise serializers.ValidationError("تعذّر تحديد الموظف الحالي")
        if requester.role not in MANAGER_ROLES and requester.pk != employee.pk:
            raise serializers.ValidationError(
                "لا يمكنك فتح وردية إلا باسمك — المدير فقط يستطيع فتح وردية لموظف آخر"
            )
        if employee.branch_id is None:
            raise serializers.ValidationError(
                {"employee": "هذا الموظف غير مرتبط بفرع — لا يمكن فتح وردية له"}
            )
        return employee

    def create(self, validated_data):
        employee = validated_data["employee"]
        return SaleSession.objects.create(employee=employee, branch=employee.branch)


class SaleSessionManualCreateSerializer(serializers.Serializer):
    """إدخال وردية كاملة كمجموع مالي بدون تفاصيل بنود ولا خصم مخزون."""

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(), required=False, allow_null=True
    )
    date = serializers.DateField()
    cash = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, default=Decimal("0"))
    transfer = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, default=Decimal("0"))
    card = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, default=Decimal("0"))
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        employee = attrs["employee"]
        requester = get_request_employee(self.context.get("request"))
        if requester is None:
            raise serializers.ValidationError("تعذّر تحديد الموظف الحالي")
        if requester.role not in MANAGER_ROLES and requester.pk != employee.pk:
            raise serializers.ValidationError(
                {"employee": "لا يمكنك إدخال وردية إلا باسمك — المدير فقط يستطيع إدخالها لموظف آخر"}
            )
        branch = attrs.get("branch") or employee.branch
        if branch is None:
            raise serializers.ValidationError({"branch": "حدّد الفرع"})
        if employee.branch_id != branch.id:
            raise serializers.ValidationError(
                {"employee": "الموظف لا يتبع الفرع المحدد"}
            )
        cash = attrs.get("cash") or Decimal("0")
        transfer = attrs.get("transfer") or Decimal("0")
        card = attrs.get("card") or Decimal("0")
        for label, amount in (("cash", cash), ("transfer", transfer), ("card", card)):
            if amount < 0:
                raise serializers.ValidationError({label: "المبلغ لا يمكن أن يكون سالباً"})
        if cash + transfer + card <= 0:
            raise serializers.ValidationError(
                {"detail": "أدخل مبلغاً واحداً على الأقل أكبر من صفر"}
            )
        attrs["branch"] = branch
        return attrs

    def create(self, validated_data):
        return create_manual_session(
            employee=validated_data["employee"],
            branch=validated_data["branch"],
            sale_date=validated_data["date"],
            cash=validated_data.get("cash") or Decimal("0"),
            transfer=validated_data.get("transfer") or Decimal("0"),
            card=validated_data.get("card") or Decimal("0"),
            notes=validated_data.get("notes") or "",
        )


class SaleSessionItemCreateSerializer(serializers.Serializer):
    fabric = serializers.PrimaryKeyRelatedField(queryset=Fabric.objects.all())
    sale_type = serializers.ChoiceField(
        choices=SaleSessionItem.SaleType.choices, default=SaleSessionItem.SaleType.YARD
    )
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=3, required=False)
    discount_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0")
    )
    payment_method = serializers.ChoiceField(
        choices=SaleSessionItem.PaymentMethod.choices,
        default=SaleSessionItem.PaymentMethod.CASH,
    )
    customer_name = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    customer_phone = serializers.CharField(
        required=False, allow_blank=True, default=""
    )

    def validate(self, attrs):
        fabric = attrs["fabric"]
        sale_type = attrs.get("sale_type", SaleSessionItem.SaleType.YARD)
        quantity = attrs["quantity"]
        if quantity <= 0:
            raise serializers.ValidationError({"quantity": "الكمية يجب أن تكون أكبر من صفر"})
        if sale_type == SaleSessionItem.SaleType.ROLL:
            session = self.context["session"]
            if not fabric.roll_sale_allowed_in(session.branch_id):
                raise serializers.ValidationError(
                    {"detail": f"البيع بالطاقة غير مسموح لهذا القماش «{fabric.name}» في هذا الفرع — فعّله في ملف القماش إذا أردت البيع بالطاقة"}
                )
        if sale_type == SaleSessionItem.SaleType.ROLL and not fabric.yards_per_roll:
            raise serializers.ValidationError(
                {"detail": f"القماش «{fabric.name}» لا توجد له ياردات اللفة — حدّدها في ملف القماش قبل البيع باللفة"}
            )

        session = self.context["session"]
        branch_price = FabricBranchPrice.objects.filter(
            branch=session.branch_id, fabric=fabric
        ).first()

        global_yard = Decimal(str(fabric.sale_price_yard if fabric.sale_price_yard is not None else 0))
        global_roll = (
            Decimal(str(fabric.sale_price_roll))
            if fabric.sale_price_roll is not None
            else None
        )
        bp_yard = branch_price.sale_price_yard if branch_price else None
        bp_roll = branch_price.sale_price_roll if branch_price else None

        auto_yard = Decimal(str(bp_yard)) if bp_yard else global_yard
        if sale_type == SaleSessionItem.SaleType.ROLL:
            auto = (
                Decimal(str(bp_roll))
                if bp_roll is not None
                else (
                    global_roll
                    if global_roll is not None
                    else auto_yard * Decimal(str(fabric.yards_per_roll))
                )
            )
        else:
            auto = auto_yard
        if "unit_price" not in attrs or attrs.get("unit_price") is None:
            attrs["unit_price"] = auto
        unit_price = Decimal(str(attrs["unit_price"]))
        if unit_price <= 0:
            raise serializers.ValidationError(
                {
                    "unit_price": (
                        "لا يمكن حفظ البيعة بدون سعر — حدّد سعر البيع في ملف القماش أو أسعار الفرع"
                    )
                }
            )

        bp_min_yard = branch_price.min_sale_yard if branch_price else None
        bp_min_roll = branch_price.min_sale_roll if branch_price else None
        min_price = None
        if sale_type == SaleSessionItem.SaleType.ROLL:
            if bp_min_roll is not None:
                min_price = Decimal(str(bp_min_roll))
            elif bp_min_yard and fabric.yards_per_roll:
                min_price = Decimal(str(bp_min_yard)) * Decimal(str(fabric.yards_per_roll))
            elif fabric.min_sale_roll is not None:
                min_price = Decimal(str(fabric.min_sale_roll))
            elif fabric.min_sale_yard and fabric.yards_per_roll:
                min_price = Decimal(str(fabric.min_sale_yard)) * Decimal(str(fabric.yards_per_roll))
        else:
            if bp_min_yard:
                min_price = Decimal(str(bp_min_yard))
            elif fabric.min_sale_yard:
                min_price = Decimal(str(fabric.min_sale_yard))
        if (
            min_price
            and min_price > 0
            and unit_price < min_price
            and session.status != SaleSession.Status.CLOSED
        ):
            raise serializers.ValidationError(
                {
                    "unit_price": (
                        f"السعر أقل من الحد الأدنى للبيع ({min_price}) — حدّده في ملف القماش أو أسعار الفرع"
                    )
                }
            )

        warehouse = Warehouse.for_branch(session.branch)
        available = Decimal("0")
        if warehouse is not None:
            available = (
                FabricRoll.objects.filter(
                    warehouse=warehouse,
                    fabric=fabric,
                    status=FabricRoll.Status.AVAILABLE,
                    remaining_yards__gt=0,
                ).aggregate(total=Sum("remaining_yards"))["total"]
                or Decimal("0")
            )
        pending = (
            session.items.filter(fabric=fabric, is_returned=False)
            .exclude(pk=self.instance.pk if self.instance is not None else None)
            .select_related("fabric")
        )
        pending_yards = sum(it.yards_effective for it in pending)
        effective_available = max(Decimal("0"), available - pending_yards)
        if sale_type == SaleSessionItem.SaleType.ROLL:
            yards_need = quantity * (fabric.yards_per_roll or Decimal("0"))
        else:
            yards_need = quantity
        if session.status != SaleSession.Status.CLOSED and effective_available < yards_need:
            raise serializers.ValidationError(
                {
                    "detail": (
                        f"الكمية غير متوفرة في فرع الوردية — القماش «{fabric.name}» "
                        f"متوفر {effective_available.normalize()} ياردة فقط بعد بنود الوردية المعلقة"
                    )
                }
            )

        attrs["total"] = Decimal(str(quantity)) * unit_price
        discount = Decimal(str(attrs.get("discount_amount") or Decimal("0")))
        from appsettings.models import AppSettings

        settings = AppSettings.load()
        max_discount = attrs["total"] * (settings.discount_max_percent / Decimal("100"))
        if discount > max_discount:
            raise serializers.ValidationError(
                {
                    "discount_amount": (
                        "الخصم يتجاوز الحد الأقصى المسموح "
                        f"({settings.discount_max_percent}% من الإجمالي)"
                    )
                }
            )
        if discount < 0:
            raise serializers.ValidationError({"discount_amount": "الخصم لا يمكن أن يكون سالباً"})
        attrs["discount_amount"] = discount
        attrs["total"] -= discount
        attrs["sale_date"] = effective_sale_date()
        return attrs

    def create(self, validated_data):
        validated_data["session"] = self.context["session"]
        validated_data["sale_group"] = self.context.get("sale_group") or str(uuid.uuid4())
        return SaleSessionItem.objects.create(**validated_data)


class SaleSessionItemEditSerializer(SaleSessionItemCreateSerializer):
    def validate(self, attrs):
        item = self.instance
        if "fabric" not in attrs:
            attrs["fabric"] = item.fabric
        if "sale_type" not in attrs:
            attrs["sale_type"] = item.sale_type
        if "quantity" not in attrs:
            attrs["quantity"] = item.quantity
        if "unit_price" not in attrs:
            attrs["unit_price"] = item.unit_price
        if "discount_amount" not in attrs:
            attrs["discount_amount"] = item.discount_amount
        if "payment_method" not in attrs:
            attrs["payment_method"] = item.payment_method
        attrs = super().validate(attrs)
        attrs.pop("sale_date", None)
        return attrs

    def update(self, instance, validated_data):
        raise NotImplementedError  # done via update_session_item service

    def create(self, validated_data):  # pragma: no cover - edit path never calls create
        raise NotImplementedError