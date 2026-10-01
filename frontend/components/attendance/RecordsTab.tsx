'use client';

import { useCallback, useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Spinner from '@/components/ui/Spinner';
import Pagination from '@/components/ui/Pagination';
import DateRangeToolbar from '@/components/ui/DateRangeToolbar';
import SearchInput from '@/components/ui/SearchInput';
import Select from '@/components/ui/Select';
import Button from '@/components/ui/Button';
import ExportButton from '@/components/ui/ExportButton';
import { useToast } from '@/components/ui/Toast';
import { Search, Plus } from 'lucide-react';
import { createAttendance, listAttendance } from '@/services/attendance';
import { listEmployees } from '@/services/employees';
import { todayISO } from '@/lib/date';
import { STATUS_LABEL } from '@/lib/attendance';
import type { AttendanceRecord, Employee, Paginated } from '@/types';
import AttendanceTable from './AttendanceTable';
import RecordEditor from './RecordEditor';

const PAGE_SIZE = 25;

const STATUS_OPTIONS = Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }));

/**
 * سجلات الحضور عبر المدى: تصفية بالأسرة والحالة، وصفحات.
 *
 * البحثُ هنا على **الخادم** لا في الصفوف المعروضة: البحث في الصفحة
 * الجارية يُظهر «لا نتائج» والقائمةُ ممتلئة تحتها، وهو أسوأ من بحثٍ
 * بطيء لأنه يوهم القارئ أن لا حضورَ في تلك السنة.
 */
interface RecordsTabProps {
  from: string;
  to: string;
  onRangeChange: (from: string, to: string) => void;
}

export default function RecordsTab({ from, to, onRangeChange }: RecordsTabProps) {
  const { toast } = useToast();
  const [data, setData] = useState<Paginated<AttendanceRecord> | null>(null);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [status, setStatus] = useState('');
  const [employee, setEmployee] = useState('');
  const [editing, setEditing] = useState<AttendanceRecord | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    listEmployees({ page_size: 200, is_active: 'true' })
      .then((res) => setEmployees(res.results))
      .catch(() => {
        /* الفلتر بالموظف ثانوي: إخفاقه لا يُسقط السجلات */
      });
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    listAttendance({
      page,
      page_size: PAGE_SIZE,
      start: from,
      end: to,
      status: status || undefined,
      employee: employee || undefined,
      search: appliedSearch || undefined,
    })
      .then(setData)
      .catch((err) => toast('error', err.message))
      .finally(() => setLoading(false));
  }, [page, from, to, status, employee, appliedSearch, toast]);

  useEffect(() => {
    load();
  }, [load, reloadKey]);

  const reload = () => setReloadKey((k) => k + 1);

  const submitSearch = () => {
    setAppliedSearch(search.trim());
    setPage(1);
  };

  const addManual = async () => {
    // لا نافذة إنشاء: سطرٌ يدويّ يحتاج يوماً وموظفاً وساعتَي دخولٍ
    // وخروج. إضافته من الشريط يعني «اليوم»، وهو تقديرٌ مكلف: خطأُ
    // يومٍ واحد في السجل يُشطب من راتب موظف.
    if (!employee) {
      toast('info', 'اختر الموظف أولاً ثم أضف سجله لليوم');
      return;
    }
    try {
      await createAttendance({ employee: Number(employee), date: todayISO() });
      toast('success', 'أُضيف سجلّ اليوم، أكمل وقتيه بالضغط على السطر');
      reload();
    } catch (err: any) {
      toast('error', err.message);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <DateRangeToolbar from={from} to={to} onChange={onRangeChange} />
        <div className="h-4" />
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[220px]">
            <span className="block text-xs font-medium text-neutral-600 mb-1">بحث</span>
            <div className="flex gap-2">
              <SearchInput value={search} onChange={setSearch} placeholder="اسم الموظف أو ملاحظة..." />
              <Button variant="secondary" onClick={submitSearch}>
                <Search size={16} />
                بحث
              </Button>
            </div>
          </div>
          <Select
            label="الحالة"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
            options={[{ value: '', label: 'كل الحالات' }, ...STATUS_OPTIONS]}
          />
          <Select
            label="الموظف"
            value={employee}
            onChange={(e) => {
              setEmployee(e.target.value);
              setPage(1);
            }}
            options={[{ value: '', label: 'كل الموظفين' }, ...employees.map((e) => ({ value: e.id, label: e.name }))]}
          />
          <Button variant="subtle" onClick={addManual}>
            <Plus size={16} />
            سجلّ اليوم للموظف المختار
          </Button>
          {/*
            التصدير يحمل فلاترَ الجدول كلَّها، البحثَ نصّياً كان: لولا
            ذلك لأخرج الملفُ كلَّ المدى بينما الجدولُ يعرض صفحةً واحدة
            مفلترة، فيقول المستخدم «التصديرُ معطوب» وما عطب إلا أنه
            صدّق الملفَ لا الشاشة.
          */}
          <ExportButton
            path="/attendance/records/export/"
            params={{
              start: from,
              end: to,
              status: status || undefined,
              employee: employee || undefined,
              search: appliedSearch || undefined,
            }}
            filename="الحضور-والانصراف.xlsx"
            label="تصدير المدى"
            variant="secondary"
          />
        </div>
      </Card>

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner size={28} />
        </div>
      ) : (
        <>
          <AttendanceTable
            rows={data?.results || []}
            policy={null}
            showDate
            onEdit={setEditing}
            emptyTitle="لا سجلات في هذا المدى"
            emptyDescription="وسّع المدى أو غيّر الفلاتر — السجلات تُبنى من الدخول والخروج لا من إدخالٍ يدوي"
          />
          {data && data.results.length > 0 && (
            <Pagination
              page={page}
              totalPages={Math.max(1, Math.ceil(data.count / PAGE_SIZE))}
              onChange={setPage}
              count={data.count}
              pageSize={PAGE_SIZE}
            />
          )}
        </>
      )}

      <RecordEditor record={editing} onClose={() => setEditing(null)} onSaved={reload} />
    </div>
  );
}