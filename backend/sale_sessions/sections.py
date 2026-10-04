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
    {"key": "attendance", "label": "الحضور", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "daily", "label": "ورقة اليوم"},
        {"key": "records", "label": "السجلات"},
        {"key": "summary", "label": "الملخص"},
        {"key": "policy", "label": "سياسة الحضور"},
    ]},
    {"key": "payroll", "label": "الرواتب", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "runs", "label": "مسيّرات الرواتب"},
        {"key": "payslips", "label": "قسائم الرواتب"},
        {"key": "advances", "label": "سلف الموظفين"},
        {"key": "structures", "label": "هياكل الرواتب"},
        {"key": "statement", "label": "كشف حساب الموظف"},
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
    {"key": "machine_account", "label": "التسويات المالية", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "summary", "label": "الملخص والرصيد"},
        {"key": "collections", "label": "الدفعات المستلمة"},
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
        {"key": "branch-performance", "label": "أداء الفروع المقارن"},
        {"key": "fabric-profitability", "label": "ربحية الأقمشة"},
        {"key": "sales-trend", "label": "تطور المبيعات"},
        {"key": "employee-performance", "label": "أداء الموظفين"},
        {"key": "inventory-slow", "label": "المخزون الراكد"},
        {"key": "supplier-aging", "label": "أعمار ديون الموردين"},
        {"key": "partner-aging", "label": "أعمار حسابات الشركاء"},
        {"key": "cashflow", "label": "حركة الخزينة"},
        {"key": "payroll", "label": "تقرير الرواتب"},
    ]},
    {"key": "accounting", "label": "المحاسبة", "fixed": False, "actions": PERMISSION_ACTIONS, "windows": [
        {"key": "journal", "label": "دفتر اليومية"},
        {"key": "accounts", "label": "شجرة الحسابات"},
        {"key": "trial-balance", "label": "ميزان المراجعة"},
        {"key": "statements", "label": "القوائم المالية"},
        {"key": "cashbox", "label": "الخزينة والإقفال"},
    ]},
    {"key": "audit", "label": "سجل التدقيق", "fixed": False, "actions": ["view"], "windows": [
        {"key": "log", "label": "سجل العمليات"},
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
            "payroll": {"view": False, "create": False, "edit": False, "delete": False},
            "warehouses": {"view": True, "create": False, "edit": False, "delete": False},
            "attendance": {"view": True, "create": False, "edit": False, "delete": False},
            "expenses": {"view": False, "create": False, "edit": False, "delete": False},
            "reports": {"view": True, "create": False, "edit": False, "delete": False},
            "accounting": {"view": False, "create": False, "edit": False, "delete": False},
            "audit": {"view": False},
            "messages": {"view": True, "create": True},
            "settings": {"view": False, "create": False, "edit": False, "delete": False},
        },
        "hidden_sections": ["suppliers", "partners", "employees", "expenses", "payroll"],
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
            "payroll": {"view": True, "create": True, "edit": True, "delete": False},
            "attendance": {"view": True, "create": False, "edit": False, "delete": False},
            "machine_account": {"view": True, "create": True, "edit": True, "delete": False},
            "warehouses": {"view": True, "create": True, "edit": True, "delete": False},
            "expenses": {"view": True, "create": True, "edit": True, "delete": False},
            "reports": {"view": True, "create": False, "edit": False, "delete": False},
            "accounting": {"view": True, "create": True, "edit": True, "delete": True},
            "audit": {"view": False},
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
            "payroll": {"view": False, "create": False, "edit": False, "delete": False},
            "warehouses": {"view": False, "create": False, "edit": False, "delete": False},
            "attendance": {"view": False, "create": False, "edit": False, "delete": False},
            "expenses": {"view": False, "create": False, "edit": False, "delete": False},
            "reports": {"view": False, "create": False, "edit": False, "delete": False},
            "accounting": {"view": False, "create": False, "edit": False, "delete": False},
            "audit": {"view": False},
            "messages": {"view": True, "create": True},
            "settings": {"view": False, "create": False, "edit": False, "delete": False},
        },
        "hidden_sections": [],
    },
}

ROLE_CHOICES = [(k, v["label"]) for k, v in ROLE_PRESETS.items()]


def canonical_role(role):
    """الدورُ كما تعرّفه `Employee.Role`، أو `None` إن كان خارجَ الاختيارات.

    الحقلُ نصٌّ حرٌّ لا مفاتيحَ مقيَّدة، فالصفوفُ المكتوبةُ بغير
    الاختيارات تمرّ. وهي خطأٌ لا نيّة: `ADMIN` لا تعني شيئاً في هذا
    المشروع، فلا يصلح أن تُقرأ ولا أن تُعرض.
    """
    text = str(role or "").strip().lower()
    return text if text in ROLE_PRESETS else None


def role_preset(role):
    """إعدادُ الدور، يُقرأ بلا حساسيةٍ لحالة الحروف.

    كانت الصفوفُ المكتوبةُ `ADMIN` لا `admin` بلا إعدادٍ أصلاً، لأنّ
    `ROLE_PRESETS` لا يعرف إلا الحروفَ الصغيرة. و«لا أعرف هذا الدور» في
    هذا المشروع تعني «مقفَلٌ كلُّ شيء»، فالموظفُ يخسر ما يملكه باردةً
    بسبب حرفٍ واحدٍ في خانة.
    """
    preset = ROLE_PRESETS.get(role)
    if preset is not None:
        return preset
    return ROLE_PRESETS.get(str(role or "").strip().lower(), {})


def effective_permissions(role, stored=None):
    """صلاحياتُ الموظف كما تُقرأ في الجلسة، لا كما هي مخزَّنة في صفّه.

    الخريطةُ المخزَّنة كُتبت لحظةَ إنشاء الحساب، فكلُّ قسمٍ أُضيف إلى
    `SECTIONS` بعد ذلك الحين غائبٌ منها. والقسمُ الغائبُ يُخفى من القائمة،
    وصفحتُه تخرجُ بلا تبويباتٍ لأنّ `hasWindow` لا يجد مفتاحاً أصلاً.
    فالموظفُ الذي أُعطي القسمَ يظنّ أنّ النظامَ نسي قسماً موجوداً، والسببُ
    خانةٌ لم تُملأ لا خطأٌ في الصلاحيات ولا قرارٌ اتُّخذ.

    فالقسمُ الناقصُ يُؤخَذُ من دوره: مديرٌ يأخذه كاملاً، ومندوبُ مبيعاتٍ
    يأخذ عرضَه وحده. ولا يُكتب فوق مفتاحٍ موجودٍ أبداً، فاختيارُ الموظف
    في شاشة الصلاحيات يبقى قائمًا، وهذا يملأ الغائبَ ولا يمسّ الحاضر.

    وقاعدةٌ ثانية في الباب نفسِه: القسمُ الممنوحُ بلا قائمةِ نوافذ يأخذ
    كلَّ نوافذه المعلنة. فحرفُ «view» وعدٌ بصفحةٍ فيها شيء، ولو تُرك بلا
    نافذةٍ لكانت الصفحةُ فضاءً والوعدُ كذباً. وهذا ما تفعله الواجهةُ عند
    تطبيع صلاحيات دورٍ في `normalizePermissions`، فالحكمُ هنا وعلى هناك
    واحد، وإلّا صار لكلِّ طرفٍ قانونُه فيُعطى الموظفُ ما لا يرى فيه شيئاً.
    """
    stored = stored if isinstance(stored, dict) else {}
    preset = role_preset(role).get("permissions", {})
    out = {}
    for s in SECTIONS:
        key = s["key"]
        declared = {w["key"] for w in (s.get("windows") or [])}
        cur = stored.get(key)
        if not isinstance(cur, dict):
            cur = preset.get(key)
        actions = s["actions"]
        if not isinstance(cur, dict):
            # لا دورَ يذكره ولا سطرٌ في الصفّ: مُقفَلٌ كلُّه، وهو ما يريده
            # من لم يذكره. والمُقفَلُ يُكتب صريحاً لا غائباً، فيرى الفهرسُ
            # القسمَ كلَّه في كلِّ مرّة.
            out[key] = {a: False for a in actions}
            continue
        entry = {a: bool(cur.get(a)) for a in actions}
        windows = cur.get("windows")
        if declared:
            entry["windows"] = (
                [w for w in windows if w in declared]
                if isinstance(windows, list) and windows
                else sorted(declared)
            )
        elif isinstance(windows, list):
            entry["windows"] = list(windows)
        out[key] = entry
    return out
