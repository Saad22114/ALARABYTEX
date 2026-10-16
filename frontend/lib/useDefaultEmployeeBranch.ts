'use client';

import { Dispatch, SetStateAction, useEffect, useRef } from 'react';
import { useAuth } from '@/components/providers/AuthProvider';

/** Starts branch filters at the employee's primary branch, while the API remains
 * responsible for restricting every request to branches assigned to that employee. */
export function useDefaultEmployeeBranch(
  setBranch: Dispatch<SetStateAction<string>> | ((value: string) => void),
  urlKey: string | null = 'branch',
) {
  const { session } = useAuth();
  const employee = session?.employee;
  const initializedFor = useRef<number | null>(null);

  useEffect(() => {
    if (!employee || initializedFor.current === employee.id) return;
    initializedFor.current = employee.id;
    if (employee.role === 'admin' || employee.role === 'supervisor' || !employee.branch) return;
    if (urlKey && typeof window !== 'undefined' && new URLSearchParams(window.location.search).has(urlKey)) return;
    setBranch(String(employee.branch));
  }, [employee, setBranch, urlKey]);
}
