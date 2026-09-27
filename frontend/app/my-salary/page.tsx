'use client';

import { useEffect, useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Spinner from '@/components/ui/Spinner';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import EmptyState from '@/components/ui/EmptyState';
import { BadgeDollarSign, Wallet, Clock3, Landmark } from 'lucide-react';
import { MyPayrollResult } from '@/types';
import { getMyPayroll } from '@/services/payroll';
import { formatCurrency, formatDate } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';

export default function MySalaryPage() {
  const { toast } = useToast();
  const [data, setData] = useState<MyPayrollResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getMyPayroll()
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [toast]);

  const st = data?.structure;
  const activePayslips = data?.payslips.filter((p) => p.run_status !== 'CANCELLED') || [];

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Wallet size={22} />
          </div>
          <div>
            <h1 className="text-xl font-bold">راتبي</h1>
            <p className="text-sm text-neutral-500">كشف خاص بك — يظهر لك وحدك</p>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-16"><Spinner size={36} /></div>
        ) : !data ? (
          <EmptyState title="تعذر التحميل" description="لم نتمكن من جلب بيانات راتبك" />
        ) : (
          <>
            {/* بطاقات الملخص */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <Card className="!p-4">
                <div className="text-xs text-neutral-500 mb-1">إجمالي الراتب (الصافي)</div>
                <div className="text-xl font-bold tabular-nums text-brand-700">{formatCurrency(data.summary.net_total)}</div>
                <div className="text-xs text-neutral-400 mt-1">على {data.summary.payslip_count} قسيمة</div>
              </Card>
              <Card className="!p-4">
                <div className="text-xs text-neutral-500 mb-1">المدفوع فعلياً</div>
                <div className="text-xl font-bold tabular-nums text-emerald-700">{formatCurrency(data.summary.paid_net)}</div>
              </Card>
              <Card className="!p-4">
                <div className="text-xs text-neutral-500 mb-1">المستحق غير المدفوع</div>
                <div className="text-xl font-bold tabular-nums text-amber-600">{formatCurrency(data.summary.net_total - data.summary.paid_net)}</div>
              </Card>
              <Card className="!p-4">
                <div className="text-xs text-neutral-500 mb-1">سلف قائمة (غير مسددة)</div>
                <div className="text-xl font-bold tabular-nums text-red-600">{formatCurrency(data.summary.outstanding_advances)}</div>
              </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* بيانات الموظف والهيكل */}
              <Card title="بياناتي وهيكل راتبي">
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-100 text-xl font-bold text-brand-700">
                      {data.employee.avatar_image ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={data.employee.avatar_image} alt={data.employee.name} className="h-full w-full rounded-full object-cover" />
                      ) : data.employee.avatar ? (
                        <span className="text-2xl" aria-hidden>{data.employee.avatar}</span>
                      ) : (
                        data.employee.name.charAt(0)
                      )}
                    </div>
                    <div>
                      <div className="font-semibold text-lg">{data.employee.name}</div>
                      <div className="text-sm text-neutral-500">
                        {[data.employee.position, data.employee.department].filter(Boolean).join(' — ') || 'موظف'}
                      </div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="rounded-lg bg-sand-50 dark:bg-neutral-900 p-3">
                      <div className="text-neutral-500 text-xs">الفرع</div>
                      <div className="font-medium">{data.employee.branch_name || '—'}</div>
                    </div>
                    <div className="rounded-lg bg-sand-50 dark:bg-neutral-900 p-3">
                      <div className="text-neutral-500 text-xs">تاريخ التوظيف</div>
                      <div className="font-medium">{data.employee.hire_date ? formatDate(data.employee.hire_date) : '—'}</div>
                    </div>
                  </div>

                  <div className="border-t border-sand-200 dark:border-neutral-800 pt-3">
                    <div className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                      <BadgeDollarSign size={16} className="text-brand-600" />
                      هيكل الراتب الحالي
                    </div>
                    {st?.has_structure ? (
                      <div className="grid grid-cols-2 lg:grid-cols-3 gap-2 text-sm">
                        <div className="rounded-lg bg-sand-50 dark:bg-neutral-900 p-3">
                          <div className="text-neutral-500 text-xs">الراتب الأساسي</div>
                          <div className="font-semibold tabular-nums">{formatCurrency(st.base_salary)}</div>
                        </div>
                        <div className="rounded-lg bg-sand-50 dark:bg-neutral-900 p-3">
                          <div className="text-neutral-500 text-xs">بدل سكن</div>
                          <div className="font-semibold tabular-nums">{formatCurrency(st.housing_allowance)}</div>
                        </div>
                        <div className="rounded-lg bg-sand-50 dark:bg-neutral-900 p-3">
                          <div className="text-neutral-500 text-xs">بدل نقل</div>
                          <div className="font-semibold tabular-nums">{formatCurrency(st.transport_allowance)}</div>
                        </div>
                        <div className="rounded-lg bg-sand-50 dark:bg-neutral-900 p-3">
                          <div className="text-neutral-500 text-xs">بدلات أخرى</div>
                          <div className="font-semibold tabular-nums">{formatCurrency(st.other_allowance)}</div>
                        </div>
                        <div className="rounded-lg bg-sand-50 dark:bg-neutral-900 p-3">
                          <div className="text-neutral-500 text-xs">أيام العمل</div>
                          <div className="font-semibold tabular-nums">{st.working_days}</div>
                        </div>
                        <div className="rounded-lg bg-sand-50 dark:bg-neutral-900 p-3">
                          <div className="text-neutral-500 text-xs">اليومية</div>
                          <div className="font-semibold tabular-nums">{formatCurrency(st.daily_rate)}</div>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-neutral-500">
                        لا يوجد هيكل راتب مُحدّد — يُحتسب راتبك من الراتب الأساسي المسجل في بياناتك
                        {data.structure.base_salary > 0 ? ` (${formatCurrency(data.structure.base_salary)})` : ''}.
                      </p>
                    )}
                  </div>
                </div>
              </Card>

              {/* السلف */}
              <Card title="سلف الرواتب">
                {data.advances.length === 0 ? (
                  <EmptyState title="لا توجد سلف" description="لم تُسجَّل عليك أي سلفة" />
                ) : (
                  <div className="space-y-2 max-h-[320px] overflow-y-auto">
                    {data.advances.map((a) => (
                      <div key={a.id} className="flex items-center justify-between rounded-lg bg-sand-50 dark:bg-neutral-900 p-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{formatCurrency(a.amount)}</span>
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${a.status === 'APPROVED' ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300' : a.status === 'PENDING' ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300' : 'bg-neutral-100 text-neutral-500 dark:bg-neutral-800'}`}>
                              {a.status_label}
                            </span>
                          </div>
                          <div className="text-xs text-neutral-500 mt-0.5">
                            {formatDate(a.date)}{a.reason ? ` — ${a.reason}` : ''}
                          </div>
                        </div>
                        <div className="text-left">
                          <div className="text-xs text-neutral-500">المتبقي</div>
                          <div className={`font-semibold tabular-nums ${a.is_settled ? 'text-emerald-600' : 'text-red-600'}`}>
                            {formatCurrency(a.remaining_amount)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>

            {/* القسائم */}
            <Card title="قسائم رواتبي">
              {activePayslips.length === 0 ? (
                <EmptyState title="لا توجد قسائم بعد" description="لم يُصدَر لك أي قسيمة راتب" />
              ) : (
                <Table>
                  <thead>
                    <tr>
                      <Th>الشهر</Th>
                      <Th>الأساسي</Th>
                      <Th>البدلات</Th>
                      <Th>الخصومات</Th>
                      <Th>الصافي</Th>
                      <Th>الحالة</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {activePayslips.map((p) => (
                      <Tr key={p.id}>
                        <Td className="font-medium">{p.month ? formatDate(p.month) : '—'}</Td>
                        <Td className="tabular-nums">{formatCurrency(p.base_salary)}</Td>
                        <Td className="tabular-nums text-emerald-600">{formatCurrency(p.total_allowances)}</Td>
                        <Td className="tabular-nums text-red-600">{formatCurrency(p.total_deductions)}</Td>
                        <Td className="tabular-nums font-semibold">{formatCurrency(p.net_pay)}</Td>
                        <Td>
                          {p.is_paid ? (
                            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 px-2 py-0.5 text-xs font-medium">
                              <Landmark size={11} /> مدفوعة
                            </span>
                          ) : p.run_status === 'DRAFT' ? (
                            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300 px-2 py-0.5 text-xs font-medium">
                              <Clock3 size={11} /> مسودة
                            </span>
                          ) : (
                            <span className="text-xs text-neutral-500">{p.run_status === 'APPROVED' ? 'معتمدة' : p.run_status}</span>
                          )}
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card>
          </>
        )}
      </div>
    </AppShell>
  );
}