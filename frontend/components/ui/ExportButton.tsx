'use client';

import React, { useState } from 'react';
import { Download } from 'lucide-react';
import Button from './Button';
import Spinner from './Spinner';
import { API_URL, downloadBlob } from '@/services/api';
import { useToast } from './Toast';

interface ExportButtonProps {
  /** المسار بعد ``API_URL``، مثل ``/reports/profit-loss/``؛ و ``undefined``
   *  يعني أن التبويب لا تصدير له، فيُعطَّل الزر ويُعرف السبب. */
  path?: string;
  /** معاملات التصفية للتصدير؛ تُضاف كما هي. */
  params?: Record<string, string | number | boolean | undefined | null>;
  /** اسم احتياطي يُستعمل إن غاب اسم الملف من ترويسة الخادم. */
  filename: string;
  label?: string;
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'subtle';
  size?: 'sm' | 'md';
  className?: string;
  title?: string;
}

/**
 * زر تصدير Excel يمرّ عبر ``downloadBlob`` لا عبر رابط مباشر.
 *
 * لماذا لا يكفي ``<a href="...">``: مصادقة هذا النظام رمز في ترويسة
 * ``Authorization``، والرابط لا يحمل ترويسات — المتصفح يفتحه كطلب جديد بلا
 * رمز، فيردّ الخادم «لم يتم تزويد بيانات الدخول» ويظهر للمستخدم JSON عوض
 * الملف. هذا ما كان يحدث في **كل** أزرار التصدير المبنية كرابط.
 *
 * ولأن ``downloadBlob`` يقرأ اسم الملف من ``Content-Disposition`` ويؤجّل
 * إبطال رابطه، فالملف ينزل باسم يحمل تاريخه ويُفتح كاملاً.
 */
export default function ExportButton({
  path,
  params = {},
  filename,
  label = 'تصدير Excel',
  variant = 'secondary',
  size = 'sm',
  className = '',
  title,
}: ExportButtonProps) {
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const hint = title || (!path ? 'هذا التبويب لا يُصدَّر إلى Excel' : undefined);

  const onClick = async () => {
    if (!path) return;
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '' && value !== false) {
        search.append(key, String(value));
      }
    });
    search.append('export', 'xlsx');
    setBusy(true);
    try {
      await downloadBlob(`${API_URL}${path}?${search.toString()}`, filename);
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'تعذّر تصدير الملف');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button
      variant={variant}
      size={size}
      className={className}
      onClick={onClick}
      disabled={!path}
      title={hint}
    >
      {busy ? <Spinner size={14} /> : <Download size={14} />}
      {label}
    </Button>
  );
}