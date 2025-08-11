import axios, { AxiosResponse } from 'axios';
import {
  Player,
  PlayerDetailed,
  Team,
  League,
  Draft,
  DraftPick,
  DraftRecommendation,
  TeamEvaluation,
  ScarcityAnalysis,
  SeasonSimulation,
  ScoringType,
  Position,
  ApiResponse,
  CompetitiveAdvantage,
} from '@/types';

// Create axios instance with base configuration
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Response Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// Player API
export const playerApi = {
  // Get all players with optional filters
  getPlayers: async (params?: {
    position?: Position;
    limit?: number;
    scoring_type?: ScoringType;
  }): Promise<{ players: Player[]; count: number; scoring_type: ScoringType }> => {
    const response = await api.get('/data/players', { params });
    return response.data;
  },

  // Get detailed player information
  getPlayer: async (
    playerId: number,
    scoringType: ScoringType = 'ppr'
  ): Promise<PlayerDetailed> => {
    const response = await api.get(`/data/players/${playerId}`, {
      params: { scoring_type: scoringType },
    });
    return response.data;
  },

  // Search players by name
  searchPlayers: async (
    name: string,
    scoringType: ScoringType = 'ppr'
  ): Promise<{ query: string; players: Player[]; count: number }> => {
    const response = await api.get(`/data/players/search/${encodeURIComponent(name)}`, {
      params: { scoring_type: scoringType },
    });
    return response.data;
  },

  // Get VORP rankings
  getVORPRankings: async (params?: {
    position?: Position;
    limit?: number;
    scoring_type?: ScoringType;
  }): Promise<{
    rankings: Array<{
      rank: number;
      player: Player;
      vorp: number;
      projected_points: number;
      adp: number;
    }>;
    position: string;
    scoring_type: ScoringType;
    count: number;
  }> => {
    const response = await api.get('/data/vorp-rankings', { params });
    return response.data;
  },

  // Compare multiple players
  comparePlayers: async (
    playerIds: number[],
    scoringType: ScoringType = 'ppr'
  ): Promise<{
    players: Array<{
      id: number;
      name: string;
      position: Position;
      team: string;
      projected_points: number;
      vorp: number;
      adp: number;
    }>;
    scoring_type: ScoringType;
  }> => {
    const response = await api.get('/data/player-comparison', {
      params: {
        player_ids: playerIds.join(','),
        scoring_type: scoringType,
      },
    });
    return response.data;
  },

  // Get data summary statistics
  getDataSummary: async (): Promise<{
    total_players: number;
    position_breakdown: Record<Position, number>;
    data_completeness: {
      players_with_ppr_projections: number;
      players_with_vorp: number;
      completion_rate: number;
    };
  }> => {
    const response = await api.get('/data/stats/summary');
    return response.data;
  },

  // Ingest new player data
  ingestData: async (scrapedData: any[]): Promise<{ message: string; results: any }> => {
    const response = await api.post('/data/ingest-data', scrapedData);
    return response.data;
  },
};

// Draft API
export const draftApi = {
  // Get draft recommendations for a specific pick
  getDraftRecommendations: async (
    leagueId: number,
    teamId: number,
    pickNumber: number,
    scoringType: ScoringType = 'ppr'
  ): Promise<DraftRecommendation> => {
    const response = await api.get(
      `/draft/recommendations/${leagueId}/${teamId}/${pickNumber}`,
      { params: { scoring_type: scoringType } }
    );
    return response.data;
  },

  // Get available players for draft
  getAvailablePlayers: async (
    draftId: number,
    params?: {
      position?: string;
      limit?: number;
      scoring_type?: ScoringType;
    }
  ): Promise<{
    draft_id: number;
    players: Player[];
    count: number;
  }> => {
    const response = await api.get(`/draft/available-players/${draftId}`, { params });
    return response.data;
  },

  // Simulate full draft
  simulateFullDraft: async (
    leagueId: number,
    scoringType: ScoringType = 'ppr'
  ): Promise<{
    league_id: number;
    simulation_results: any;
    scoring_type: ScoringType;
  }> => {
    const response = await api.post(`/draft/simulate-full-draft/${leagueId}`, null, {
      params: { scoring_type: scoringType },
    });
    return response.data;
  },

  // Get draft board state
  getDraftBoard: async (draftId: number): Promise<{
    draft_id: number;
    status: string;
    current_pick: number;
    current_round: number;
    picks: Array<{
      pick_number: number;
      round: number;
      team_id: number;
      player: Player | null;
      pick_grade: string | null;
      picked_at: string | null;
    }>;
  }> => {
    const response = await api.get(`/draft/draft-board/${draftId}`);
    return response.data;
  },
};

// Analysis API
export const analysisApi = {
  // Get team evaluation
  getTeamEvaluation: async (
    teamId: number,
    scoringType: ScoringType = 'ppr'
  ): Promise<TeamEvaluation> => {
    const response = await api.get(`/analysis/team-evaluation/${teamId}`, {
      params: { scoring_type: scoringType },
    });
    return response.data;
  },

  // Compare all teams in a league
  compareLeagueTeams: async (
    leagueId: number,
    scoringType: ScoringType = 'ppr'
  ): Promise<{
    league_id: number;
    scoring_type: ScoringType;
    team_count: number;
    teams: TeamEvaluation[];
    league_averages: {
      avg_projected_points: number;
      avg_total_vorp: number;
      avg_depth_score: number;
    };
  }> => {
    const response = await api.get(`/analysis/league-comparison/${leagueId}`, {
      params: { scoring_type: scoringType },
    });
    return response.data;
  },

  // Get scarcity analysis
  getScarcityAnalysis: async (params?: {
    position?: Position;
    scoring_type?: ScoringType;
  }): Promise<
    | ScarcityAnalysis
    | {
        positions: Array<{
          position: Position;
          tier_breaks: number[];
          drop_off_points: number[];
          scarcity_score: number;
          player_count: number;
        }>;
      }
  > => {
    const response = await api.get('/analysis/scarcity-analysis', { params });
    return response.data;
  },


};

export const liveDraftApi = {
  // Create a new live draft
  createDraft: async (params: {
    team_count?: number;
    user_team_id?: number;
    scoring_type?: string;
  }) => {
    const response = await api.post('/live-draft/create', params);
    return response.data;
  },

  // Get draft state
  getDraftState: async (draftId: string) => {
    const response = await api.get(`/live-draft/${draftId}/state`);
    return response.data;
  },

  // Make user pick
  makeUserPick: async (draftId: string, playerId: number) => {
    const response = await api.post(`/live-draft/${draftId}/pick`, {
      player_id: playerId
    });
    return response.data;
  },

  // Simulate bot picks
  simulateBotPicks: async (draftId: string, rounds: number = 1, strategy: string = 'scarcity_aware') => {
    const response = await api.post('/live-draft/simulate-bot-picks', {
      draft_id: draftId,
      rounds,
      strategy
    });
    return response.data;
  },

  simulateSingleBotPick: async (draftId: string, strategy: string = 'scarcity_aware') => {
    const response = await api.post('/live-draft/simulate-single-bot-pick', {
      draft_id: draftId,
      strategy
    });
    return response.data;
  },

  // Get user recommendations
  getUserRecommendations: async (draftId: string, topN: number = 5) => {
    const response = await api.get(`/live-draft/${draftId}/recommendations`, {
      params: { top_n: topN }
    });
    return response.data;
  },

  // Get available players
  getAvailablePlayers: async (draftId: string, position?: string, limit: number = 50) => {
    const response = await api.get(`/live-draft/${draftId}/available-players`, {
      params: { position, limit }
    });
    return response.data;
  },

  // Get draft board
  getDraftBoard: async (draftId: string) => {
    const response = await api.get(`/live-draft/${draftId}/draft-board`);
    return response.data;
  },

  // End draft
  endDraft: async (draftId: string) => {
    const response = await api.delete(`/live-draft/${draftId}`);
    return response.data;
  }
};

export const dynamicDraftApi = {
  // Create a new dynamic draft
  createDraft: async (params: {
    num_teams?: number;
    draft_spot?: number;
    snake?: boolean;
    scoring_mode?: string;
  }) => {
    const response = await api.post('/dynamic-draft/drafts', params);
    return response.data;
  },

  // Get draft state
  getDraftState: async (draftId: string) => {
    const response = await api.get(`/dynamic-draft/drafts/${draftId}/state`);
    return response.data;
  },

  // Get players with VORP
  getPlayersWithVorp: async (params: {
    draft_id: string;
    scoring_mode?: string;
    position?: string;
    limit?: number;
  }) => {
    const response = await api.get('/dynamic-draft/players', { params });
    return response.data;
  },

  // Get players for draft
  getPlayers: async (draftId: string) => {
    const response = await api.get('/dynamic-draft/players', { 
      params: { draft_id: draftId } 
    });
    return response.data;
  },

  // Make a pick
  makePick: async (draftId: string, playerId: number) => {
    const response = await api.post(`/dynamic-draft/drafts/${draftId}/pick`, {
      player_id: playerId
    });
    return response.data;
  },

  // Get draft advice
  getAdvice: async (draftId: string, teamId: number = 1, mode: string = 'robust') => {
    const response = await api.get(`/dynamic-draft/drafts/${draftId}/advice`, {
      params: { team_id: teamId, mode }
    });
    return response.data;
  },

  // Get availability forecast
  getAvailabilityForecast: async (draftId: string, teamId: number = 1, numSims: number = 500) => {
    const response = await api.get(`/dynamic-draft/drafts/${draftId}/availability`, {
      params: { team_id: teamId, num_sims: numSims }
    });
    return response.data;
  },

  // Get next pick line
  getNextPickLine: async (draftId: string) => {
    const response = await api.get(`/dynamic-draft/drafts/${draftId}/next-pick-line`);
    return response.data;
  },

  // Delete draft
  deleteDraft: async (draftId: string) => {
    const response = await api.delete(`/dynamic-draft/drafts/${draftId}`);
    return response.data;
  },

  // List active drafts
  listActiveDrafts: async () => {
    const response = await api.get('/dynamic-draft/drafts');
    return response.data;
  }
};

// Utility functions
export const apiUtils = {
  // Handle API errors consistently
  handleError: (error: any): string => {
    if (error.response?.data?.detail) {
      return error.response.data.detail;
    }
    if (error.response?.data?.message) {
      return error.response.data.message;
    }
    if (error.message) {
      return error.message;
    }
    return 'An unexpected error occurred';
  },

  // Check if API is healthy
  healthCheck: async (): Promise<{ status: string }> => {
    const response = await api.get('/health');
    return response.data;
  },

  // Get API version info
  getVersion: async (): Promise<{ message: string; version: string }> => {
    const response = await api.get('/');
    return response.data;
  },
};

export default api;
