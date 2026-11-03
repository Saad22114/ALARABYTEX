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

export interface GameCommunityEmployee {
  id: number;
  name: string;
  avatar?: string | null;
  avatar_image?: string | null;
  wins?: number;
  math_level?: number;
}

export interface GameChallenge {
  id: number;
  requester_id: number;
  opponent_id: number;
  game: GameKey;
  status: 'pending' | 'accepted' | 'declined' | 'completed';
  created_at: string;
  updated_at: string;
  is_incoming: boolean;
  other_employee: GameCommunityEmployee;
  game_state: { board?: string[]; turn?: number; winner_id: number | null; draw: boolean; forfeit_id?: number; choices?: Record<string, 'rock' | 'paper' | 'scissors'>; has_moved?: { X: boolean; O: boolean }; moves_played?: number };
}

export interface GameCommunity {
  show_game_level: boolean;
  employees: GameCommunityEmployee[];
  leaderboard: GameCommunityEmployee[];
  challenges: GameChallenge[];
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

export function getGameCommunity(): Promise<GameCommunity> {
  return apiRequest<GameCommunity>('/games/community/');
}

export function setGameLevelVisibility(show_game_level: boolean): Promise<{ show_game_level: boolean }> {
  return apiRequest<{ show_game_level: boolean }>('/games/community/', {
    method: 'PATCH', body: JSON.stringify({ show_game_level }),
  });
}

export function createGameChallenge(opponent_id: number, game: GameKey): Promise<GameChallenge> {
  return apiRequest<GameChallenge>('/games/community/', {
    method: 'POST', body: JSON.stringify({ action: 'request', opponent_id, game }),
  });
}

export function respondGameChallenge(challenge_id: number, action: 'accept' | 'decline'): Promise<GameChallenge> {
  return apiRequest<GameChallenge>('/games/community/', {
    method: 'POST', body: JSON.stringify({ action, challenge_id }),
  });
}

export function getGameChallenge(challenge_id: number): Promise<GameChallenge> {
  return apiRequest<GameChallenge>(`/games/challenges/${challenge_id}/`);
}

export function makeGameChallengeMove(challenge_id: number, move: number | { choice: 'rock' | 'paper' | 'scissors' } | { from: number; to: number } | { action: 'forfeit' }): Promise<GameChallenge> {
  return apiRequest<GameChallenge>(`/games/challenges/${challenge_id}/`, {
    method: 'POST', body: JSON.stringify(typeof move === 'number' ? { cell: move } : move),
  });
}
