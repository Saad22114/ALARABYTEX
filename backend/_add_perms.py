"""إضافة permission_section إلى كل View بناءً على خريطة الفئة ← القسم."""

import io
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "D:\\QOMASH\\site working\\site 3 open code\\backend")

MAP = {
    "branches/views.py": {
        "BranchViewSet": "branches",
        "FabricBranchPriceViewSet": "branches",
    },
    "appsettings/views.py": {
        "LogoUploadView": "settings",
        "AppSettingsView": "settings",
        "BackupView": "settings",
        "RestoreView": "settings",
        "ResetView": "settings",
    },
    "customers/views.py": {"CustomerViewSet": "customers"},
    "dashboard/views.py": {
        "DashboardAlertsView": "dashboard",
        "DashboardSummaryView": "dashboard",
        "DashboardActivityView": "dashboard",
    },
    "partners/views.py": {
        "PartnerViewSet": "partners",
        "PartnerOperationViewSet": "partners",
    },
    "accounting/views.py": {
        "AccountViewSet": "accounting",
        "JournalEntryViewSet": "accounting",
        "ClosePeriodView": "accounting",
        "TrialBalanceView": "accounting",
        "IncomeStatementView": "accounting",
        "BalanceSheetView": "accounting",
        "CashFlowView": "accounting",
        "CashBoxView": "accounting",
    },
    "reports/views.py": {
        "SalesReportView": "reports",
        "ExpensesReportView": "reports",
        "ExpensesBudgetReportView": "reports",
        "NetDailyReportView": "reports",
        "SupplierReportView": "reports",
        "BranchReportView": "reports",
        "InventoryReportView": "reports",
        "InventoryMovementsReportView": "reports",
        "CogsReportView": "reports",
        "ProfitLossReportView": "reports",
        "CommissionsReportView": "reports",
        "JournalReportView": "reports",
    },
    "suppliers/views.py": {
        "SupplierViewSet": "suppliers",
        "FabricViewSet": "fabrics",
        "SupplierLedgerViewSet": "suppliers",
    },
    "expenses/views.py": {
        "ExpenseCategoryViewSet": "expenses",
        "ExpenseViewSet": "expenses",
        "ExpenseBudgetViewSet": "expenses",
    },
    "sale_sessions/views.py": {
        "SectionsView": "@identity",
        "EmployeeViewSet": "employees",
        "SaleSessionViewSet": "sessions",
    },
    "warehouses/views.py": {
        "WarehouseViewSet": "warehouses",
        "FabricRollViewSet": "warehouses",
        "GoodsReceiptViewSet": "warehouses",
        "StockTransferViewSet": "warehouses",
        "StockAdjustmentViewSet": "warehouses",
        "StockCountViewSet": "warehouses",
        "StockMovementViewSet": "warehouses",
        "StockOpeningViewSet": "warehouses",
        "StockBalanceView": "warehouses",
        "StockBalanceSetView": "warehouses",
    },
    "sales/views.py": {
        "DailySaleViewSet": "sales",
        "SalesByEmployeeView": "sales",
        "SaleStockView": "sales",
    },
}

BASE = "D:\\QOMASH\\site working\\site 3 open code\\backend\\"


def process(path, class_map):
    full = BASE + path
    src = io.open(full, "r", encoding="utf-8").read()
    lines = src.split("\n")
    out = []
    changed = 0
    i = 0
    class_re = re.compile(r"^class\s+(\w+)\s*\(")
    attr_map = {k: v for k, v in class_map.items()}
    while i < len(lines):
        line = lines[i]
        m = class_re.match(line)
        if m and m.group(1) in attr_map:
            section = attr_map[m.group(1)]
            # check body indent
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines) and not lines[j].startswith(" "):
                print(f"  WARN: empty class body {path}:{m.group(1)}")
            indent = "    "
            # skip leading docstring to keep __doc__
            k = i + 1
            while k < len(lines):
                s = lines[k].strip()
                if s.startswith('"""') or s.startswith("'''"):
                    # find end of docstring
                    if s.endswith('"""') or s.endswith("'''") or (len(s) > 3 and (s[-3:] in ('"""', "'''"))):
                        k += 1
                        break
                    while k < len(lines) and not (lines[k].strip().endswith('"""') or lines[k].strip().endswith("'''")):
                        k += 1
                    k += 1
                    break
                break
            out.extend(lines[i:k])
            out.append(f'{indent}permission_section = "{section}"')
            i = k
            changed += 1
            continue
        out.append(line)
        i += 1
    if changed:
        io.open(full, "w", encoding="utf-8", newline="").write("\n".join(out))
        print(f"{path}: inserted {changed}")
    else:
        print(f"{path}: no changes")


for path, cmap in MAP.items():
    process(path, cmap)