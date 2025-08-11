import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/router';
import { dynamicDraftApi } from '../services/api';

// Types
interface Player {
  id: number;
  name: string;
  position: string;
  team: string;
  bye_week: number;
  projected_points: number;
  adp: number;
  vorp: number;
  ecr: number;
  injury_risk: number;
  scarcity_flag: boolean;
  replacement_level: number;
}

interface Pick {
  pick_index: number;
  team_id: number;
  player: Player;
  round_number: number;
  pick_in_round: number;
  timestamp: number;
  auto_pick?: boolean;
  reasoning?: string;
}

interface TeamRoster {
  team_id: number;
  picks: number[];
  positional_counts: Record<string, number>;
  need_scores: Record<string, number>;
}

interface ScarcityMetrics {
  position: string;
  avg_vorp_remaining: number;
  dropoff_at_next_tier: number;
  scarcity_score: number;
  urgency_flag: boolean;
  replacement_level: number;
  players_remaining: number;
}

interface DraftState {
  draft_id: string;
  num_teams: number;
  draft_spot: number;
  scoring_mode: string;
  current_pick_index: number;
  current_team_id: number;
  user_next_pick_index: number | null;
  picks_made: number;
  total_picks: number;
  rosters: Record<string, TeamRoster>;
  scarcity_metrics: Record<string, ScarcityMetrics>;
}

interface AdviceSuggestion {
  player_id: number;
  name: string;
  position: string;
  vorp: number;
  reason: string;
  scarcity_flag: boolean;
  robust_score?: number;
  need_score?: number;
}

interface NextPickLine {
  has_next_pick: boolean;
  picks_until_user: number;
  message: string;
  likely_available_count?: number;
  likely_available_players?: number[];
}

const DynamicDraftPage: React.FC = () => {
  const router = useRouter();
  
  // Draft configuration
  const [numTeams, setNumTeams] = useState(12);
  const [draftSpot, setDraftSpot] = useState(1);
  const [scoringMode, setScoringMode] = useState('ppr');
  
  // Draft state
  const [draftId, setDraftId] = useState<string | null>(null);
  const [draftState, setDraftState] = useState<DraftState | null>(null);
  const [isConnected, setIsConnected] = useState(true);
  const [isDraftStarted, setIsDraftStarted] = useState(false);
  
  // Player data
  const [availablePlayers, setAvailablePlayers] = useState<Player[]>([]);
  const [allPlayers, setAllPlayers] = useState<Player[]>([]); // Keep all players for roster display
  const [filteredPlayers, setFilteredPlayers] = useState<Player[]>([]);
  const [positionFilter, setPositionFilter] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('vorp');
  const [sortOrder, setSortOrder] = useState('desc');
  const [selectedTeamRoster, setSelectedTeamRoster] = useState<number | null>(null);
  
  // Draft advice and UI
  const [advice, setAdvice] = useState<AdviceSuggestion[]>([]);
  const [adviceMode, setAdviceMode] = useState('robust');
  const [nextPickLine, setNextPickLine] = useState<NextPickLine | null>(null);
  const [showDraftBoard, setShowDraftBoard] = useState(true);
  const [notifications, setNotifications] = useState<string[]>([]);
  
  // Loading states
  const [isCreatingDraft, setIsCreatingDraft] = useState(false);
  const [isLoadingPlayers, setIsLoadingPlayers] = useState(false);
  const [isLoadingAdvice, setIsLoadingAdvice] = useState(false);

  // Refresh draft state periodically
  useEffect(() => {
    if (!draftId) return;

    const loadDraftState = async (draftId: string) => {
      try {
        const state = await dynamicDraftApi.getDraftState(draftId);
        setDraftState(state);
      } catch (error) {
        console.error('Error loading draft state:', error);
      }
    };

    const interval = setInterval(() => loadDraftState(draftId), 3000); // Refresh every 3 seconds

    return () => clearInterval(interval);
  }, [draftId]);

  // Create new draft
  const createDraft = async () => {
    setIsCreatingDraft(true);
    try {
      const response = await dynamicDraftApi.createDraft({
        num_teams: numTeams,
        draft_spot: draftSpot,
        snake: true,
        scoring_mode: scoringMode
      });

      const newDraftId = response.draft_id;
      setDraftId(newDraftId);
      setIsDraftStarted(true);

      // Load initial data
      await loadAvailablePlayers(newDraftId);
      await loadAdvice(newDraftId);
      await loadNextPickLine(newDraftId);

      // Load initial draft state and trigger bot picks if needed
      const initialState = await dynamicDraftApi.getDraftState(newDraftId);
      setDraftState(initialState);

      addNotification(`Draft created! You are team ${draftSpot} of ${numTeams}.`);

      // Check if bots should pick first (if user is not team 1 or if it's not user's turn)
      if (initialState.current_team_id !== draftSpot) {
        console.log('Initial draft state - bots should pick first', { 
          currentTeam: initialState.current_team_id, 
          userSpot: draftSpot 
        });
        // Small delay to let UI update, then start bot picks
        setTimeout(() => {
          triggerBotPicks();
        }, 1000);
      } else {
        console.log('Initial draft state - user picks first', { 
          currentTeam: initialState.current_team_id, 
          userSpot: draftSpot 
        });
        addNotification("It's your turn to pick!");
      }
    } catch (error) {
      console.error('Error creating draft:', error);
      addNotification('Error creating draft. Please try again.');
    } finally {
      setIsCreatingDraft(false);
    }
  };

  // Load available players
  const loadAvailablePlayers = async (draftId: string) => {
    setIsLoadingPlayers(true);
    try {
      const response = await dynamicDraftApi.getPlayersWithVorp({
        draft_id: draftId,
        scoring_mode: scoringMode,
        limit: 200
      });
      setAvailablePlayers(response.players);
    } catch (error) {
      console.error('Error loading players:', error);
    } finally {
      setIsLoadingPlayers(false);
    }
  };

  // Load draft advice
  const loadAdvice = async (draftId: string) => {
    setIsLoadingAdvice(true);
    try {
      const result = await dynamicDraftApi.getAdvice(draftId, draftSpot, adviceMode);
      setAdvice(result.advice);
    } catch (error) {
      console.error('Error loading advice:', error);
    } finally {
      setIsLoadingAdvice(false);
    }
  };

  // Load next pick line info
  const loadNextPickLine = async (draftId: string) => {
    try {
      const result = await dynamicDraftApi.getNextPickLine(draftId);
      setNextPickLine(result);
    } catch (error) {
      console.error('Error loading next pick line:', error);
    }
  };

  // Load draft state
  const loadDraftState = async (draftId: string) => {
    try {
      const state = await dynamicDraftApi.getDraftState(draftId);
      setDraftState(state);
    } catch (error) {
      console.error('Error loading draft state:', error);
    }
  };

  // Make a pick
  const makePick = async (playerId: number) => {
    if (!draftId || !draftState) return;

    if (draftState.current_team_id !== draftSpot) {
      addNotification("It's not your turn!");
      return;
    }

    try {
      const result = await dynamicDraftApi.makePick(draftId, playerId);
      const pickedPlayer = availablePlayers.find(p => p.id === playerId);
      addNotification(`You drafted: ${pickedPlayer?.name || 'Unknown'} (${pickedPlayer?.position || 'N/A'})`);
      
      // Immediately refresh available players to remove drafted player
      await loadAvailablePlayers(draftId);
      
      // Update draft state
      const newDraftState = await dynamicDraftApi.getDraftState(draftId);
      setDraftState(newDraftState);
      
      // Refresh other data
      await loadAdvice(draftId);
      await loadNextPickLine(draftId);
      
      // Trigger bot picks immediately if it's not the user's turn
      if (newDraftState.current_team_id !== draftSpot) {
        // Small delay to let UI update, then start bot picks
        setTimeout(() => {
          triggerBotPicks();
        }, 500);
      }
    } catch (error) {
      console.error('Error making pick:', error);
      addNotification('Error making pick. Please try again.');
    }
  };

  // Trigger bot picks with realistic 3-second delays
  const triggerBotPicks = async () => {
    console.log('triggerBotPicks called', { draftId, draftState });
    if (!draftId) {
      console.log('Missing draftId, returning');
      return;
    }
    
    try {
      // Get fresh draft state to ensure we have current data
      let currentState = await dynamicDraftApi.getDraftState(draftId);
      setDraftState(currentState);
      console.log('Starting bot picks loop with fresh state', { currentTeam: currentState.current_team_id, userSpot: draftSpot });
      
      while (currentState.current_team_id !== draftSpot && currentState.current_pick_index < currentState.total_picks) {
        console.log(`Bot pick iteration - Team ${currentState.current_team_id} picking`);
        
        // Show notification that bot is thinking
        addNotification(`Team ${currentState.current_team_id} is making their pick...`);
        
        // 3-second delay for realism
        await new Promise(resolve => setTimeout(resolve, 3000));
        
        try {
          // Simulate bot pick with some randomness
          console.log(`Getting advice for team ${currentState.current_team_id}`);
          const botResult = await dynamicDraftApi.getAdvice(draftId, currentState.current_team_id, 'robust');
          console.log('Bot advice result:', botResult);
          
          if (botResult.advice && botResult.advice.length > 0) {
            // Add some randomness - pick from top 3 recommendations
            const randomIndex = Math.floor(Math.random() * Math.min(3, botResult.advice.length));
            const selectedPlayer = botResult.advice[randomIndex];
            console.log('Selected player for bot pick:', selectedPlayer);
            
            const pickResult = await dynamicDraftApi.makePick(draftId, selectedPlayer.player_id);
            console.log('Pick result:', pickResult);
            addNotification(`Team ${pickResult.pick.team_id} drafted: ${pickResult.pick.player.name} (${pickResult.pick.player.position})`);
            
            // Update current state
            currentState = await dynamicDraftApi.getDraftState(draftId);
            console.log('Updated draft state:', currentState);
            
            // Refresh available players immediately to remove drafted player
            await loadAvailablePlayers(draftId);
          } else {
            console.log('No advice available, breaking bot pick loop');
            break;
          }
        } catch (pickError) {
          console.error('Error in bot pick iteration:', pickError);
          addNotification(`Error with Team ${currentState.current_team_id} pick`);
          break;
        }
      }
      
      console.log('Bot picks complete, final refresh');
      // Final refresh of all data after bot picks complete
      await loadAdvice(draftId);
      await loadNextPickLine(draftId);
      await loadDraftState(draftId);
      
      if (currentState.current_team_id === draftSpot) {
        addNotification("It's your turn to pick!");
      }
    } catch (error) {
      console.error('Error with bot picks:', error);
      addNotification('Error occurred during bot picks. Please refresh.');
    }
  };

  // Request advice
  const requestAdvice = useCallback(() => {
    if (!draftId) return;
    loadAdvice(draftId);
  }, [draftId]);

  // Filter and sort players
  useEffect(() => {
    let filtered = availablePlayers;

    if (positionFilter !== 'ALL') {
      filtered = filtered.filter(p => p.position === positionFilter);
    }

    if (searchTerm) {
      filtered = filtered.filter(p => 
        p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.team.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Sort players
    filtered = filtered.sort((a, b) => {
      let aValue, bValue;
      switch (sortBy) {
        case 'vorp':
          aValue = a.vorp || 0;
          bValue = b.vorp || 0;
          break;
        case 'projected_points':
          aValue = a.projected_points || 0;
          bValue = b.projected_points || 0;
          break;
        case 'adp':
          aValue = a.adp || 999;
          bValue = b.adp || 999;
          break;
        case 'ecr':
          aValue = a.ecr || 999;
          bValue = b.ecr || 999;
          break;
        default:
          aValue = a.vorp || 0;
          bValue = b.vorp || 0;
      }
      
      if (sortOrder === 'desc') {
        return bValue - aValue;
      } else {
        return aValue - bValue;
      }
    });

    setFilteredPlayers(filtered);
  }, [availablePlayers, positionFilter, searchTerm, sortBy, sortOrder]);

  // Add notification
  const addNotification = (message: string) => {
    setNotifications(prev => [...prev.slice(-4), message]);
    setTimeout(() => {
      setNotifications(prev => prev.slice(1));
    }, 5000);
  };

  // Get VORP badge color
  const getVorpBadgeColor = (vorp: number) => {
    if (vorp >= 10) return 'bg-green-600';
    if (vorp >= 5) return 'bg-green-500';
    if (vorp >= 2) return 'bg-yellow-500';
    if (vorp >= 0) return 'bg-gray-500';
    return 'bg-red-500';
  };

  const getPositionColor = (position: string) => {
    switch (position) {
      case 'QB': return 'bg-red-50 border-l-4 border-red-400';
      case 'RB': return 'bg-green-50 border-l-4 border-green-400';
      case 'WR': return 'bg-blue-50 border-l-4 border-blue-400';
      case 'TE': return 'bg-yellow-50 border-l-4 border-yellow-400';
      case 'K': return 'bg-purple-50 border-l-4 border-purple-400';
      case 'DEF': return 'bg-gray-50 border-l-4 border-gray-400';
      default: return 'bg-white';
    }
  };

  const isLikelyAvailable = (player: Player) => {
    return nextPickLine && nextPickLine.likely_available_players && nextPickLine.likely_available_players.includes(player.id);
  };

  const isTrulyScarce = (player: any) => {
    // Only show scarce tag if VORP is high and scarcity flag is true
    return player.scarcity_flag && player.vorp > 2;
  };

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(column);
      setSortOrder(column === 'adp' || column === 'ecr' ? 'asc' : 'desc');
    }
  };

  if (!isDraftStarted) {
    return (
      <div className="min-h-screen bg-gray-100 p-8">
        <div className="max-w-2xl mx-auto">
          <h1 className="text-4xl font-bold text-center mb-8">Dynamic VORP Draft</h1>
          
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-2xl font-semibold mb-6">Draft Configuration</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Number of Teams
                </label>
                <select
                  value={numTeams}
                  onChange={(e) => setNumTeams(parseInt(e.target.value))}
                  className="w-full p-2 border border-gray-300 rounded-md"
                >
                  {[8, 10, 12, 14, 16].map(n => (
                    <option key={n} value={n}>{n} Teams</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Your Draft Position
                </label>
                <select
                  value={draftSpot}
                  onChange={(e) => setDraftSpot(parseInt(e.target.value))}
                  className="w-full p-2 border border-gray-300 rounded-md"
                >
                  {Array.from({ length: numTeams }, (_, i) => i + 1).map(n => (
                    <option key={n} value={n}>Pick {n}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Scoring Mode
                </label>
                <select
                  value={scoringMode}
                  onChange={(e) => setScoringMode(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded-md"
                >
                  <option value="ppr">PPR (Point Per Reception)</option>
                  <option value="half_ppr">Half PPR</option>
                  <option value="standard">Standard</option>
                </select>
              </div>
            </div>

            <div className="mt-8">
              <button
                onClick={createDraft}
                disabled={isCreatingDraft || !isConnected}
                className="w-full bg-blue-600 text-white py-3 px-6 rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50"
              >
                {isCreatingDraft ? 'Creating Draft...' : 'Start Dynamic Draft'}
              </button>
              
              {!isConnected && (
                <p className="text-red-600 text-sm mt-2">
                  Connecting to draft server...
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold">Dynamic VORP Draft</h1>
              <p className="text-gray-600">
                {draftState && (
                  <>
                    Pick {draftState.current_pick_index + 1} of {draftState.total_picks} • 
                    Team {draftState.current_team_id}'s turn
                    {draftState.user_next_pick_index && (
                      <> • Your next pick: #{draftState.user_next_pick_index + 1}</>
                    )}
                  </>
                )}
              </p>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
              <span className="text-sm text-gray-600">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
              
              <button
                onClick={() => setShowDraftBoard(!showDraftBoard)}
                className="bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700"
              >
                {showDraftBoard ? 'Hide' : 'Show'} Draft Board
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-4">
        <div className="flex gap-6">
          {/* Main Content */}
          <div className={`flex-1 ${showDraftBoard ? 'w-2/3' : 'w-full'}`}>
            {/* Available Players */}
            <div className="bg-white rounded-lg shadow-sm">
              <div className="p-4 border-b">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-xl font-semibold">Available Players</h2>
                  <div className="flex items-center space-x-2">
                    <input
                      type="text"
                      placeholder="Search players..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="p-2 border border-gray-300 rounded-md text-sm"
                    />
                    <select
                      value={positionFilter}
                      onChange={(e) => setPositionFilter(e.target.value)}
                      className="p-2 border border-gray-300 rounded-md text-sm"
                    >
                      <option value="ALL">All Positions</option>
                      <option value="QB">QB</option>
                      <option value="RB">RB</option>
                      <option value="WR">WR</option>
                      <option value="TE">TE</option>
                      <option value="K">K</option>
                      <option value="DEF">DEF</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Player</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100" onClick={() => handleSort('vorp')}>
                        VORP {sortBy === 'vorp' && (sortOrder === 'desc' ? '↓' : '↑')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100" onClick={() => handleSort('projected_points')}>
                        PROJ {sortBy === 'projected_points' && (sortOrder === 'desc' ? '↓' : '↑')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100" onClick={() => handleSort('adp')}>
                        ADP {sortBy === 'adp' && (sortOrder === 'desc' ? '↓' : '↑')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100" onClick={() => handleSort('ecr')}>
                        ECR {sortBy === 'ecr' && (sortOrder === 'desc' ? '↓' : '↑')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {filteredPlayers.slice(0, 50).map((player) => (
                      <tr 
                        key={player.id}
                        className={`hover:bg-gray-100 ${getPositionColor(player.position)} ${!isLikelyAvailable(player) ? 'opacity-60' : ''}`}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center space-x-2">
                            <div>
                              <span className="font-medium">{player.name}</span>
                              <span className="ml-2 text-sm font-semibold text-gray-600">({player.position})</span>
                              <div className="text-xs text-gray-500">{player.team}</div>
                            </div>
                            {isTrulyScarce(player) && (
                              <span className="bg-red-100 text-red-800 text-xs px-1 py-0.5 rounded">SCARCE</span>
                            )}
                            {!isLikelyAvailable(player) && (
                              <span className="bg-yellow-100 text-yellow-800 text-xs px-1 py-0.5 rounded">RISK</span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-block px-2 py-1 rounded text-white text-xs font-medium ${getVorpBadgeColor(player.vorp)}`}>
                            {player.vorp.toFixed(1)}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm font-medium">{player.projected_points?.toFixed(1) || 'N/A'}</td>
                        <td className="px-4 py-3 text-sm">{player.adp?.toFixed(1) || 'N/A'}</td>
                        <td className="px-4 py-3 text-sm">{player.ecr || 'N/A'}</td>
                        <td className="px-4 py-3">
                          {draftState?.current_team_id === draftSpot ? (
                            <button
                              onClick={() => makePick(player.id)}
                              className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700"
                            >
                              Draft
                            </button>
                          ) : (
                            <span className="text-gray-400 text-sm">Wait</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Draft Board Sidebar */}
          {showDraftBoard && draftState && (
            <div className="w-1/3 bg-white rounded-lg shadow-sm p-4">
              <h2 className="text-xl font-semibold mb-4">Draft Board</h2>
              
              <div className="space-y-4">
                {Object.entries(draftState.rosters).map(([teamId, roster]) => (
                  <div 
                    key={teamId} 
                    className="border rounded-lg p-3 cursor-pointer hover:bg-gray-50" 
                    onClick={() => setSelectedTeamRoster(parseInt(teamId))}
                  >
                    <div className="flex justify-between items-center mb-2">
                      <h3 className="font-semibold">
                        Team {teamId}
                        {parseInt(teamId) === draftSpot && <span className="text-blue-600"> (You)</span>}
                      </h3>
                      <span className="text-sm text-gray-600">
                        {roster.picks.length} picks
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-1 text-xs">
                      {Object.entries(roster.need_scores).map(([pos, score]) => (
                        <div key={pos} className={`p-1 rounded text-center ${score > 0 ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}`}>
                          {pos}: {roster.positional_counts[pos] || 0}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Team Roster Modal */}
      {selectedTeamRoster && draftState && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">
                Team {selectedTeamRoster} Roster
                {selectedTeamRoster === draftSpot && <span className="text-blue-600"> (You)</span>}
              </h3>
              <button
                onClick={() => setSelectedTeamRoster(null)}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>
            
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {draftState.rosters[selectedTeamRoster.toString()]?.picks.map((playerId, index) => {
                const player = allPlayers.find(p => p.id === playerId);
                return (
                  <div key={index} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                    <div>
                      <span className="font-medium">{player?.name || 'Unknown Player'}</span>
                      <span className="ml-2 text-sm text-gray-600">({player?.position || 'N/A'})</span>
                      <div className="text-xs text-gray-500">{player?.team || ''}</div>
                    </div>
                    <div className="text-right">
                      <span className="text-sm text-gray-500">Pick #{index + 1}</span>
                      {player?.vorp && (
                        <div className="text-xs text-gray-400">VORP: {player.vorp.toFixed(1)}</div>
                      )}
                    </div>
                  </div>
                );
              })}
              
              {(!draftState.rosters[selectedTeamRoster.toString()]?.picks || 
                draftState.rosters[selectedTeamRoster.toString()].picks.length === 0) && (
                <p className="text-gray-500 text-center py-4">No picks yet</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Notifications */}
      <div className="fixed bottom-4 right-4 space-y-2 z-50">
        {notifications.map((notification, index) => (
          <div
            key={index}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg max-w-sm"
          >
            {notification}
          </div>
        ))}
      </div>
    </div>
  );
};

export default DynamicDraftPage;
