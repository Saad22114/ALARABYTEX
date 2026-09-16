'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { ArrowLeft, CornerUpLeft, Pencil, Search, Send, Trash2, Users, X } from 'lucide-react';
import { useCurrentEmployee, CurrentEmployee } from '@/components/providers/CurrentEmployeeProvider';
import { getConversations, getMessageThread, sendMessage, editMessage, deleteMessage, EDIT_WINDOW_MINUTES } from '@/services/messages';
import { listEmployees } from '@/services/employees';
import { ChatMessage, ChatContactSummary } from '@/types';
import Badge from '@/components/ui/Badge';
import Card from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';

function withinWindow(msg: ChatMessage): boolean {
  const diff = Date.now() - new Date(msg.created_at).getTime();
  return diff <= EDIT_WINDOW_MINUTES * 60 * 1000;
}

export default function MessagesPage() {
  const { currentEmployee, setCurrentEmployee } = useCurrentEmployee();
  const me = currentEmployee;
  const { toast } = useToast();
  const [contacts, setContacts] = useState<ChatContactSummary[]>([]);
  const [allEmployees, setAllEmployees] = useState<{ id: number; name: string; role_label: string; branch_name: string }[]>([]);
  const [activePartnerId, setActivePartnerId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [contactSearch, setContactSearch] = useState('');
  const [threadSearch, setThreadSearch] = useState('');
  const [replyTarget, setReplyTarget] = useState<ChatMessage | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState('');
  const messagesEnd = useRef<HTMLDivElement>(null);
  const lastIdRef = useRef<number | null>(null);

  const activePartner = contacts.find((c) => c.employee.id === activePartnerId)?.employee || null;
  const totalUnread = contacts.reduce((s, c) => s + c.unread, 0);

  const loadConversations = useCallback(async () => {
    if (!me) return;
    try {
      const res = await getConversations(me.id, contactSearch.trim() || undefined);
      setContacts(res.conversations);
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
        }
        const newLast = res.messages.at(-1);
        if (newLast) lastIdRef.current = newLast.id;
      } catch {}
    },
    [me, activePartnerId, threadSearch],
  );

  // polling conversations every 12s + thread every 3s when open (skip when searching thread)
  useEffect(() => {
    if (!me) return;
    loadConversations();
    const cv = setInterval(loadConversations, 12000);
    let tv: ReturnType<typeof setInterval> | undefined;
    if (activePartnerId !== null && !threadSearch.trim()) {
      loadThread();
      tv = setInterval(() => loadThread(lastIdRef.current || undefined), 3000);
    }
    if (activePartnerId !== null && threadSearch.trim()) {
      loadThread();
    }
    return () => {
      clearInterval(cv);
      if (tv) clearInterval(tv);
    };
  }, [me, activePartnerId, threadSearch, loadConversations, loadThread]);

  // scroll bottom when thread loads
  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // load all employees for the identity picker
  useEffect(() => {
    listEmployees({ page_size: 100 })
      .then((res) =>
        setAllEmployees(
          res.results.map((e) => ({
            id: e.id,
            name: e.name,
            role_label: e.role_label,
            branch_name: e.branch_name || '',
          })),
        ),
      )
      .catch(() => {});
  }, []);

  const selectPartner = (partnerId: number) => {
    if (activePartnerId === partnerId) return;
    lastIdRef.current = null;
    setActivePartnerId(partnerId);
    setMessages([]);
    setText('');
    setReplyTarget(null);
    setEditingId(null);
    setThreadSearch('');
  };

  const handleSend = async () => {
    if (!me || activePartnerId === null || !text.trim() || sending) return;
    setSending(true);
    try {
      const msg = await sendMessage(me.id, activePartnerId, text.trim(), replyTarget?.id);
      setMessages((prev) => [...prev, msg]);
      if (!threadSearch.trim()) lastIdRef.current = msg.id;
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

  const onPickIdentity = (empId: string) => {
    const emp = allEmployees.find((e) => e.id === Number(empId));
    if (emp) setCurrentEmployee(emp);
  };

  const editable = (msg: ChatMessage) => me && msg.sender === me.id && !msg.is_deleted && withinWindow(msg);

  if (!me) {
    return (
      <Card
        title="اختر هويتك للمتابعة"
        subtitle="اختر اسمك لتبدأ المحادثة مع زملائك"
        className="max-w-lg mx-auto mt-8"
      >
        <div className="space-y-4">
          <Users size={36} className="mx-auto text-brand-500 mb-2" />
          <select
            onChange={(e) => onPickIdentity(e.target.value)}
            className="w-full p-3 rounded-xl border border-sand-200 bg-surface text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/50"
            defaultValue=""
          >
            <option value="" disabled>
              اختر اسمك...
            </option>
            {allEmployees.map((emp) => (
              <option key={emp.id} value={emp.id}>
                {emp.name} — {emp.role_label}
              </option>
            ))}
          </select>
        </div>
      </Card>
    );
  }

  return (
    <div className="h-[calc(100vh-180px)] min-h-[480px] flex rounded-2xl border border-sand-200 bg-surface shadow-sm overflow-hidden">
      {/* ── conversations sidebar ── */}
      <div
        className={`
          w-80 border-sand-200 border-l shrink-0 flex flex-col
          ${activePartnerId !== null ? 'hidden md:flex' : 'flex w-full md:w-80'}
        `}
      >
        {/* identity bar */}
        <div className="px-4 py-3 border-b border-sand-200 flex items-center gap-3 bg-sand-50">
          <div className="w-8 h-8 rounded-full bg-brand-600 text-white flex items-center justify-center text-sm font-bold shrink-0">
            {me.name[0]}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold truncate">{me.name}</p>
            <p className="text-xs text-neutral-400 truncate">{me.role_label}</p>
          </div>
          {totalUnread > 0 && (
            <Badge variant="danger">{totalUnread > 99 ? '+99' : totalUnread}</Badge>
          )}
          <button
            onClick={() => {
              setCurrentEmployee(null);
              setActivePartnerId(null);
              setContacts([]);
              setMessages([]);
            }}
            className="text-xs text-neutral-400 hover:text-red-500 shrink-0"
            title="تغيير الهوية"
          >
            تغيير
          </button>
        </div>

        {/* search box */}
        <div className="p-3 border-b border-sand-200">
          <div className="relative">
            <Search size={15} className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              value={contactSearch}
              onChange={(e) => setContactSearch(e.target.value)}
              placeholder="بحث برقم الاسم..."
              className="w-full pr-9 pl-3 py-2 rounded-xl border border-sand-200 bg-sand-50 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
            />
          </div>
        </div>

        {/* list */}
        <div className="flex-1 overflow-y-auto divide-y divide-sand-100">
          {contacts.length === 0 && (
            <p className="text-sm text-neutral-400 text-center py-8 px-4">
              {contactSearch ? 'لا نتائج مطابقة' : 'لا توجد محادثات بعد — ابدأ بإرسال رسالة لأي زميل.'}
            </p>
          )}
          {contacts.map((c) => (
            <button
              key={c.employee.id}
              onClick={() => selectPartner(c.employee.id)}
              className={`w-full text-right px-4 py-3 flex items-center gap-3 hover:bg-sand-50 transition-colors ${
                activePartnerId === c.employee.id ? 'bg-brand-50 border-r-2 border-brand-600' : ''
              }`}
            >
              <div className="w-10 h-10 rounded-full bg-sand-200 dark:bg-sand-700 flex items-center justify-center text-sm font-bold text-neutral-700 dark:text-neutral-200 shrink-0">
                {c.employee.name[0]}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-sm truncate">{c.employee.name}</span>
                  {c.last_at && (
                    <span className="text-[10px] text-neutral-400 shrink-0 tabular-nums">
                      {new Date(c.last_at).toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-between gap-2 mt-0.5">
                  <p className={`text-xs truncate ${c.unread > 0 ? 'font-medium text-neutral-700' : 'text-neutral-400'}`}>
                    {c.last_message
                      ? `${c.last_message_from_me ? 'أنت: ' : ''}${c.last_message}`
                      : c.employee.role_label}
                  </p>
                  {c.unread > 0 && (
                    <span className="min-w-[18px] h-[18px] px-1 rounded-full bg-brand-600 text-white text-[10px] font-bold flex items-center justify-center shrink-0">
                      {c.unread > 99 ? '+99' : c.unread}
                    </span>
                  )}
                </div>
              </div>
            </button>
          ))}
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
          </div>
        ) : (
          <>
            {/* thread header */}
            <div className="px-4 py-3 border-b border-sand-200 flex items-center gap-3 bg-sand-50">
              <button
                onClick={() => setActivePartnerId(null)}
                className="md:hidden p-1.5 rounded-lg hover:bg-sand-200 text-neutral-500"
              >
                <ArrowLeft size={18} />
              </button>
              <div className="w-9 h-9 rounded-full bg-sand-200 dark:bg-sand-700 flex items-center justify-center text-sm font-bold text-neutral-700 dark:text-neutral-200 shrink-0">
                {activePartner?.name?.[0]}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold truncate">{activePartner?.name}</p>
                <p className="text-xs text-neutral-400">{activePartner?.role_label} {activePartner?.branch_name ? `— ${activePartner.branch_name}` : ''}</p>
              </div>
              <div className="relative shrink-0 w-40">
                <Search size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
                <input
                  value={threadSearch}
                  onChange={(e) => {
                    setThreadSearch(e.target.value);
                    setMessages([]);
                  }}
                  placeholder="بحث في الرسائل"
                  className="w-full pr-8 pl-2 py-1.5 rounded-lg border border-sand-200 bg-sand-50 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                />
              </div>
            </div>

            {/* messages */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-2 bg-sand-50/50">
              {messages.length === 0 && (
                <p className="text-xs text-neutral-400 text-center py-6">
                  {threadSearch ? 'لا رسائل مطابقة للبحث' : 'ابدأ المحادثة بإرسال رسالة'}
                </p>
              )}
              {messages.map((msg) => {
                const mine = msg.sender === me.id;
                return (
                  <div key={msg.id} className={`flex ${mine ? 'justify-start' : 'justify-end'} group`}>
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
                              {msg.body}
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

                      {/* actions (sender only, within window, not deleted) */}
                      {!msg.is_deleted && editable(msg) && (
                        <div className="mt-1.5 flex justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => startReply(msg)}
                            title="رد"
                            className={`p-1 rounded-md ${mine ? 'hover:bg-white/20' : 'hover:bg-sand-100'}`}
                          >
                            <CornerUpLeft size={14} />
                          </button>
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
                        </div>
                      )}
                      {!msg.is_deleted && editable(msg) && (
                        <button
                          onClick={() => startReply(msg)}
                          title="رد"
                          className="lg:hidden mt-1 flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-md bg-sand-100 text-neutral-500"
                        >
                          <CornerUpLeft size={11} /> رد
                        </button>
                      )}
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
    </div>
  );
}