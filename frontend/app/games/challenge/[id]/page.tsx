'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowRight, Circle, Flag, RotateCcw, Trophy, X } from 'lucide-react';
import AppShell from '@/components/layout/AppShell';
import Avatar from '@/components/ui/Avatar';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import { useAuth } from '@/components/providers/AuthProvider';
import { GameChallenge, getGameChallenge, makeGameChallengeMove } from '@/services/games';

const rpsOptions = [
  { key: 'rock', label: 'حجر', emoji: '✊' },
  { key: 'paper', label: 'ورقة', emoji: '✋' },
  { key: 'scissors', label: 'مقص', emoji: '✌️' },
] as const;

export default function GameChallengePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { session } = useAuth();
  const challengeId = Number(params.id);
  const [challenge, setChallenge] = useState<GameChallenge | null>(null);
  const [error, setError] = useState('');
  const [moving, setMoving] = useState(false);
  const [selectedSeegaPiece, setSelectedSeegaPiece] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      setChallenge(await getGameChallenge(challengeId));
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'تعذر تحميل المباراة');
    }
  }, [challengeId]);

  useEffect(() => {
    if (!Number.isInteger(challengeId) || challengeId < 1) {
      setError('رابط المباراة غير صالح');
      return;
    }
    void refresh();
    const timer = setInterval(() => void refresh(), 1500);
    return () => clearInterval(timer);
  }, [challengeId, refresh]);

  const submitMove = async (move: number | { choice: 'rock' | 'paper' | 'scissors' } | { from: number; to: number } | { action: 'forfeit' }) => {
    if (!challenge || moving) return;
    setMoving(true);
    try {
      setChallenge(await makeGameChallengeMove(challenge.id, move));
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'تعذر تسجيل الحركة');
      void refresh();
    } finally { setMoving(false); }
  };

  const meId = session?.employee.id;
  const state = challenge?.game_state;
  const isTicTacToe = challenge?.game === 'tic_tac_toe';
  const isSeega = challenge?.game === 'seega';
  const isMyTurn = !!(state && meId && state.turn === meId);
  const mySeegaMark = challenge?.is_incoming ? 'O' : 'X';
  const myChoice = meId ? state?.choices?.[String(meId)] : undefined;
  const winnerName = challenge && state?.winner_id
    ? state.winner_id === challenge.requester_id
      ? (challenge.is_incoming ? challenge.other_employee.name : session?.employee.name)
      : (challenge.is_incoming ? session?.employee.name : challenge.other_employee.name)
    : null;
  const playSeegaCell = (point: number) => {
    if (!challenge || !state?.board || !isMyTurn || moving) return;
    if (selectedSeegaPiece === null) {
      if (state.board[point] === mySeegaMark) setSelectedSeegaPiece(point);
      return;
    }
    if (state.board[point] === mySeegaMark) { setSelectedSeegaPiece(point); return; }
    if (!state.board[point]) {
      const from = selectedSeegaPiece;
      setSelectedSeegaPiece(null);
      void submitMove({ from, to: point });
    }
  };
  const loserName = challenge && state?.forfeit_id
    ? state.forfeit_id === challenge.requester_id
      ? (challenge.is_incoming ? challenge.other_employee.name : session?.employee.name)
      : (challenge.is_incoming ? session?.employee.name : challenge.other_employee.name)
    : null;

  return <AppShell>
    <div className="mx-auto max-w-2xl space-y-5">
      <Button variant="ghost" onClick={() => router.push('/games')}><ArrowRight size={16} /> العودة للألعاب</Button>
      <Card title={isTicTacToe ? 'مباراة إكس-أو' : isSeega ? 'مباراة سيجا' : 'مباراة حجر ورقة مقص'} subtitle="المباراة مشتركة بينكما وتتحدث تلقائيًا">
        {!challenge ? <p className="py-10 text-center text-sm text-neutral-500">{error || 'جارٍ تحميل المباراة…'}</p> : <>
          <div className="mb-5 grid grid-cols-2 gap-3">
            <div className={`flex items-center gap-3 rounded-2xl border p-3 ${challenge.is_incoming ? 'border-sand-200 bg-sand-50 dark:border-neutral-700 dark:bg-neutral-800' : 'border-brand-300 bg-brand-50 dark:border-brand-500/40 dark:bg-brand-500/10'}`}>
              <Avatar name={challenge.is_incoming ? challenge.other_employee.name : session?.employee.name || ''} avatar={challenge.is_incoming ? challenge.other_employee.avatar : session?.employee.avatar} avatarImage={challenge.is_incoming ? challenge.other_employee.avatar_image : session?.employee.avatar_image} size="md" />
              <span className="min-w-0 flex-1"><b className="block truncate text-sm">{challenge.is_incoming ? challenge.other_employee.name : session?.employee.name}</b><small className="text-neutral-500">{isTicTacToe || isSeega ? 'X · يبدأ' : 'اللاعب الأول'}</small></span>{isTicTacToe && <X className="text-sky-600" />}{isSeega && <span className="text-brand-700">●</span>}
            </div>
            <div className={`flex items-center gap-3 rounded-2xl border p-3 ${challenge.is_incoming ? 'border-brand-300 bg-brand-50 dark:border-brand-500/40 dark:bg-brand-500/10' : 'border-sand-200 bg-sand-50 dark:border-neutral-700 dark:bg-neutral-800'}`}>
              <Avatar name={challenge.is_incoming ? session?.employee.name || '' : challenge.other_employee.name} avatar={challenge.is_incoming ? session?.employee.avatar : challenge.other_employee.avatar} avatarImage={challenge.is_incoming ? session?.employee.avatar_image : challenge.other_employee.avatar_image} size="md" />
              <span className="min-w-0 flex-1"><b className="block truncate text-sm">{challenge.is_incoming ? session?.employee.name : challenge.other_employee.name}</b><small className="text-neutral-500">{isTicTacToe || isSeega ? 'O' : 'اللاعب الثاني'}</small></span>{isTicTacToe && <Circle className="text-rose-500" />}{isSeega && <span className="text-amber-600">○</span>}
            </div>
          </div>

          {challenge.status === 'completed' ? <div className="rounded-2xl bg-amber-50 p-5 text-center dark:bg-amber-500/10">
            {state?.draw ? <p className="text-lg font-bold">تعادل! أحسنتم 🎉</p> : <><Trophy className="mx-auto mb-2 text-amber-500" size={30} /><p className="text-lg font-bold">الفائز: {winnerName || 'المباراة انتهت'}</p>{loserName && <p className="mt-1 text-sm text-rose-700">{loserName} انسحب وسُجّلت عليه خسارة</p>}</>}
            <Button className="mt-4" onClick={() => router.push('/games')}><RotateCcw size={15} /> العودة إلى الألعاب</Button>
          </div> : challenge.status !== 'accepted' ? <p className="rounded-xl bg-amber-50 p-4 text-center text-sm text-amber-800">بانتظار قبول الطلب من الموظف الآخر.</p> : <>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold">{isTicTacToe || isSeega ? isMyTurn ? 'دورك الآن' : 'دور الموظف الآخر' : myChoice ? 'تم تثبيت اختيارك، ننتظر اختيار الخصم سرًا' : 'اختر حركتك؛ لن يظهر اختيارك للخصم حتى يختار'}</p>
              <button type="button" disabled={moving} onClick={() => { if (window.confirm('سيتم إنهاء المباراة وتسجيل خسارة عليك. هل تريد الانسحاب؟')) void submitMove({ action: 'forfeit' }); }} className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50"><Flag size={14} /> انسحاب (خسارة)</button>
            </div>
            {isTicTacToe ? <>
              <div className="mx-auto grid max-w-sm grid-cols-3 gap-2 rounded-2xl bg-gradient-to-br from-violet-100 to-indigo-100 p-3 dark:from-violet-950/50 dark:to-indigo-950/50">
                {(state?.board || Array(9).fill('')).map((mark, index) => <button key={index} type="button" disabled={!isMyTurn || moving || !!mark || challenge.status !== 'accepted'} onClick={() => void submitMove(index)} aria-label={`الخانة ${index + 1}${mark ? ` ${mark}` : ''}`} className="flex aspect-square items-center justify-center rounded-xl bg-white text-5xl font-black shadow-sm transition hover:bg-violet-50 disabled:cursor-not-allowed dark:bg-neutral-900 dark:hover:bg-neutral-800">{mark === 'X' ? <X className="text-sky-600" size={54} strokeWidth={2.6} /> : mark === 'O' ? <Circle className="text-rose-500" size={48} strokeWidth={2.6} /> : null}</button>)}
              </div>
            </> : isSeega ? <>
              <p className="mb-3 text-center text-xs text-neutral-500">اختر إحدى قطعك، ثم اختر خانة فارغة لتحريكها. الفوز بخط أفقي أو رأسي فقط.</p>
              <div className="mx-auto grid max-w-sm grid-cols-3 gap-2 rounded-2xl bg-gradient-to-br from-amber-50 to-orange-100 p-3 dark:from-amber-950/30 dark:to-orange-950/30">
                {(state?.board || Array(9).fill('')).map((piece, index) => <button key={index} type="button" disabled={!isMyTurn || moving || challenge.status !== 'accepted'} onClick={() => playSeegaCell(index)} aria-label={`الخانة ${index + 1}`} className={`flex aspect-square items-center justify-center rounded-xl border text-4xl shadow-sm transition disabled:cursor-not-allowed dark:bg-neutral-900 ${selectedSeegaPiece === index ? 'border-brand-500 bg-brand-100 ring-4 ring-brand-200/60 dark:bg-brand-500/20' : selectedSeegaPiece !== null && !piece ? 'border-emerald-400 bg-emerald-50 dark:bg-emerald-500/10' : 'border-sand-200 bg-white hover:bg-amber-50 dark:border-neutral-700'} ${piece === 'X' ? 'text-brand-700 dark:text-brand-300' : 'text-amber-600 dark:text-amber-300'}`}>{piece === 'X' ? '●' : piece === 'O' ? '○' : ''}</button>)}
              </div>
              <p className="mt-3 text-center text-xs text-neutral-400">عدد الحركات: {state?.moves_played || 0}/40</p>
            </> : <div className="grid grid-cols-3 gap-3">
              {rpsOptions.map((option) => <button key={option.key} type="button" disabled={moving || !!myChoice || challenge.status !== 'accepted'} onClick={() => void submitMove({ choice: option.key })} className="flex flex-col items-center gap-2 rounded-2xl border border-violet-200 bg-gradient-to-b from-violet-50 to-white p-5 text-lg font-bold shadow-sm transition hover:-translate-y-0.5 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50 dark:border-neutral-700 dark:from-neutral-800 dark:to-neutral-900"><span className="text-4xl">{option.emoji}</span>{option.label}</button>)}
            </div>}
            <p className="mt-4 text-center text-xs text-neutral-500">يمكنك الانسحاب في أي وقت؛ سيُسجَّل الانسحاب خسارةً لك وفوزًا للطرف الآخر.</p>
          </>}
          {error && <p role="alert" className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        </>}
      </Card>
    </div>
  </AppShell>;
}
