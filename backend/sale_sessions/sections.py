PERMISSION_ACTIONS = ["view", "create", "edit", "delete"]

SECTIONS = [
    {"key": "dashboard", "label": "الرئيسية", "fixed": True, "actions": ["view"]},
    {"key": "branches", "label": "الفروع", "fixed": False, "actions": PERMISSION_ACTIONS},
    {"key": "suppliers", "label": "الموردون", "fixed": False, "actions": PERMISSION_ACTIONS},
    {"key": "customers", "label": "الزبائن", "fixed": False, "actions": PERMISSION_ACTIONS},
    {"key": "partners", "label": "الشركاء", "fixed": False, "actions": PERMISSION_ACTIONS},
    {"key": "fabrics", "label": "الأقمشة", "fixed": False, "actions": PERMISSION_ACTIONS},
    {"key": "sales", "label": "المبيعات", "fixed": False, "actions": PERMISSION_ACTIONS},
    {"key": "sessions", "label": "ورديات البيع", "fixed": False, "actions": PERMISSION_ACTIONS},
    {"key": "employees", "label": "الموظفون", "fixed": False, "actions": PERMISSION_ACTIONS},
    {"key": "warehouses", "label": "المخازن", "fixed": False, "actions": PERMISSION_ACTIONS},
    {"key": "expenses", "label": "المصاريف", "fixed": False, "actions": PERMISSION_ACTIONS},
    {"key": "reports", "label": "التقارير", "fixed": False, "actions": PERMISSION_ACTIONS},
    {"key": "accounting", "label": "المحاسبة", "fixed": False, "actions": PERMISSION_ACTIONS},
    {"key": "messages", "label": "التواصل", "fixed": False, "actions": ["view", "create"]},
    {"key": "settings", "label": "الإعدادات", "fixed": True, "actions": PERMISSION_ACTIONS},
]

ROLE_PRESETS = {
    "admin": {
        "label": "مدير النظام",
        "description": "صلاحيات كاملة على جميع الأقسام",
        "permissions": {
            s["key"]: {a: True for a in s["actions"]}
            for s in SECTIONS
        },
        "hidden_sections": [],
    },
    "supervisor": {
        "label": "مشرف",
        "description": "يراقب ويعدل — لا يمكنه الحذف",
        "permissions": {
            s["key"]: {a: (a != "delete") for a in s["actions"]}
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
            s["key"]: {a: (a == "view") for a in s["actions"]}
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
