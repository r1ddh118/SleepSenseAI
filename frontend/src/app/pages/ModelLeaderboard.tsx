import { Link } from "react-router";
import { ArrowLeft, Trophy, Clock, TrendingUp, CheckCircle2, LogOut, User } from "lucide-react";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../context/AuthContext";
import { modelLeaderboard } from "../data/mockData";

export function ModelLeaderboard() {
  const { user, logout } = useAuth();

  // Sort by AUC-ROC
  const sortedModels = [...modelLeaderboard].sort((a, b) => b.aucRoc - a.aucRoc);

  const formatMetric = (value: number) => (value * 100).toFixed(1) + "%";
  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    return `${(seconds / 60).toFixed(1)}m`;
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                to="/dashboard"
                className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-gray-600 dark:text-gray-400" />
              </Link>
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Model Leaderboard</h1>
                <p className="text-sm text-gray-600 dark:text-gray-400">Benchmark comparison of 8 ML models</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2">
                <TrendingUp className="w-4 h-4" />
                Retrain Models
              </button>
              <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 dark:bg-gray-700 rounded-lg">
                <User className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                <span className="text-sm text-gray-700 dark:text-gray-300">{user?.name}</span>
              </div>
              <button
                onClick={logout}
                className="p-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                title="Logout"
              >
                <LogOut className="w-5 h-5" />
              </button>
              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Info Banner */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-8">
          <p className="text-sm text-blue-900">
            <strong>Active Model:</strong> XGBoost — All predictions are currently using this model. Models are
            benchmarked on 40+ engineered physiological features from Empatica E4 sensor data.
          </p>
        </div>

        {/* Leaderboard Table */}
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
                  <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                    Rank
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                    Model
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                    Accuracy
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                    Precision
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                    Recall
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                    F1 Score
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                    AUC-ROC
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                    Train Time
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-600">
                {sortedModels.map((model, index) => (
                  <tr key={model.name} className={index < 3 ? "bg-blue-50/30 dark:bg-blue-50/30" : "bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700"}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        {index === 0 && <Trophy className="w-5 h-5 text-yellow-500" />}
                        {index === 1 && <Trophy className="w-5 h-5 text-gray-400" />}
                        {index === 2 && <Trophy className="w-5 h-5 text-orange-600" />}
                        <span className="font-semibold text-gray-900 dark:text-gray-100">{index + 1}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-900 dark:text-gray-100">{model.name}</span>
                        {model.isActive && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-800 rounded text-xs font-medium">
                            <CheckCircle2 className="w-3 h-3" />
                            Active
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <div className="relative">
                        <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{formatMetric(model.accuracy)}</div>
                        <div
                          className="absolute bottom-0 left-0 h-1 bg-blue-500 rounded"
                          style={{ width: `${model.accuracy * 100}%` }}
                        />
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center text-sm text-gray-700 dark:text-gray-300">
                      {formatMetric(model.precision)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center text-sm text-gray-700 dark:text-gray-300">
                      {formatMetric(model.recall)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center text-sm text-gray-700 dark:text-gray-300">
                      {formatMetric(model.f1Score)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className="font-semibold text-gray-900 dark:text-gray-100">{formatMetric(model.aucRoc)}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center text-sm text-gray-700 dark:text-gray-300">
                      <div className="flex items-center justify-center gap-1">
                        <Clock className="w-3 h-3 text-gray-400" />
                        {formatTime(model.trainTime)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <button
                        className="text-sm text-blue-600 hover:text-blue-700 font-medium disabled:text-gray-400 disabled:cursor-not-allowed"
                        disabled={model.isActive}
                      >
                        {model.isActive ? "In Use" : "Activate"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Model Details */}
        <div className="mt-8 grid grid-cols-2 gap-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Training Configuration</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Dataset</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">Empatica E4 + PSG Ground Truth</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Features Engineered</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">40+ physiological features</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Cross-Validation</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">5-fold stratified CV</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Test Set Size</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">20% holdout</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Hardware</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">Raspberry Pi 5 (4GB)</span>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Performance Insights</h3>
            <div className="space-y-3">
              <div className="p-3 bg-green-50 rounded-lg">
                <p className="text-sm text-green-900">
                  <strong>Best Overall:</strong> XGBoost achieves 96.7% AUC-ROC with excellent precision-recall
                  balance
                </p>
              </div>
              <div className="p-3 bg-blue-50 rounded-lg">
                <p className="text-sm text-blue-900">
                  <strong>Fastest:</strong> Logistic Regression trains in 12.4s — ideal for rapid prototyping
                </p>
              </div>
              <div className="p-3 bg-amber-50 rounded-lg">
                <p className="text-sm text-amber-900">
                  <strong>Trade-off:</strong> Neural Network has high accuracy but 3x longer training time
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Feature Importance Preview */}
        <div className="mt-8 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Top Features (XGBoost SHAP Values)</h3>
          <div className="space-y-2">
            {[
              { name: "HR_std (Heart rate variability)", importance: 0.18 },
              { name: "EDA_mean (Electrodermal activity)", importance: 0.15 },
              { name: "sleep_stage_pct_N3 (Deep sleep %)", importance: 0.13 },
              { name: "event_rate (Apnea events)", importance: 0.12 },
              { name: "TEMP_mean (Skin temperature)", importance: 0.09 },
            ].map((feature) => (
              <div key={feature.name} className="flex items-center gap-4">
                <div className="w-64 text-sm text-gray-700 dark:text-gray-300">{feature.name}</div>
                <div className="flex-1 bg-gray-100 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{ width: `${feature.importance * 100}%` }}
                  />
                </div>
                <div className="w-12 text-right text-sm font-medium text-gray-900 dark:text-gray-100">
                  {(feature.importance * 100).toFixed(0)}%
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}