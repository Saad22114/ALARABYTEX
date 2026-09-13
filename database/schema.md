# مخطط قاعدة البيانات — القماش العربي

PostgreSQL 17+ | Encoding: UTF8 | Timezone: Asia/Muscat

المصدر المعتمد لإنشاء البنية هو Django migrations (`python manage.py migrate`).
ملف `schema.sql` يُحفظ كمرجع DDL كامل للنشر اليدوي خارج Django.

## الجداول

### `branches_branch` — الفروع
| الحقل | النوع | وصف |
|---|---|---|
| id | bigserial | PK |
| code | varchar(30) UNIQUE | كود الفرع |
| name | varchar(150) | اسم الفرع |
| phone | varchar(30) | الهاتف |
| address | varchar(255) | العنوان |
| city | varchar(100) | المدينة |
| notes | text | ملاحظات |
| is_active | boolean | الحالة |
| created_at / updated_at | timestamptz | طوابع زمنية |

### `suppliers_supplier` — الموردون
| الحقل | النوع | وصف |
|---|---|---|
| id | bigserial | PK |
| name | varchar(150) | اسم المورد |
| company_name | varchar(200) | اسم الشركة |
| phone | varchar(30) | الهاتف |
| email | varchar(254) | البريد |
| address / city / country | varchar | العناوين |
| tax_number | varchar(50) | الرقم الضريبي |
| notes | text | ملاحظات |
| is_active | boolean | الحالة |

### `sales_dailysale` — المبيعات اليومية
سجل واحد لكل (فرع، يوم) بقيود `UNIQUE (branch_id, date)`.

| الحقل | النوع | وصف |
|---|---|---|
| id | bigserial | PK |
| branch_id | bigint FK → branches_branch | الفرع (PROTECT) |
| date | date | اليوم |
| total_sales | numeric(15,2) | إجمالي المبيعات |
| cash_amount | numeric(15,2) | نقدي |
| transfer_amount | numeric(15,2) | تحويل |
| card_amount | numeric(15,2) | بطاقة |
| other_amount | numeric(15,2) | أخرى |
| notes | text | ملاحظات |

- `payment_total = cash + transfer + card + other` (محسوب، غير مخزّن)
- يُقبل السجل فقط إذا: `|payment_total - total_sales| < 0.01`
- فهارس: `(branch_id)`, `(branch_id, date)`, `(date)`

### `expenses_expensecategory` — تصنيفات المصاريف
| الحقل | النوع | وصف |
|---|---|---|
| id | bigserial | PK |
| name | varchar(120) | اسم التصنيف |
| code | varchar(30) UNIQUE | الكود |
| is_system | boolean | تصنيف أساسي (لا يُعدَّل/يُحذف) |
| notes | varchar(255) | ملاحظات |
| is_active | boolean | الحالة |

التصنيفات النظامية المزروعة (9): إيجار، كهرباء، مياه، رواتب، نقل، صيانة، مشتريات أخرى، تشغيلية، أخرى.

### `expenses_expense` — المصاريف
| الحقل | النوع | وصف |
|---|---|---|
| id | bigserial | PK |
| branch_id | bigint FK → branches_branch | الفرع (PROTECT) |
| category_id | bigint FK → expenses_expensecategory | النوع (PROTECT) |
| date | date | اليوم |
| amount | numeric(15,2) | المبلغ |
| payment_method | varchar(10) | cash/transfer/card/other |
| description | varchar(255) | الوصف |
| notes | text | ملاحظات |

- فهارس: `(branch_id)`, `(category_id)`, `(branch_id, date)`, `(category_id, date)`

## العلاقات

```
branches_branch ──< sales_dailysale     (PROTECT, related_name="daily_sales")
branches_branch ──< expenses_expense    (PROTECT, related_name="expenses")
expenses_expensecategory ──< expenses_expense (PROTECT, related_name="expenses")
```

- `on_delete=PROTECT` على كل مفاتيح الأعمال: لا يُحذف فرع/تصنيف له سجلات مرتبطة.
- حذف الفرع محظور ويرجع رسالة عربية؛ حذف التصنيف النظامي محظور.

## التشغيل المحلي

PostgreSQL عبر Docker:

```bash
docker compose -f database/docker-compose.yml up -d
```

ثم تجهيز قاعدة Django بالهجرة والبذر:

```bash
python manage.py migrate
python manage.py seed_categories
```