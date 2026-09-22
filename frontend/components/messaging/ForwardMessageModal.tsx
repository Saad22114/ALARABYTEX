'use client';

import { useState } from 'react';
import Modal from '@/components/ui/Modal';
import { forwardMessage } from '@/services/messages';
import { useToast } from '@/components/ui/Toast';
import EmployeePickerModal from './EmployeePickerModal';
import { ChatMessage, MessagingContact } from '@/types';

interface Props {
  open: boolean;
  message: ChatMessage | null;
  me: { id: number; name: string };
  onClose: () => void;
  onForwarded: () => void;
}

export default function ForwardMessageModal({ open, message, me, onClose, onForwarded }: Props) {
  const { toast } = useToast();
  const [picking, setPicking] = useState(false);
  const [sending, setSending] = useState(false);

  if (!message) return null;

  const handleSelect = async (contact: MessagingContact) => {
    setPicking(false);
    setSending(true);
    try {
      await forwardMessage(contact.id, message.id);
      toast('success', `تمت إعادة التوجيه إلى ${contact.name}`);
      onForwarded();
      onClose();
    } catch (e: any) {
      toast('error', e?.message || 'تعذرت إعادة التوجيه');
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <Modal open={open && !picking} onClose={onClose} title="إعادة توجيه الرسالة" maxWidth="max-w-lg">
        <div className="space-y-4">
          <div className="rounded-xl border border-sand-200 bg-sand-50/60 px-4 py-3">
            <p className="text-[10px] text-neutral-400 mb-1">
              {message.sender === me.id ? 'رسالة أرسلتها' : `من ${message.sender_name}`}
            </p>
            <p className="text-sm text-neutral-700 whitespace-pre-wrap break-words">
              {message.is_deleted ? 'تم حذف رسالة' : message.body}
            </p>
          </div>
          <div className="flex items-center justify-end gap-3">
            <button
              onClick={() => setPicking(true)}
              disabled={sending}
              className="px-4 py-2 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-40"
            >
              اختر المستلم
            </button>
          </div>
        </div>
      </Modal>
      <EmployeePickerModal
        open={open && picking}
        title="إعادة توجيه إلى زميل"
        description="اختر الزميل الذي سترسل له الرسالة."
        onClose={() => setPicking(false)}
        onSelect={handleSelect}
      />
    </>
  );
}