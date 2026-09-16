from decimal import Decimal

from rest_framework import serializers

from .models import Account, ClosedPeriod, JournalEntry, JournalLine


class AccountSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="get_type_display", read_only=True)
    children_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Account
        fields = [
            "id",
            "code",
            "name",
            "type",
            "type_label",
            "parent",
            "is_active",
            "is_system",
            "children_count",
        ]

    def create(self, validated_data):
        self._set_parent(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._set_parent(validated_data)
        return super().update(instance, validated_data)

    def _set_parent(self, data):
        parent = data.get("parent")
        if parent and data.get("type") == parent.type:
            pass
        return data


class JournalLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = JournalLine
        fields = [
            "id",
            "account",
            "account_code",
            "account_name",
            "debit",
            "credit",
            "description",
        ]


class JournalEntrySerializer(serializers.ModelSerializer):
    source_label = serializers.CharField(source="get_source_display", read_only=True)
    lines = JournalLineSerializer(many=True)
    total_debit = serializers.SerializerMethodField()
    total_credit = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source="created_by.username", read_only=True, default="")

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "number",
            "date",
            "description",
            "source",
            "source_label",
            "source_id",
            "created_by",
            "created_by_name",
            "created_at",
            "reversed_at",
            "lines",
            "total_debit",
            "total_credit",
        ]
        read_only_fields = ["number", "created_by", "reversed_at", "source_label"]

    def get_total_debit(self, obj):
        return float(sum((ln.debit for ln in obj.lines.all()), Decimal("0")))

    def get_total_credit(self, obj):
        return float(sum((ln.credit for ln in obj.lines.all()), Decimal("0")))

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        entry = JournalEntry.objects.create(**validated_data)
        self._create_lines(entry, lines_data)
        return entry

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lines_data is not None:
            instance.lines.all().delete()
            self._create_lines(instance, lines_data)
        return instance

    def _create_lines(self, entry, lines_data):
        total_debit = Decimal("0")
        total_credit = Decimal("0")
        for line_data in lines_data:
            account = line_data["account"]
            debit = line_data.get("debit") or Decimal("0")
            credit = line_data.get("credit") or Decimal("0")
            if debit > 0 and credit > 0:
                raise serializers.ValidationError(
                    {"lines": f"السطر على حساب {account.name} مدين ودائن معاً"}
                )
            if debit == 0 and credit == 0:
                raise serializers.ValidationError(
                    {"lines": f"سطر صفر على حساب {account.name}"}
                )
            total_debit += debit
            total_credit += credit
            JournalLine.objects.create(
                entry=entry,
                account=account,
                debit=debit,
                credit=credit,
                description=line_data.get("description", ""),
            )
        if total_debit != total_credit:
            raise serializers.ValidationError(
                {"lines": f"القيد غير متوازن: المدين {total_debit} لا يساوي الدائن {total_credit}"}
            )


class ManualEntrySerializer(serializers.Serializer):
    date = serializers.DateField()
    description = serializers.CharField(required=False, allow_blank=True)
    lines = JournalLineSerializer(many=True)


class ClosedPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClosedPeriod
        fields = ["id", "period_end", "description", "net_profit", "created_at"]