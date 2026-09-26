'use client';

import { useCallback, useEffect, useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Spinner from '@/components/ui/Spinner';
import { useToast } from '@/components/ui/Toast';
import { Branch } from '@/types';
import { listBranches } from '@/services/branches';
import { getPayrollDates, getPayrollEmployees } from '@/services/payroll';
import { useUrlState } from '@/lib/useUrlState';
import RunsTab from '@/components/payroll/RunsTab';
import AdvancesTab from '@/components/payroll/AdvancesTab';
import StructuresTab from '@/components/payroll/StructuresTab';
import StatementModal from '@/components/payroll/StatementModal';
import type { StructureEmployeeOption } from '@/components/payroll/SalaryStructureForm';

const TABS = [
  { key: 'runs', label: 'مسيّرات الرواتب' },
  { key: 'advances', label: 'سلف الرواتب' },
  { key: 'structures', label: 'هياكل الرواتب' },
  { key: 'statement', label: 'كشف حساب موظف' },
];

export default function PayrollPage() {
  const { toast } = useToast();
  const [tab, setTab] = useUrlState('tab', 'runs');
  const [month, setMonth] = useUrlState('month', '');
  const [branchFilter, setBranchFilter] = useUrlState('branch', '');

  const [branches, setBranches] = useState<Branch[]>([]);
  const [employees, setEmployees] = useState<StructureEmployeeOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [statementEmployee, setStatementEmployee] = useState<number | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const activeMonth = month || '';

  useEffect(() => {
    let cancelled = false;
    getPayrollDates()
      .then((d) => {
        if (!cancelled && !month) setMonth(d.month);
      })
      .catch(() => {
        /* مرجع الشهر اختياري */
      });
    return () => {
      cancelled = true;
    };
  }, [month, setMonth]);

  const loadMeta = useCallback(() => {
    if (!activeMonth) return;
    listBranches({ page_size: 100 })
      .then((res) => setBranches(res.results.filter((b) => b.is_active)))
      .catch((err) => toast('error', err.message));
    getPayrollEmployees({ month: activeMonth })
      .then((res) =>
        setEmployees(
          res.rows.map((e) => ({
            id: e.employee,
            name: e.employee_name,
            branch_name: e.branch_name,
          })),
        ),
      )
      .catch((err) => toast('error', err.message))
      .finally(() => setLoading(false));
  }, [activeMonth, toast]);

  useEffect(() => {
    loadMeta();
  }, [loadMeta, reloadKey]);

  const openStatement = (employeeId: number) => {
    setStatementEmployee(employeeId);
    setTab('statement');
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center gap-2 border-b border-sand-200 pb-2">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                tab === t.key
                  ? 'bg-brand-600 text-white'
                  : 'text-neutral-600 hover:bg-sand-100'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {loading || !activeMonth ? (
          <div className="flex justify-center py-20">
            <Spinner size={32} />
          </div>
        ) : tab === 'runs' ? (
          <RunsTab
            month={activeMonth}
            onMonthChange={setMonth}
            branches={branches}
            filterBranch={branchFilter}
            onFilterBranch={setBranchFilter}
            onStatement={openStatement}
          />
        ) : tab === 'advances' ? (
          <AdvancesTab branches={branches} employees={employees} defaultDate={activeMonth} />
        ) : tab === 'structures' ? (
          <StructuresTab
            branches={branches}
            month={activeMonth}
            onSaved={() => setReloadKey((k) => k + 1)}
          />
        ) : (
          <Card>
            <StatementModal
              employees={employees}
              initialEmployeeId={statementEmployee}
              open
              onClose={() => setTab('runs')}
            />
          </Card>
        )}
      </div>
    </AppShell>
  );
}
