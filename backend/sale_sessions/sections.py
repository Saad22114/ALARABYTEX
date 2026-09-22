PERMISSION_ACTIONS = ["view", "create", "edit", "delete"]

SECTIONS = [
    {"key": "dashboard", "label": "الرئيسية", "fixed": True, "actions": ["view"]},
    {"key": "branches", "label": "الفروع", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "branches", "label": "قائمة الفروع"},
        {"key": "detail", "label": "تفاصيل الفرع"},
    ]},
    {"key": "suppliers", "label": "الموردون", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "list", "label": "قائمة الموردين"},
        {"key": "ledger", "label": "كشف المورد"},
        {"key": "purchases", "label": "المشتريات"},
        {"key": "statement", "label": "بيان الحساب"},
    ]},
    {"key": "customers", "label": "الزبائن", "fixed": False, "actions": PERMISSION_ACTIONS},
    {"key": "partners", "label": "الشركاء", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "partners", "label": "الشركاء"},
        {"key": "operations", "label": "العمليات"},
        {"key": "distribution", "label": "التوزيع"},
        {"key": "statement", "label": "كشف الحساب"},
    ]},
    {"key": "fabrics", "label": "الأقمشة", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "fabric_list", "label": "قائمة الأقمشة"},
        {"key": "stock", "label": "المخزون حسب المخازن"},
    ]},
    {"key": "sales", "label": "المبيعات", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "sales", "label": "صفحة البيع"},
        {"key": "sessions", "label": "ورديات البيع"},
        {"key": "closed", "label": "الورديات المحفوظة"},
        {"key": "by_employee", "label": "توزيع المبيعات على الموظفين"},
    ]},
    {"key": "sessions", "label": "ورديات البيع", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "open", "label": "الورديات المفتوحة"},
        {"key": "close", "label": "إغلاق الوردية"},
        {"key": "manual", "label": "إضافة وردية كاملة"},
        {"key": "move_item", "label": "نقل البند بين الورديات"},
    ]},
    {"key": "employees", "label": "الموظفون", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "list", "label": "قائمة الموظفين"},
        {"key": "permissions", "label": "الصلاحيات والأدوار"},
    ]},
    {"key": "warehouses", "label": "المخازن", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "warehouses", "label": "المخازن"},
        {"key": "stock", "label": "المخزون"},
        {"key": "receipts", "label": "سندات الاستلام"},
        {"key": "transfers", "label": "التحويلات"},
        {"key": "adjustments", "label": "التسويات"},
        {"key": "counts", "label": "الجرد"},
        {"key": "movements", "label": "الحركات"},
    ]},
    {"key": "expenses", "label": "المصاريف", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "expense_list", "label": "قائمة المصاريف"},
        {"key": "categories", "label": "تصنيفات المصاريف"},
        {"key": "budgets", "label": "الميزانيات"},
    ]},
    {"key": "reports", "label": "التقارير", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "sales", "label": "تقرير المبيعات"},
        {"key": "expenses", "label": "تقرير المصاريف"},
        {"key": "budget", "label": "المصاريف مقابل الميزانية"},
        {"key": "commissions", "label": "عمولات المبيعات"},
        {"key": "net", "label": "صافي النتيجة اليومي"},
        {"key": "profit-loss", "label": "الربح والخسارة"},
        {"key": "cogs", "label": "تكلفة البضاعة المباعة"},
        {"key": "journal", "label": "القيود اليومية"},
        {"key": "inventory", "label": "تقرير المخزون"},
        {"key": "inventory-movements", "label": "حركات المخزون"},
        {"key": "suppliers", "label": "قائمة الموردين"},
        {"key": "branches", "label": "قائمة الفروع"},
    ]},
    {"key": "accounting", "label": "المحاسبة", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "journal", "label": "دفتر اليومية"},
        {"key": "accounts", "label": "شجرة الحسابات"},
        {"key": "trial-balance", "label": "ميزان المراجعة"},
        {"key": "statements", "label": "القوائم المالية"},
        {"key": "cashbox", "label": "الخزينة والإقفال"},
    ]},
    {"key": "messages", "label": "التواصل", "fixed": False, "actions": ["view", "create"]},
    {"key": "themes", "label": "الثيمات والتحكم", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "appearance", "label": "المظهر"},
        {"key": "print", "label": "الطباعة"},
        {"key": "categories", "label": "تصنيفات المصاريف"},
    ]},
    {"key": "settings", "label": "الإعدادات", "fixed": True, "actions": PERMISSION_ACTIONS},
]


def section_windows(section):
    """قائمة مفاتيح نوافذ القسم — فارغة إن كان القسم بلا نوافذ."""
    return [w["key"] for w in section.get("windows", [])]

ROLE_PRESETS = {
    "admin": {
        "label": "مدير النظام",
        "description": "صلاحيات كاملة على جميع الأقسام",
        "permissions": {
            s["key"]: {
                **{a: True for a in s["actions"]},
                **({"windows": section_windows(s)} if s.get("windows") else {}),
            }
            for s in SECTIONS
        },
        "hidden_sections": [],
    },
    "supervisor": {
        "label": "مشرف",
        "description": "يراقب ويعدل — لا يمكنه الحذف",
        "permissions": {
            s["key"]: {
                **{a: (a != "delete") for a in s["actions"]},
                **({"windows": section_windows(s)} if s.get("windows") else {}),
            }
            for s in SECTIONS
        },
        "hidden_sections": [],
    },
    "sales": {
        "label": "مندوب مبيعات",
        "description": "المبيعات والمخزون فقط — يُنشئ ويعيدل",
        "permissions": {
            "dashboard": {"view": True},
            "branches": {"view": True},
            "suppliers": {"view": False, "create": False, "edit": False, "delete": False},
            "customers": {"view": True, "create": True, "edit": True, "delete": False},
            "partners": {"view": False, "create": False, "edit": False, "delete": False},
            "fabrics": {"view": True, "create": False, "edit": False, "delete": False},
            "sales": {"view": True, "create": True, "edit": True, "delete": False},
            "sessions": {"view": True, "create": True, "edit": True, "delete": False},
            "employees": {"view": False, "create": False, "edit": False, "delete": False},
            "warehouses": {"view": True, "create": False, "edit": False, "delete": False},
            "expenses": {"view": False, "create": False, "edit": False, "delete": False},
            "reports": {"view": True, "create": False, "edit": False, "delete": False},
            "accounting": {"view": False, "create": False, "edit": False, "delete": False},
            "messages": {"view": True, "create": True},
            "settings": {"view": False, "create": False, "edit": False, "delete": False},
        },
        "hidden_sections": ["suppliers", "partners", "employees", "expenses"],
    },
    "accountant": {
        "label": "محاسب",
        "description": "يدير المحاسبة ويطّلع على كل شيء",
        "permissions": {
            "dashboard": {"view": True},
            "branches": {"view": True, "create": False, "edit": False, "delete": False},
            "suppliers": {"view": True, "create": True, "edit": True, "delete": False},
            "customers": {"view": True, "create": True, "edit": True, "delete": False},
            "partners": {"view": True, "create": True, "edit": True, "delete": False},
            "fabrics": {"view": True, "create": False, "edit": False, "delete": False},
            "sales": {"view": True, "create": False, "edit": False, "delete": False},
            "sessions": {"view": True, "create": True, "edit": True, "delete": False},
            "employees": {"view": False, "create": False, "edit": False, "delete": False},
            "warehouses": {"view": True, "create": True, "edit": True, "delete": False},
            "expenses": {"view": True, "create": True, "edit": True, "delete": False},
            "reports": {"view": True, "create": False, "edit": False, "delete": False},
            "accounting": {"view": True, "create": True, "edit": True, "delete": True},
            "messages": {"view": True, "create": True},
            "settings": {"view": False, "create": False, "edit": False, "delete": False},
        },
        "hidden_sections": ["employees", "settings"],
    },
    "viewer": {
        "label": "مشاهد",
        "description": "عرض فقط — لا يمكنه أي تعديل",
        "permissions": {
            s["key"]: {
                **{a: (a == "view") for a in s["actions"]},
                **({"windows": section_windows(s)} if s.get("windows") else {}),
            }
            for s in SECTIONS
        },
        "hidden_sections": [],
    },
    "custom": {
        "label": "مخصص",
        "description": "صلاحيات يدوية حسب القسم",
        "permissions": {
            "dashboard": {"view": True},
            "branches": {"view": False, "create": False, "edit": False, "delete": False},
            "suppliers": {"view": False, "create": False, "edit": False, "delete": False},
            "customers": {"view": False, "create": False, "edit": False, "delete": False},
            "partners": {"view": False, "create": False, "edit": False, "delete": False},
            "fabrics": {"view": False, "create": False, "edit": False, "delete": False},
            "sales": {"view": False, "create": False, "edit": False, "delete": False},
            "sessions": {"view": False, "create": False, "edit": False, "delete": False},
            "employees": {"view": False, "create": False, "edit": False, "delete": False},
            "warehouses": {"view": False, "create": False, "edit": False, "delete": False},
            "expenses": {"view": False, "create": False, "edit": False, "delete": False},
            "reports": {"view": False, "create": False, "edit": False, "delete": False},
            "accounting": {"view": False, "create": False, "edit": False, "delete": False},
            "messages": {"view": True, "create": True},
            "settings": {"view": False, "create": False, "edit": False, "delete": False},
        },
        "hidden_sections": [],
    },
}

ROLE_CHOICES = [(k, v["label"]) for k, v in ROLE_PRESETS.items()]
