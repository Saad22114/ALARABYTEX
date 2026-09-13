import React from 'react';

interface TableWrapperProps {
  children: React.ReactNode;
  className?: string;
}

export default function Table({ children, className = '' }: TableWrapperProps) {
  return (
    <div className={`overflow-x-auto rounded-xl border border-sand-200 ${className}`}>
      <table className="w-full text-sm">{children}</table>
    </div>
  );
}

export function Th({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={`px-4 py-3 text-right text-xs font-semibold text-neutral-500 bg-sand-100 border-b border-sand-200 ${className}`}>
      {children}
    </th>
  );
}

export function Td({ children, className = '', ...props }: { children?: React.ReactNode; className?: string } & React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={`px-4 py-3 text-neutral-700 border-b border-sand-100 ${className}`} {...props}>
      {children}
    </td>
  );
}

export function Tr({ children, className = '', ...props }: { children: React.ReactNode; className?: string } & React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className={`hover:bg-sand-50 transition-colors duration-100 ${className}`} {...props}>
      {children}
    </tr>
  );
}
