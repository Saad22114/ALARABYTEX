export interface CustomerContact {
  phone: string;
  name: string;
  lastUsed: number;
}

const CONTACTS_KEY = 'qomash_customer_contacts';
const LAST_KEY = 'qomash_last_customer';

function readRaw(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeRaw(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // ignore quota / privacy errors
  }
}

export function loadContacts(): CustomerContact[] {
  const raw = readRaw(CONTACTS_KEY);
  if (!raw) return [];
  try {
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export function saveContact(phone: string, name = ''): CustomerContact | null {
  const p = phone.replace(/[\s\-]/g, '');
  if (!p) return null;
  const contact: CustomerContact = { phone: p, name: name.trim(), lastUsed: Date.now() };
  const list = loadContacts().filter((c) => c.phone !== p);
  list.unshift(contact);
  writeRaw(CONTACTS_KEY, JSON.stringify(list.slice(0, 200)));
  setLastCustomer(contact);
  return contact;
}

export function setLastCustomer(contact: CustomerContact) {
  if (!contact || !contact.phone) return;
  writeRaw(LAST_KEY, JSON.stringify({ ...contact, lastUsed: Date.now() }));
}

export function getLastCustomer(): CustomerContact | null {
  const raw = readRaw(LAST_KEY);
  if (!raw) return null;
  try {
    const c = JSON.parse(raw);
    return c && c.phone ? c : null;
  } catch {
    return null;
  }
}

export function findContact(phone: string): CustomerContact | null {
  const p = phone.replace(/[\s\-]/g, '');
  if (!p) return null;
  return loadContacts().find((c) => c.phone === p) || null;
}

export function searchContacts(query: string, limit = 6): CustomerContact[] {
  const q = (query || '').trim().toLowerCase();
  const list = loadContacts().sort((a, b) => b.lastUsed - a.lastUsed);
  if (!q) return list.slice(0, limit);
  return list
    .filter((c) => c.phone.replace(/[\s\-]/g, '').includes(q) || c.name.toLowerCase().includes(q))
    .slice(0, limit);
}

export function normalizePhone(phone: string): string {
  return (phone || '').replace(/[\s\-]/g, '');
}