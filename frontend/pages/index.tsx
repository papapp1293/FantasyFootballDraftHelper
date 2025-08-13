import { useState, useEffect } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { 
  ChartBarIcon, 
  TrophyIcon, 
  UserGroupIcon, 
  LightBulbIcon,
  ArrowRightIcon,
  PlayIcon
} from '@heroicons/react/24/outline';
import { playerApi, apiUtils } from '@/services/api';
import toast from 'react-hot-toast';

interface DataSummary {
  total_players: number;
  position_breakdown: Record<string, number>;
  data_completeness: {
    players_with_ppr_projections: number;
    players_with_vorp: number;
    completion_rate: number;
  };
}

export default function Home() {
  const [dataSummary, setDataSummary] = useState<DataSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadDataSummary();
  }, []);

  const loadDataSummary = async () => {
    try {
      const summary = await playerApi.getDataSummary();
      setDataSummary(summary);
    } catch (error) {
      console.error('Failed to load data summary:', error);
      toast.error('Failed to load player data summary');
    } finally {
      setIsLoading(false);
    }
  };

  const features = [
    {
      name: 'Draft Recommendations',
      description: 'Get AI-powered pick recommendations based on VORP, scarcity analysis, and Monte Carlo simulations.',
      icon: LightBulbIcon,
      href: '/draft',
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      name: 'Team Analysis',
      description: 'Comprehensive post-draft team evaluation with depth analysis, bye week impact, and competitive advantage.',
      icon: ChartBarIcon,
      href: '/analysis',
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      name: 'Player Rankings',
      description: 'Complete player rankings with projections, ECR, ADP, and VORP analysis for all positions.',
      icon: UserGroupIcon,
      href: '/player-rankings',
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
    },
    {
      name: 'Season Simulation',
      description: 'Monte Carlo season simulations to predict playoff chances and championship probabilities.',
      icon: TrophyIcon,
      href: '/analysis?tab=simulation',
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50',
    },
  ];

  const stats = [
    { name: 'Total Players', value: dataSummary?.total_players || 0 },
    { name: 'Data Completeness', value: `${dataSummary?.data_completeness.completion_rate || 0}%` },
    { name: 'VORP Calculated', value: dataSummary?.data_completeness.players_with_vorp || 0 },
    { name: 'Positions Analyzed', value: Object.keys(dataSummary?.position_breakdown || {}).length },
  ];

  return (
    <>
      <Head>
        <title>Fantasy Football Draft Helper</title>
        <meta 
          name="description" 
          content="Advanced fantasy football draft analysis with VORP, scarcity analysis, and Monte Carlo simulations" 
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-green-50">
        {/* Header */}
        <header className="bg-white shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center py-6">
              <div className="flex items-center">
                <TrophyIcon className="h-8 w-8 text-blue-600 mr-3" />
                <h1 className="text-2xl font-bold text-gray-900">
                  Fantasy Football Draft Helper
                </h1>
              </div>
              <nav className="flex space-x-8">
                <Link href="/dynamic-draft" className="text-gray-600 hover:text-gray-900 font-medium">
                  Draft
                </Link>
                <Link href="/analysis" className="text-gray-600 hover:text-gray-900 font-medium">
                  Analysis
                </Link>
              </nav>
            </div>
          </div>
        </header>

        {/* Hero Section */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center"
          >
            <h2 className="text-4xl font-extrabold text-gray-900 sm:text-5xl md:text-6xl">
              <span className="block">Dominate Your</span>
              <span className="block text-gradient">Fantasy Draft</span>
            </h2>
            <p className="mt-3 max-w-md mx-auto text-base text-gray-500 sm:text-lg md:mt-5 md:text-xl md:max-w-3xl">
              Advanced analytics powered by VORP calculations, scarcity analysis, and Monte Carlo simulations 
              to give you the competitive edge in your fantasy football league.
            </p>
            <div className="mt-10 flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/dynamic-draft"
                className="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-white bg-purple-600 hover:bg-purple-700 md:py-4 md:text-lg md:px-10 transition-colors duration-200"
              >
                🚀 Start Dynamic Draft
                <ArrowRightIcon className="ml-2 h-5 w-5" />
              </Link>
              <Link
                href="/player-rankings"
                className="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-blue-600 bg-white hover:bg-gray-50 md:py-4 md:text-lg md:px-10 transition-colors duration-200"
              >
                View Player Rankings
                <ArrowRightIcon className="ml-2 h-5 w-5" />
              </Link>
            </div>
          </motion.div>

          {/* Stats Section */}
          {!isLoading && dataSummary && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="mt-16"
            >
              <div className="bg-white rounded-lg shadow-card p-8">
                <h3 className="text-lg font-semibold text-gray-900 text-center mb-8">
                  Current Data Status
                </h3>
                <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
                  {stats.map((item) => (
                    <div key={item.name} className="px-4 py-5 bg-gray-50 shadow rounded-lg overflow-hidden">
                      <dt className="text-sm font-medium text-gray-500 truncate">{item.name}</dt>
                      <dd className="mt-1 text-3xl font-semibold text-gray-900">{item.value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </motion.div>
          )}

          {/* Features Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="mt-16"
          >
            <div className="text-center">
              <h3 className="text-3xl font-extrabold text-gray-900">
                Everything you need to win
              </h3>
              <p className="mt-4 max-w-2xl mx-auto text-xl text-gray-500">
                Comprehensive tools and analysis to give you the edge in your fantasy football draft and season.
              </p>
            </div>

            <div className="mt-12 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-2">
              {features.map((feature, index) => (
                <motion.div
                  key={feature.name}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6, delay: 0.1 * index }}
                  className="relative"
                >
                  <Link href={feature.href}>
                    <div className="card hover:shadow-lg transition-shadow duration-300 cursor-pointer h-full">
                      <div className="card-body">
                        <div>
                          <span className={`rounded-lg ${feature.bgColor} p-3 inline-flex`}>
                            <feature.icon className={`h-6 w-6 ${feature.color}`} aria-hidden="true" />
                          </span>
                        </div>
                        <div className="mt-4">
                          <h4 className="text-lg font-medium text-gray-900">{feature.name}</h4>
                          <p className="mt-2 text-base text-gray-500">{feature.description}</p>
                        </div>
                        <div className="mt-4">
                          <span className="text-blue-600 font-medium flex items-center">
                            Learn more
                            <ArrowRightIcon className="ml-1 h-4 w-4" />
                          </span>
                        </div>
                      </div>
                    </div>
                  </Link>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* How It Works Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.6 }}
            className="mt-16"
          >
            <div className="bg-gray-900 rounded-lg shadow-xl overflow-hidden">
              <div className="px-6 py-12 sm:px-12">
                <div className="text-center">
                  <h3 className="text-3xl font-extrabold text-white">
                    How It Works
                  </h3>
                  <p className="mt-4 text-xl text-gray-300">
                    Our advanced analytics pipeline in three simple steps
                  </p>
                </div>
                <div className="mt-12 grid grid-cols-1 gap-8 lg:grid-cols-3">
                  {[
                    {
                      step: '01',
                      title: 'Data Collection',
                      description: 'We scrape the latest player data, projections, and ADP from FantasyPros and other sources.',
                    },
                    {
                      step: '02',
                      title: 'Advanced Analysis',
                      description: 'Our algorithms calculate VORP, analyze positional scarcity, and identify tier breaks.',
                    },
                    {
                      step: '03',
                      title: 'Smart Recommendations',
                      description: 'Monte Carlo simulations provide optimal draft strategies and season projections.',
                    },
                  ].map((item, index) => (
                    <div key={item.step} className="text-center">
                      <div className="text-4xl font-bold text-blue-400 mb-4">{item.step}</div>
                      <h4 className="text-xl font-semibold text-white mb-2">{item.title}</h4>
                      <p className="text-gray-300">{item.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>

          {/* CTA Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.8 }}
            className="mt-16 text-center"
          >
            <div className="bg-blue-600 rounded-lg shadow-xl">
              <div className="px-6 py-12 sm:px-12">
                <h3 className="text-3xl font-extrabold text-white">
                  Ready to dominate your league?
                </h3>
                <p className="mt-4 text-xl text-blue-100">
                  Get started with our draft recommendations and team analysis tools.
                </p>
                <div className="mt-8">
                  <Link
                    href="/draft"
                    className="inline-flex items-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-blue-600 bg-white hover:bg-gray-50 transition-colors duration-200"
                  >
                    Start Your Draft Analysis
                    <ArrowRightIcon className="ml-2 h-5 w-5" />
                  </Link>
                </div>
              </div>
            </div>
          </motion.div>
        </main>

        {/* Footer */}
        <footer className="bg-white border-t border-gray-200 mt-16">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div className="text-center text-gray-500">
              <p>&copy; 2024 Fantasy Football Draft Helper. Built with advanced analytics and AI.</p>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
}
