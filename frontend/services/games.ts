import { apiRequest } from './api';

export type GameKey = 'tic_tac_toe' | 'rock_paper_scissors' | 'number_guess' | 'memory_sequence' | 'seega' | 'math_levels';
export type GameOutcome = 'win' | 'loss' | 'draw';
export type GameDifficulty = 'easy' | 'medium' | 'hard';

export interface GameResult {
  id: number;
  game: GameKey;
  outcome: GameOutcome;
  difficulty: GameDifficulty;
  level: number;
  created_at: string;
}

export interface MathGameProgress {
  highest_level: number;
  unlocked_level: number;
  season_length: number;
}

export interface GameHistory {
  totals: { wins: number; losses: number; draws: number };
  results: GameResult[];
  math_progress: MathGameProgress;
}

export function getGameHistory(): Promise<GameHistory> {
  return apiRequest<GameHistory>('/games/results/');
}

export function saveGameResult(data: {
  game: GameKey;
  outcome: GameOutcome;
  difficulty: GameDifficulty;
  level?: number;
}): Promise<GameResult> {
  return apiRequest<GameResult>('/games/results/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
