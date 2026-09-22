'use client';

import { useEffect, useMemo, useState } from 'react';
import Modal from '@/components/ui/Modal';
import Avatar from '@/components/ui/Avatar';
import { Search } from 'lucide-react';
import { getMessageContacts } from '@/services/messages';
import { MessagingContact } from '@/types';

interface Props {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  onSelect: (contact: MessagingContact) => void;
}

export default function EmployeePickerModal({ open, title, description, onClose, onSelect }: Props) {
  const [employees, setEmployees] = useState<MessagingContact[]>([]);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState('');

  useEffect(() => {
    if (!open) return;
    setQ('');
    setLoading(true);
    getMessageContacts()
      .then((res) => setEmployees(res.employees))
      .catch(() => setEmployees([]))
      .finally(() => setLoading(false));
  }, [open]);

  const filtered = useMemo(() => {
    const term = q.trim();
    if (!term) return employees;
    return employees.filter(
      (e) => e.name.includes(term) || (e.branch_name || '').includes(term),
    );
  }, [employees, q]);

  return (
    <Modal open={open} onClose={onClose} title={title} maxWidth="max-w-lg">
      <div className="space-y-3">
        {description && <p className="text-sm text-neutral-500">{description}</p>}

        <div className="relative">
          <Search size={15} className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="ابحث بالاسم أو الفرع..."
            autoFocus
            className="w-full pr-9 pl-3 py-2 rounded-xl border border-sand-200 bg-sand-50 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
          />
        </div>

        <div className="max-h-72 overflow-y-auto divide-y divide-sand-100 rounded-xl border border-sand-200 bg-surface">
          {loading ? (
            <p className="text-sm text-neutral-400 text-center py-8">جارٍ التحميل...</p>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-neutral-400 text-center py-8">
              {q ? 'لا نتائج مطابقة' : 'لا يوجد زملاء'}
            </p>
          ) : (
            filtered.map((e) => (
              <button
                key={e.id}
                onClick={() => onSelect(e)}
                className="w-full text-right px-4 py-2.5 flex items-center gap-3 hover:bg-sand-50 transition-colors"
              >
                <Avatar name={e.name} avatar={e.avatar} size="md" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate">{e.name}</p>
                  {e.branch_name && <p className="text-xs text-neutral-400 truncate">{e.branch_name}</p>}
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </Modal>
  );
}