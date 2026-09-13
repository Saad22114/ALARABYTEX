'use client';

import React, { useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: string;
}

export default function Modal({ open, onClose, title, children, footer, maxWidth = 'max-w-lg' }: ModalProps) {
  const handleEscape = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [open, handleEscape]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div
        className={`relative bg-surface rounded-2xl shadow-xl w-full ${maxWidth} animate-scale-in`}
      >
        {title && (
          <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-sand-100">
            <h3 className="text-lg font-semibold text-neutral-800">{title}</h3>
            <button
              onClick={onClose}
              className="p-1 rounded-lg hover:bg-sand-100 transition-colors"
            >
              <X size={20} className="text-neutral-500" />
            </button>
          </div>
        )}
        <div className="p-4 sm:p-6 max-h-[70vh] overflow-y-auto">{children}</div>
        {footer && (
          <div className="flex items-center justify-start gap-3 px-4 sm:px-6 py-4 border-t border-sand-100">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
