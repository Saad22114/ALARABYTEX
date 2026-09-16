import { apiRequest, buildQuery } from './api';
import { ChatMessage, ConversationsResult, MessageThreadResult } from '@/types';

export async function getConversations(employeeId: number, q?: string): Promise<ConversationsResult> {
  const query = buildQuery({ employee: employeeId, q });
  return apiRequest<ConversationsResult>(`/messaging/conversations/${query}`);
}

export async function getMessageThread(
  employeeId: number,
  partnerId: number,
  afterId?: number,
  q?: string,
): Promise<MessageThreadResult> {
  const query = buildQuery({ employee: employeeId, partner: partnerId, after_id: afterId, q });
  return apiRequest<MessageThreadResult>(`/messaging/messages/${query}`);
}

export async function sendMessage(
  sender: number,
  receiver: number,
  body: string,
  replyTo?: number | null,
): Promise<ChatMessage> {
  return apiRequest<ChatMessage>('/messaging/send/', {
    method: 'POST',
    body: JSON.stringify({ sender, receiver, body, reply_to: replyTo || null }),
  });
}

export async function editMessage(id: number, employeeId: number, body: string): Promise<ChatMessage> {
  return apiRequest<ChatMessage>(`/messaging/messages/${id}/edit/`, {
    method: 'POST',
    body: JSON.stringify({ employee: employeeId, body }),
  });
}

export async function deleteMessage(id: number, employeeId: number): Promise<ChatMessage> {
  return apiRequest<ChatMessage>(`/messaging/messages/${id}/delete/`, {
    method: 'POST',
    body: JSON.stringify({ employee: employeeId }),
  });
}

export async function getUnreadCount(employeeId: number): Promise<{ count: number }> {
  const q = buildQuery({ employee: employeeId });
  return apiRequest<{ count: number }>(`/messaging/unread/${q}`);
}

export const EDIT_WINDOW_MINUTES = 30;