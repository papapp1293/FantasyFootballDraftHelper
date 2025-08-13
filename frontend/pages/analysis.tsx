import { useState, useEffect } from 'react';
import Head from 'next/head';
import { motion } from 'framer-motion';
import {
  ChartBarIcon,
  TrophyIcon,
  UserGroupIcon,
  ArrowPathIcon,
  StarIcon
} from '@heroicons/react/24/outline';
import { analysisApi } from '@/services/api';
import { TeamEvaluation, ScoringType } from '@/types';
import toast from 'react-hot-toast';

export default function AnalysisPage() {
  const [teamComparison, setTeamComparison] = useState<any>(null);
  const [seasonSimulation, setSeasonSimulation] = useState<any>(null);
  const [scoringType, setScoringType] = useState<ScoringType>('ppr');
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'rankings' | 'simulation'>('rankings');
  const [selectedTeam, setSelectedTeam] = useState<{ id: number; name: string } | null>(null);
  const [teamDetails, setTeamDetails] = useState<any>(null);
  const [teamDraftBoard, setTeamDraftBoard] = useState<any>(null);
  const [teamSimPreview, setTeamSimPreview] = useState<any>(null);
  const [teamModalTab, setTeamModalTab] = useState<'overview' | 'draft' | 'simulation'>('overview');
  const [isTeamModalLoading, setIsTeamModalLoading] = useState(false);

  // Mock league ID for demo - in production this would come from user selection
  const mockLeagueId = 1;

  useEffect(() => {
    loadAnalysisData();
  }, [scoringType]);

  const loadAnalysisData = async () => {
    setIsLoading(true);
    try {
      // In a real app, you'd have actual league data
      // For demo purposes, we'll show the structure

      // Mock team comparison data - showing realistic top-ranked teams
      const mockTeamData = {
        league_id: 1,
        scoring_type: scoringType,
        team_count: 12,
        teams: [
          {
            team_id: 1,
            team_name: "Elite Draft Team",
            overall_grade: "A+",
            projected_points: { total_projected_points: 1485.2, projected_rank_estimate: 1 },
            vorp_analysis: { total_vorp: 52.8, starting_lineup_vorp: 45.3 },
            depth_analysis: { overall_depth_score: 8.9, depth_grade: "A" },
            bye_week_analysis: { total_bye_impact: 6.2, bye_grade: "A-" }
          },
          {
            team_id: 2,
            team_name: "Solid Draft Team",
            overall_grade: "A-",
            projected_points: { total_projected_points: 1456.7, projected_rank_estimate: 2 },
            vorp_analysis: { total_vorp: 41.3, starting_lineup_vorp: 36.8 },
            depth_analysis: { overall_depth_score: 7.6, depth_grade: "B+" },
            bye_week_analysis: { total_bye_impact: 8.9, bye_grade: "B+" }
          }
        ],
        league_averages: {
          avg_projected_points: 1356.8,
          avg_total_vorp: 28.4,
          avg_depth_score: 6.1
        }
      };

      setTeamComparison(mockTeamData);

      // Mock season simulation data
      const mockSimData = {
        team_results: [
          {
            team_name: "Team Alpha",
            championship_probability: 18.5,
            playoff_probability: 78.2,
            avg_wins: 8.7,
            avg_points_for: 1425.6
          },
          {
            team_name: "Team Beta",
            championship_probability: 12.3,
            playoff_probability: 65.4,
            avg_wins: 7.9,
            avg_points_for: 1398.3
          }
        ],
        league_analysis: {
          parity_score: 72.4,
          championship_favorite: "Team Alpha",
          championship_favorite_probability: 18.5
        }
      };

      setSeasonSimulation(mockSimData);

    } catch (error) {
      console.error('Failed to load analysis data:', error);
      toast.error('Failed to load analysis data');
    } finally {
      setIsLoading(false);
    }
  };

  const openTeamModal = async (team: { id: number; name: string }) => {
    setSelectedTeam(team);
    setTeamModalTab('overview');
    setIsTeamModalLoading(true);
    try {
      const [details, draftBoard, simPreview] = await Promise.all([
        analysisApi.getTeamDetails(team.id, scoringType),
        analysisApi.getTeamDraftBoard(team.id),
        analysisApi.getTeamSimulationPreview(team.id, scoringType),
      ]);
      setTeamDetails(details);
      setTeamDraftBoard(draftBoard);
      setTeamSimPreview(simPreview);
    } catch (e) {
      console.error('Failed to load team drill-down', e);
      toast.error('Failed to load team details');
    } finally {
      setIsTeamModalLoading(false);
    }
  };

  const closeTeamModal = () => {
    setSelectedTeam(null);
    setTeamDetails(null);
    setTeamDraftBoard(null);
    setTeamSimPreview(null);
  };

  const getGradeColor = (grade: string) => {
    const firstChar = grade.charAt(0).toLowerCase();
    const colors: Record<string, string> = {
      'a': 'bg-green-100 text-green-800 border-green-200',
      'b': 'bg-blue-100 text-blue-800 border-blue-200',
      'c': 'bg-yellow-100 text-yellow-800 border-yellow-200',
      'd': 'bg-red-100 text-red-800 border-red-200'
    };
    return colors[firstChar] || 'bg-gray-100 text-gray-800 border-gray-200';
  };

  return (
    <>
      <Head>
        <title>League Analysis - Fantasy Football Draft Helper</title>
        <meta name="description" content="Team rankings, power analysis, and season simulations" />
      </Head>

      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <header className="bg-white shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center py-6">
              <h1 className="text-2xl font-bold text-gray-900 flex items-center">
                <ChartBarIcon className="h-8 w-8 text-blue-600 mr-3" />
                League Analysis
              </h1>
              <div className="flex items-center space-x-4">
                <select
                  value={scoringType}
                  onChange={(e) => setScoringType(e.target.value as ScoringType)}
                  className="form-select"
                >
                  <option value="ppr">PPR</option>
                  <option value="half_ppr">Half PPR</option>
                  <option value="standard">Standard</option>
                </select>
                <button
                  onClick={loadAnalysisData}
                  className="btn-primary flex items-center"
                  disabled={isLoading}
                >
                  <ArrowPathIcon className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                  Refresh
                </button>
              </div>
            </div>
          </div>
        </header>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Tab Navigation */}
          <div className="bg-white rounded-lg shadow-sm mb-8">
            <div className="border-b border-gray-200">
              <nav className="-mb-px flex">
                <button
                  onClick={() => setActiveTab('rankings')}
                  className={`py-4 px-6 text-sm font-medium border-b-2 ${activeTab === 'rankings'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`}
                >
                  <UserGroupIcon className="h-5 w-5 inline mr-2" />
                  Team Rankings
                </button>
                <button
                  onClick={() => setActiveTab('simulation')}
                  className={`py-4 px-6 text-sm font-medium border-b-2 ${activeTab === 'simulation'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`}
                >
                  <TrophyIcon className="h-5 w-5 inline mr-2" />
                  Season Simulation
                </button>
              </nav>
            </div>
          </div>

          {isLoading ? (
            <div className="bg-white rounded-lg shadow-sm p-8 text-center">
              <div className="loading-spinner mx-auto mb-4"></div>
              <p className="text-gray-500">Loading analysis data...</p>
            </div>
          ) : (
            <>
              {/* Team Rankings Tab */}
              {activeTab === 'rankings' && teamComparison && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-6"
                >
                  {/* League Averages */}
                  <div className="bg-white rounded-lg shadow-sm p-6">
                    <h2 className="text-lg font-semibold text-gray-900 mb-4">League Averages</h2>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-blue-600">
                          {teamComparison.league_averages.avg_projected_points.toFixed(1)}
                        </div>
                        <div className="text-sm text-gray-500">Avg Projected Points</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-green-600">
                          {teamComparison.league_averages.avg_total_vorp.toFixed(1)}
                        </div>
                        <div className="text-sm text-gray-500">Avg VORP</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-purple-600">
                          {teamComparison.league_averages.avg_depth_score.toFixed(1)}
                        </div>
                        <div className="text-sm text-gray-500">Avg Depth Score</div>
                      </div>
                    </div>
                  </div>

                  {/* Team Rankings */}
                  <div className="bg-white rounded-lg shadow-sm">
                    <div className="px-6 py-4 border-b border-gray-200">
                      <h2 className="text-lg font-semibold text-gray-900">Power Rankings</h2>
                    </div>
                    <div className="divide-y divide-gray-200">
                      {teamComparison.teams.map((team: any, index: number) => (
                        <motion.div
                          key={team.team_id}
                          initial={{ opacity: 0, x: -20 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: index * 0.1 }}
                          className="p-6 hover:bg-gray-50 cursor-pointer"
                          onClick={() => openTeamModal({ id: team.team_id, name: team.team_name })}
                          role="button"
                          title="View team details"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center">
                              <div className="flex-shrink-0">
                                <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white font-bold text-sm">
                                  {index + 1}
                                </div>
                              </div>
                              <div className="ml-4">
                                <div className="text-left text-lg font-medium text-gray-900 hover:underline">
                                  {team.team_name}
                                </div>
                                <div className="flex items-center space-x-2 mt-1">
                                  <span className={`badge border ${getGradeColor(team.overall_grade)}`}>
                                    Grade: {team.overall_grade}
                                  </span>
                                  <span className="text-sm text-gray-500">
                                    Rank #{team.projected_points.projected_rank_estimate}
                                  </span>
                                </div>
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="text-lg font-semibold text-gray-900">
                                {team.projected_points.total_projected_points.toFixed(1)} pts
                              </div>
                              <div className="text-sm text-gray-500">
                                VORP: {team.vorp_analysis.total_vorp.toFixed(1)}
                              </div>
                            </div>
                          </div>

                          <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
                            <div>
                              <span className="text-gray-500">Depth:</span>
                              <span className={`ml-2 badge ${getGradeColor(team.depth_analysis.depth_grade)}`}>
                                {team.depth_analysis.depth_grade}
                              </span>
                            </div>
                            <div>
                              <span className="text-gray-500">Bye Weeks:</span>
                              <span className={`ml-2 badge ${getGradeColor(team.bye_week_analysis.bye_grade)}`}>
                                {team.bye_week_analysis.bye_grade}
                              </span>
                            </div>
                            <div>
                              <span className="text-gray-500">Impact:</span>
                              <span className="ml-2 font-medium">
                                {team.bye_week_analysis.total_bye_impact.toFixed(1)}
                              </span>
                            </div>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}

              {/* Season Simulation Tab */}
              {activeTab === 'simulation' && seasonSimulation && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-6"
                >
                  {/* League Analysis */}
                  <div className="bg-white rounded-lg shadow-sm p-6">
                    <h2 className="text-lg font-semibold text-gray-900 mb-4">League Competitiveness</h2>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-blue-600">
                          {seasonSimulation.league_analysis.parity_score.toFixed(1)}
                        </div>
                        <div className="text-sm text-gray-500">Parity Score</div>
                      </div>
                      <div className="text-center">
                        <div className="text-lg font-bold text-green-600 flex items-center justify-center">
                          <StarIcon className="h-5 w-5 mr-1" />
                          {seasonSimulation.league_analysis.championship_favorite}
                        </div>
                        <div className="text-sm text-gray-500">Championship Favorite</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-yellow-600">
                          {seasonSimulation.league_analysis.championship_favorite_probability.toFixed(1)}%
                        </div>
                        <div className="text-sm text-gray-500">Favorite's Odds</div>
                      </div>
                    </div>
                  </div>

                  {/* Team Simulation Results */}
                  <div className="bg-white rounded-lg shadow-sm">
                    <div className="px-6 py-4 border-b border-gray-200">
                      <h2 className="text-lg font-semibold text-gray-900">Season Projections</h2>
                      <p className="text-sm text-gray-500 mt-1">Based on 10,000 Monte Carlo simulations</p>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="table">
                        <thead className="table-header">
                          <tr>
                            <th className="table-header-cell">Team</th>
                            <th className="table-header-cell">Proj Wins</th>
                            <th className="table-header-cell">Proj Points</th>
                            <th className="table-header-cell">Playoff %</th>
                            <th className="table-header-cell">Championship %</th>
                          </tr>
                        </thead>
                        <tbody className="table-body">
                          {seasonSimulation.team_results.map((team: any, index: number) => (
                            <motion.tr
                              key={team.team_name}
                              initial={{ opacity: 0, x: -20 }}
                              animate={{ opacity: 1, x: 0 }}
                              transition={{ delay: index * 0.1 }}
                              className="hover:bg-gray-50"
                            >
                              <td className="table-cell">
                                <div className="font-medium text-gray-900">{team.team_name}</div>
                              </td>
                              <td className="table-cell">
                                <span className="font-medium">{team.avg_wins.toFixed(1)}</span>
                              </td>
                              <td className="table-cell">
                                <span className="text-gray-600">{team.avg_points_for.toFixed(1)}</span>
                              </td>
                              <td className="table-cell">
                                <div className="flex items-center">
                                  <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                                    <div
                                      className="bg-blue-600 h-2 rounded-full"
                                      style={{ width: `${team.playoff_probability}%` }}
                                    ></div>
                                  </div>
                                  <span className="text-sm font-medium">{team.playoff_probability.toFixed(1)}%</span>
                                </div>
                              </td>
                              <td className="table-cell">
                                <div className="flex items-center">
                                  <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                                    <div
                                      className="bg-yellow-500 h-2 rounded-full"
                                      style={{ width: `${Math.min(team.championship_probability * 5, 100)}%` }}
                                    ></div>
                                  </div>
                                  <span className="text-sm font-medium">{team.championship_probability.toFixed(1)}%</span>
                                </div>
                              </td>
                            </motion.tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </motion.div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Team Drill-down Modal */}
      {selectedTeam && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-5xl w-full mx-4">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <div>
                <h3 className="text-xl font-semibold">{selectedTeam.name}</h3>
                <p className="text-sm text-gray-500">Team drill-down</p>
              </div>
              <button onClick={closeTeamModal} className="text-gray-500 hover:text-gray-700">✕</button>
            </div>

            {/* Tabs */}
            <div className="px-6 pt-4">
              <div className="flex space-x-4 border-b">
                {['overview', 'draft', 'simulation'].map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setTeamModalTab(tab as any)}
                    className={`py-2 px-3 text-sm font-medium border-b-2 ${teamModalTab === tab ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                  >
                    {tab === 'overview' ? 'Overview' : tab === 'draft' ? 'Draft Board' : 'Simulation'}
                  </button>
                ))}
              </div>
            </div>

            <div className="p-6 max-h-[70vh] overflow-y-auto">
              {isTeamModalLoading ? (
                <div className="text-center text-gray-500">Loading...</div>
              ) : (
                <>
                  {teamModalTab === 'overview' && (
                    <div className="space-y-6">
                      {teamDetails ? (
                        <>
                          <div>
                            <h4 className="text-lg font-semibold mb-2">Evaluation</h4>
                            <pre className="bg-gray-50 p-4 rounded text-sm overflow-auto">{JSON.stringify(teamDetails.evaluation, null, 2)}</pre>
                          </div>
                          <div>
                            <h4 className="text-lg font-semibold mb-2">Draft Picks</h4>
                            <div className="overflow-x-auto">
                              <table className="table">
                                <thead className="table-header">
                                  <tr>
                                    <th className="table-header-cell">Pick</th>
                                    <th className="table-header-cell">Round</th>
                                    <th className="table-header-cell">Pick in Round</th>
                                    <th className="table-header-cell">Player</th>
                                    <th className="table-header-cell">Pos</th>
                                    <th className="table-header-cell">Team</th>
                                  </tr>
                                </thead>
                                <tbody className="table-body">
                                  {teamDetails.picks.map((p: any) => (
                                    <tr key={`${p.pick_number}-${p.player?.id ?? 'none'}`}>
                                      <td className="table-cell">#{p.pick_number}</td>
                                      <td className="table-cell">{p.round_number}</td>
                                      <td className="table-cell">{p.pick_in_round}</td>
                                      <td className="table-cell">{p.player?.name ?? '—'}</td>
                                      <td className="table-cell">{p.player?.position ?? '—'}</td>
                                      <td className="table-cell">{p.player?.team ?? '—'}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        </>
                      ) : (
                        <div className="text-gray-500">No evaluation or draft data available for this team yet.</div>
                      )}
                    </div>
                  )}

                  {teamModalTab === 'draft' && teamDraftBoard && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <h4 className="text-lg font-semibold">Draft Board</h4>
                        <div className="text-sm text-gray-500">Draft #{teamDraftBoard.draft_id} • Round {teamDraftBoard.current_round} • Pick {teamDraftBoard.current_pick}</div>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="table">
                          <thead className="table-header">
                            <tr>
                              <th className="table-header-cell">Pick</th>
                              <th className="table-header-cell">Round</th>
                              <th className="table-header-cell">Pick in Round</th>
                              <th className="table-header-cell">Team</th>
                              <th className="table-header-cell">Player</th>
                              <th className="table-header-cell">Pos</th>
                              <th className="table-header-cell">NFL Team</th>
                            </tr>
                          </thead>
                          <tbody className="table-body">
                            {teamDraftBoard.picks.map((p: any) => (
                              <tr key={`${p.pick_number}-${p.player?.id ?? 'none'}`} className={p.team_id === (selectedTeam?.id ?? 0) ? 'bg-blue-50' : ''}>
                                <td className="table-cell">#{p.pick_number}</td>
                                <td className="table-cell">{p.round_number}</td>
                                <td className="table-cell">{p.pick_in_round}</td>
                                <td className="table-cell">{p.team_name}</td>
                                <td className="table-cell">{p.player?.name ?? '—'}</td>
                                <td className="table-cell">{p.player?.position ?? '—'}</td>
                                <td className="table-cell">{p.player?.team ?? '—'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {teamModalTab === 'simulation' && teamSimPreview && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <h4 className="text-lg font-semibold">Simulation Preview</h4>
                        <div className="text-sm text-gray-500">Avg score: {teamSimPreview.avg_score}</div>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="table">
                          <thead className="table-header">
                            <tr>
                              <th className="table-header-cell">Week</th>
                              <th className="table-header-cell">Projected Score</th>
                            </tr>
                          </thead>
                          <tbody className="table-body">
                            {teamSimPreview.weekly_scores.map((score: number, idx: number) => (
                              <tr key={idx}>
                                <td className="table-cell">{idx + 1}</td>
                                <td className="table-cell">{score.toFixed(2)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
