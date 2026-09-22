import os, sys, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
sys.stdout.reconfigure(encoding="utf-8")
from sale_sessions.models import Employee
from branches.models import Branch
print("Branches:", list(Branch.objects.values_list("id", "name", "code")))
for emp in Employee.objects.select_related("user").order_by("id"):
    print(emp.id, "|", emp.user.username if emp.user_id else "(no user)", "| branch_id=", emp.branch_id, "|", emp.name, "| role=", emp.role)
