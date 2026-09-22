import re

files = [
    "backend/branches/tests.py",
    "backend/warehouses/tests.py",
    "backend/appsettings/tests.py",
    "backend/reports/tests.py",
    "backend/dashboard/tests.py",
    "backend/suppliers/tests.py",
    "backend/sale_sessions/tests.py",
    "backend/expenses/tests.py",
    "backend/sales/tests.py",
]

for path in files:
    with open(path, encoding="utf-8") as f:
        s = f.read()
    if "from core.testsupport import authenticate_admin" not in s:
        s = s.replace(
            "from rest_framework.test import APIClient",
            "from rest_framework.test import APIClient\nfrom core.testsupport import authenticate_admin",
            1,
        )

    pat = re.compile(r"(\n)([ \t]*)self\.c = APIClient\(\)")

    def repl(m):
        return (
            m.group(1)
            + m.group(2)
            + "self.c = APIClient()\n"
            + m.group(2)
            + "authenticate_admin(self.c)"
        )

    s2, n = pat.subn(repl, s)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(s2)
    print(path, "->", n, "insertions")