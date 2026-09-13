# القماش العربي — نظام إدارة أعمال الأقمشة

نظام عربي بالكامل (RTL) لإدارة أعمال تجارة الأقمشة — المرحلة الأولى (MVP).
Next.js Frontend + Django REST Framework Backend + PostgreSQL.

## المحتوى (Phase 1)

- لوحة التحكم: إجمالي المبيعات / المصاريف / الصافي اليومي، عدد الفروع والموردين، رسم بياني، فلترة حسب اليوم/الأسبوع/الشهر/فترة مخصصة وفرع.
- الفروع: إضافة/تعديل/حذف (الحذف محظور عند وجود سجلات)، صفحة تفاصيل مع المبيعات والمصاريف المرتبطة.
- الموردون: إضافة/تعديل/حذف وعرض التفاصيل.
- المبيعات اليومية: سجل واحد لكل (فرع، يوم) مع تحقق «مجموع طرق الدفع = إجمالي المبيعات»، فلترة بالفرع والتاريخ والبحث.
- المصاريف: تسجيل المصاريف وتصنيفاتها، فلترة بالفرع والتصنيف والتاريخ والبحث.
- التقارير: المبيعات، المصاريف، الصافي اليومي، قائمة الموردين، قائمة الفروع — مع تصدير Excel (xlsx).
- الإعدادات: تصنيفات المصاريف (إضافة/حذف التصنيفات المخصصة) وبيانات النظام.

خارج نطاق المرحلة: تسجيل الدخول، المخزون، الأصناف، المشتريات، نقاط البيع، قارئ الباركود.

## هيكل المشروع

```
site 3 open code/
├── backend/          # Django REST Framework API
│   ├── config/       # الإعدادات والمسارات الرئيسية
│   ├── core/         # نماذج مشتركة + ترقيم صفحات
│   ├── branches/     # الفروع
│   ├── suppliers/    # الموردون
│   ├── sales/        # المبيعات اليومية
│   ├── expenses/     # المصاريف والتصنيفات
│   ├── dashboard/    # ملخصات لوحة التحكم
│   └── reports/      # التقارير + تصدير Excel
├── frontend/         # Next.js 14 + TypeScript + Tailwind (RTL)
└── database/         # schema.sql + توثيق المخطط + docker-compose
```

## المتطلبات

- Python 3.12+ و pip
- Node.js 18+ و npm
- PostgreSQL 17 (مثبت محلياً أو عبر Docker)

## 1) تشغيل قاعدة البيانات

PostgreSQL محلي، أو:

```bash
docker compose -f database/docker-compose.yml up -d
```

أنشئ القاعدة (كلمة مرور المستخدم `postgres` الافتراضية `postgres`):

```sql
CREATE DATABASE fabric_arabi ENCODING 'UTF8';
```

## 2) تشغيل Backend (Django)

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # Linux / macOS
pip install -r requirements.txt
cp .env.example .env              # عدّل القيم إن لزم
python manage.py migrate          # إنشاء الجداول
python manage.py seed_categories  # بذر تصنيفات المصاريف الأساسية (9)
python manage.py seed_demo        # (اختياري) بيانات تجريبية للمعاينة: فروع، موردون، مبيعات، مصاريف
python manage.py runserver 127.0.0.1:8000
```

متغيرات بيئة `backend/.env`:

| المتغير | الافتراضي | الوصف |
|---|---|---|
| DJANGO_DEBUG | True | وضع التطوير |
| SECRET_KEY | — | مفتاح سرّي (استبدله في الإنتاج) |
| DB_NAME | fabric_arabi | اسم القاعدة |
| DB_USER / DB_PASSWORD | postgres / postgres | بيانات الاتصال |
| DB_HOST / DB_PORT | 127.0.0.1 / 5432 | عنوان القاعدة |
| FRONTEND_URL | http://localhost:3000 | أصل المسموح به لـ CORS |

> ملاحظة: `manage.py` يقرأ `.env` من مجلد `backend/` تلقائياً.

## 3) تشغيل Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

أنشئ `frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api
```

## نقاط نهاية API الرئيسية

| المسار | الوصف |
|---|---|
| `/api/branches/` | CRUD الفروع (بحث + ترقيم) |
| `/api/suppliers/` | CRUD الموردين |
| `/api/sales/` | المبيعات اليومية (فلترة branch/date_from/date_to/search) |
| `/api/expenses/` | المصاريف (فلترة branch/category/date/..) |
| `/api/expense-categories/` | التصنيفات |
| `/api/dashboard/summary/?period=today\|week\|month\|custom&branch=&date_from=&date_to=` | ملخص لوحة التحكم |
| `/api/reports/sales/` | تقرير المبيعات |
| `/api/reports/expenses/` | تقرير المصاريف |
| `/api/reports/net-daily/` | الصافي اليومي |
| `/api/reports/suppliers/` | قائمة الموردين |
| `/api/reports/branches/` | قائمة الفروع |

أضف `?export=xlsx` لأي تقرير لتنزيله كملف Excel.

الاستجابات المترقمة: `{ count, next, previous, results }`.

## ملاحظات

- كل الرسائل (API والواجهة) بالعربية والعملة `ر.ع` (ريال عماني).
- الاتجاه RTL والخط Cairo عبر `next/font/google`.
- انظر `database/schema.md` لتوثيق كامل للمخطط والعلاقات.
- اختبارات Backend: `cd backend && .\.venv\Scripts\python.exe manage.py test` (44 اختبارًا: فروع، موردون، مبيعات، مصاريف، لوحة تحكم، تقارير).