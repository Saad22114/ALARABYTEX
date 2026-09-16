import { apiRequest } from './api';
import { SectionsInfo } from '@/types';

export async function getSectionsInfo(): Promise<SectionsInfo> {
  return apiRequest<SectionsInfo>('/sections/');
}