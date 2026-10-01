'use client';

import { useCallback, useEffect, useState } from 'react';
import { Plus, Trash2, Tags } from 'lucide-react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import { useToast } from '@/components/ui/Toast';
import { ExpenseCategory } from '@/types';
import { listExpenseCategories, createExpenseCategory, deleteExpenseCategory } from '@/services/expenses';

/**
 * لوحة تصنيفات المصاريف.
 *
 * كانت في صفحة «الثيمات» مع الإعدادات، وكل ما فيها ليس من الثيمات: لا لون
 * ولا خط ولا طباعة. ونقلها إلى قسم المصاريف يضعها بجهة تُنشئ منها،
 * فمن يحرّر مصروفاً يحتاج اسم تصنيفه تحت يده.
 */
export default function CategoriesPanel() {
  const { toast } = useToast();
  const [categories, setCategories] = useState<ExpenseCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<ExpenseCategory | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const fetchCategories = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    listExpenseCategories({ page_size: 200 })
      .then((res) => { if (!cancelled) setCategories(res.results); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [toast]);

  useEffect(() => fetchCategories(), [fetchCategories]);

  const handleAdd = async () => {
    if (!name.trim()) {
      toast('error', 'اسم التصنيف مطلوب');
      return;
    }
    setSaving(true);
    try {
      await createExpenseCategory({ name, code });
      toast('success', 'تمت إضافة التصنيف بنجاح');
      setName('');
      setCode('');
      setAddOpen(false);
      fetchCategories();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteExpenseCategory(deleting.id);
      toast('success', 'تم حذف التصنيف بنجاح');
      setDeleting(null);
      fetchCategories();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <>
      <Card
        title="تصنيفات المصاريف"
        action={
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <Plus size={16} />
            إضافة تصنيف
          </Button>
        }
      >
        {loading ? (
          <div className="flex justify-center py-8"><Spinner size={28} /></div>
        ) : categories.length === 0 ? (
          <EmptyState
            title="لا توجد تصنيفات"
            description="أضف تصنيفاً لتستطيع تسجيل مصروفاتك"
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>الاسم</Th>
                <Th>الكود</Th>
                <Th>النوع</Th>
                <Th>عدد المصاريف</Th>
                <Th>إجراءات</Th>
              </tr>
            </thead>
            <tbody>
              {categories.map((c) => (
                <Tr key={c.id}>
                  <Td className="font-medium">{c.name}</Td>
                  <Td>
                    <span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded">
                      {c.code || '-'}
                    </span>
                  </Td>
                  <Td>
                    <Badge variant={c.is_system ? 'neutral' : 'success'}>
                      {c.is_system ? 'نظامي' : 'مخصص'}
                    </Badge>
                  </Td>
                  <Td className="tabular-nums">{c.expense_count}</Td>
                  <Td>
                    {c.is_system ? (
                      <span className="text-xs text-neutral-400">لا يُحذف</span>
                    ) : (
                      <button
                        onClick={() => setDeleting(c)}
                        className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 transition-colors"
                        title="حذف التصنيف"
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="إضافة تصنيف جديد">
        <div className="space-y-4">
          <Input
            label="اسم التصنيف"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="مثال: كهرباء"
          />
          <Input
            label="الكود (اختياري)"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="مثال: CAT-001"
          />
          <div className="flex justify-start gap-3 pt-2">
            <Button onClick={handleAdd} loading={saving}>إضافة</Button>
            <Button variant="secondary" onClick={() => setAddOpen(false)}>إلغاء</Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={handleDelete}
        loading={deleteLoading}
        message={`هل أنت متأكد من حذف تصنيف "${deleting?.name}"؟`}
      />
    </>
  );
}