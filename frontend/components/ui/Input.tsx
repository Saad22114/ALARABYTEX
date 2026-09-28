'use client';

import React, { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

/**
 * لوحات المفاتيح العربية على أندرويد وiOS تُدخل أرقاماً هندية شرقية (٠١٢٣)
 * أو فارسية (۰۱۲۳) وفاصلة عشرية عربية (٫). تمرّ من مرشّح «ليس حرفاً»
 * فتحفظ خطأً في قاعدة البيانات. نحوّلها إلى ما يفهمه الخادم.
 */
const NON_LATIN_DIGITS = '٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹';
const NON_LATIN_SEP = '٫٬،';

/**
 * يُبقي الأرقام فقط، وفاصلة عشرية واحدة كحد أقصى، ويسقط كل ما عداها:
 * الحروف، الرموز، إشارة السالب، وعلامة الأسّ (e) التي يقبلها type="number".
 *
 * تُستخدم عند كل تغيير — كتابةً ولصقاً وسحباً — لأنّ الحجب في onKeyDown
 * وحده لا يوقف اللصق ولا الأرقام العربية.
 */
export function sanitizeNumeric(raw: string, allowDecimal: boolean): string {
  let out = '';
  let dotSeen = false;
  for (const ch of raw) {
    const digit = NON_LATIN_DIGITS.indexOf(ch);
    if (digit >= 0) {
      out += String(digit % 10);
    } else if (ch >= '0' && ch <= '9') {
      out += ch;
    } else if (ch === '.' || ch === ',' || NON_LATIN_SEP.includes(ch)) {
      if (allowDecimal && !dotSeen) {
        dotSeen = true;
        out += '.';
      }
    }
  }
  return out;
}

/** يضبط قيمة العنصر فعلياً قبل تسليم الحدث للصفحة، حتى لا يمحوها الرسم التالي. */
function applyValue(e: React.SyntheticEvent<HTMLInputElement>, next: string) {
  (e.currentTarget as HTMLInputElement).value = next;
}

/** يعيد فرض min/max عند الخروج، كما كان المتصفح يفعل مع type="number". */
function clampToRange(raw: string, min: number | undefined, max: number | undefined): string {
  if (raw === '' || raw === '.') return raw;
  const n = Number(raw);
  if (!Number.isFinite(n)) return raw;
  let out = n;
  if (min !== undefined && out < min) out = min;
  if (max !== undefined && out > max) out = max;
  return out === n ? raw : String(out);
}

interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  error?: string;
  /**
   * عند التركيز: قيمة «0» تفرغ تلقائياً، وأي قيمة أخرى تُحدَّد بالكامل
   * ليستبدلها أول رقم تكتبه — بدون الحاجة لحذف الرقم القديم.
   */
  selectOnFocus?: boolean;
  type?: React.HTMLInputTypeAttribute;
  /**
   * شكل الخانة الرقمية، ويُطبَّق فقط على type="number"؛ الخانات الحرة تبقى كما هي:
   * - 'decimal' (الافتراضي): أرقام + فاصلة عشرية واحدة ⇒ لوحة أرقام بفاصلة
   * - 'int': أرقام فقط ⇒ لوحة أرقام بلا فاصلة (عدد اللفات، الساعات، الوزن)
   */
  numeric?: 'decimal' | 'int';
}

export default function Input({
  label,
  error,
  className = '',
  type,
  inputMode,
  pattern,
  min,
  max,
  step: _step,
  onKeyDown,
  onPaste,
  required,
  selectOnFocus,
  numeric = 'decimal',
  onFocus,
  onBlur,
  onChange,
  value,
  ...props
}: InputProps) {
  const isNumber = type === 'number';
  const isPassword = type === 'password';
  const isInt = isNumber && numeric === 'int';
  const [showPw, setShowPw] = useState(false);
  const [draft, setDraft] = useState<string | null>(null);
  const effectiveType = isPassword ? (showPw ? 'text' : 'password') : type;

  // type="tel" مع inputMode يفتح لوحة أرقام على أندرويد وiOS معاً، بينما
  // type="number" وحده يفتح لوحة فيها e و +/- و * / على iOS، ويقبل الأرقام العربية.
  const domType = isNumber ? 'tel' : effectiveType;
  const minNum = typeof min === 'number' ? min : undefined;
  const maxNum = typeof max === 'number' ? max : undefined;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (isNumber && e.key.length === 1 && !/[0-9]/.test(e.key)) {
      e.preventDefault();
    }
    onKeyDown?.(e);
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    if (isNumber) {
      e.preventDefault();
      const el = e.currentTarget;
      const start = el.selectionStart ?? el.value.length;
      const end = el.selectionEnd ?? el.value.length;
      const clean = sanitizeNumeric(e.clipboardData.getData('text'), !isInt);
      const next = el.value.slice(0, start) + clean + el.value.slice(end);
      el.value = next;
      el.setSelectionRange(next.length, next.length);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }
    onPaste?.(e);
  };

  const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    if (selectOnFocus) {
      const v = value !== undefined && value !== null ? String(value) : '';
      if (v === '0' || v === '') {
        setDraft('');
      } else {
        setDraft(v);
        e.target.select();
      }
    }
    onFocus?.(e);
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    setDraft(null);
    if (isNumber) {
      const raw = e.target.value;
      const clamped = clampToRange(raw, minNum, maxNum);
      if (clamped !== raw) {
        applyValue(e, clamped);
        onChange?.({ ...e, target: { ...e.target, value: clamped } } as unknown as React.ChangeEvent<HTMLInputElement>);
      }
    }
    onBlur?.(e);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (isNumber) {
      const clean = sanitizeNumeric(e.target.value, !isInt);
      if (clean !== e.target.value) applyValue(e, clean);
    }
    setDraft(null);
    onChange?.(e);
  };

  const shownValue = draft !== null ? draft : value;

  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-sm font-medium text-neutral-700">
          {label}
          {required && <span className="text-red-500"> *</span>}
        </label>
      )}
      <div className="relative">
        <input
          dir="rtl"
          type={domType}
          required={required}
          value={shownValue}
          inputMode={isNumber ? (inputMode ?? (isInt ? 'numeric' : 'decimal')) : inputMode}
          pattern={isNumber ? (pattern ?? (isInt ? '[0-9]*' : '[0-9]*([.,][0-9])*')) : pattern}
          onKeyDown={isNumber ? handleKeyDown : onKeyDown}
          onPaste={isNumber ? handlePaste : onPaste}
          onFocus={handleFocus}
          onBlur={handleBlur}
          onChange={handleChange}
          className={`
            w-full rounded-xl border px-4 py-2.5 text-sm
            bg-surface text-neutral-800 placeholder:text-neutral-400
            border-sand-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-100
            outline-none transition-colors duration-150
            ${isPassword ? 'pl-11' : ''}
            ${error ? 'border-red-400 focus:border-red-500 focus:ring-red-100' : ''}
            ${className}
          `}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPw((v) => !v)}
            title={showPw ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور'}
            aria-label={showPw ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور'}
            tabIndex={-1}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 p-1 rounded-lg text-neutral-400 hover:text-brand-600 transition-colors"
          >
            {showPw ? <EyeOff size={17} /> : <Eye size={17} />}
          </button>
        )}
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
