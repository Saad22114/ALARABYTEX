"""شجرة الحسابات الافتراضية — تُنشأ عند أول تشغيل للنظام.

المفاتيح (source_key) تربط الحسابات تلقائياً بالمصادر الخارجية:
  CASH              -> حساب النقد بالخزنة          (مدين بطبيعته)
  BANK              -> حساب البنك                   (مدين بطبيعته)
  SUPPLIER_PAYABLE  -> ذمم الموردين (دائن)
  PARTNER_EQUITY    -> حصص الشركاء (دائن)
  SALE_REVENUE      -> إيراد المبيعات (دائن)
  COGS              -> تكلفة البضاعة المباعة (مدين)
  INVENTORY         -> مخزون البضاعة (مدين)
  OPENING_OFFSET    -> مقابل الأرصدة الافتتاحية (دائن)
  RETAINED_EARNINGS -> الأرباح المحتجزة (دائن)
  EXPENSE_ROOT      -> جذر حسابات المصاريف (لبناء حسابات التصنيفات تحته)
"""

from django.db import transaction

from .models import Account

ROOT_TYPES = ["asset", "liability", "equity", "income", "expense"]

ROOTS = [
    ("1", "الأصول", "asset", "", ""),
    ("2", "الالتزامات", "liability", "", ""),
    ("3", "حقوق الملكية", "equity", "", ""),
    ("4", "الإيرادات", "income", "", ""),
    ("5", "المصاريف", "expense", "", ""),
]

ACCOUNTS = [
    # أصول متداولة
    ("11", "الأصول المتداولة", "asset", "1", ""),
    ("12", "الأصول الثابتة", "asset", "1", ""),
    ("1101", "النقد بالخزنة", "asset", "11", "CASH"),
    ("1102", "البنك", "asset", "11", "BANK"),
    ("1103", "ذمم العملاء", "asset", "11", ""),
    ("1104", "مخزون البضاعة", "asset", "11", "INVENTORY"),
    ("1210", "أصول ثابتة", "asset", "12", ""),
    # التزامات
    ("21", "الالتزامات المتداولة", "liability", "2", ""),
    ("22", "الالتزامات طويلة الأجل", "liability", "2", ""),
    ("2101", "ذمم الموردين", "liability", "21", "SUPPLIER_PAYABLE"),
    ("2102", "التزامات أخرى", "liability", "21", ""),
    ("2201", "قروض طويلة الأجل", "liability", "22", ""),
    # حقوق الملكية
    ("31", "رأس المال", "equity", "3", ""),
    ("32", "الشركاء", "equity", "3", ""),
    ("33", "الأرباح المحتجزة", "equity", "3", ""),
    ("3101", "رأس المال", "equity", "31", ""),
    ("3201", "حسابات الشركاء", "equity", "32", "PARTNER_EQUITY"),
    ("3301", "الأرباح المحتجزة", "equity", "33", "RETAINED_EARNINGS"),
    ("3901", "مقابل الأرصدة الافتتاحية", "equity", "3", "OPENING_OFFSET"),
    # إيرادات
    ("41", "إيرادات التشغيل", "income", "4", ""),
    ("42", "إيرادات أخرى", "income", "4", ""),
    ("4101", "إيراد مبيعات الأقمشة", "income", "41", "SALE_REVENUE"),
    ("4201", "إيرادات أخرى", "income", "42", ""),
    # مصاريف
    ("51", "تكلفة البضاعة المباعة", "expense", "5", ""),
    ("52", "مصاريف التشغيل", "expense", "5", ""),
    ("53", "مصاريف عامة وإدارية", "expense", "5", ""),
    ("5101", "تكلفة البضاعة المباعة", "expense", "51", "COGS"),
    ("5201", "مصاريف التشغيل", "expense", "52", "EXPENSE_ROOT"),
    ("5301", "مصاريف عامة وإدارية", "expense", "53", ""),
    ("5401", "مصاريف أخرى", "expense", "5", ""),
]


@transaction.atomic
def seed_chart_of_accounts():
    if Account.objects.exists():
        return
    index = {}
    for code, name, type_, parent_code, source_key in ROOTS + ACCOUNTS:
        parent = index.get(parent_code) if parent_code else None
        index[code] = Account.objects.create(
            code=code,
            name=name,
            type=type_,
            parent=parent,
            source_key=source_key or None,
            is_system=bool(source_key),
        )
    return index


def ensure_seeded():
    if not Account.objects.exists():
        seed_chart_of_accounts()