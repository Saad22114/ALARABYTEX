import { describe, it, expect } from 'vitest';
import { elapsedLabel, elapsedMinutes } from './shiftClock';

const OPENED = '2026-10-03T12:35:00';

describe('elapsedMinutes', () => {
  it('يعدّ الدقائق بين وقت الفتح والوقت الحالي', () => {
    expect(elapsedMinutes(OPENED, new Date('2026-10-03T12:40:00').getTime())).toBe(5);
  });

  it('وردية مفتوحة منذ يوم تُظهر عمرها لا صفراً', () => {
    // المرجع القديم كان الساعة الحالية على يوم الوردية، فكانت تعطي 13 دقيقة
    expect(elapsedMinutes(OPENED, new Date('2026-10-04T12:48:00').getTime())).toBe(1453);
  });

  it('لا يعطي صفراً لوردية امتدت فوق منتصف الليل', () => {
    const opened = new Date('2026-10-03T23:50:00').getTime();
    expect(elapsedMinutes(new Date(opened).toISOString(), opened + 20 * 60000)).toBe(20);
  });

  it('لا ينزل تحت الصفر ولا ينهار على تاريخ فاسد', () => {
    const now = new Date('2026-10-03T12:00:00').getTime();
    expect(elapsedMinutes('2026-10-03T13:00:00', now)).toBe(0);
    expect(elapsedMinutes('not-a-date', now)).toBe(0);
  });

  it('لا يظهر بالأيام: بيوم كامل مئتان وأربعون ساعة', () => {
    const opened = new Date('2026-10-03T12:35:00').getTime();
    expect(elapsedMinutes(new Date(opened).toISOString(), opened + 24 * 3600000)).toBe(1440);
  });
});

describe('elapsedLabel', () => {
  it('الساعات والدقائق معاً', () => {
    expect(elapsedLabel(1530)).toBe('منذ 25 ساعة و 30 دقيقة');
    expect(elapsedLabel(90)).toBe('منذ 1 ساعة و 30 دقيقة');
  });

  it('الساعات وحدها إذا كانت الدقائق صفراً', () => {
    expect(elapsedLabel(120)).toBe('منذ 2 ساعة');
  });

  it('الدقائق قبل الساعة، والوردية المغلقة بلا نص', () => {
    expect(elapsedLabel(45)).toBe('منذ 45 دقيقة');
    expect(elapsedLabel(null)).toBe('');
  });

  it('يقبل بادئة أخرى ل-dialog التفاصيل', () => {
    expect(elapsedLabel(30, '')).toBe('30 دقيقة');
  });
});