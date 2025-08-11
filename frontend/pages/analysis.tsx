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
      
      // Mock team comparison data
      const mockTeamData = {
        league_id: 1,
        scoring_type: scoringType,
        team_count: 12,
        teams: [
          {
            team_id: 1,
            team_name: "Team Alpha",
            overall_grade: "A-",
            projected_points: { total_projected_points: 1425.6, projected_rank_estimate: 2 },
            vorp_analysis: { total_vorp: 45.2, starting_lineup_vorp: 38.1 },
            depth_analysis: { overall_depth_score: 7.2, depth_grade: "B+" },
            bye_week_analysis: { total_bye_impact: 8.5, bye_grade: "B" }
          },
          {
            team_id: 2,
            team_name: "Team Beta",
            overall_grade: "B+",
            projected_points: { total_projected_points: 1398.3, projected_rank_estimate: 4 },
            vorp_analysis: { total_vorp: 32.7, starting_lineup_vorp: 29.4 },
            depth_analysis: { overall_depth_score: 6.8, depth_grade: "B" },
            bye_week_analysis: { total_bye_impact: 12.1, bye_grade: "C+" }
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
                  className={`py-4 px-6 text-sm font-medium border-b-2 ${
                    activeTab === 'rankings'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <UserGroupIcon className="h-5 w-5 inline mr-2" />
                  Team Rankings
                </button>
                <button
                  onClick={() => setActiveTab('simulation')}
                  className={`py-4 px-6 text-sm font-medium border-b-2 ${
                    activeTab === 'simulation'
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
                          className="p-6 hover:bg-gray-50"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center">
                              <div className="flex-shrink-0">
                                <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white font-bold text-sm">
                                  {index + 1}
                                </div>
                              </div>
                              <div className="ml-4">
                                <h3 className="text-lg font-medium text-gray-900">{team.team_name}</h3>
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
    </>
  );
}
