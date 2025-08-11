// Core Types
export interface Player {
  id: number;
  name: string;
  position: Position;
  team: string | null;
  bye_week: number | null;
  projected_points: number | null;
  adp: number | null;
  vorp: number | null;
  scarcity_score: number | null;
  expert_consensus_rank: number | null;
  positional_rank: number | null;
}

export interface PlayerDetailed extends Omit<Player, 'adp' | 'vorp'> {
  projections: {
    ppr: number | null;
    half_ppr: number | null;
    standard: number | null;
  };
  adp: {
    ppr: number | null;
    half_ppr: number | null;
    standard: number | null;
  };
  vorp: {
    ppr: number | null;
    half_ppr: number | null;
    standard: number | null;
  };
  raw_projections: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface Team {
  id: number;
  name: string;
  owner_name: string | null;
  league_id: number;
  draft_position: number | null;
  total_vorp: number | null;
  projected_points: number | null;
  depth_score: number | null;
  bye_week_penalty: number | null;
  playoff_probability: number | null;
}

export interface League {
  id: number;
  name: string;
  league_size: number;
  scoring_type: ScoringType;
  roster_size: number;
  starting_lineup: StartingLineup;
  draft_order: number[] | null;
  snake_draft: boolean;
}

export interface Draft {
  id: number;
  league_id: number;
  status: DraftStatus;
  current_pick: number;
  current_round: number;
  draft_date: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface DraftPick {
  id: number;
  draft_id: number;
  team_id: number;
  player_id: number | null;
  pick_number: number;
  round_number: number;
  pick_in_round: number;
  expected_value: number | null;
  opportunity_cost: number | null;
  pick_grade: string | null;
  picked_at: string | null;
  player: Player | null;
}

// Enums
export type Position = 'QB' | 'RB' | 'WR' | 'TE' | 'K' | 'DEF';
export type ScoringType = 'ppr' | 'half_ppr' | 'standard';
export type DraftStatus = 'pending' | 'in_progress' | 'completed';

// Analysis Types
export interface ScarcityAnalysis {
  position: Position;
  scoring_type: ScoringType;
  tier_breaks: number[];
  drop_off_points: number[];
  scarcity_score: number;
  player_count: number;
  analysis_date: string;
}

export interface TeamEvaluation {
  team_id: number;
  team_name: string;
  scoring_type: ScoringType;
  overall_grade: string;
  projected_points: {
    total_projected_points: number;
    positional_breakdown: Record<Position, number>;
    projected_rank_estimate: number;
  };
  vorp_analysis: {
    total_vorp: number;
    starting_lineup_vorp: number;
    positional_vorp: Record<Position, number>;
    vorp_rank_estimate: number;
  };
  depth_analysis: {
    overall_depth_score: number;
    positional_depth: Record<Position, number>;
    depth_grade: string;
  };
  bye_week_analysis: {
    total_bye_impact: number;
    worst_bye_week: number | null;
    bye_week_breakdown: Record<number, {
      players_count: number;
      starters_count: number;
      impact_score: number;
    }>;
    bye_grade: string;
  };
  positional_strength: Record<Position, {
    best_player: string;
    projected_points: number;
    estimated_rank: number;
    player_count: number;
    strength_grade: string;
  }>;
  roster_summary: Record<Position, Array<{
    name: string;
    team: string | null;
    projected_points: number | null;
    vorp: number | null;
    bye_week: number | null;
  }>>;
}

export interface DraftRecommendation {
  pick_number: number;
  team_id: number;
  recommendation: {
    player: Player;
    expected_value: number;
    opportunity_cost: number;
    pick_grade: string;
    reasoning: string;
  };
  scoring_type: ScoringType;
}

export interface SeasonSimulation {
  league_id: number;
  scoring_type: ScoringType;
  iterations: number;
  team_results: Array<{
    team_id: number;
    team_name: string;
    avg_wins: number;
    avg_losses: number;
    avg_points_for: number;
    avg_points_against: number;
    playoff_probability: number;
    championship_probability: number;
    seed_distribution: Record<number, number>;
  }>;
  league_analysis: {
    parity_score: number;
    competitive_balance: number;
    championship_favorite: string | null;
    championship_favorite_probability: number;
    playoff_lock_teams: number;
    bubble_teams: number;
  };
}

// UI Component Types
export interface StartingLineup {
  QB: number;
  RB: number;
  WR: number;
  TE: number;
  FLEX: number;
  K: number;
  DEF: number;
}

export interface FilterOptions {
  position?: Position;
  team?: string;
  minProjectedPoints?: number;
  maxADP?: number;
  availableOnly?: boolean;
}

export interface SortOption {
  field: keyof Player;
  direction: 'asc' | 'desc';
}

// API Response Types
export interface ApiResponse<T> {
  data?: T;
  error?: string;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

// Chart Data Types
export interface ChartDataPoint {
  name: string;
  value: number;
  color?: string;
}

export interface ScarcityChartData {
  position: Position;
  players: Array<{
    name: string;
    rank: number;
    projected_points: number;
    tier: number;
  }>;
}

// Draft Board Types
export interface DraftBoardCell {
  pick_number: number;
  round: number;
  pick_in_round: number;
  team_id: number;
  player: Player | null;
  is_current_pick: boolean;
  is_user_team: boolean;
}

export interface DraftBoardRow {
  round: number;
  picks: DraftBoardCell[];
}

// Notification Types
export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  duration?: number;
}

// Form Types
export interface LeagueSettings {
  name: string;
  league_size: number;
  scoring_type: ScoringType;
  roster_size: number;
  starting_lineup: StartingLineup;
  snake_draft: boolean;
}

export interface PlayerSearchFilters {
  query?: string;
  position?: Position;
  team?: string;
  available_only?: boolean;
  min_projected_points?: number;
  max_adp?: number;
}

// Utility Types
export type Grade = 'A+' | 'A' | 'A-' | 'B+' | 'B' | 'B-' | 'C+' | 'C' | 'C-' | 'D+' | 'D' | 'D-' | 'F';

export interface PositionColors {
  QB: string;
  RB: string;
  WR: string;
  TE: string;
  K: string;
  DEF: string;
}

export interface CompetitiveAdvantage {
  team_evaluation: TeamEvaluation;
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
}
