import secrets

from django.contrib.auth.hashers import check_password
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from sale_sessions.models import Employee
from sale_sessions.serializers import EmployeeSerializer

from .models import EmployeeAuthToken


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get("username") or "").strip().lower()
        password = request.data.get("password") or ""
        employee = Employee.objects.filter(username__iexact=username).first()
        if employee is None or not employee.password or not check_password(password, employee.password):
            return Response(
                {"detail": "اسم المستخدم أو كلمة المرور غير صحيحة"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not employee.is_active:
            return Response(
                {"detail": "هذا الموظف موقوف من النظام"},
                status=status.HTTP_403_FORBIDDEN,
            )
        token, _ = EmployeeAuthToken.objects.update_or_create(
            employee=employee, defaults={"key": EmployeeAuthToken.generate_key()}
        )
        return Response({"token": token.key, "employee": EmployeeSerializer(employee).data})


class MeView(APIView):
    def get(self, request):
        return Response(EmployeeSerializer(request.user).data)


class LogoutView(APIView):
    def post(self, request):
        if request.auth is not None:
            request.auth.delete()
        return Response({"detail": "تم تسجيل الخروج"})