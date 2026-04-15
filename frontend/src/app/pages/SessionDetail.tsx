import { Link, useParams } from "react-router";
import { ArrowLeft, Download, Calendar, Clock, Activity, Thermometer, Droplets } from "lucide-react";
import { RiskBadge } from "../components/RiskBadge";
import { SensorChart } from "../components/SensorChart";
import { SleepHypnogram } from "../components/SleepHypnogram";
import { ThemeToggle } from "../components/ThemeToggle";
import { mockSessions, generateSensorData, generateHypnogramData } from "../data/mockData";

export function SessionDetail() {
  const { id } = useParams<{ id: string }>();
  const session = mockSessions.find((s) => s.id === id);

  if (!session) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Session Not Found</h1>
          <Link to="/dashboard" className="text-blue-600 dark:text-blue-400 hover:underline">
            Return to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  const sensorData = generateSensorData(id || "S001");
  const hypnogramData = generateHypnogramData(id || "S001");

  const recommendations: string[] = [];
  if (session.sleepStages.n3 < 10) {
    recommendations.push("⚠️ Deep sleep (N3) was below 10% — consider reducing evening caffeine intake");
  }
  if (session.features.event_rate > 0.05) {
    recommendations.push("⚠️ Elevated apnea event rate detected — sleep clinic referral recommended");
  }
  if (session.features.HR_mean > 75) {
    recommendations.push("💡 Resting heart rate elevated — evening relaxation exercises may help");
  }
  if (session.features.sleep_efficiency > 90) {
    recommendations.push("✅ Excellent sleep efficiency — maintain current sleep hygiene practices");
  }
  if (session.sleepStages.rem < 12) {
    recommendations.push("💡 REM sleep below optimal range — ensure 7-9 hours of total sleep time");
  }

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
                <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Session {session.sid}</h1>
                <p className="text-sm text-gray-600 dark:text-gray-400">Detailed sleep analysis report</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2">
                <Download className="w-4 h-4" />
                Download Report
              </button>
              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Session Overview */}
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-8">
          <div className="flex items-start justify-between mb-6">
            <div className="flex gap-8">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Date</p>
                <p className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                  {new Date(session.date).toLocaleDateString("en-US", {
                    month: "long",
                    day: "numeric",
                    year: "numeric",
                  })}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Duration</p>
                <p className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                  {Math.floor(session.duration / 60)}h {session.duration % 60}m
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Status</p>
                <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100 rounded text-sm font-medium">
                  <div className="w-2 h-2 bg-green-500 dark:bg-green-400 rounded-full" />
                  {session.status}
                </span>
              </div>
            </div>
            <RiskBadge probability={session.riskProbability} size="lg" />
          </div>

          {/* Key Metrics */}
          <div className="grid grid-cols-4 gap-6 pt-6 border-t border-gray-100 dark:border-gray-700">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-5 h-5 text-red-500" />
                <p className="text-sm text-gray-600 dark:text-gray-400">Heart Rate</p>
              </div>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {session.features.HR_mean.toFixed(0)} <span className="text-sm font-normal text-gray-500">bpm</span>
              </p>
              <p className="text-xs text-gray-500 mt-1">±{session.features.HR_std.toFixed(1)} SD</p>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Droplets className="w-5 h-5 text-blue-500" />
                <p className="text-sm text-gray-600 dark:text-gray-400">EDA</p>
              </div>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {session.features.EDA_mean.toFixed(1)} <span className="text-sm font-normal text-gray-500">µS</span>
              </p>
              <p className="text-xs text-gray-500 mt-1">Electrodermal Activity</p>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Thermometer className="w-5 h-5 text-orange-500" />
                <p className="text-sm text-gray-600 dark:text-gray-400">Temperature</p>
              </div>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {session.features.TEMP_mean.toFixed(1)} <span className="text-sm font-normal text-gray-500">°C</span>
              </p>
              <p className="text-xs text-gray-500 mt-1">Skin Temperature</p>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-5 h-5 text-purple-500" />
                <p className="text-sm text-gray-600 dark:text-gray-400">Sleep Efficiency</p>
              </div>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{session.features.sleep_efficiency.toFixed(1)}%</p>
              <p className="text-xs text-gray-500 mt-1">
                Event Rate: {(session.features.event_rate * 100).toFixed(1)}%
              </p>
            </div>
          </div>
        </div>

        {/* Sleep Stages Distribution */}
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-8">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Sleep Stages Distribution</h3>
          <div className="grid grid-cols-5 gap-4">
            {Object.entries(session.sleepStages).map(([stage, pct]) => {
              const stageInfo: Record<
                string,
                { label: string; color: string; bgColor: string; description: string }
              > = {
                wake: {
                  label: "Wake",
                  color: "text-red-700",
                  bgColor: "bg-red-100 border-red-300",
                  description: "Time spent awake",
                },
                n1: {
                  label: "N1 (Light)",
                  color: "text-amber-700",
                  bgColor: "bg-amber-100 border-amber-300",
                  description: "Transition to sleep",
                },
                n2: {
                  label: "N2 (Light)",
                  color: "text-blue-700",
                  bgColor: "bg-blue-100 border-blue-300",
                  description: "Light sleep",
                },
                n3: {
                  label: "N3 (Deep)",
                  color: "text-purple-700",
                  bgColor: "bg-purple-100 border-purple-300",
                  description: "Deep restorative sleep",
                },
                rem: {
                  label: "REM",
                  color: "text-green-700",
                  bgColor: "bg-green-100 border-green-300",
                  description: "Dream stage",
                },
              };
              const info = stageInfo[stage];
              return (
                <div key={stage} className={`border rounded-lg p-4 ${info.bgColor}`}>
                  <p className={`font-semibold ${info.color} mb-1`}>{info.label}</p>
                  <p className={`text-3xl font-bold ${info.color}`}>{pct}%</p>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">{info.description}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Hypnogram */}
        <div className="mb-8">
          <SleepHypnogram data={hypnogramData} />
        </div>

        {/* Sensor Charts */}
        <div className="grid grid-cols-2 gap-6 mb-8">
          <SensorChart
            data={sensorData.hr}
            title="Heart Rate (HR)"
            color="#ef4444"
            unit="bpm"
            yAxisDomain={[40, 100]}
          />
          <SensorChart data={sensorData.eda} title="Electrodermal Activity (EDA)" color="#3b82f6" unit="µS" />
          <SensorChart
            data={sensorData.temp}
            title="Skin Temperature"
            color="#f59e0b"
            unit="°C"
            yAxisDomain={[32, 36]}
          />
          <SensorChart data={sensorData.bvp} title="Blood Volume Pulse (BVP)" color="#8b5cf6" unit="a.u." />
        </div>

        {/* Recommendations */}
        {recommendations.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Personalized Recommendations</h3>
            <div className="space-y-3">
              {recommendations.map((rec, idx) => (
                <div key={idx} className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                  <p className="text-sm text-gray-700 dark:text-gray-300">{rec}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}