"""اختبارات البحث الشامل: التغطية، الترتيب، الصلاحيات، والنطاق بالفرع."""

from django.test import TestCase
from rest_framework.test import APIClient

from branches.models import Branch
from core.branch_scope import employee_branch_scope
from core.testsupport import authenticate_admin, make_admin_user
from customers.models import Customer
from sale_sessions.models import Employee
from suppliers.models import Fabric, Supplier
from warehouses.models import Warehouse

from .views import SPECS


class SearchSpecIntegrityTests(TestCase):
    def test_every_spec_field_exists_on_its_model(self):
        """يمنع كسر البحث بصمت عند إضافة/حذف حقل في نموذج."""
        for spec in SPECS:
            names = {f.name for f in spec.model._meta.fields}
            for name in spec.fields:
                self.assertIn(name, names, f"{spec.key}: الحقل {name} غير موجود")

    def test_every_branch_field_is_resolvable(self):
        """``branch_field`` يُستخدم في ``scope_queryset`` — يجب أن يقبله النطاق."""
        for spec in SPECS:
            if not spec.branch_field:
                continue
            lookup = (
                f"{spec.branch_field}__in"
                if spec.branch_field == "id" or spec.branch_field.endswith("_id")
                else f"{spec.branch_field}_id__in"
            )
            models = {spec.model}
            self.assertTrue(models, spec.key)
            spec.model.objects.filter(**{lookup: [0]}).query  # يبني الاستعلام دون تنفيذه

    def test_every_spec_has_navigation_and_label(self):
        for spec in SPECS:
            self.assertTrue(spec.href.startswith("/"), spec.key)
            self.assertTrue(spec.label, spec.key)
            self.assertTrue(spec.singular, spec.key)
            self.assertTrue(spec.section, spec.key)

    def test_spec_keys_are_unique(self):
        keys = [s.key for s in SPECS]
        self.assertEqual(len(keys), len(set(keys)))


class GlobalSearchTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user, self.employee = authenticate_admin(self.client)
        self.branch = self.employee.branch

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/search/?q=ali").status_code, 401)

    def test_short_query_returns_empty_with_hint(self):
        response = self.client.get("/api/search/?q=a")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["groups"], [])
        self.assertEqual(payload["min_length"], 2)

    def test_finds_supplier_by_name_and_phone(self):
        Supplier.objects.create(name="مورد الرياض", phone="0555000111")
        by_name = self.client.get("/api/search/?q=الرياض").json()
        self.assertEqual(by_name["total"], 1)
        self.assertEqual(by_name["results"][0]["type"], "supplier")
        self.assertEqual(by_name["results"][0]["title"], "مورد الرياض")
        self.assertEqual(by_name["results"][0]["href"], "/suppliers")

        by_phone = self.client.get("/api/search/?q=0555000111").json()
        self.assertEqual(by_phone["total"], 1)

    def test_result_shape_is_complete(self):
        Supplier.objects.create(name="مورد الشكل", company_name="شركة النسيج", city="حائل")
        row = self.client.get("/api/search/?q=الشكل").json()["results"][0]
        for key in ("type", "type_label", "group_label", "icon", "id", "title", "subtitle", "href"):
            self.assertIn(key, row)
        self.assertEqual(row["type_label"], "مورد")
        self.assertEqual(row["group_label"], "الموردون")
        self.assertEqual(row["subtitle"], "شركة النسيج")


    def test_groups_expose_label_and_count(self):
        Supplier.objects.create(name="مورد تجميع")
        Fabric.objects.create(name="قماش تجميع", code="G-1")
        payload = self.client.get("/api/search/?q=تجميع").json()
        keys = {g["key"] for g in payload["groups"]}
        self.assertEqual(keys, {"supplier", "fabric"})
        for group in payload["groups"]:
            self.assertTrue(group["label"])
            self.assertEqual(group["count"], len(group["results"]))
        self.assertEqual(payload["total"], 2)

    def test_exact_match_ranks_before_partial(self):
        Supplier.objects.create(name="موردidal")
        Supplier.objects.create(name="مورد、公司idal outsource")
        Supplier.objects.create(name="zzz")
        rows = self.client.get("/api/search/?q=موردidal").json()["results"]
        self.assertEqual(rows[0]["title"], "موردidal")

    def test_prefix_match_ranks_before_contains(self):
        Supplier.objects.create(name="الرياض للتجارة")
        Supplier.objects.create(name="مؤسسة الرياض القديمة")
        rows = self.client.get("/api/search/?q=الرياض").json()["results"]
        self.assertEqual(rows[0]["title"], "الرياض للتجارة")

    def test_types_filter_restricts_entity_kinds(self):
        Supplier.objects.create(name="مورد مقفل")
        Fabric.objects.create(name="قماش مقفل")
        payload = self.client.get("/api/search/?q=مقفل&types=fabric").json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["results"][0]["type"], "fabric")

    def test_limit_caps_results_per_type(self):
        for i in range(7):
            Supplier.objects.create(name=f"مورد مكرر {i}")
        payload = self.client.get("/api/search/?q=مكرر&limit=3").json()
        self.assertEqual(payload["total"], 3)
        limited = self.client.get("/api/search/?q=مكرر&limit=1").json()
        self.assertEqual(limited["total"], 1)

    def test_limit_is_clamped(self):
        Supplier.objects.create(name="مورد سقف")
        self.assertEqual(self.client.get("/api/search/?q=سقف&limit=0").status_code, 200)
        self.assertEqual(self.client.get("/api/search/?q=سقف&limit=abc").json()["total"], 1)
        self.assertEqual(self.client.get("/api/search/?q=سقف&limit=9999").json()["total"], 1)

    def test_no_match_returns_empty(self):
        Supplier.objects.create(name="مورد موجود")
        payload = self.client.get("/api/search/?q=لاشيءمطابق").json()
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["results"], [])

    def test_search_is_case_insensitive_for_latin(self):
        Supplier.objects.create(name="Alpha Textiles", email="alpha@example.com")
        self.assertEqual(self.client.get("/api/search/?q=alpha").json()["total"], 1)
        self.assertEqual(self.client.get("/api/search/?q=ALPHA").json()["total"], 1)


class SearchPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user, self.employee = make_admin_user()
        self.client.force_authenticate(user=self.user)

    def _deny(self, section):
        perms = dict(self.employee.permissions or {})
        perms[section] = {"view": False}
        self.employee.permissions = perms
        self.employee.save(update_fields=["permissions"])

    def test_hides_types_user_cannot_view(self):
        Supplier.objects.create(name="مورد مخفي")
        Fabric.objects.create(name="قماش ظاهر")
        self._deny("suppliers")
        payload = self.client.get("/api/search/?q=مورد").json()
        self.assertEqual(payload["total"], 0)
        self.assertEqual(self.client.get("/api/search/?q=قماش").json()["total"], 1)

    def test_hides_employee_type_without_permission(self):
        Employee.objects.create(name="موظف سري")
        self._deny("employees")
        self.assertEqual(self.client.get("/api/search/?q=سري").json()["total"], 0)

    def test_inactive_employee_gets_no_results(self):
        Supplier.objects.create(name="مورد الموظف المعطل")
        self.employee.is_active = False
        self.employee.save(update_fields=["is_active"])
        self.assertEqual(self.client.get("/api/search/?q=المعطل").status_code, 403)


class SearchScopeTests(TestCase):
    """النطاق بالفرع: المدير يرى كل شيء، أما موظف بفرع فيقتصر بحثه على فرعه."""

    def setUp(self):
        self.branch_a = Branch.objects.create(name="فرع أ", code="SA", is_active=False)
        self.branch_b = Branch.objects.create(name="فرع ب", code="SB", is_active=False)
        self.user, self.employee = make_admin_user(branch=self.branch_a)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_manager_sees_all_branches(self):
        self.assertIsNone(employee_branch_scope(self.employee))
        Warehouse.objects.create(name="مخزن ألف", code="WA", branch=self.branch_a)
        Warehouse.objects.create(name="مخزن ألف作答", code="WB", branch=self.branch_b)
        titles = [r["title"] for r in self.client.get("/api/search/?q=مخزن ألف").json()["results"]]
        self.assertEqual(len(titles), 2)

    def test_restricted_employee_sees_only_own_branch(self):
        self.employee.role = Employee.Role.SALES
        self.employee.apply_role_preset(Employee.Role.SALES)
        self.employee.save()
        self.assertEqual(employee_branch_scope(self.employee), {self.branch_a.pk})

        Warehouse.objects.create(name="مخزن ألف", code="WA", branch=self.branch_a)
        Warehouse.objects.create(name="مخزن ألف作答", code="WB", branch=self.branch_b)
        titles = [r["title"] for r in self.client.get("/api/search/?q=مخزن ألف").json()["results"]]
        self.assertIn("مخزن ألف", titles)
        self.assertNotIn("مخزن ألف作答", titles)

    def test_employee_without_branch_sees_nothing_scoped(self):
        self.employee.role = Employee.Role.SALES
        self.employee.apply_role_preset(Employee.Role.SALES)
        self.employee.branch = None
        self.employee.multi_branch_access = False
        self.employee.save()
        Warehouse.objects.create(name="مخزن معزول", code="WC", branch=self.branch_a)
        self.assertEqual(self.client.get("/api/search/?q=مخزن معزول").json()["total"], 0)

    def test_unscoped_types_are_visible_to_all(self):
        Supplier.objects.create(name="مورد عام للكل")
        self.assertEqual(self.client.get("/api/search/?q=عام للكل").json()["total"], 1)
