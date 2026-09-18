from django.contrib.auth.hashers import check_password, make_password
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from branches.models import Branch
from sale_sessions.models import Employee


class AuthApiTests(APITestCase):
    def setUp(self):
        self.c = APIClient()
        self.branch = Branch.objects.create(name="فرع الاختبار", code="TSTBR")
        self.manager = Employee.objects.create(
            name="المدير الرئيسي",
            phone="90000000",
            branch=self.branch,
            username="manager1",
            password=make_password("secret123"),
        )
        self.manager.apply_role_preset("admin")
        self.manager.save()
        self.sales = Employee.objects.create(
            name="مندوب المبيعات",
            phone="91111111",
            branch=self.branch,
            username="sales1",
            password=make_password("secret123"),
        )
        self.sales.apply_role_preset("sales")
        self.sales.save()

    def login(self, username, password):
        return self.c.post(
            "/api/auth/login/",
            {"username": username, "password": password},
            format="json",
        )

    def test_login_success_returns_token_and_employee(self):
        res = self.login("manager1", "secret123")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("token", res.data)
        self.assertEqual(res.data["employee"]["username"], "manager1")
        self.assertEqual(res.data["employee"]["role"], "admin")

    def test_login_is_case_insensitive_username(self):
        res = self.login("Manager1", "secret123")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_login_wrong_password(self):
        res = self.login("manager1", "wrong")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_unknown_username(self):
        res = self.login("ghost", "secret123")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_inactive_employee_blocked(self):
        self.manager.is_active = False
        self.manager.save()
        res = self.login("manager1", "secret123")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_me_requires_token(self):
        self.assertEqual(self.c.get("/api/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.c.get("/api/branches/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_authenticated_employee(self):
        token = self.login("manager1", "secret123").data["token"]
        self.c.credentials(HTTP_AUTHORIZATION="Token " + token)
        res = self.c.get("/api/auth/me/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["username"], "manager1")

    def test_logout_revokes_token(self):
        token = self.login("manager1", "secret123").data["token"]
        self.c.credentials(HTTP_AUTHORIZATION="Token " + token)
        self.assertEqual(self.c.post("/api/auth/logout/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.c.get("/api/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_employees_requires_auth(self):
        self.c.credentials(HTTP_AUTHORIZATION="Token invalidkey123")
        self.assertEqual(self.c.get("/api/employees/").status_code, status.HTTP_401_UNAUTHORIZED)


class EmployeesAdminOnlyTests(APITestCase):
    def setUp(self):
        self.c = APIClient()
        self.branch = Branch.objects.create(name="فرع الاختبار", code="TSTBR")
        self.manager = Employee.objects.create(
            name="المدير", branch=self.branch, username="mgr", password=make_password("p")
        )
        self.manager.apply_role_preset("admin")
        self.manager.save()
        self.sales = Employee.objects.create(
            name="مندوب", branch=self.branch, username="sal", password=make_password("p")
        )
        self.sales.apply_role_preset("sales")
        self.sales.save()

    def auth(self, employee):
        token = self.c.post(
            "/api/auth/login/",
            {"username": employee.username, "password": "p"},
            format="json",
        ).data["token"]
        self.c.credentials(HTTP_AUTHORIZATION="Token " + token)

    def test_manager_can_read_employees(self):
        self.auth(self.manager)
        res = self.c.get("/api/employees/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_non_manager_cannot_create_employee(self):
        self.auth(self.sales)
        res = self.c.post(
            "/api/employees/",
            {"name": "موظف جديد", "branch": self.branch.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_manager_cannot_update_or_delete_employee(self):
        self.auth(self.sales)
        patch = self.c.patch(f"/api/employees/{self.manager.id}/", {"phone": "9"}, format="json")
        self.assertEqual(patch.status_code, status.HTTP_403_FORBIDDEN)
        delete = self.c.delete(f"/api/employees/{self.manager.id}/")
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_create_employee_with_credentials(self):
        self.auth(self.manager)
        res = self.c.post(
            "/api/employees/",
            {
                "name": "موظف جديد",
                "username": "newemp",
                "password": "pass123",
                "branch": self.branch.id,
                "role": "sales",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        emp = Employee.objects.get(pk=res.data["id"])
        self.assertTrue(check_password("pass123", emp.password))
        self.assertEqual(emp.username, "newemp")
        self.assertEqual(emp.role, "sales")

    def test_manager_can_create_another_manager(self):
        self.auth(self.manager)
        res = self.c.post(
            "/api/employees/",
            {
                "name": "مدير ثانٍ",
                "username": "mgr2",
                "password": "pass123",
                "branch": self.branch.id,
                "role": "admin",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        emp = Employee.objects.get(pk=res.data["id"])
        self.assertEqual(emp.role, "admin")
        self.assertEqual(emp.permissions.get("dashboard", {}).get("view"), True)

    def test_duplicate_username_rejected(self):
        self.auth(self.manager)
        res = self.c.post(
            "/api/employees/",
            {"name": "موظف آخر", "username": "mgr", "password": "x", "branch": self.branch.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_serializer_never_returns_password(self):
        self.auth(self.manager)
        res = self.c.get(f"/api/employees/{self.manager.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotIn("password", res.data)