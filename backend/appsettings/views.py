import json
from datetime import datetime, timezone

from django.db import transaction
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from branches.models import Branch
from expenses.models import Expense, ExpenseCategory
from sales.models import DailySale
from suppliers.models import Supplier

from .models import AppSettings
from .serializers import AppSettingsSerializer


class AppSettingsView(APIView):
    """GET returns the singleton settings; PATCH partially updates them."""

    def get(self, request):
        s = AppSettings.load()
        return Response(AppSettingsSerializer(s).data)

    def patch(self, request):
        s = AppSettings.load()
        ser = AppSettingsSerializer(s, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class BackupView(APIView):
    """GET exports all data as a downloadable JSON file."""

    def get(self, request):
        data = {
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "settings": AppSettingsSerializer(AppSettings.load()).data,
            "branches": list(Branch.objects.values()),
            "suppliers": list(Supplier.objects.values()),
            "expense_categories": list(ExpenseCategory.objects.values()),
            "sales": list(DailySale.objects.values()),
            "expenses": list(Expense.objects.values()),
        }
        content = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        response = HttpResponse(content, content_type="application/json; charset=utf-8")
        filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class RestoreView(APIView):
    """POST replaces ALL data with the uploaded backup JSON (version must be 1)."""

    def post(self, request):
        if not isinstance(request.data, dict):
            return Response({"detail": "البيانات المرسلة غير صالحة"}, status=status.HTTP_400_BAD_REQUEST)
        if request.data.get("version") != 1:
            return Response({"detail": "إصدار النسخة الاحتياطية غير مدعوم"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            Expense.objects.all().delete()
            DailySale.objects.all().delete()
            ExpenseCategory.objects.all().delete()
            Supplier.objects.all().delete()
            Branch.objects.all().delete()

            for row in request.data.get("expense_categories", []):
                ExpenseCategory.objects.create(**row)
            for row in request.data.get("branches", []):
                Branch.objects.create(**row)
            for row in request.data.get("suppliers", []):
                Supplier.objects.create(**row)
            for row in request.data.get("sales", []):
                DailySale.objects.create(**row)
            for row in request.data.get("expenses", []):
                Expense.objects.create(**row)

            settings_data = request.data.get("settings")
            if settings_data and isinstance(settings_data, dict):
                ser = AppSettingsSerializer(AppSettings.load(), data=settings_data, partial=True)
                if ser.is_valid():
                    ser.save()

        return Response({"detail": "تمت استعادة النسخة الاحتياطية بنجاح"}, status=status.HTTP_200_OK)


class ResetView(APIView):
    """POST resets data. Body: {"confirm": true, "scope": "transactions"|"all"}."""

    def post(self, request):
        if request.data.get("confirm") is not True:
            return Response({"detail": "يرجى التأكيد بإرسال confirm: true"}, status=status.HTTP_400_BAD_REQUEST)
        scope = request.data.get("scope", "transactions")
        if scope not in ("transactions", "all"):
            return Response({"detail": "scope غير صالح"}, status=status.HTTP_400_BAD_REQUEST)

        deleted = {}
        with transaction.atomic():
            deleted["expenses"] = Expense.objects.all().delete()[0]
            deleted["sales"] = DailySale.objects.all().delete()[0]
            if scope == "all":
                deleted["suppliers"] = Supplier.objects.all().delete()[0]
                deleted["branches"] = Branch.objects.all().delete()[0]
                deleted["categories"] = ExpenseCategory.objects.all().delete()[0]

        return Response(
            {"detail": "تم إعادة الضبط بنجاح", "deleted": deleted},
            status=status.HTTP_200_OK,
        )