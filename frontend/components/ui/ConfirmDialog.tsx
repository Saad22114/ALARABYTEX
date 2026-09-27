'use client';

import React from 'react';
import Modal from './Modal';
import Button from './Button';

interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title?: string;
  message?: React.ReactNode;
  loading?: boolean;
  confirmLabel?: string;
  children?: React.ReactNode;
}

export default function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title = 'تأكيد العملية',
  message = 'هل أنت متأكد من تنفيذ هذا الإجراء؟ قد لا يمكن التراجع عنه.',
  loading = false,
  confirmLabel = 'تأكيد',
  children,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button variant="danger" onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
          <Button variant="secondary" onClick={onClose}>
            إلغاء
          </Button>
        </>
      }
    >
      <div className="text-neutral-600 text-sm leading-relaxed">{message}</div>
      {children}
    </Modal>
  );
}
