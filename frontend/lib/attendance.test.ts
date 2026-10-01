import { describe, it, expect } from 'vitest';
import {
  attainmentPercent,
  clockLabel,
  dirtyRecord,
  dirtyTimes,
  EXCUSE_LABEL,
  fromDateTimeLocal,
  isOpen,
  minutesLabel,
  minutesToClock,
  monthLabel,
  relativeDayLabel,
  shortfall,
  statusLabel,
  statusVariant,
  toDateTimeLocal,
  workedText,
} from './attendance';
import type { AttendanceRecord } from '@/types';

/**
 * منطق عرض الحضور، منفصلاً عن الشاشة ليبقى قابلاً للاختبار.
 *
 * كل ما هنا حالةٌ واحدة مُقلَّبة على نفسها: الصفر. «لم يخرج بعد» ليست
 * صفراً، و«لا نعلم» ليست صفراً. ومن يخلط بينهما يعرض موظفاً داخل الدوام
 * منذ الفجر على أنه غائب — وهو أسوأُ من عرض حضورٍ خاطئ، لأن الغياب يخصم من
 * الراتب ولا يُراجَع.
 */

function record(overrides: Partial<AttendanceRecord> = {}): AttendanceRecord {
  return {
    id: 1,
    employee: { id: 1, name: 'موظف' } as AttendanceRecord['employee'],
    date: '2026-10-01',
    login_at: '2026-10-01T06:00:00Z',
    logout_at: '2026-10-01T15:00:00Z',
    worked_minutes: 540,
    late_minutes: 0,
    early_leave_minutes: 0,
    overtime_minutes: 0,
    status: 'present',
    excuse: 'none',
    working_day: true,
    source: 'auto',
    note: '',
    ...overrides,
  };
}

describe('minutesToClock', () => {
  it('يكتب الساعة بالدقائق لا بصيغة 1:00', () => {
    expect(minutesToClock(60)).toBe('1:00');
    expect(minutesToClock(90)).toBe('1:30');
    expect(minutesToClock(450)).toBe('7:30');
  });

  it('يبدأ الصفر بصفر لا بصفرين', () => {
    expect(minutesToClock(0)).toBe('0:00');
    expect(minutesToClock(5)).toBe('0:05');
  });

  it('يقصّ السالب عند الصفر بدل أن يعرض «-0:30»', () => {
    expect(minutesToClock(-30)).toBe('0:00');
  });

  it('يقرأ السطر المفتوح كفراغ لا كصفر', () => {
    // الصفرُ يعني عملَه صفرَ دقيقة؛ الفارغُ يعني «لم يُقَس بعد». الخلط
    // بينهما هو أصلُ كل خطأ في هذا القسم.
    expect(minutesToClock(0)).toBe('0:00');
    expect(minutesToClock(null)).toBe('');
    expect(minutesToClock(undefined)).toBe('');
  });
});

describe('workedText', () => {
  it('يرفض أن يخترع ساعةً لسطرٍ مفتوح', () => {
    expect(workedText(null)).toBe('لم يخرج بعد');
    expect(workedText(undefined)).toBe('لم يخرج بعد');
  });

  it('يكتب «لا عمل» لصفرٍ مقيس لا لغيابِ معلومة', () => {
    expect(workedText(0)).toBe('لا عمل');
  });

  it('يصوغ الدقائق بالعربية', () => {
    expect(workedText(45)).toBe('45 دقيقة');
    expect(workedText(120)).toBe('2 ساعة');
    expect(workedText(510)).toBe('8 ساعة و30 دقيقة');
  });
});

describe('minutesLabel', () => {
  it('يفرّق الواحد والمثنى والجمع', () => {
    expect(minutesLabel(1)).toBe('1 دقيقة');
    expect(minutesLabel(2)).toBe('2 دقيقتان');
    expect(minutesLabel(5)).toBe('5 دقائق');
    expect(minutesLabel(25)).toBe('25 دقيقة');
  });

  it('يعود إلى «لا شيء» عند الصفر والفارغ', () => {
    expect(minutesLabel(0)).toBe('لا شيء');
    expect(minutesLabel(null)).toBe('لا شيء');
  });
});

describe('shortfall', () => {
  it('يقيس النقص عن يوم العمل', () => {
    expect(shortfall(420, 480)).toBe(60);
  });

  it('لا يُقرض يوماً لم يُسجَّل له دخول أصلاً', () => {
    // خصمُ يومٍ كامل بسبب سهوٍ في التسجيل ليس جوراً، بل خصمٌ بلا دليل.
    expect(shortfall(null, 480)).toBe(0);
    expect(shortfall(0, 480)).toBe(0);
  });

  it('لا يُقرض ما زاد العملُ عن اليوم', () => {
    expect(shortfall(600, 480)).toBe(0);
  });

  it('لا يختلق نقصاً ليومِ عملٍ لا يعرفه', () => {
    // «ناقص ساعتان» تحت كل سطرٍ من جدولٍ لم تُفتح سياستُه بعدُ: حكمٌ
    // على الموظف برقمٍ لم يأتِ من أحد.
    expect(shortfall(300, null)).toBe(0);
    expect(shortfall(null, null)).toBe(0);
  });
});

describe('attainmentPercent', () => {
  it('يحسب النسبة ويقصّها عند 100', () => {
    expect(attainmentPercent(240, 480)).toBe(50);
    expect(attainmentPercent(700, 480)).toBe(100);
  });

  it('لا يقسم على صفرٍ فيعطي Nan', () => {
    expect(attainmentPercent(240, 0)).toBe(0);
  });
});

describe('isOpen', () => {
  it('السطر المفتوح دليلُ حضورٍ لا دليلُ غياب', () => {
    expect(isOpen(record({ logout_at: null, worked_minutes: null }))).toBe(true);
  });

  it('السطر المغلق ليس مفتوحاً', () => {
    expect(isOpen(record())).toBe(false);
  });

  it('لا خروج بلا دخولٍ لا سطرَ له أصلاً', () => {
    expect(isOpen(record({ login_at: null, logout_at: null }))).toBe(false);
  });
});

describe('statusLabel / statusVariant', () => {
  it('يترجم كل حالةٍ معروفة', () => {
    expect(statusLabel('present')).toBe('حاضر');
    expect(statusLabel('late')).toBe('متأخر');
    expect(statusLabel('early_leave')).toBe('انصراف مبكر');
    expect(statusLabel('absent')).toBe('غائب');
    expect(statusLabel('excused')).toBe('مبرر');
    expect(statusLabel('inside')).toBe('داخل الدوام');
    expect(statusLabel('off')).toBe('عطلة');
  });

  it('العطلة ليست يوماً ناقصاً، فلا تُحمَّل حَمل الغياب', () => {
    expect(statusVariant('off')).toBe('neutral');
    expect(statusVariant('absent')).toBe('danger');
  });

  it('لا يبتلع حالةً لم يأتِ بها الخادم، بل يُظهرها كما هي', () => {
    // الحجب الصامت هنا يُخفي تعارضَ بياناتٍ حقيقياً فيصير الجدول ناقصاً
    // بلا تفسير، وهو أسوأ من عرض اسمٍ غريب.
    expect(statusLabel('mystery')).toBe('mystery');
    expect(statusVariant('mystery')).toBe('neutral');
  });
});

describe('EXCUSE_LABEL', () => {
  it('يترجم كل تبريرٍ معروف', () => {
    expect(EXCUSE_LABEL.sick).toBe('مريض');
    expect(EXCUSE_LABEL.leave).toBe('إجازة');
    expect(EXCUSE_LABEL.official).toBe('مهمة رسمية');
    expect(EXCUSE_LABEL.none).toBe('لا شيء');
  });
});

describe('dirtyRecord', () => {
  it('لا يرسل شيئاً لم يُغيَّر', () => {
    const saved = record();
    expect(dirtyRecord({ excuse: saved.excuse, note: saved.note }, saved)).toBe(false);
    expect(dirtyRecord({}, saved)).toBe(false);
  });

  it('يكتفي بتغيير التبرير وحده', () => {
    expect(dirtyRecord({ excuse: 'sick' }, record())).toBe(true);
    expect(dirtyRecord({ note: 'اتصال' }, record())).toBe(true);
  });

  it('غيابُ الحقل في المسوّدة ليس فراغاً', () => {
    // `undefined` تعني «الشاشة لم تمسّه»؛ و«لا شيء» تعني «كتب لا شيء».
    // الخلطُ بينهما يجعل الحفظ يمسح تبريراً بسبب حقولٍ لم تُفتح أصلاً.
    expect(dirtyRecord({ excuse: undefined, note: undefined }, record())).toBe(false);
  });
});

describe('dirtyTimes', () => {
  const saved = record();

  it('لا تغيير حين يبقى الحقلان كما هما', () => {
    expect(dirtyTimes(toDateTimeLocal(saved.login_at), toDateTimeLocal(saved.logout_at), saved))
      .toBe(false);
  });

  it('تفريغ وقت الخروج تغييرٌ حقيقي', () => {
    // هو ما يجعل موظفاً نسي أن يخرج يبدو أنه أنهى يومه في وقته.
    expect(dirtyTimes(toDateTimeLocal(saved.login_at), '', saved)).toBe(true);
  });

  it('سطرٌ بلا أوقات لا يتغيّر بفراغٍ فيه', () => {
    const open = record({ login_at: null, logout_at: null });
    expect(dirtyTimes('', '', open)).toBe(false);
  });

  it('تعديلُ وقت الدخول تغييرٌ', () => {
    expect(dirtyTimes('2026-10-01T07:15', toDateTimeLocal(saved.logout_at), saved))
      .toBe(true);
  });
});

describe('monthLabel', () => {
  it('يكتب الشهر بالعربية من ISO بلا منطقة زمنية', () => {
    expect(monthLabel('2026-09-01')).toBe('سبتمبر 2026');
    expect(monthLabel('2026-01')).toBe('يناير 2026');
    expect(monthLabel('2026-12-31')).toBe('ديسمبر 2026');
  });

  it('لا يخترع شهراً من نصٍّ ناقص', () => {
    expect(monthLabel('')).toBe('');
    expect(monthLabel('2026')).toBe('');
    expect(monthLabel('2026-13-01')).toBe('');
  });
});

describe('relativeDayLabel', () => {
  it('يسمّي اليوم وأمس', () => {
    expect(relativeDayLabel('2026-10-01', '2026-10-01')).toBe('اليوم');
    expect(relativeDayLabel('2026-09-30', '2026-10-01')).toBe('أمس');
    expect(relativeDayLabel('2026-09-29', '2026-10-01')).toBe('قبل يومين');
  });

  it('ما بعد ذلك تاريخٌ كامل: «قبل أسبوع» تقديرٌ يُخطئ عند حدّه', () => {
    expect(relativeDayLabel('2026-09-20', '2026-10-01')).toBe('2026-09-20');
  });
});

describe('toDateTimeLocal / fromDateTimeLocal', () => {
  it('يحوّل ISO إلى قيمة حقل datetime-local', () => {
    // حقل الإدخال لا يعرف المنطقة الزمنية، فإن تركنا الـ Z ظهرت «00:00»
    // لمحو دخل عند التاسعة — ومن حفظها سجّل دخولاً فجراً.
    const value = toDateTimeLocal('2026-10-01T09:00:00Z');
    expect(value).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
  });

  it('السلسلة الفارغة تعني «لا وقت» لا «منتصف الليل»', () => {
    expect(toDateTimeLocal(null)).toBe('');
    expect(toDateTimeLocal('')).toBe('');
    expect(toDateTimeLocal('لاشيء')).toBe('');
    expect(fromDateTimeLocal('')).toBeNull();
    expect(fromDateTimeLocal('لاشيء')).toBeNull();
  });

  it('يدور في الاتجاهين بلا فقد', () => {
    // المقارنةُ بالتاريخ لا بالنصّ: ``toISOString`` يُخرج أصفارَ الأجزاء
    // من الثانية («.000Z») بينما قد يعيد الخادمُ «Z» بلا أجزاء. النصان
    // وقتٌ واحد، والفرقُ بينهما في التنسيق لا في اللحظة.
    const iso = '2026-10-01T09:00:00Z';
    const round = fromDateTimeLocal(toDateTimeLocal(iso));
    expect(round).not.toBeNull();
    expect(new Date(round as string).toISOString()).toBe(new Date(iso).toISOString());
  });
});

describe('clockLabel', () => {
  it('يكتب الساعة وحدها', () => {
    expect(clockLabel('2026-10-01T09:00:00Z')).toMatch(/^\d{2}:\d{2}$/);
    expect(clockLabel(null)).toBe('');
    expect(clockLabel('لاشيء')).toBe('');
  });
});