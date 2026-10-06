'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { ArrowLeft, ChevronDown, ChevronUp, Copy, CornerUpLeft, Forward, Info, Pencil, Pin, Plus, Search, Send, Trash2, X } from 'lucide-react';
import { useAuth } from '@/components/providers/AuthProvider';
import { getConversations, getMessageThread, sendMessage, editMessage, deleteMessage, searchMessages, EDIT_WINDOW_MINUTES } from '@/services/messages';
import { ChatMessage, ChatContactSummary, MessagingContact, MessageSearchGroup } from '@/types';
import { formatLastSeen } from '@/lib/format';
import Badge from '@/components/ui/Badge';
import Avatar from '@/components/ui/Avatar';
import ImagePreview from '@/components/ui/ImagePreview';
import EmployeeInfoModal from '@/components/employees/EmployeeInfoModal';
import { useToast } from '@/components/ui/Toast';
import { useUrlState } from '@/lib/useUrlState';
import EmployeePickerModal from '@/components/messaging/EmployeePickerModal';
import ForwardMessageModal from '@/components/messaging/ForwardMessageModal';

function withinWindow(msg: ChatMessage): boolean {
  const diff = Date.now() - new Date(msg.created_at).getTime();
  return diff <= EDIT_WINDOW_MINUTES * 60 * 1000;
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function Highlight({ text, query }: { text: string; query: string }) {
  const q = query.trim();
  if (!q) return <>{text}</>;
  const parts = text.split(new RegExp(`(${escapeRegExp(q)})`, 'ig'));
  return (
    <>
      {parts.map((p, i) =>
        p.toLowerCase() === q.toLowerCase() ? (
          <mark key={i} className="bg-amber-200 text-neutral-900 rounded px-0.5">
            {p}
          </mark>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

const dayStart = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

function dayLabel(dateStr: string, now: Date): string {
  const d = new Date(dateStr);
  const diff = Math.round((dayStart(now) - dayStart(d)) / 86400000);
  if (diff === 0) return 'اليوم';
  if (diff === 1) return 'أمس';
  return d.toLocaleDateString('ar-EG', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
}

function PresenceAvatar({
  name,
  avatar,
  avatarImage,
  online,
  size = 'md',
  onClick,
  title,
}: {
  name: string;
  avatar?: string | null;
  avatarImage?: string | null;
  online?: boolean;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  onClick?: () => void;
  title?: string;
}) {
  const [previewOpen, setPreviewOpen] = useState(false);
  const dotSize = size === 'lg' ? 'w-3 h-3' : size === 'xs' ? 'w-2 h-2' : 'w-2.5 h-2.5';
  return (
    <span className="relative inline-flex shrink-0">
      <Avatar
        name={name}
        avatar={avatar}
        avatarImage={avatarImage}
        size={size}
        onClick={avatarImage ? () => setPreviewOpen(true) : onClick}
        title={avatarImage ? 'تكبير الصورة الشخصية' : title}
      />
      <ImagePreview src={previewOpen ? avatarImage || null : null} alt={`الصورة الشخصية لـ ${name}`} onClose={() => setPreviewOpen(false)} />
      {avatarImage && onClick && (
        <button
          type="button"
          aria-label={`معلومات ${name}`}
          title={`معلومات ${name}`}
          onClick={(event) => { event.stopPropagation(); onClick(); }}
          className="absolute -top-1 -start-1 z-10 flex h-4 w-4 items-center justify-center rounded-full bg-white text-brand-700 shadow ring-1 ring-sand-200"
        >
          <Info size={11} />
        </button>
      )}
      {online && (
        <span className={`absolute bottom-0 end-0 ${dotSize} rounded-full bg-emerald-500 ring-2 ring-surface`} title="متصل الآن" />
      )}
    </span>
  );
}

/**
 * سطر آخر ظهور تحت اسم الشخص.
 *
 * الطلب: «اكتب آخر ظهور الوقت، وإذا أكثر من يوم اكتب اليوم والتاريخ». فالمتّصل
 * الآن لا يحتاج سطراً — نقطته خضراء قدّامه — والغائب يحتاج أن يُقال **متى**
 * غاب، وإلا بدا ثلاثة أيام من الغياب كأنها لحظة.
 */
function LastSeenLine({
  online,
  lastSeenAt,
  className = '',
}: {
  online?: boolean;
  lastSeenAt?: string | null;
  className?: string;
}) {
  if (online) {
    return <p className={`text-[11px] text-emerald-600 truncate ${className}`}>متصل الآن</p>;
  }
  const text = formatLastSeen(lastSeenAt);
  if (!text) return null;
  return <p className={`text-[11px] text-neutral-400 truncate ${className}`} title={text}>{text}</p>;
}

export default function MessagesPage() {
  const { session, updateEmployee } = useAuth();
  const me = session?.employee;
  const { toast } = useToast();
  const [contacts, setContacts] = useState<ChatContactSummary[]>([]);
  const [pinnedContacts, setPinnedContacts] = useState<number[]>([]);
  const [pinsLoadedFor, setPinsLoadedFor] = useState<number | null>(null);
  const [activePartnerId, setActivePartnerId] = useState<number | null>(null);
  const [partnerOverride, setPartnerOverride] = useState<MessagingContact | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [contactSearch, setContactSearch] = useUrlState('q', '');
  const [threadSearch, setThreadSearch] = useUrlState('thread_q', '');
  const [globalResults, setGlobalResults] = useState<MessageSearchGroup[]>([]);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [matchIndex, setMatchIndex] = useState(0);
  const [replyTarget, setReplyTarget] = useState<ChatMessage | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState('');
  const [newChatOpen, setNewChatOpen] = useState(false);
  // كم زميلاً متصل الآن. الخادم يحسبه من «آخر ظهور» لكل موظف بغضّ النظر
  // عن الصفحة المفتوحة، فالموظف الذي يبيع في صفحة المبيعات يظهر متصلاً.
  const [onlineCount, setOnlineCount] = useState(0);
  const [forwardTarget, setForwardTarget] = useState<ChatMessage | null>(null);
  const [infoTarget, setInfoTarget] = useState<{ id: number; name: string; avatar?: string | null; avatar_image?: string | null } | null>(null);
  const [infoIsMe, setInfoIsMe] = useState(false);
  const messagesEnd = useRef<HTMLDivElement>(null);
  const messageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const lastIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (!me) return;
    try {
      const saved = localStorage.getItem(`qomash:pinned-conversations:${me.id}`);
      const ids = saved ? JSON.parse(saved) : [];
      setPinnedContacts(Array.isArray(ids) ? ids.filter((id) => Number.isInteger(id)) : []);
    } catch {
      setPinnedContacts([]);
    }
    setPinsLoadedFor(me.id);
  }, [me?.id]);

  useEffect(() => {
    if (!me || pinsLoadedFor !== me.id) return;
    try { localStorage.setItem(`qomash:pinned-conversations:${me.id}`, JSON.stringify(pinnedContacts)); } catch {}
  }, [me?.id, pinsLoadedFor, pinnedContacts]);

  const activePartner =
    contacts.find((c) => c.employee.id === activePartnerId)?.employee || partnerOverride;
  const totalUnread = contacts.reduce((s, c) => s + c.unread, 0);
  const searching = contactSearch.trim().length > 0;
  const threadSearching = threadSearch.trim().length > 0;

  const loadConversations = useCallback(async () => {
    if (!me) return;
    try {
      const res = await getConversations(me.id, contactSearch.trim() || undefined);
      const sorted = [...res.conversations].sort((a, b) => {
        if (!a.last_at && !b.last_at) return 0;
        if (!a.last_at) return 1;
        if (!b.last_at) return -1;
        return new Date(b.last_at).getTime() - new Date(a.last_at).getTime();
      });
      setContacts(sorted);
      setOnlineCount(res.online_count ?? 0);
      setPartnerOverride((prev) => (prev && sorted.some((c) => c.employee.id === prev.id) ? null : prev));
    } catch {}
  }, [me, contactSearch]);

  const loadThread = useCallback(
    async (afterId?: number) => {
      if (!me || activePartnerId === null) return;
      try {
        const res = await getMessageThread(me.id, activePartnerId, afterId, threadSearch.trim() || undefined);
        if (afterId) {
          setMessages((prev) => [...prev, ...res.messages]);
        } else {
          setMessages(res.messages);
          setMatchIndex(0);
        }
        const newLast = res.messages.at(-1);
        if (newLast) lastIdRef.current = newLast.id;
      } catch {}
    },
    [me, activePartnerId, threadSearch],
  );

  // global message search (debounced)
  useEffect(() => {
    if (!me || !contactSearch.trim()) {
      setGlobalResults([]);
      return;
    }
    const t = setTimeout(() => {
      searchMessages(contactSearch.trim())
        .then((r) => setGlobalResults(r.groups))
        .catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [me, contactSearch]);

  // polling conversations every 12s + thread every 3s when open (skip when searching thread)
  useEffect(() => {
    if (!me) return;
    loadConversations();
    const cv = setInterval(loadConversations, 12000);
    let tv: ReturnType<typeof setInterval> | undefined;
    if (activePartnerId !== null && !threadSearching) {
      loadThread();
      tv = setInterval(() => loadThread(lastIdRef.current || undefined), 3000);
    }
    if (activePartnerId !== null && threadSearching) {
      loadThread();
    }
    return () => {
      clearInterval(cv);
      if (tv) clearInterval(tv);
    };
  }, [me, activePartnerId, threadSearching, loadConversations, loadThread]);

  // scroll: bottom normally, active match when searching
  useEffect(() => {
    if (!threadSearching) {
      messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
    } else if (messages.length > 0) {
      const active = messages[Math.min(Math.max(matchIndex, 0), messages.length - 1)];
      messageRefs.current.get(active.id)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, threadSearching, matchIndex]);

  const selectPartner = (partnerId: number, contact?: MessagingContact, withSearch?: string) => {
    if (activePartnerId !== partnerId) {
      lastIdRef.current = null;
      setActivePartnerId(partnerId);
      setMessages([]);
    }
    setText('');
    setReplyTarget(null);
    setEditingId(null);
    setThreadSearch(withSearch || '');
    setMatchIndex(0);
    if (contact) setPartnerOverride(contact);
  };

  const goMatch = (dir: 1 | -1) => {
    if (messages.length === 0) return;
    const next = (matchIndex + dir + messages.length) % messages.length;
    messageRefs.current.get(messages[next].id)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setMatchIndex(next);
  };

  const handleNewChatSelect = (contact: MessagingContact) => {
    setNewChatOpen(false);
    setContactSearch('');
    setGlobalResults([]);
    selectPartner(contact.id, contact);
  };

  const handleForwarded = () => {
    loadConversations();
    if (activePartnerId !== null) loadThread();
  };

  const openInfo = (emp: { id: number; name: string; avatar?: string | null; avatar_image?: string | null }, isMe = false) => {
    setInfoIsMe(isMe);
    setInfoTarget(emp);
  };

  const copyMessage = async (msg: ChatMessage) => {
    if (msg.is_deleted) return;
    try {
      await navigator.clipboard.writeText(msg.body);
      toast('success', 'تم نسخ الرسالة');
    } catch {
      toast('error', 'تعذر نسخ الرسالة');
    }
  };

  const handleSend = async () => {
    if (!me || activePartnerId === null || !text.trim() || sending) return;
    setSending(true);
    try {
      const msg = await sendMessage(me.id, activePartnerId, text.trim(), replyTarget?.id);
      setMessages((prev) => [...prev, msg]);
      if (!threadSearching) lastIdRef.current = msg.id;
      setText('');
      setReplyTarget(null);
      loadConversations();
    } catch (e: any) {
      toast('error', e?.message === 'حدث خطأ غير متوقع' ? 'تعذر إرسال الرسالة' : e?.message || 'تعذر الإرسال');
    } finally {
      setSending(false);
    }
  };

  const startReply = (msg: ChatMessage) => setReplyTarget(msg);
  const cancelReply = () => setReplyTarget(null);

  const startEdit = (msg: ChatMessage) => {
    setEditingId(msg.id);
    setEditText(msg.body);
  };
  const cancelEdit = () => {
    setEditingId(null);
    setEditText('');
  };

  const submitEdit = async (msg: ChatMessage) => {
    if (!me || !editText.trim()) return;
    try {
      const updated = await editMessage(msg.id, me.id, editText.trim());
      setMessages((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
      cancelEdit();
      loadConversations();
    } catch (e: any) {
      toast('error', e?.message || 'تعذر تعديل الرسالة');
    }
  };

  const confirmDelete = async (msg: ChatMessage) => {
    if (!me) return;
    if (!window.confirm('حذف الرسالة من الطرفين؟')) return;
    try {
      const updated = await deleteMessage(msg.id, me.id);
      setMessages((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
      loadConversations();
    } catch (e: any) {
      toast('error', e?.message || 'تعذر حذف الرسالة');
    }
  };

  const editable = (msg: ChatMessage) => me && msg.sender === me.id && !msg.is_deleted && withinWindow(msg);

  if (!me) return null;

  const pinOrder = new Map(pinnedContacts.map((id, index) => [id, index]));
  const orderedContacts = [...contacts].sort((a, b) => {
    const ai = pinOrder.get(a.employee.id);
    const bi = pinOrder.get(b.employee.id);
    if (ai !== undefined || bi !== undefined) {
      if (ai === undefined) return 1;
      if (bi === undefined) return -1;
      return ai - bi;
    }
    return 0;
  });
  const visibleContacts = unreadOnly ? orderedContacts.filter((c) => c.unread > 0) : orderedContacts;
  const togglePinned = (id: number) => setPinnedContacts((current) =>
    current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
  );

  return (
    <div className="space-y-3 h-full min-h-fit flex flex-col">
      <div className="flex items-center gap-2">
        <button
          onClick={() => window.history.back()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-sand-200 bg-surface text-sm font-medium text-neutral-600 hover:bg-sand-50 hover:text-brand-700 transition-colors"
          title="الرجوع للخلف"
        >
          <ArrowLeft size={16} />
          رجوع
        </button>
      </div>
      <div className="h-[calc(100vh-220px)] min-h-[450px] flex rounded-2xl border border-sand-200 bg-surface shadow-sm overflow-hidden">
      {/* ── conversations sidebar ── */}
      <div
        className={`
          w-80 border-sand-200 border-l shrink-0 flex flex-col
          ${activePartnerId !== null ? 'hidden md:flex' : 'flex w-full md:w-80'}
        `}
      >
        {/* identity bar */}
        <div className="px-4 py-3 border-b border-sand-200 flex items-center gap-3 bg-sand-50">
          <PresenceAvatar name={me.name} avatar={me.avatar} avatarImage={me.avatar_image} size="sm" onClick={() => openInfo(me, true)} title="معلوماتي وتغيير الأفاتار" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold truncate">{me.name}</p>
          </div>
          {totalUnread > 0 && (
            <Badge variant="danger">{totalUnread > 99 ? '+99' : totalUnread}</Badge>
          )}
          {/* العدّاد معنى «حاضر في النظام» لا «يفتح صفحة التواصل»؛ لذا نوضّح
              ذلك في التلميح حتى لا يتساءل المستخدم لماذا يظهر زميل يبيع. */}
          <span
            className="inline-flex items-center gap-1.5 shrink-0 cursor-help"
            title="الزملاء الذين استخدموا النظام خلال آخر دقيقتين، أياً كانت الصفحة التي يعملون عليها"
          >
            <span
              className={`w-2 h-2 rounded-full ${onlineCount > 0 ? 'bg-emerald-500' : 'bg-neutral-300'}`}
              aria-hidden
            />
            <span
              className={`text-xs font-medium tabular-nums ${onlineCount > 0 ? 'text-emerald-700' : 'text-neutral-400'}`}
            >
              {onlineCount} متصل
            </span>
          </span>
          <button
            onClick={() => setNewChatOpen(true)}
            title="رسالة جديدة"
            className="p-2 rounded-lg bg-brand-600 text-white hover:bg-brand-700 shrink-0 transition-colors"
          >
            <Plus size={16} />
          </button>
        </div>

        {/* global search */}
        <div className="p-3 border-b border-sand-200">
          <div className="relative">
            <Search size={15} className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              value={contactSearch}
              onChange={(e) => setContactSearch(e.target.value)}
              placeholder="ابحث في المحادثات والرسائل..."
              className="w-full pr-9 pl-3 py-2 rounded-xl border border-sand-200 bg-sand-50 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
            />
          </div>
        </div>

        {/* filter tabs */}
        {!searching && (
          <div className="px-3 py-2 border-b border-sand-200 flex items-center gap-2">
            {(['all', 'unread'] as const).map((key) => (
              <button
                key={key}
                onClick={() => setUnreadOnly(key === 'unread')}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  (key === 'unread' ? unreadOnly : !unreadOnly)
                    ? 'bg-brand-600 text-white'
                    : 'bg-sand-100 text-neutral-500 hover:bg-sand-200'
                }`}
              >
                {key === 'all' ? 'الكل' : 'غير المقروء'}
                {key === 'unread' && totalUnread > 0 && ` (${totalUnread})`}
              </button>
            ))}
          </div>
        )}

        {/* list */}
        <div className="flex-1 overflow-y-auto divide-y divide-sand-100">
          {!searching && visibleContacts.length === 0 && (
            <p className="text-sm text-neutral-400 text-center py-8 px-4">
              {unreadOnly
                ? 'لا توجد رسائل غير مقروءة'
                : contactSearch
                  ? 'لا نتائج مطابقة'
                  : 'لا توجد محادثات بعد — اضغط + أو ابحث عن زميل.'}
            </p>
          )}

          {!searching &&
            visibleContacts.map((c) => (
              <div
                key={c.employee.id}
                onClick={() => selectPartner(c.employee.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    selectPartner(c.employee.id);
                  }
                }}
                className={`w-full text-right px-4 py-3 flex items-center gap-3 hover:bg-sand-50 transition-colors ${
                  activePartnerId === c.employee.id ? 'bg-brand-50 border-r-2 border-brand-600' : ''
                }`}
              >
                <PresenceAvatar name={c.employee.name} avatar={c.employee.avatar} avatarImage={c.employee.avatar_image} online={c.employee.is_online} size="lg" onClick={() => openInfo(c.employee)} title="معلومات الموظف" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-sm truncate">
                      <Highlight text={c.employee.name} query={contactSearch} />
                    </span>
                    {c.last_at && (
                      <span className="text-[10px] text-neutral-400 shrink-0 tabular-nums">
                        {new Date(c.last_at).toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                  </div>
                  <LastSeenLine
                    online={c.employee.is_online}
                    lastSeenAt={c.employee.last_seen_at}
                    className="mt-0.5"
                  />
                  <div className="flex items-center justify-between gap-2 mt-0.5">
                    <p className={`text-xs truncate ${c.unread > 0 ? 'font-medium text-neutral-700' : 'text-neutral-400'}`}>
                      {c.last_message
                        ? `${c.last_message_from_me ? 'أنت: ' : ''}${c.last_message}`
                        : (c.employee.branch_name || '')}
                    </p>
                    {c.unread > 0 && (
                      <span className="min-w-[18px] h-[18px] px-1 rounded-full bg-brand-600 text-white text-[10px] font-bold flex items-center justify-center shrink-0">
                        {c.unread > 99 ? '+99' : c.unread}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={(event) => { event.stopPropagation(); togglePinned(c.employee.id); }}
                  title={pinnedContacts.includes(c.employee.id) ? 'إلغاء تثبيت المحادثة' : 'تثبيت المحادثة'}
                  aria-label={pinnedContacts.includes(c.employee.id) ? `إلغاء تثبيت محادثة ${c.employee.name}` : `تثبيت محادثة ${c.employee.name}`}
                  className={`shrink-0 rounded-lg p-1.5 transition ${pinnedContacts.includes(c.employee.id) ? 'text-brand-700 bg-brand-50' : 'text-neutral-300 hover:text-brand-600 hover:bg-sand-100'}`}
                >
                  <Pin size={15} className={pinnedContacts.includes(c.employee.id) ? 'fill-current' : ''} />
                </button>
              </div>
            ))}

          {searching && (
            <>
              {contacts.length === 0 && globalResults.length === 0 && (
                <p className="text-sm text-neutral-400 text-center py-8 px-4">لا نتائج مطابقة لبحثك</p>
              )}

              {contacts.length > 0 && (
                <>
                  <p className="px-4 pt-3 pb-1 text-[11px] font-medium text-neutral-400">المحادثات المطابقة</p>
                  {contacts.map((c) => (
                    <button
                      key={c.employee.id}
                      onClick={() => selectPartner(c.employee.id)}
                      className={`w-full text-right px-4 py-2.5 flex items-center gap-3 hover:bg-sand-50 transition-colors`}
                    >
                      <PresenceAvatar name={c.employee.name} avatar={c.employee.avatar} avatarImage={c.employee.avatar_image} online={c.employee.is_online} size="md" onClick={() => openInfo(c.employee)} title="معلومات الموظف" />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-sm truncate">
                          <Highlight text={c.employee.name} query={contactSearch} />
                        </p>
                        <LastSeenLine
                          online={c.employee.is_online}
                          lastSeenAt={c.employee.last_seen_at}
                          className="mt-0.5"
                        />
                        <p className="text-xs text-neutral-400 truncate">
                          {c.last_message
                            ? `${c.last_message_from_me ? 'أنت: ' : ''}${c.last_message}`
                            : c.employee.branch_name || ''}
                        </p>
                      </div>
                    </button>
                  ))}
                </>
              )}

              {globalResults.length > 0 && (
                <>
                  <p className="px-4 pt-3 pb-1 text-[11px] font-medium text-neutral-400">رسائل مطابقة في المحادثات</p>
                  {globalResults.map((g) => (
                    <button
                      key={g.employee.id}
                      onClick={() => selectPartner(g.employee.id, g.employee, contactSearch.trim())}
                      className="w-full text-right px-4 py-2.5 flex items-center gap-3 hover:bg-sand-50 transition-colors"
                    >
                      <PresenceAvatar name={g.employee.name} avatar={g.employee.avatar} avatarImage={g.employee.avatar_image} online={g.employee.is_online} size="md" onClick={() => openInfo(g.employee)} title="معلومات الموظف" />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-sm truncate">{g.employee.name}</p>
                        <LastSeenLine
                          online={g.employee.is_online}
                          lastSeenAt={g.employee.last_seen_at}
                          className="mt-0.5"
                        />
                        <p className="text-xs text-neutral-600 truncate">
                          <Highlight text={g.matches[0]?.body || ''} query={contactSearch} />
                        </p>
                        <p className="text-[10px] text-neutral-400 mt-0.5">
                          {g.matches.length} {g.matches.length === 1 ? 'نتيجة' : 'نتائج'}
                        </p>
                      </div>
                    </button>
                  ))}
                </>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── chat thread ── */}
      <div
        className={`flex-1 flex flex-col min-w-0 ${
          activePartnerId === null ? 'hidden md:flex' : 'flex'
        }`}
      >
        {activePartnerId === null ? (
          <div className="flex-1 flex flex-col items-center justify-center text-neutral-400 gap-3 p-8">
            <Send size={40} className="opacity-30" />
            <p className="text-sm text-center">اختر محادثة من القائمة على اليمين<br />أو ابدأ محادثة جديدة</p>
            <button
              onClick={() => setNewChatOpen(true)}
              className="px-4 py-2 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 transition-colors"
            >
              <Plus size={15} className="inline-block ml-1 -mt-0.5" />
              رسالة جديدة
            </button>
          </div>
        ) : (
          <>
            {/* thread header */}
            <div className="px-4 py-3 border-b border-sand-200 flex items-center gap-3 bg-sand-50">
              <button
                onClick={() => setActivePartnerId(null)}
                className="p-1.5 rounded-lg hover:bg-sand-200 text-neutral-500"
                title="الرجوع إلى قائمة المحادثات"
              >
                <ArrowLeft size={18} />
              </button>
<PresenceAvatar name={activePartner?.name || ''} avatar={activePartner?.avatar} avatarImage={activePartner?.avatar_image} online={activePartner?.is_online} size="md" onClick={() => activePartner && openInfo(activePartner)} title="معلومات الموظف" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold truncate">{activePartner?.name}</p>
                {/* آخر ظهور يأخذ سطره: اسم الفرع وحده يقول أين يعمل، ولا يقول
                    متى كان حاضراً — وهو ما يُسأل عنه في رسالة متأخرة. */}
                <LastSeenLine
                  online={activePartner?.is_online}
                  lastSeenAt={activePartner?.last_seen_at}
                  className="mt-0.5"
                />
                {activePartner?.branch_name && (
                  <p className="text-xs text-neutral-400 truncate">{activePartner.branch_name}</p>
                )}
              </div>

              {threadSearching ? (
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-neutral-500 tabular-nums">
                    {messages.length > 0 ? `${matchIndex + 1}/${messages.length}` : '0'}
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => goMatch(-1)}
                      disabled={messages.length === 0}
                      title="النتيجة السابقة"
                      className="p-1 rounded-lg hover:bg-sand-200 text-neutral-500 disabled:opacity-30"
                    >
                      <ChevronUp size={15} />
                    </button>
                    <button
                      onClick={() => goMatch(1)}
                      disabled={messages.length === 0}
                      title="النتيجة التالية"
                      className="p-1 rounded-lg hover:bg-sand-200 text-neutral-500 disabled:opacity-30"
                    >
                      <ChevronDown size={15} />
                    </button>
                    <button
                      onClick={() => setThreadSearch('')}
                      title="إغلاق البحث"
                      className="p-1 rounded-lg hover:bg-sand-200 text-neutral-500"
                    >
                      <X size={15} />
                    </button>
                  </div>
                </div>
              ) : (
                <div className="relative shrink-0 w-40">
                  <Search size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
                  <input
                    value={threadSearch}
                    onChange={(e) => {
                      setThreadSearch(e.target.value);
                      setMessages([]);
                      setMatchIndex(0);
                    }}
                    placeholder="بحث في الرسائل"
                    className="w-full pr-8 pl-2 py-1.5 rounded-lg border border-sand-200 bg-sand-50 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  />
                </div>
              )}
            </div>

            {/* messages */}
            <div className="flex-1 overflow-y-auto px-4 py-4 bg-sand-50/50">
              {messages.length === 0 && (
                <p className="text-xs text-neutral-400 text-center py-6">
                  {threadSearching ? 'لا رسائل مطابقة للبحث' : 'ابدأ المحادثة بإرسال رسالة'}
                </p>
              )}
              {messages.map((msg, i) => {
                const mine = msg.sender === me.id;
                const showDate = i === 0 || dayStart(new Date(msg.created_at)) !== dayStart(new Date(messages[i - 1].created_at));
                const activeHit = threadSearching && i === matchIndex;
                return (
                  <div key={msg.id}>
                    {showDate && (
                      <div className="flex items-center justify-center my-3">
                        <span className="px-3 py-1 rounded-full bg-sand-100 border border-sand-200 text-[10px] text-neutral-400">
                          {dayLabel(msg.created_at, new Date())}
                        </span>
                      </div>
                    )}
                    <div
                      ref={(el) => {
                        if (el) messageRefs.current.set(msg.id, el);
                        else messageRefs.current.delete(msg.id);
                      }}
                      className={`flex ${mine ? 'justify-start' : 'justify-end'} group ${
                        activeHit ? 'ring-2 ring-offset-1 ring-amber-400 rounded-2xl' : ''
                      }`}
                    >
                      <div
                        className={`max-w-[75%] px-3.5 py-2 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                          mine
                            ? 'bg-brand-600 text-white rounded-br-md'
                            : 'bg-white dark:bg-sand-200 text-neutral-800 border border-sand-200 rounded-bl-md'
                        }`}
                      >
                        {/* reply quote */}
                        {msg.reply_to_id && (
                          <div
                            className={`mb-1.5 px-2.5 py-1.5 rounded-lg text-xs border-r-[3px] ${
                              mine ? 'bg-white/15 border-white/40 text-white/85' : 'bg-sand-100 border-brand-500 text-neutral-500'
                            }`}
                          >
                            <span className={`font-semibold ${mine ? 'text-white/90' : 'text-brand-700'}`}>
                              {msg.reply_from_name || 'رسالة'}
                            </span>{' '}
                            — {msg.reply_to_body}
                          </div>
                        )}

                        {msg.is_deleted ? (
                          <p className={`italic ${mine ? 'text-white/60' : 'text-neutral-400'}`}>تم حذف رسالة</p>
                        ) : (
                          <>
                            {editingId === msg.id ? (
                              <div className="w-full flex flex-col gap-2">
                                <textarea
                                  value={editText}
                                  onChange={(e) => setEditText(e.target.value)}
                                  rows={2}
                                  autoFocus
                                  className={`w-64 resize-none rounded-lg px-2 py-1.5 text-sm border focus:outline-none ${
                                    mine ? 'bg-brand-700 border-white/30 text-white' : 'bg-white border-sand-300 text-neutral-800'
                                  }`}
                                />
                                <div className="flex gap-2">
                                  <button
                                    onClick={() => submitEdit(msg)}
                                    disabled={!editText.trim()}
                                    className="px-2.5 py-1 rounded-lg text-xs font-medium bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-40"
                                  >
                                    حفظ
                                  </button>
                                  <button
                                    onClick={cancelEdit}
                                    className="px-2.5 py-1 rounded-lg text-xs font-medium bg-sand-200 text-neutral-600 hover:bg-sand-300"
                                  >
                                    إلغاء
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <p>
                                <Highlight text={msg.body} query={threadSearch} />
                                {msg.edited_at && (
                                  <span className={`text-[10px] ms-1.5 ${mine ? 'text-white/55' : 'text-neutral-400'}`}>تم التعديل</span>
                                )}
                              </p>
                            )}
                          </>
                        )}

                        <p
                          className={`text-[10px] mt-1 text-right tabular-nums flex items-center justify-end gap-1 ${
                            mine ? 'text-white/60' : 'text-neutral-400'
                          }`}
                        >
                          {msg.is_deleted
                            ? new Date(msg.deleted_at || msg.created_at).toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' })
                            : new Date(msg.created_at).toLocaleTimeString('ar', {
                                hour: '2-digit',
                                minute: '2-digit',
                              })}
                          {mine && !msg.is_deleted && (
                            <span className={msg.read_at ? 'text-sky-300' : ''} title={msg.read_at ? 'تمت القراءة' : 'تم الإرسال'}>
                              {msg.read_at ? '✓✓' : '✓'}
                            </span>
                          )}
                        </p>

                        {/* actions on hover: copy / forward for all, reply/edit/delete for own editable */}
                        {!msg.is_deleted && (
                          <div className="mt-1.5 flex justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={() => startReply(msg)}
                              title="رد"
                              className={`p-1 rounded-md ${mine ? 'hover:bg-white/20' : 'hover:bg-sand-100'}`}
                            >
                              <CornerUpLeft size={14} />
                            </button>
                            <button
                              onClick={() => copyMessage(msg)}
                              title="نسخ"
                              className={`p-1 rounded-md ${mine ? 'hover:bg-white/20' : 'hover:bg-sand-100'}`}
                            >
                              <Copy size={14} />
                            </button>
                            <button
                              onClick={() => setForwardTarget(msg)}
                              title="إعادة توجيه"
                              className={`p-1 rounded-md ${mine ? 'hover:bg-white/20' : 'hover:bg-sand-100'}`}
                            >
                              <Forward size={14} />
                            </button>
                            {editable(msg) && (
                              <>
                                <button
                                  onClick={() => startEdit(msg)}
                                  title="تعديل"
                                  className={`p-1 rounded-md ${mine ? 'hover:bg-white/20' : 'hover:bg-sand-100'}`}
                                >
                                  <Pencil size={14} />
                                </button>
                                <button
                                  onClick={() => confirmDelete(msg)}
                                  title="حذف من الطرفين"
                                  className={`p-1 rounded-md ${mine ? 'hover:bg-white/20' : 'hover:bg-red-50 text-red-500'}`}
                                >
                                  <Trash2 size={14} />
                                </button>
                              </>
                            )}
                          </div>
                        )}
                        {!msg.is_deleted && (
                          <div className="lg:hidden mt-1 flex items-center gap-1">
                            {editable(msg) && (
                              <button
                                onClick={() => startReply(msg)}
                                title="رد"
                                className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-md bg-sand-100 text-neutral-500"
                              >
                                <CornerUpLeft size={11} /> رد
                              </button>
                            )}
                            <button
                              onClick={() => copyMessage(msg)}
                              title="نسخ"
                              className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-md bg-sand-100 text-neutral-500"
                            >
                              <Copy size={11} /> نسخ
                            </button>
                            <button
                              onClick={() => setForwardTarget(msg)}
                              title="إعادة توجيه"
                              className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-md bg-sand-100 text-neutral-500"
                            >
                              <Forward size={11} /> إعادة توجيه
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEnd} />
            </div>

            {/* input */}
            <div className="border-t border-sand-200 bg-surface px-4 py-3">
              {replyTarget && (
                <div className="flex items-center gap-2 mb-2 rounded-lg bg-sand-100 px-3 py-1.5 text-xs text-neutral-600">
                  <CornerUpLeft size={13} className="shrink-0 text-brand-600" />
                  <span className="truncate">
                    <span className="font-medium">{replyTarget.sender_name || 'مرسلة'}</span> — {replyTarget.is_deleted ? 'تم حذف رسالة' : replyTarget.body}
                  </span>
                  <button onClick={cancelReply} className="shrink-0 ml-1 text-neutral-400 hover:text-neutral-600">
                    <X size={14} />
                  </button>
                </div>
              )}
              <div className="flex items-end gap-2">
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder="اكتب رسالة..."
                  rows={1}
                  className="flex-1 resize-none rounded-xl border border-sand-200 bg-sand-50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40 max-h-32"
                />
                <button
                  onClick={handleSend}
                  disabled={!text.trim() || sending}
                  className="p-2.5 rounded-xl bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
                >
                  <Send size={16} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      <EmployeePickerModal
        open={newChatOpen}
        title="رسالة جديدة"
        description="اختر الزميل لبدء محادثة جديدة."
        onClose={() => setNewChatOpen(false)}
        onSelect={handleNewChatSelect}
      />
      <ForwardMessageModal
        open={!!forwardTarget}
        message={forwardTarget}
        me={me}
        onClose={() => setForwardTarget(null)}
        onForwarded={handleForwarded}
      />
      <EmployeeInfoModal
        open={!!infoTarget}
        employee={infoTarget}
        isMe={infoIsMe}
        onClose={() => setInfoTarget(null)}
        onAvatarChanged={(avatar) => updateEmployee({ avatar })}
        onAvatarImageChanged={(avatarImage) => updateEmployee({ avatar_image: avatarImage || '' })}
      />
      </div>
    </div>
  );
}
