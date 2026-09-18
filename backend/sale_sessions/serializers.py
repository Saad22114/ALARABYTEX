from decimal import Decimal
import uuid

from django.contrib.auth.hashers import make_password
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from branches.models import Branch, FabricBranchPrice
from suppliers.models import Fabric
from warehouses.models import FabricRoll, Warehouse

from .models import Employee, SaleSession, SaleSessionItem
from .services import effective_sale_date, create_manual_session

PAYMENT_METHODS = {m for m, _ in SaleSessionItem.PaymentMethod.choices}


class EmployeeSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    username = serializers.CharField(
        required=False, allow_blank=True, max_length=50, trim_whitespace=True
    )
    password = serializers.CharField(
        required=False, allow_blank=True, write_only=True
    )

    class Meta:
        model = Employee
        fields = [
            "id", "name", "phone", "username", "password", "branch", "branch_name",
            "notes", "is_active", "role", "role_label",
            "permissions", "hidden_sections",
            "commission_active", "commission_percent",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_username(self, value):
        username = (value or "").strip().lower()
        if not username:
            return ""
        qs = Employee.objects.filter(username__iexact=username)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("اسم المستخدم مستخدم بالفعل")
        return username

    def create(self, validated_data):
        password = validated_data.pop("password", "")
        role = validated_data.pop("role", Employee.Role.ADMIN)
        permissions = validated_data.pop("permissions", None)
        hidden_sections = validated_data.pop("hidden_sections", None)
        employee = Employee(**validated_data)
        if password:
            employee.password = make_password(password)
        if permissions is not None and hidden_sections is not None:
            employee.role = role
            employee.permissions = permissions
            employee.hidden_sections = hidden_sections
        else:
            employee.apply_role_preset(role)
        employee.save()
        return employee

    def update(self, instance, validated_data):
        password = validated_data.pop("password", "")
        role = validated_data.pop("role", None)
        has_custom = "permissions" in validated_data or "hidden_sections" in validated_data
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.password = make_password(password)
        if role is not None and not has_custom:
            instance.apply_role_preset(role)
        elif role is not None:
            instance.role = role
        if "permissions" in validated_data:
            instance.permissions = validated_data["permissions"]
        if "hidden_sections" in validated_data:
            instance.hidden_sections = validated_data["hidden_sections"]
        instance.save()
        return instance


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
        ]


class SaleSessionUpdateSerializer(serializers.ModelSerializer):
    """تعديل بيانات الوردية: الموظف، الفرع، الملاحظات."""

    class Meta:
        model = SaleSession
        fields = ["employee", "branch", "notes"]

    def validate(self, attrs):
        employee = attrs.get("employee") or getattr(self.instance, "employee", None)
        branch = attrs.get("branch") or getattr(self.instance, "branch", None)
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
        for it in obj.items.all():
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
        if sale_type == SaleSessionItem.SaleType.ROLL:
            yards_need = quantity * (fabric.yards_per_roll or Decimal("0"))
        else:
            yards_need = quantity
        if session.status != SaleSession.Status.CLOSED and available < yards_need:
            raise serializers.ValidationError(
                {
                    "detail": (
                        f"الكمية غير متوفرة في فرع الوردية — القماش «{fabric.name}» "
                        f"متوفر {available.normalize()} ياردة فقط"
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