import { Customer } from '@/types';
import { createCustomer, lookupCustomer } from '@/services/customers';

export async function ensureCustomer(name: string, phone: string, branch?: number | null): Promise<Customer | null> {
  const p = (phone || '').trim();
  const n = (name || '').trim();
  if (!p) return null;
  try {
    const lookup = await lookupCustomer(p);
    if (lookup.found && lookup.customer) return lookup.customer;
  } catch {
    return null;
  }
  if (!n) return null;
  try {
    return await createCustomer({ name: n, phone: p, branch: branch ?? null });
  } catch {
    return null;
  }
}