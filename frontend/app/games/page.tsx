'use client';

import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '@/components/layout/AppShell';
import Avatar from '@/components/ui/Avatar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { useAuth } from '@/components/providers/AuthProvider';
import { useToast } from '@/components/ui/Toast';
import {
  GameChallenge, GameCommunity, GameDifficulty, GameHistory, GameKey, GameOutcome, GameResult,
  createGameChallenge, getGameCommunity, getGameHistory, respondGameChallenge, saveGameResult, setGameLevelVisibility,
} from '@/services/games';
import { Check, Dices, History, RotateCcw, Send, Sparkles, Swords, Trophy, X } from 'lucide-react';

const gameNames: Record<GameKey, string> = {
  tic_tac_toe: 'إكس-أو',
  rock_paper_scissors: 'حجر ورقة مقص',
  number_guess: 'تحدي الرقم',
  memory_sequence: 'تحدي الذاكرة',
  seega: 'سيجا',
  math_levels: 'تحدي الحساب',
};
const outcomeLabels: Record<GameOutcome, string> = { win: 'فوز', loss: 'خسارة', draw: 'تعادل' };
const difficultyLabels: Record<GameDifficulty, string> = { easy: 'سهل', medium: 'متوسط', hard: 'صعب' };
const outcomeColors: Record<GameOutcome, string> = {
  win: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300',
  loss: 'bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300',
  draw: 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300',
};
const gameOptions: Array<{ key: GameKey; emoji: string; summary: string; instructions: string }> = [
  { key: 'tic_tac_toe', emoji: '×○', summary: 'جولة استراتيجية ضد الكمبيوتر.', instructions: 'اختر مربعًا لتكوين ثلاثة رموز متتالية قبل الكمبيوتر.' },
  { key: 'rock_paper_scissors', emoji: '✊', summary: 'جولات سريعة وحظ وتوقع.', instructions: 'اختر حجرًا أو ورقة أو مقصًا؛ الحجر يهزم المقص، والمقص يهزم الورقة، والورقة تهزم الحجر.' },
  { key: 'number_guess', emoji: '🔢', summary: 'الكمبيوتر يخفي رقمًا وعليك اكتشافه.', instructions: 'أدخل رقمًا، وستظهر لك إشارة أعلى أو أقل حتى تصيب الرقم قبل نفاد المحاولات.' },
  { key: 'memory_sequence', emoji: '🧠', summary: 'اختبر ذاكرتك في تحدٍ قصير.', instructions: 'شاهد تسلسل الألوان الذي يعرضه الكمبيوتر ثم اضغط الألوان بالترتيب نفسه.' },
  { key: 'seega', emoji: '⚫', summary: 'ابدأ التحريك بثلاث قطع مرصوصة لكل لاعب.', instructions: 'تبدأ قطع الكمبيوتر في الصف العلوي وقطعك في الصف السفلي. حرّك قطعة في كل دور إلى خانة فارغة؛ الفوز لثلاث قطع في صف أفقي أو عمودي فقط، ولا تُحسب الأقطار.' },
  { key: 'math_levels', emoji: '🧮', summary: 'مواسم متتابعة، في كل موسم 50 مستوى.', instructions: 'حل ثلاثة أسئلة لفتح المستوى التالي. استنتج القيم من معادلات تستخدم رموز الحيوانات والزهور والطيور والطبيعة، وتزداد صعوبة مع كل موسم.' },
];
const victorySparks = [
  { left: '14%', top: '28%', delay: '0ms' }, { left: '28%', top: '68%', delay: '90ms' },
  { left: '42%', top: '20%', delay: '170ms' }, { left: '58%', top: '74%', delay: '40ms' },
  { left: '72%', top: '30%', delay: '130ms' }, { left: '86%', top: '62%', delay: '210ms' },
  { left: '20%', top: '48%', delay: '250ms' }, { left: '80%', top: '48%', delay: '60ms' },
];

function playVictorySound() {
  try {
    const AudioContextClass = window.AudioContext;
    if (!AudioContextClass) return;
    const context = new AudioContextClass();
    const master = context.createGain();
    master.gain.value = 0.16;
    master.connect(context.destination);
    const now = context.currentTime;
    [523.25, 659.25, 783.99, 1046.5].forEach((frequency, index) => {
      const start = now + index * 0.13;
      const oscillator = context.createOscillator();
      const volume = context.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.value = frequency;
      volume.gain.setValueAtTime(0.0001, start);
      volume.gain.exponentialRampToValueAtTime(0.8, start + 0.025);
      volume.gain.exponentialRampToValueAtTime(0.0001, start + 0.24);
      oscillator.connect(volume);
      volume.connect(master);
      oscillator.start(start);
      oscillator.stop(start + 0.25);
    });
    void context.resume().catch(() => undefined);
    window.setTimeout(() => { void context.close().catch(() => undefined); }, 1100);
  } catch {
    // Keep the victory animation available if the browser blocks Web Audio.
  }
}

function TTTBoard({ difficulty, onFinish }: { difficulty: GameDifficulty; onFinish: (result: GameOutcome) => void }) {
  const [board, setBoard] = useState<string[]>(Array(9).fill(''));
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<GameOutcome | null>(null);
  const [winningCells, setWinningCells] = useState<number[]>([]);
  const [message, setMessage] = useState('ابدأ الجولة — دورك');
  const recorded = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const findWinner = (cells: string[]) => {
    const lines = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
    for (const line of lines) if (cells[line[0]] && cells[line[0]] === cells[line[1]] && cells[line[1]] === cells[line[2]]) return { mark: cells[line[0]], line };
    return null;
  };
  const complete = (cells: string[]) => {
    const winner = findWinner(cells);
    let result: GameOutcome | null = null;
    if (winner) {
      result = winner.mark === 'X' ? 'win' : 'loss';
      setWinningCells(winner.line);
      setMessage(result === 'win' ? 'فزت بالجولة! أحسنت 🎉' : 'فاز الكمبيوتر — جولة أخرى؟');
    } else if (cells.every(Boolean)) {
      result = 'draw';
      setMessage('تعادل جميل! جرب جولة أخرى');
    }
    if (result) {
      setOutcome(result);
      if (!recorded.current) { recorded.current = true; onFinish(result); }
      return true;
    }
    return false;
  };
  const cpuChoice = (cells: string[]) => {
    const empty = cells.map((value, i) => value ? -1 : i).filter((i) => i >= 0);
    if (difficulty === 'easy') return empty[Math.floor(Math.random() * empty.length)];
    const winningMove = (mark: string) => empty.find((i) => { const next = [...cells]; next[i] = mark; return findWinner(next)?.mark === mark; });
    const win = winningMove('O');
    if (win !== undefined) return win;
    const block = winningMove('X');
    if (block !== undefined) return block;
    if (difficulty === 'medium') {
      if (empty.includes(4)) return 4;
      const edgesOrCorners = empty.filter((i) => [0,2,6,8].includes(i));
      return edgesOrCorners[Math.floor(Math.random() * edgesOrCorners.length)] ?? empty[0];
    }
    const minimax = (state: string[], maximize: boolean, depth: number): number => {
      const won = findWinner(state);
      if (won?.mark === 'O') return 10 - depth;
      if (won?.mark === 'X') return depth - 10;
      if (state.every(Boolean)) return 0;
      const moves = state.map((value, i) => value ? -1 : i).filter((i) => i >= 0);
      const scores = moves.map((i) => {
        const next = [...state]; next[i] = maximize ? 'O' : 'X';
        return minimax(next, !maximize, depth + 1);
      });
      return maximize ? Math.max(...scores) : Math.min(...scores);
    };
    return empty.reduce((best, i) => {
      const next = [...cells]; next[i] = 'O';
      const score = minimax(next, false, 0);
      return score > best.score ? { index: i, score } : best;
    }, { index: empty[0], score: -Infinity }).index;
  };
  const choose = (index: number) => {
    if (busy || outcome || board[index]) return;
    const afterPlayer = [...board]; afterPlayer[index] = 'X'; setBoard(afterPlayer);
    if (complete(afterPlayer)) return;
    setBusy(true); setMessage('الكمبيوتر يفكر…');
    timer.current = setTimeout(() => {
      const afterCpu = [...afterPlayer]; afterCpu[cpuChoice(afterPlayer)] = 'O';
      setBoard(afterCpu); setBusy(false);
      if (!complete(afterCpu)) setMessage('دورك الآن');
    }, 320);
  };
  const restart = () => {
    if (timer.current) clearTimeout(timer.current);
    setBoard(Array(9).fill('')); setBusy(false); setOutcome(null); setWinningCells([]); setMessage('ابدأ الجولة — دورك'); recorded.current = false;
  };

  return <div className="mx-auto max-w-sm text-center">
    <div className="mb-4 flex items-center justify-center gap-4 text-sm"><span className="font-semibold text-brand-700 dark:text-brand-300">أنت ×</span><span className="text-neutral-300">•</span><span className="font-semibold text-amber-600 dark:text-amber-300">الكمبيوتر ○</span></div>
    <div className="mx-auto grid max-w-[300px] grid-cols-3 gap-2.5" dir="ltr">
      {board.map((mark, index) => <button key={index} type="button" onClick={() => choose(index)} disabled={!!mark || busy || !!outcome} aria-label={`المربع ${index + 1}`} className={`aspect-square rounded-2xl border text-5xl font-bold shadow-sm transition hover:-translate-y-0.5 disabled:cursor-default disabled:hover:translate-y-0 ${winningCells.includes(index) ? 'border-emerald-400 bg-emerald-50 dark:bg-emerald-500/15' : 'border-sand-200 bg-sand-50 hover:bg-brand-50 dark:border-neutral-700 dark:bg-neutral-800 dark:hover:bg-neutral-700'} ${mark === 'X' ? 'text-brand-700 dark:text-brand-300' : 'text-amber-600 dark:text-amber-300'}`}>{mark === 'X' ? '×' : mark === 'O' ? '○' : ''}</button>)}
    </div>
    <p className="mt-4 min-h-6 text-sm font-semibold text-neutral-600 dark:text-neutral-300" aria-live="polite">{message}</p>
    <Button variant="secondary" size="sm" onClick={restart} className="mt-2"><RotateCcw size={15} /> جولة جديدة</Button>
  </div>;
}

const moves = [
  { id: 'rock', label: 'حجر', emoji: '✊' },
  { id: 'paper', label: 'ورقة', emoji: '✋' },
  { id: 'scissors', label: 'مقص', emoji: '✌️' },
] as const;
type Move = typeof moves[number]['id'];
const beats: Record<Move, Move> = { rock: 'scissors', paper: 'rock', scissors: 'paper' };
const counters: Record<Move, Move> = { rock: 'paper', paper: 'scissors', scissors: 'rock' };

function RPSGame({ difficulty, onFinish }: { difficulty: GameDifficulty; onFinish: (result: GameOutcome) => void }) {
  const [last, setLast] = useState<{ player: Move; cpu: Move; outcome: GameOutcome } | null>(null);
  const [message, setMessage] = useState('اختر حركتك لبدء الجولة');
  const [rounds, setRounds] = useState(0);
  const history = useRef<Move[]>([]);
  const play = (player: Move) => {
    const random = () => moves[Math.floor(Math.random() * moves.length)].id;
    let cpu = random();
    if (difficulty !== 'easy' && history.current.length) {
      const counts = new Map<Move, number>();
      [...history.current.slice(-8), player].forEach((move) => counts.set(move, (counts.get(move) || 0) + 1));
      const frequent: Move = Array.from(counts.entries()).sort((a,b) => b[1] - a[1])[0][0];
      if (difficulty === 'hard' || Math.random() < 0.55) cpu = counters[frequent];
    }
    let result: GameOutcome = player === cpu ? 'draw' : beats[player] === cpu ? 'win' : 'loss';
    history.current = [...history.current, player]; setRounds((value) => value + 1);
    setLast({ player, cpu, outcome: result });
    setMessage(result === 'win' ? 'فزت بالجولة! 🎉' : result === 'loss' ? 'فاز الكمبيوتر — حاول مرة أخرى' : 'تعادل!');
    onFinish(result);
  };
  const reset = () => { setLast(null); setMessage('اختر حركتك لبدء الجولة'); setRounds(0); history.current = []; };
  const label = (move: Move) => moves.find((item) => item.id === move)?.label;
  return <div className="mx-auto max-w-xl text-center">
    <p className="mb-5 text-sm text-neutral-500 dark:text-neutral-400">اختر حركة، ثم اكشف حركة الكمبيوتر</p>
    <div className="grid grid-cols-3 gap-3">
      {moves.map(({ id, label: moveLabel, emoji }) => <button key={id} type="button" onClick={() => play(id)} className="rounded-2xl border border-sand-200 bg-sand-50 px-3 py-5 transition hover:-translate-y-1 hover:border-brand-300 hover:bg-brand-50 dark:border-neutral-700 dark:bg-neutral-800 dark:hover:bg-neutral-700"><span className="block text-4xl">{emoji}</span><span className="mt-2 block text-sm font-semibold">{moveLabel}</span></button>)}
    </div>
    <p className="mt-5 min-h-6 font-semibold text-neutral-700 dark:text-neutral-200" aria-live="polite">{message}</p>
    {last && <div className="mx-auto mt-2 flex w-fit items-center gap-3 rounded-xl bg-sand-50 px-4 py-2 text-sm dark:bg-neutral-800"><span>أنت: <b>{label(last.player)}</b></span><span className="text-neutral-400">—</span><span>الكمبيوتر: <b>{label(last.cpu)}</b></span></div>}
    <div className="mt-4 flex items-center justify-center gap-3"><span className="text-xs text-neutral-500">الجولات: {rounds}</span><Button variant="secondary" size="sm" onClick={reset}><RotateCcw size={15} /> تصفير الجولة</Button></div>
  </div>;
}

const numberChallenge: Record<GameDifficulty, { max: number; attempts: number }> = {
  easy: { max: 20, attempts: 6 },
  medium: { max: 50, attempts: 7 },
  hard: { max: 100, attempts: 7 },
};

function NumberGuessGame({ difficulty, onFinish }: { difficulty: GameDifficulty; onFinish: (result: GameOutcome) => void }) {
  const { max, attempts: maxAttempts } = numberChallenge[difficulty];
  const [secret, setSecret] = useState<number | null>(null);
  const [guess, setGuess] = useState('');
  const [attempts, setAttempts] = useState(0);
  const [finished, setFinished] = useState(false);
  const [message, setMessage] = useState('ابدأ التحدي ثم حاول معرفة الرقم');
  const recorded = useRef(false);
  const start = () => {
    setSecret(Math.floor(Math.random() * max) + 1);
    setGuess(''); setAttempts(0); setFinished(false); recorded.current = false;
    setMessage(`اختر رقمًا من 1 إلى ${max}`);
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = Number(guess);
    if (secret === null || finished || !Number.isInteger(value) || value < 1 || value > max) return;
    const used = attempts + 1;
    setAttempts(used); setGuess('');
    let result: GameOutcome | null = null;
    if (value === secret) { result = 'win'; setMessage(`أصبت الرقم ${secret}! أحسنت 🎉`); }
    else if (used >= maxAttempts) { result = 'loss'; setMessage(`انتهت المحاولات، كان الرقم ${secret}`); }
    else setMessage(value < secret ? `الرقم أكبر — بقيت ${maxAttempts - used} محاولات` : `الرقم أصغر — بقيت ${maxAttempts - used} محاولات`);
    if (result) { setFinished(true); if (!recorded.current) { recorded.current = true; onFinish(result); } }
  };
  return <div className="mx-auto max-w-md text-center">
    <div className="mb-5 rounded-2xl bg-indigo-50 px-4 py-5 dark:bg-indigo-500/10"><p className="text-sm text-neutral-500 dark:text-neutral-400">نطاق الرقم</p><p className="mt-1 text-3xl font-bold tracking-wide text-indigo-700 dark:text-indigo-300">1 — {max}</p><p className="mt-2 text-xs text-neutral-500">المحاولات: {attempts} / {maxAttempts}</p></div>
    <form onSubmit={submit} className="flex gap-2">
      <input type="number" min={1} max={max} value={guess} onChange={(event) => setGuess(event.target.value)} disabled={secret === null || finished} required placeholder="اكتب تخمينك" className="min-w-0 flex-1 rounded-xl border border-sand-300 bg-white px-4 py-2.5 text-center text-lg outline-none focus:border-brand-500 dark:border-neutral-700 dark:bg-neutral-800" />
      <Button type="submit" disabled={secret === null || finished || !guess}>تخمين</Button>
    </form>
    <p className="mt-4 min-h-6 text-sm font-semibold text-neutral-700 dark:text-neutral-200" aria-live="polite">{message}</p>
    <Button variant="secondary" size="sm" onClick={start} className="mt-2"><RotateCcw size={15} /> {secret === null || finished ? 'ابدأ تحديًا جديدًا' : 'إعادة التحدي'}</Button>
  </div>;
}

const memoryTiles = [
  { name: 'الأحمر', color: 'bg-rose-500' },
  { name: 'الأزرق', color: 'bg-sky-500' },
  { name: 'الأصفر', color: 'bg-amber-400' },
  { name: 'الأخضر', color: 'bg-emerald-500' },
];
const memoryLength: Record<GameDifficulty, number> = { easy: 4, medium: 6, hard: 8 };

function MemoryGame({ difficulty, onFinish }: { difficulty: GameDifficulty; onFinish: (result: GameOutcome) => void }) {
  const length = memoryLength[difficulty];
  const [sequence, setSequence] = useState<number[]>([]);
  const [activeTile, setActiveTile] = useState<number | null>(null);
  const [showing, setShowing] = useState(false);
  const [canAnswer, setCanAnswer] = useState(false);
  const [inputCount, setInputCount] = useState(0);
  const [message, setMessage] = useState('ابدأ التحدي لمشاهدة تسلسل الألوان');
  const timerIds = useRef<number[]>([]);
  const runId = useRef(0);
  const recorded = useRef(false);
  useEffect(() => () => { runId.current++; timerIds.current.forEach(window.clearTimeout); }, []);
  const wait = (ms: number) => new Promise<void>((resolve) => {
    const timerId = window.setTimeout(() => { timerIds.current = timerIds.current.filter((id) => id !== timerId); resolve(); }, ms);
    timerIds.current.push(timerId);
  });
  const start = async () => {
    runId.current++; const currentRun = runId.current;
    timerIds.current.forEach(window.clearTimeout); timerIds.current = [];
    const nextSequence = Array.from({ length }, () => Math.floor(Math.random() * memoryTiles.length));
    setSequence(nextSequence); setInputCount(0); setCanAnswer(false); setShowing(true); setActiveTile(null); recorded.current = false;
    setMessage('شاهد الألوان واحفظ ترتيبها…');
    for (const tile of nextSequence) {
      await wait(350);
      if (runId.current !== currentRun) return;
      setActiveTile(tile);
      await wait(550);
      if (runId.current !== currentRun) return;
      setActiveTile(null);
    }
    if (runId.current !== currentRun) return;
    setShowing(false); setCanAnswer(true); setMessage(`الآن كرر التسلسل: ${length} ألوان`);
  };
  const tapTile = (tile: number) => {
    if (!canAnswer || showing || recorded.current) return;
    const index = inputCount;
    setInputCount(index + 1);
    if (sequence[index] !== tile) {
      recorded.current = true; setCanAnswer(false); setMessage('لم يطابق الترتيب — جرب مرة أخرى'); onFinish('loss'); return;
    }
    if (index + 1 === sequence.length) {
      recorded.current = true; setCanAnswer(false); setMessage('ذاكرتك ممتازة! أكملت التسلسل 🎉'); onFinish('win'); return;
    }
    setMessage(`صحيح! بقي ${sequence.length - index - 1} ألوان`);
  };
  return <div className="mx-auto max-w-sm text-center">
    <p className="mb-4 text-sm text-neutral-500 dark:text-neutral-400">تسلسل من {length} ألوان</p>
    <div className="mx-auto grid max-w-[250px] grid-cols-2 gap-3">
      {memoryTiles.map((tile, index) => <button key={tile.name} type="button" aria-label={tile.name} onClick={() => tapTile(index)} disabled={!canAnswer || showing} className={`aspect-square rounded-2xl ${tile.color} transition duration-150 disabled:cursor-default ${activeTile === index ? 'scale-105 opacity-100 ring-4 ring-neutral-700/30 shadow-lg' : canAnswer ? 'opacity-80 hover:scale-[1.03] hover:opacity-100' : 'opacity-50'}`} />)}
    </div>
    <p className="mt-4 min-h-6 text-sm font-semibold text-neutral-700 dark:text-neutral-200" aria-live="polite">{message}</p>
    <Button variant="secondary" size="sm" onClick={() => void start()} disabled={showing}><Sparkles size={15} /> {sequence.length ? 'تحدٍ جديد' : 'ابدأ التحدي'}</Button>
  </div>;
}

const seegaLines = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8]];
const initialSeegaBoard = ['O','O','O','','','','X','X','X'];
type SeegaMove = { from: number | null; to: number };

function seegaActions(board: string[], player: 'X' | 'O'): SeegaMove[] {
  const placed = board.filter((piece) => piece === player).length;
  const result: SeegaMove[] = [];
  if (placed < 3) {
    board.forEach((piece, to) => { if (!piece) result.push({ from: null, to }); });
    return result;
  }
  board.forEach((piece, from) => {
    if (piece !== player) return;
    board.forEach((target, to) => { if (!target) result.push({ from, to }); });
  });
  return result;
}

function applySeegaMove(board: string[], move: SeegaMove, player: 'X' | 'O') {
  const next = [...board];
  if (move.from !== null) next[move.from] = '';
  next[move.to] = player;
  return next;
}

function seegaWinner(board: string[], moved: { X: boolean; O: boolean } = { X: true, O: true }): 'X' | 'O' | null {
  for (const line of seegaLines) {
    const player = board[line[0]] as 'X' | 'O';
    if (player && moved[player] && board[line[1]] === player && board[line[2]] === player) return player;
  }
  return null;
}

function evaluateSeega(board: string[]): number {
  let score = 0;
  for (const line of seegaLines) {
    const pieces = line.map((point) => board[point]);
    const cpu = pieces.filter((piece) => piece === 'O').length;
    const human = pieces.filter((piece) => piece === 'X').length;
    if (!human) score += cpu === 2 ? 14 : cpu === 1 ? 3 : 0;
    if (!cpu) score -= human === 2 ? 14 : human === 1 ? 3 : 0;
  }
  if (board[4] === 'O') score += 1;
  if (board[4] === 'X') score -= 1;
  return score;
}

function searchSeega(board: string[], turn: 'X' | 'O', depth: number, alpha: number, beta: number): number {
  const winner = seegaWinner(board);
  if (winner === 'O') return 100 + depth;
  if (winner === 'X') return -100 - depth;
  const actions = seegaActions(board, turn);
  if (!actions.length) return turn === 'O' ? -90 - depth : 90 + depth;
  if (!depth) return evaluateSeega(board);

  if (turn === 'O') {
    let best = -Infinity;
    for (const action of actions) {
      best = Math.max(best, searchSeega(applySeegaMove(board, action, 'O'), 'X', depth - 1, alpha, beta));
      alpha = Math.max(alpha, best);
      if (beta <= alpha) break;
    }
    return best;
  }
  let best = Infinity;
  for (const action of actions) {
    best = Math.min(best, searchSeega(applySeegaMove(board, action, 'X'), 'O', depth - 1, alpha, beta));
    beta = Math.min(beta, best);
    if (beta <= alpha) break;
  }
  return best;
}

function chooseSeegaMove(board: string[], difficulty: GameDifficulty): SeegaMove | null {
  const actions = seegaActions(board, 'O');
  if (!actions.length) return null;
  if (difficulty === 'easy') return actions[Math.floor(Math.random() * actions.length)];
  let best = -Infinity;
  let choices: SeegaMove[] = [];
  const depth = difficulty === 'medium' ? 2 : 5;
  for (const action of actions) {
    const score = searchSeega(applySeegaMove(board, action, 'O'), 'X', depth - 1, -Infinity, Infinity);
    if (score > best) { best = score; choices = [action]; }
    else if (score === best) choices.push(action);
  }
  return choices[Math.floor(Math.random() * choices.length)];
}

function SeegaGame({ difficulty, onFinish }: { difficulty: GameDifficulty; onFinish: (result: GameOutcome) => void }) {
  const [board, setBoard] = useState<string[]>(() => [...initialSeegaBoard]);
  const [selected, setSelected] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<GameOutcome | null>(null);
  const [hasMoved, setHasMoved] = useState({ X: false, O: false });
  const [movesPlayed, setMovesPlayed] = useState(0);
  const [message, setMessage] = useState('حرّك إحدى قطعك إلى خانة فارغة — أنت تبدأ');
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recorded = useRef(false);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const concludeTurn = (nextBoard: string[], nextMoveCount: number, nextPlayer: 'X' | 'O', nextHasMoved: { X: boolean; O: boolean }) => {
    setBoard(nextBoard); setSelected(null); setMovesPlayed(nextMoveCount); setHasMoved(nextHasMoved);
    const winner = seegaWinner(nextBoard, nextHasMoved);
    let result: GameOutcome | null = winner === 'X' ? 'win' : winner === 'O' ? 'loss' : null;
    if (!result && nextMoveCount >= 40) result = 'draw';
    if (!result && !seegaActions(nextBoard, nextPlayer).length) result = nextPlayer === 'X' ? 'loss' : 'win';
    if (result) {
      setOutcome(result);
      setMessage(result === 'win' ? 'فزت بالسيجا! أحسنت 🎉' : result === 'loss' ? 'فاز الكمبيوتر — جرب مرة أخرى' : 'انتهت الجولة بالتعادل');
      if (!recorded.current) { recorded.current = true; onFinish(result); }
      return true;
    }
    setMessage(nextPlayer === 'X' ? 'دورك — اختر خانة أو قطعة لتحريكها' : 'الكمبيوتر يفكر…');
    return false;
  };

  const runComputer = (current: string[], moveCount: number, moved: { X: boolean; O: boolean }) => {
    setBusy(true);
    timer.current = setTimeout(() => {
      const action = chooseSeegaMove(current, difficulty);
      if (!action) { concludeTurn(current, moveCount, 'O', moved); setBusy(false); return; }
      const next = applySeegaMove(current, action, 'O');
      const count = moveCount + 1;
      const nextHasMoved = { ...moved, O: true };
      concludeTurn(next, count, 'X', nextHasMoved);
      setBusy(false);
    }, 350);
  };

  const play = (point: number) => {
    if (busy || outcome) return;
    let action: SeegaMove | null = null;
    if (selected === null) {
      if (board[point] === 'X' && seegaActions(board, 'X').some((move) => move.from === point)) {
        setSelected(point); setMessage('اختر أي خانة فارغة لنقل القطعة إليها');
      } else setMessage('اختر إحدى قطعك التي لها حركة متاحة');
      return;
    } else if (board[point] === 'X') {
      setSelected(point); setMessage('اختر أي خانة فارغة لنقل القطعة إليها'); return;
    } else if (!board[point]) {
      action = { from: selected, to: point };
    } else {
      setMessage('اختر خانة فارغة لنقل القطعة إليها'); return;
    }
    const next = applySeegaMove(board, action, 'X');
    const count = movesPlayed + 1;
    const nextHasMoved = { ...hasMoved, X: true };
    const ended = concludeTurn(next, count, 'O', nextHasMoved);
    if (!ended) runComputer(next, count, nextHasMoved);
  };

  const restart = () => {
    if (timer.current) clearTimeout(timer.current);
    setBoard([...initialSeegaBoard]); setSelected(null); setBusy(false); setOutcome(null); setHasMoved({ X: false, O: false }); setMovesPlayed(0);
    setMessage('حرّك إحدى قطعك إلى خانة فارغة — أنت تبدأ'); recorded.current = false;
  };

  return <div className="mx-auto max-w-sm text-center">
    <div className="mb-4 flex items-center justify-center gap-4 text-sm"><span className="font-semibold text-brand-700 dark:text-brand-300">أنت ● <small className="font-normal text-neutral-500">{board.filter((piece) => piece === 'X').length}/3</small></span><span className="text-neutral-300">•</span><span className="font-semibold text-amber-600 dark:text-amber-300">الكمبيوتر ○ <small className="font-normal text-neutral-500">{board.filter((piece) => piece === 'O').length}/3</small></span></div>
    <div className="mx-auto grid max-w-[300px] grid-cols-3 gap-2.5" dir="ltr">
      {board.map((piece, point) => <button key={point} type="button" onClick={() => play(point)} disabled={busy || !!outcome} aria-label={`الخانة ${point + 1}`} className={`aspect-square rounded-2xl border text-4xl font-bold shadow-sm transition disabled:cursor-default ${selected === point ? 'border-brand-500 bg-brand-100 ring-4 ring-brand-200/60 dark:bg-brand-500/20' : selected !== null && !piece ? 'border-emerald-400 bg-emerald-50 dark:bg-emerald-500/10' : 'border-sand-200 bg-sand-50 hover:bg-brand-50 dark:border-neutral-700 dark:bg-neutral-800 dark:hover:bg-neutral-700'} ${piece === 'X' ? 'text-brand-700 dark:text-brand-300' : 'text-amber-600 dark:text-amber-300'}`}>{piece === 'X' ? '●' : piece === 'O' ? '○' : ''}</button>)}
    </div>
    <p className="mt-4 min-h-6 text-sm font-semibold text-neutral-600 dark:text-neutral-300" aria-live="polite">{message}</p>
    <p className="mb-2 text-xs text-neutral-400">التحريك · {movesPlayed}/40 — الفوز أفقيًا أو رأسيًا فقط</p>
    <Button variant="secondary" size="sm" onClick={restart}><RotateCcw size={15} /> لعبة جديدة</Button>
  </div>;
}

interface MathQuestion { prompt: string; answer: number; instruction?: string; isShapePuzzle?: boolean }

function makeMathQuestion(level: number): MathQuestion {
  const random = (min: number, max: number) => Math.floor(Math.random() * (max - min + 1)) + min;
  const season = Math.ceil(level / 50);
  const seasonLevel = ((level - 1) % 50) + 1;
  const symbolGroups = [
    ['🐱', '🐶', '🐰', '🦊', '🐻', '🐼', '🦁', '🐸'],
    ['🌸', '🌹', '🌻', '🌷', '🌼', '🌺', '🍀', '🌵'],
    ['🐦', '🦉', '🦜', '🦚', '🦆', '🕊️', '🦅', '🐧'],
    ['🌙', '☀️', '⭐', '🌈', '☁️', '❄️', '🔥', '🌊'],
  ];
  const group = symbolGroups[(season - 1) % symbolGroups.length];
  const symbols = [...group].sort(() => Math.random() - 0.5).slice(0, 3);
  // مسائل الأشكال تظهر من البداية وتزداد نسبتها وتعقيدها مع كل موسم.
  if (Math.random() < Math.min(0.42 + season * 0.06 + seasonLevel * 0.002, 0.82)) {
    const maxValue = Math.min(8 + season * 2 + Math.floor(seasonLevel / 10), 99);
    const first = random(2, maxValue);
    const second = random(2, maxValue);
    const target = random(2, maxValue);
    const factor = seasonLevel >= 35 ? random(2, Math.min(5, season + 2)) : 1;
    const firstEquation = seasonLevel < 10 ? `${symbols[0]} + ${symbols[0]} = ${first * 2}` : `${symbols[0]} × ${factor + 1} = ${first * (factor + 1)}`;
    const secondEquation = seasonLevel < 20 ? `${symbols[1]} + ${symbols[0]} = ${second + first}` : `${symbols[1]} × 2 + ${symbols[0]} = ${second * 2 + first}`;
    const targetEquation = seasonLevel < 35 ? `${symbols[2]} + ${symbols[1]} = ${target + second}` : `${symbols[2]} × ${factor} + ${symbols[1]} = ${target * factor + second}`;
    return {
      prompt: `${firstEquation}\n${secondEquation}\n${targetEquation}`,
      answer: target,
      instruction: `أوجد قيمة ${symbols[2]}`,
      isShapePuzzle: true,
    };
  }
  const max = Math.min(10 + season * 4 + Math.floor(seasonLevel / 5), 500);
  if (seasonLevel <= Math.max(5, 12 - season)) {
    const first = random(2, max);
    const second = random(1, max);
    const subtract = Math.random() < 0.4;
    const a = subtract ? Math.max(first, second) : first;
    const b = subtract ? Math.min(first, second) : second;
    return subtract ? { prompt: `${a} − ${b}`, answer: a - b } : { prompt: `${a} + ${b}`, answer: a + b };
  }
  if (seasonLevel <= 25) {
    const first = random(2, Math.min(12 + season, 30));
    const second = random(2, Math.min(9 + season, 25));
    return { prompt: `${first} × ${second}`, answer: first * second };
  }
  if (seasonLevel <= 38) {
    const divisor = random(2, Math.min(12 + season, 30));
    const quotient = random(2, Math.min(12 + season, 30));
    return { prompt: `${divisor * quotient} ÷ ${divisor}`, answer: quotient };
  }
  const first = random(2, Math.min(12 + season, 30));
  const second = random(2, Math.min(12 + season, 30));
  const extra = random(3, Math.min(25 + season * 5 + seasonLevel, 500));
  return { prompt: `${first} × ${second} + ${extra}`, answer: first * second + extra };
}

function MathLevelsGame({
  startLevel,
  difficulty,
  onFinish,
}: {
  startLevel: number;
  difficulty: GameDifficulty;
  onFinish: (outcome: GameOutcome, level: number) => Promise<void>;
}) {
  const [level, setLevel] = useState(startLevel);
  const [questionIndex, setQuestionIndex] = useState(1);
  const [question, setQuestion] = useState(() => makeMathQuestion(startLevel));
  const [answer, setAnswer] = useState('');
  const [revealVisible, setRevealVisible] = useState(false);
  const [attempts, setAttempts] = useState(0);
  const [status, setStatus] = useState<'playing' | 'won' | 'lost'>('playing');
  const [message, setMessage] = useState('حل ثلاثة أسئلة متتالية لاجتياز المستوى.');
  const [saving, setSaving] = useState(false);
  const recorded = useRef(false);
  const revealTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => { if (revealTimer.current) clearTimeout(revealTimer.current); }, []);

  const resetLevel = (nextLevel: number) => {
    if (revealTimer.current) clearTimeout(revealTimer.current);
    setRevealVisible(false);
    setLevel(nextLevel); setQuestionIndex(1); setQuestion(makeMathQuestion(nextLevel));
    setAnswer(''); setAttempts(0); setStatus('playing'); setSaving(false); recorded.current = false;
    setMessage('حل ثلاثة أسئلة متتالية لاجتياز المستوى.');
  };

  const finish = async (outcome: GameOutcome) => {
    if (recorded.current) return;
    recorded.current = true;
    setStatus(outcome === 'win' ? 'won' : 'lost');
    setSaving(true);
    await onFinish(outcome, level);
    setSaving(false);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (status !== 'playing' || answer.trim() === '') return;
    if (answer.trim() === 'كشف') {
      if (revealTimer.current) clearTimeout(revealTimer.current);
      setRevealVisible(true);
      setAnswer('');
      setMessage('ظهرت الإجابة الصحيحة لثانية واحدة.');
      revealTimer.current = setTimeout(() => setRevealVisible(false), 1000);
      return;
    }
    if (Number(answer) === question.answer) {
      setAnswer(''); setAttempts(0);
      if (questionIndex >= 3) {
        setMessage(`أحسنت! اجتزت المستوى ${level} وفتحنا المستوى التالي 🎉`);
        await finish('win');
      } else {
        setQuestionIndex((index) => index + 1);
        setQuestion(makeMathQuestion(level));
        setMessage('إجابة صحيحة! انتقل إلى المسألة التالية.');
      }
      return;
    }
    const usedAttempts = attempts + 1;
    setAnswer(''); setAttempts(usedAttempts);
    if (usedAttempts >= 2) {
      setMessage(`الإجابة الصحيحة كانت ${question.answer}. أعد المحاولة في المستوى نفسه.`);
      await finish('loss');
    } else setMessage('إجابة غير صحيحة؛ بقيت لك محاولة واحدة لهذا السؤال.');
  };

  return <div className="mx-auto max-w-md text-center">
      <div className="mb-5 flex items-center justify-between rounded-2xl bg-indigo-50 px-4 py-3 dark:bg-indigo-500/10"><span className="text-sm font-semibold text-neutral-600 dark:text-neutral-300">الموسم {Math.ceil(level / 50)} · المستوى {((level - 1) % 50) + 1} من 50</span><span className="text-xs text-neutral-500">السؤال {Math.min(questionIndex, 3)} / 3</span></div>
      <div className="mb-5 rounded-2xl border border-sand-200 bg-sand-50 px-4 py-7 dark:border-neutral-700 dark:bg-neutral-800"><p className="mb-2 text-xs text-neutral-500">{question.isShapePuzzle ? 'اقرأ المعادلات واستنتج قيمة كل شكل' : 'أوجد الناتج'}</p><p className={`whitespace-pre-line font-bold tracking-widest text-indigo-700 dark:text-indigo-300 ${question.isShapePuzzle ? 'text-2xl leading-relaxed sm:text-3xl' : 'text-4xl'}`} dir="ltr">{question.isShapePuzzle ? question.prompt : `${question.prompt} = ؟`}</p>{question.instruction && <p className="mt-4 text-lg font-extrabold text-violet-700 dark:text-violet-300">{question.instruction} = ؟</p>}{revealVisible && <p className="mt-3 animate-pulse text-xl font-black text-emerald-700 dark:text-emerald-300" aria-live="polite">الإجابة الصحيحة: {question.answer}</p>}</div>
      {status === 'playing' ? <form onSubmit={submit} className="flex gap-2"><input type="text" inputMode="numeric" value={answer} onChange={(event) => setAnswer(event.target.value)} autoComplete="off" required aria-label="الإجابة أو رمز كشف الحل" placeholder="الإجابة أو اكتب: كشف" className="min-w-0 flex-1 rounded-xl border border-sand-300 bg-white px-4 py-2.5 text-center text-lg outline-none focus:border-brand-500 dark:border-neutral-700 dark:bg-neutral-800" /><Button type="submit" disabled={!answer.trim()}>تحقق</Button></form> : <div className="flex flex-wrap justify-center gap-2">{status === 'won' && <Button onClick={() => resetLevel(level + 1)}>ابدأ المستوى {level + 1}</Button>}{status === 'lost' && <Button variant="secondary" onClick={() => resetLevel(level)}>أعد المستوى {level}</Button>}</div>}
      <p className={`mt-4 min-h-6 text-sm font-semibold ${status === 'lost' ? 'text-rose-600 dark:text-rose-300' : status === 'won' ? 'text-emerald-700 dark:text-emerald-300' : 'text-neutral-600 dark:text-neutral-300'}`} aria-live="polite">{saving ? 'جارٍ حفظ تقدمك…' : message}</p>
      {status === 'playing' && <p className="text-xs text-neutral-400">المستويات المتقدمة تضيف عمليات وأعدادًا أكبر ومسائل استنتاج بالأشكال.</p>}
      <p className="mt-2 text-[11px] text-neutral-400">تزداد المسائل صعوبة مع كل مستوى وموسم، وتتغير رموزها بين الحيوانات والزهور والطيور والطبيعة.</p>
      <p className="mt-1 text-[11px] text-neutral-400">الصعوبة الحالية للألعاب الأخرى: {difficultyLabels[difficulty]}</p>
  </div>;
}

export default function GamesPage() {
  const { session } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [activeGame, setActiveGame] = useState<GameKey>('tic_tac_toe');
  const [difficulty, setDifficulty] = useState<GameDifficulty>('medium');
  const [history, setHistory] = useState<GameHistory>({ totals: { wins: 0, losses: 0, draws: 0 }, results: [], math_progress: { highest_level: 0, unlocked_level: 1, season_length: 50 } });
  const [community, setCommunity] = useState<GameCommunity | null>(null);
  const [challengeEmployeeId, setChallengeEmployeeId] = useState('');
  const [challengeGame, setChallengeGame] = useState<GameKey>('tic_tac_toe');
  const [communityBusy, setCommunityBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [victoryKey, setVictoryKey] = useState(0);
  const playerScore = history.totals.wins;

  useEffect(() => {
    let cancelled = false;
    getGameHistory().then((data) => { if (!cancelled) setHistory({ ...data, math_progress: data.math_progress || { highest_level: 0, unlocked_level: 1, season_length: 50 } }); })
      .catch((error) => { if (!cancelled) toast('error', `تعذر تحميل سجل الألعاب: ${error.message}`); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [toast]);

  const refreshCommunity = useCallback(async () => {
    try { setCommunity(await getGameCommunity()); }
    catch (error) { toast('error', `تعذر تحميل تحديات الألعاب: ${error instanceof Error ? error.message : 'خطأ غير معروف'}`); }
  }, [toast]);

  useEffect(() => {
    void refreshCommunity();
    const timer = setInterval(() => { void refreshCommunity(); }, 5000);
    return () => clearInterval(timer);
  }, [refreshCommunity]);

  useEffect(() => {
    const active = community?.challenges.filter((challenge) => challenge.status === 'accepted').sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())[0];
    if (active) router.replace(`/games/challenge/${active.id}`);
  }, [community, router]);

  const toggleGameLevelVisibility = async (show: boolean) => {
    setCommunityBusy(true);
    try {
      await setGameLevelVisibility(show);
      await refreshCommunity();
      toast('success', show ? 'أصبحت نقاط فوزك ظاهرة للموظفين' : 'أخفيت نقاط فوزك عن الموظفين');
    } catch (error) { toast('error', error instanceof Error ? error.message : 'تعذر تحديث إعداد الظهور'); }
    finally { setCommunityBusy(false); }
  };

  const sendChallenge = async () => {
    if (!challengeEmployeeId) { toast('error', 'اختر الموظف الذي تريد تحديه'); return; }
    setCommunityBusy(true);
    try {
      await createGameChallenge(Number(challengeEmployeeId), challengeGame);
      await refreshCommunity();
      toast('success', 'تم إرسال طلب التحدي');
    } catch (error) { toast('error', error instanceof Error ? error.message : 'تعذر إرسال طلب التحدي'); }
    finally { setCommunityBusy(false); }
  };

  const answerChallenge = async (challenge: GameChallenge, action: 'accept' | 'decline') => {
    setCommunityBusy(true);
    try {
      const response = await respondGameChallenge(challenge.id, action);
      if (action === 'accept') {
        toast('success', 'قبلت طلب التحدي، جارٍ فتح المباراة');
        router.push(`/games/challenge/${response.id}`);
        return;
      }
      await refreshCommunity();
      toast('success', 'تم رفض طلب التحدي');
    } catch (error) { toast('error', error instanceof Error ? error.message : 'تعذر الرد على الطلب'); }
    finally { setCommunityBusy(false); }
  };

  const record = useCallback(async (game: GameKey, outcome: GameOutcome, level?: number) => {
    if (outcome === 'win') {
      setVictoryKey((key) => key + 1);
      playVictorySound();
    }
    setSaving(true);
    try {
      const result = await saveGameResult({ game, outcome, difficulty, ...(level ? { level } : {}) });
      setHistory((current) => ({
        totals: { ...current.totals, [outcome === 'win' ? 'wins' : outcome === 'loss' ? 'losses' : 'draws']: current.totals[outcome === 'win' ? 'wins' : outcome === 'loss' ? 'losses' : 'draws'] + 1 },
        results: [result, ...current.results].slice(0, 40),
        math_progress: game === 'math_levels' && outcome === 'win' && level
          ? { ...current.math_progress, highest_level: Math.max(current.math_progress.highest_level, level), unlocked_level: Math.max(current.math_progress.highest_level, level) + 1 }
          : current.math_progress,
      }));
    } catch (error) {
      toast('error', `لم يُحفظ سجل الجولة: ${error instanceof Error ? error.message : 'خطأ غير معروف'}`);
    } finally { setSaving(false); }
  }, [difficulty, toast]);

  return <AppShell>
    {victoryKey > 0 && <div key={victoryKey} aria-hidden="true" className="game-victory-overlay">
      <div className="game-victory-badge"><span>✓</span><b>فوز!</b></div>
      {victorySparks.map((spark, index) => <span key={`${victoryKey}-${index}`} className="game-victory-spark" style={{ left: spark.left, top: spark.top, animationDelay: spark.delay }}>{index % 2 ? '✦' : '✧'}</span>)}
    </div>}
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-l from-violet-800 via-indigo-800 to-brand-900 p-6 text-white shadow-lg sm:p-8">
        <div className="absolute -left-12 -top-20 h-60 w-60 rounded-full bg-white/10 blur-3xl" />
        <div className="relative flex flex-wrap items-center justify-between gap-5">
          <div><div className="mb-2 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs"><Sparkles size={14} /> استراحة قصيرة</div><h1 className="text-2xl font-bold sm:text-3xl">الألعاب والتسلية</h1><p className="mt-2 max-w-xl text-sm leading-6 text-white/75">ألعاب خفيفة وتحديات متدرجة. تابع نتائجك وتقدمك في سجل خاص بك.</p></div>
          <div className="flex items-center gap-3 rounded-2xl border border-white/15 bg-white/10 px-4 py-3"><Avatar name={session?.employee.name || ''} avatar={session?.employee.avatar} avatarImage={session?.employee.avatar_image} size="lg" /><div><b className="block text-sm">{session?.employee.name || 'الموظف'}</b><span className="mt-0.5 block text-xs text-white/75">نقاط الفوز</span></div><span className="flex h-10 min-w-10 items-center justify-center rounded-xl bg-amber-300 px-2 text-lg font-black tabular-nums text-amber-950" title="نقطة لكل فوز">{playerScore}</span></div>
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-white/15 bg-white/10"><Dices size={32} /></div>
        </div>
      </div>

      <Card title="تحديات الموظفين" subtitle="أرسل طلب لعب، أو أجب عن التحديات الواردة">
        <div className="grid gap-5 xl:grid-cols-[1fr_1.2fr_1.2fr]">
          <div className="rounded-2xl border border-sand-200 p-4 dark:border-neutral-700">
            <label className="flex cursor-pointer items-start gap-3">
              <input type="checkbox" className="mt-1 h-4 w-4 accent-brand-700" checked={community?.show_game_level ?? false} disabled={!community || communityBusy} onChange={(event) => void toggleGameLevelVisibility(event.target.checked)} />
              <span><b className="block text-sm">إظهار نقاط فوزي للموظفين</b><small className="mt-1 block leading-5 text-neutral-500">عند إيقافه تختفي نقاطك ومستواك في تحدي الحساب من قائمة الموظفين.</small></span>
            </label>
            <div className="mt-5 border-t border-sand-100 pt-4 dark:border-neutral-800">
              <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold"><Swords size={16} className="text-violet-600" /> أرسل تحديًا</h4>
              <select aria-label="اختر لعبة التحدي" value={challengeGame} onChange={(event) => setChallengeGame(event.target.value as GameKey)} className="mb-2 w-full rounded-xl border border-sand-300 bg-white px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900">
                <option value="tic_tac_toe">إكس-أو · بالتناوب</option>
                <option value="rock_paper_scissors">حجر ورقة مقص · اختيار سري</option>
                <option value="seega">سيجا · تحريك القطع</option>
              </select>
              <select aria-label="اختر موظفًا للتحدي" value={challengeEmployeeId} onChange={(event) => setChallengeEmployeeId(event.target.value)} className="mb-2 w-full rounded-xl border border-sand-300 bg-white px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900">
                <option value="">اختر الموظف</option>
                {community?.employees.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
              </select>
              <Button size="sm" onClick={() => void sendChallenge()} disabled={communityBusy || !community?.employees.length}><Send size={14} /> إرسال طلب اللعب</Button>
            </div>
          </div>

          <div className="rounded-2xl border border-sand-200 p-4 dark:border-neutral-700">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Trophy size={16} className="text-amber-500" /> الموظفون الذين يشاركون نقاطهم</h4>
            {!community?.leaderboard.length ? <p className="py-5 text-center text-sm text-neutral-400">لا توجد نقاط ظاهرة حاليًا. فعّل خيار الظهور لتظهر في القائمة.</p> : <div className="max-h-64 space-y-2 overflow-y-auto">
              {community.leaderboard.map((person, index) => <div key={person.id} className="flex items-center gap-3 rounded-xl bg-sand-50 px-3 py-2 dark:bg-neutral-800"><span className="w-5 text-center text-xs font-bold text-neutral-400">{index + 1}</span><Avatar name={person.name} avatar={person.avatar} avatarImage={person.avatar_image} size="sm" /><span className="min-w-0 flex-1 truncate text-sm font-medium">{person.name}</span><span className="text-xs font-bold text-amber-700 dark:text-amber-300">{person.wins || 0} فوز</span>{(person.math_level || 0) > 0 && <span className="text-[11px] text-violet-600 dark:text-violet-300">حساب: {person.math_level}</span>}</div>)}
            </div>}
          </div>

          <div className="rounded-2xl border border-sand-200 p-4 dark:border-neutral-700">
            <h4 className="mb-3 text-sm font-semibold">طلبات اللعب</h4>
            {!community?.challenges.length ? <p className="py-5 text-center text-sm text-neutral-400">لا توجد طلبات لعب حتى الآن.</p> : <div className="max-h-64 space-y-2 overflow-y-auto">
              {community.challenges.slice(0, 12).map((challenge) => <div key={challenge.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-sand-100 px-3 py-2 dark:border-neutral-800"><span className="min-w-0 flex-1 text-sm"><b>{challenge.is_incoming ? challenge.other_employee.name : `أنت ← ${challenge.other_employee.name}`}</b><span className="mx-1 text-neutral-400">·</span>{gameNames[challenge.game]}</span>{challenge.status === 'pending' && challenge.is_incoming ? <><button type="button" disabled={communityBusy} onClick={() => void answerChallenge(challenge, 'accept')} className="rounded-lg bg-emerald-50 p-2 text-emerald-700 hover:bg-emerald-100 disabled:opacity-50" title="قبول"><Check size={15} /></button><button type="button" disabled={communityBusy} onClick={() => void answerChallenge(challenge, 'decline')} className="rounded-lg bg-rose-50 p-2 text-rose-700 hover:bg-rose-100 disabled:opacity-50" title="رفض"><X size={15} /></button></> : challenge.status === 'accepted' ? <button type="button" onClick={() => router.push(`/games/challenge/${challenge.id}`)} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-emerald-700">ادخل المباراة</button> : <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${challenge.status === 'declined' ? 'bg-neutral-100 text-neutral-500' : 'bg-amber-50 text-amber-700'}`}>{challenge.status === 'declined' ? 'مرفوض' : 'بانتظار الرد'}</span>}</div>)}
            </div>}
          </div>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(280px,0.8fr)]">
        <Card title="اختر اللعبة" subtitle={`مرحبًا ${session?.employee.name || ''}، سجل النتائج خاص بحسابك`}>
          <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {gameOptions.map((game) => <button key={game.key} type="button" onClick={() => setActiveGame(game.key)} aria-pressed={activeGame === game.key} className={`rounded-2xl border p-4 text-right transition ${activeGame === game.key ? 'border-brand-400 bg-brand-50 ring-2 ring-brand-100 dark:bg-brand-500/10 dark:ring-brand-500/15' : 'border-sand-200 hover:bg-sand-50 dark:border-neutral-700 dark:hover:bg-neutral-800'}`}><span className="flex items-center gap-3"><span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-violet-100 text-2xl text-violet-700 dark:bg-violet-500/15 dark:text-violet-300">{game.emoji}</span><span><b className="block">{gameNames[game.key]}</b><small className="text-neutral-500">{game.summary}</small></span></span><span className="mt-3 block border-t border-sand-200/80 pt-2.5 text-xs leading-5 text-neutral-600 dark:border-neutral-700 dark:text-neutral-300"><b>طريقة اللعب:</b> {game.instructions}</span></button>)}
          </div>
          {activeGame !== 'math_levels' && <div className="mb-5 flex flex-wrap items-center gap-2">
            <span className="ml-1 text-sm font-semibold">مستوى الكمبيوتر:</span>
            {(['easy','medium','hard'] as const).map((level) => <button key={level} type="button" onClick={() => setDifficulty(level)} className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${difficulty === level ? 'bg-brand-700 text-white shadow-sm' : 'bg-sand-100 text-neutral-600 hover:bg-sand-200 dark:bg-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-700'}`}>{difficultyLabels[level]}</button>)}
          </div>}
          <div className="rounded-2xl border border-sand-200 bg-white p-4 dark:border-neutral-700 dark:bg-neutral-900 sm:p-6">
            {activeGame === 'tic_tac_toe' && <TTTBoard key={`ttt-${difficulty}`} difficulty={difficulty} onFinish={(result) => void record('tic_tac_toe', result)} />}
            {activeGame === 'rock_paper_scissors' && <RPSGame key={`rps-${difficulty}`} difficulty={difficulty} onFinish={(result) => void record('rock_paper_scissors', result)} />}
            {activeGame === 'number_guess' && <NumberGuessGame key={`number-${difficulty}`} difficulty={difficulty} onFinish={(result) => void record('number_guess', result)} />}
            {activeGame === 'memory_sequence' && <MemoryGame key={`memory-${difficulty}`} difficulty={difficulty} onFinish={(result) => void record('memory_sequence', result)} />}
            {activeGame === 'seega' && <SeegaGame key={`seega-${difficulty}`} difficulty={difficulty} onFinish={(result) => void record('seega', result)} />}
            {activeGame === 'math_levels' && <MathLevelsGame key="math-levels" startLevel={history.math_progress.unlocked_level} difficulty={difficulty} onFinish={(result, level) => record('math_levels', result, level)} />}
          </div>
          {saving && <p className="mt-3 text-center text-xs text-neutral-400">جارٍ حفظ نتيجة الجولة…</p>}
        </Card>

        <div className="space-y-5">
          <Card title="سجلك" subtitle="إجمالي النتائج المسجلة لك">
            <div className="mb-2 flex items-center justify-between rounded-xl bg-brand-50 px-3 py-2 text-sm dark:bg-brand-500/10"><span className="text-neutral-600 dark:text-neutral-300">نسبة الفوز</span><b className="text-brand-700 dark:text-brand-300">{history.totals.wins + history.totals.losses + history.totals.draws ? Math.round(history.totals.wins / (history.totals.wins + history.totals.losses + history.totals.draws) * 100) : 0}%</b></div>
            <div className="grid grid-cols-3 gap-2 text-center">
              {([['wins','فوز','text-emerald-700 bg-emerald-50 dark:text-emerald-300 dark:bg-emerald-500/10'],['losses','خسارة','text-rose-700 bg-rose-50 dark:text-rose-300 dark:bg-rose-500/10'],['draws','تعادل','text-amber-700 bg-amber-50 dark:text-amber-300 dark:bg-amber-500/10']] as const).map(([key,label,style]) => <div key={key} className={`rounded-xl p-3 ${style}`}><b className="block text-xl tabular-nums">{history.totals[key]}</b><span className="text-xs">{label}</span></div>)}
            </div>
          </Card>
          <Card title="آخر الجولات" subtitle="آخر 40 نتيجة">
            {loading ? <p className="py-6 text-center text-sm text-neutral-400">جارٍ تحميل السجل…</p> : history.results.length === 0 ? <div className="py-7 text-center text-sm text-neutral-500"><History size={25} className="mx-auto mb-2 opacity-50" />لا توجد جولات مسجلة بعد</div> : <div className="max-h-[380px] space-y-2 overflow-y-auto">
              {history.results.map((result: GameResult) => <div key={result.id} className="flex items-center justify-between gap-3 rounded-xl border border-sand-100 px-3 py-2.5 dark:border-neutral-800"><div className="min-w-0"><p className="truncate text-sm font-semibold">{gameNames[result.game]}</p><p className="mt-0.5 text-[11px] text-neutral-500">{result.game === 'math_levels' ? `المستوى ${result.level}` : difficultyLabels[result.difficulty]} · {new Date(result.created_at).toLocaleString('ar-OM', { dateStyle: 'short', timeStyle: 'short' })}</p></div><span className={`shrink-0 rounded-lg px-2.5 py-1 text-xs font-bold ${outcomeColors[result.outcome]}`}>{outcomeLabels[result.outcome]}</span></div>)}
            </div>}
          </Card>
        </div>
      </div>
      <p className="pb-3 text-center text-xs text-neutral-400">مستويات الصعوبة تؤثر في طريقة لعب الكمبيوتر. سجل الجولات يخص الموظف المسجل دخوله.</p>
    </div>
  </AppShell>;
}
