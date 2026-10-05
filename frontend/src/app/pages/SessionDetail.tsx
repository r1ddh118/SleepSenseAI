import { Link, useParams } from "react-router";
import {
  ArrowLeft,
  Download,
  Calendar,
  Clock,
  Activity,
  Thermometer,
  Droplets,
  LogOut,
  User,
  FileText,
  ChevronDown,
  ExternalLink,
  Check,
  Loader2,
  TrendingUp,
  Sparkles,
  BarChart3,
  ShieldAlert,
  ShieldCheck,
  Moon,
  Sun,
  Layers,
} from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";
import { RiskBadge } from "../components/RiskBadge";
import { SensorChart } from "../components/SensorChart";
import { SleepHypnogram } from "../components/SleepHypnogram";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../context/AuthContext";
import { mockSessions, generateSensorData, generateHypnogramData } from "../data/mockData";
import { readStoredSessions } from "../data/sessionUtils";
import { useState, useEffect, useRef } from "react";

type TimeframeOption = "12h" | "24h" | "3d" | "1w";

const TIMEFRAME_BUTTONS: { id: TimeframeOption; label: string; sublabel: string; icon: any }[] = [
  { id: "12h", label: "12 Hours", sublabel: "Acute Overnight", icon: Moon },
  { id: "24h", label: "24 Hours", sublabel: "Circadian Diurnal", icon: Sun },
  { id: "3d", label: "3 Days", sublabel: "Acute Trajectory", icon: BarChart3 },
  { id: "1w", label: "1 Week", sublabel: "7-Day Longitudinal", icon: Layers },
];

export function SessionDetail() {
  const { id } = useParams<{ id: string }>();
  const { user, logout } = useAuth();
  const [downloading, setDownloading] = useState(false);
  const [downloadSuccess, setDownloadSuccess] = useState<string | null>(null);
  const [formatMenuOpen, setFormatMenuOpen] = useState(false);
  const [apiSession, setApiSession] = useState<any>(null);
  const [loadingSession, setLoadingSession] = useState(false);
  const [selectedTimeframe, setSelectedTimeframe] = useState<TimeframeOption>("24h");
  const [timeframeData, setTimeframeData] = useState<any>(null);
  const [loadingTimeframe, setLoadingTimeframe] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const storedSessions = user?.email ? readStoredSessions(`sessions_${user.email}`) : [];
  const session = apiSession ?? (storedSessions.find((s) => s.id === id) ?? mockSessions.find((s) => s.id === id));
  const sessionId = session?.sid || id || "S001";

  useEffect(() => {
    // Attempt to load session from backend API if available
    if (id) {
      setLoadingSession(true);
      fetch(`/api/v1/frontend/sessions/${id}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data && !data.error) {
            setApiSession(data);
          }
        })
        .catch(() => {})
        .finally(() => setLoadingSession(false));
    }
  }, [id]);

  useEffect(() => {
    if (sessionId) {
      setLoadingTimeframe(true);
      fetch(`/api/v1/sessions/${sessionId}/timeframe-analysis?timeframe=${selectedTimeframe}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data) {
            setTimeframeData(data);
          }
        })
        .catch((err) => console.warn("Timeframe fetch error:", err))
        .finally(() => setLoadingTimeframe(false));
    }
  }, [sessionId, selectedTimeframe]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setFormatMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleGetReport = async (format: "html" | "csv" | "json", download: boolean = true) => {
    setFormatMenuOpen(false);
    const reportUrl = `/api/v1/sessions/${sessionId}/report?format=${format}&timeframe=${selectedTimeframe}${download ? "&download=1" : ""}`;

    if (!download) {
      window.open(reportUrl, "_blank");
      return;
    }

    try {
      setDownloading(true);
      const token = localStorage.getItem("token");
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(reportUrl, { headers });
      if (!res.ok) {
        window.open(reportUrl, "_blank");
        return;
      }

      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = `SleepSense_Report_${sessionId}_${selectedTimeframe}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(blobUrl);
      document.body.removeChild(a);

      setDownloadSuccess(`Downloaded ${selectedTimeframe.toUpperCase()} ${format.toUpperCase()} report!`);
      setTimeout(() => setDownloadSuccess(null), 3500);
    } catch (err) {
      console.error("Report download error:", err);
      window.open(reportUrl, "_blank");
    } finally {
      setDownloading(false);
    }
  };

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

  // Derive metrics using timeframe data if available, fallback to session
  const tfSummary = timeframeData?.summary;
  const currentSleepScore = tfSummary?.sleep_score ?? (session.features?.sleep_efficiency ? Math.round(session.features.sleep_efficiency * 0.9 + 10) : 78);
  const currentEfficiency = tfSummary?.sleep_efficiency ?? session.features?.sleep_efficiency ?? 85.0;
  const currentDurationHours = tfSummary?.sleep_duration_hours ?? (session.duration ? (session.duration / 60) : 7.5);
  const currentHr = tfSummary?.avg_hr ?? session.features?.HR_mean ?? 64.0;
  const currentRiskLevel = tfSummary?.risk_level ?? session.riskLevel ?? (session.riskProbability >= 0.7 ? "high" : session.riskProbability >= 0.4 ? "moderate" : "low");
  const currentRiskProb = tfSummary?.risk_probability ?? session.riskProbability ?? (currentRiskLevel === "high" || currentRiskLevel === "HIGH" ? 0.78 : (currentRiskLevel === "moderate" || currentRiskLevel === "MODERATE" ? 0.48 : 0.18));
  const currentStages = tfSummary?.sleepStages ?? session.sleepStages ?? { wake: 12, n1: 15, n2: 45, n3: 16, rem: 12 };

  const recommendations: string[] = timeframeData?.insights ?? [];
  if (recommendations.length === 0) {
    if (currentStages.n3 < 10) {
      recommendations.push("⚠️ Deep sleep (N3) was below 10% — consider reducing evening caffeine intake");
    }
    if (session.features?.event_rate > 0.05) {
      recommendations.push("⚠️ Elevated apnea event rate detected — sleep clinic referral recommended");
    }
    if (currentHr > 75) {
      recommendations.push("💡 Resting heart rate elevated — evening relaxation exercises may help");
    }
    if (currentEfficiency > 88) {
      recommendations.push("✅ Excellent sleep efficiency — maintain current sleep hygiene practices");
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 pb-16">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-30 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                to="/dashboard"
                className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                title="Back to Dashboard"
              >
                <ArrowLeft className="w-5 h-5 text-gray-600 dark:text-gray-400" />
              </Link>
              <div>
                <div className="flex items-center gap-2.5">
                  <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Session {sessionId}</h1>
                  <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300">
                    {timeframeData?.timeframe_label || `${selectedTimeframe.toUpperCase()} Analysis`}
                  </span>
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Patient: {session.patientEmail || user?.email || "U034"} · Recorded: {session.date || "2026-10-05"}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Report Action Button & Dropdown */}
              <div className="relative" ref={menuRef}>
                <div className="inline-flex rounded-lg shadow-sm">
                  <button
                    onClick={() => handleGetReport("html", true)}
                    disabled={downloading}
                    className="px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white rounded-l-lg transition-all flex items-center gap-2 font-medium disabled:opacity-50 text-sm"
                  >
                    {downloading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Download className="w-4 h-4" />
                    )}
                    {downloading ? "Generating..." : `Get ${selectedTimeframe.toUpperCase()} Report`}
                  </button>
                  <button
                    onClick={() => setFormatMenuOpen(!formatMenuOpen)}
                    className="px-2.5 py-2 bg-blue-700 hover:bg-blue-800 text-white rounded-r-lg border-l border-blue-500 transition-colors"
                    title="Choose report format"
                  >
                    <ChevronDown className="w-4 h-4" />
                  </button>
                </div>

                {/* Format Dropdown Menu */}
                {formatMenuOpen && (
                  <div className="absolute right-0 mt-2 w-72 bg-white dark:bg-gray-800 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 z-50 py-2 animate-in fade-in zoom-in-95">
                    <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-700">
                      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                        {selectedTimeframe.toUpperCase()} Report Exports
                      </p>
                      <p className="text-[11px] text-gray-500 mt-0.5">
                        Includes clinical disclaimer & {timeframeData?.timeframe_label}
                      </p>
                    </div>

                    <button
                      onClick={() => handleGetReport("html", false)}
                      className="w-full px-4 py-2.5 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-blue-50 dark:hover:bg-gray-700 flex items-center justify-between transition-colors"
                    >
                      <span className="flex items-center gap-2">
                        <ExternalLink className="w-4 h-4 text-blue-500" />
                        View Interactive HTML
                      </span>
                      <span className="text-xs text-gray-400">Browser</span>
                    </button>

                    <button
                      onClick={() => handleGetReport("html", true)}
                      className="w-full px-4 py-2.5 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-blue-50 dark:hover:bg-gray-700 flex items-center justify-between transition-colors"
                    >
                      <span className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-emerald-500" />
                        Download HTML Report
                      </span>
                      <span className="text-xs bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-300 px-1.5 py-0.5 rounded font-mono">.html</span>
                    </button>

                    <button
                      onClick={() => handleGetReport("csv", true)}
                      className="w-full px-4 py-2.5 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-blue-50 dark:hover:bg-gray-700 flex items-center justify-between transition-colors"
                    >
                      <span className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-amber-500" />
                        Download CSV Metrics
                      </span>
                      <span className="text-xs bg-amber-100 dark:bg-amber-900/40 text-amber-600 dark:text-amber-300 px-1.5 py-0.5 rounded font-mono">.csv</span>
                    </button>

                    <button
                      onClick={() => handleGetReport("json", true)}
                      className="w-full px-4 py-2.5 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-blue-50 dark:hover:bg-gray-700 flex items-center justify-between transition-colors"
                    >
                      <span className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-purple-500" />
                        Download JSON Data
                      </span>
                      <span className="text-xs bg-purple-100 dark:bg-purple-900/40 text-purple-600 dark:text-purple-300 px-1.5 py-0.5 rounded font-mono">.json</span>
                    </button>
                  </div>
                )}
              </div>

              {downloadSuccess && (
                <span className="inline-flex items-center gap-1 text-xs text-green-700 dark:text-green-300 bg-green-100 dark:bg-green-900/40 px-2.5 py-1.5 rounded-md animate-fade-in font-medium">
                  <Check className="w-3.5 h-3.5" />
                  {downloadSuccess}
                </span>
              )}

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

      <div className="max-w-7xl mx-auto px-6 pt-6">
        {/* Timeframe Selector Bar */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-4 mb-6 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-500" />
                <h2 className="text-base font-bold text-gray-900 dark:text-gray-100">
                  Multi-Timeframe Patient Analysis Window
                </h2>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                Switch timeframes to aggregate acute vs longitudinal data from SQLite database. Reports dynamically adapt.
              </p>
            </div>

            {/* Timeframe Buttons */}
            <div className="inline-flex p-1 bg-gray-100 dark:bg-gray-700/70 rounded-xl gap-1">
              {TIMEFRAME_BUTTONS.map((btn) => {
                const Icon = btn.icon;
                const isSelected = selectedTimeframe === btn.id;
                return (
                  <button
                    key={btn.id}
                    onClick={() => setSelectedTimeframe(btn.id)}
                    className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                      isSelected
                        ? "bg-white dark:bg-gray-900 text-blue-600 dark:text-blue-400 shadow-sm"
                        : "text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
                    }`}
                  >
                    <Icon className={`w-3.5 h-3.5 ${isSelected ? "text-blue-600 dark:text-blue-400" : "text-gray-400"}`} />
                    <div className="text-left">
                      <div>{btn.label}</div>
                      <div className="text-[10px] font-normal opacity-75">{btn.sublabel}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Session Overview Card */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-6 mb-8 shadow-sm">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 mb-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
              <div>
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Timeframe Window</p>
                <p className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-1.5 text-sm">
                  <Calendar className="w-4 h-4 text-blue-500" />
                  {timeframeData?.timeframe_label || selectedTimeframe.toUpperCase()}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Duration Window</p>
                <p className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-1.5 text-sm">
                  <Clock className="w-4 h-4 text-purple-500" />
                  {currentDurationHours.toFixed(1)} hrs total
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Sleep Score</p>
                <p className="font-bold text-gray-900 dark:text-gray-100 text-base">
                  {currentSleepScore.toFixed(1)} <span className="text-xs font-normal text-gray-500">/ 100</span>
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Pipeline Status</p>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300 rounded-full text-xs font-semibold">
                  <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                  Analyzed (PySpark)
                </span>
              </div>
            </div>

            {/* Risk Factor Display with exact probability without NaN */}
            <div className="flex items-center gap-3 bg-gray-50 dark:bg-gray-900/60 p-3 rounded-xl border border-gray-100 dark:border-gray-700">
              <div className="text-right">
                <div className="text-xs font-medium text-gray-500 dark:text-gray-400">Screening Risk Factor</div>
                <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                  {(currentRiskProb * 100).toFixed(0)}% Probability
                </div>
              </div>
              <RiskBadge probability={currentRiskProb} risk={currentRiskLevel} size="lg" />
            </div>
          </div>

          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-6 border-t border-gray-100 dark:border-gray-700">
            <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-900/40 border border-gray-100 dark:border-gray-700/50">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Heart Rate Avg</p>
                <Activity className="w-4 h-4 text-red-500" />
              </div>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {currentHr.toFixed(1)} <span className="text-xs font-normal text-gray-500">bpm</span>
              </p>
              <p className="text-[11px] text-gray-500 mt-1">±{tfSummary?.hr_std ?? 5.2} bpm std dev</p>
            </div>

            <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-900/40 border border-gray-100 dark:border-gray-700/50">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Sleep Efficiency</p>
                <TrendingUp className="w-4 h-4 text-blue-500" />
              </div>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {currentEfficiency.toFixed(1)}%
              </p>
              <p className="text-[11px] text-gray-500 mt-1">
                {selectedTimeframe.toUpperCase()} aggregate index
              </p>
            </div>

            <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-900/40 border border-gray-100 dark:border-gray-700/50">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Apnea Event Rate</p>
                <ShieldAlert className="w-4 h-4 text-amber-500" />
              </div>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {((tfSummary?.event_rate ?? 0.02) * 100).toFixed(1)}%
              </p>
              <p className="text-[11px] text-gray-500 mt-1">Movement & arousal indices</p>
            </div>

            <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-900/40 border border-gray-100 dark:border-gray-700/50">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Skin Temp / EDA</p>
                <Thermometer className="w-4 h-4 text-emerald-500" />
              </div>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {(session.features?.TEMP_mean ?? 34.2).toFixed(1)} <span className="text-xs font-normal text-gray-500">°C</span>
              </p>
              <p className="text-[11px] text-gray-500 mt-1">EDA {(session.features?.EDA_mean ?? 2.8).toFixed(1)} µS tonic</p>
            </div>
          </div>
        </div>

        {/* Dynamic Timeframe Trend Chart */}
        {timeframeData?.trendData && timeframeData.trendData.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-6 mb-8 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-bold text-gray-900 dark:text-gray-100 text-lg">
                  {selectedTimeframe === "3d" || selectedTimeframe === "1w"
                    ? `Longitudinal Multi-Night Progression (${timeframeData.timeframe_label})`
                    : `Hourly Physiological Diurnal Curve (${timeframeData.timeframe_label})`}
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Data sourced from PySpark analytics & SQLite historical records
                </p>
              </div>
              <span className="px-3 py-1 bg-indigo-50 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 rounded-lg text-xs font-semibold">
                {timeframeData.trendData.length} Data Points
              </span>
            </div>

            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                {selectedTimeframe === "3d" || selectedTimeframe === "1w" ? (
                  <BarChart data={timeframeData.trendData}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                    <XAxis dataKey="day" stroke="#888888" fontSize={11} />
                    <YAxis stroke="#888888" fontSize={11} domain={[0, 100]} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#1F2937",
                        borderColor: "#374151",
                        borderRadius: "8px",
                        color: "#fff",
                        fontSize: "12px",
                      }}
                    />
                    <Legend />
                    <Bar dataKey="score" name="Sleep Score" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="efficiency" name="Efficiency %" fill="#10B981" radius={[4, 4, 0, 0]} />
                  </BarChart>
                ) : (
                  <LineChart data={timeframeData.trendData}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                    <XAxis dataKey="time" stroke="#888888" fontSize={11} />
                    <YAxis stroke="#888888" fontSize={11} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#1F2937",
                        borderColor: "#374151",
                        borderRadius: "8px",
                        color: "#fff",
                        fontSize: "12px",
                      }}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="hr" name="Heart Rate (bpm)" stroke="#EF4444" strokeWidth={2.5} dot={{ r: 4 }} />
                    <Line type="monotone" dataKey="quality" name="Restoration Index" stroke="#6366F1" strokeWidth={2.5} dot={{ r: 4 }} />
                  </LineChart>
                )}
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Sleep Stages Distribution */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-6 mb-8 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-gray-900 dark:text-gray-100 text-lg">
              Sleep Stages Breakdown ({timeframeData?.timeframe_label || selectedTimeframe.toUpperCase()})
            </h3>
            <span className="text-xs text-gray-500">Normal Range: Deep 15-25%, REM 20-25%</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
            {[
              { key: "wake", label: "Wake", pct: currentStages.wake ?? 12, color: "text-red-700 dark:text-red-400", bg: "bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-900/50", desc: "Nocturnal arousals" },
              { key: "n1", label: "N1 (Light)", pct: currentStages.n1 ?? 15, color: "text-amber-700 dark:text-amber-400", bg: "bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-900/50", desc: "Somnolence transition" },
              { key: "n2", label: "N2 (Light)", pct: currentStages.n2 ?? 45, color: "text-blue-700 dark:text-blue-400", bg: "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-900/50", desc: "Spindle core sleep" },
              { key: "n3", label: "N3 (Deep)", pct: currentStages.n3 ?? 16, color: "text-purple-700 dark:text-purple-400", bg: "bg-purple-50 dark:bg-purple-950/30 border-purple-200 dark:border-purple-900/50", desc: "Slow-wave restorative" },
              { key: "rem", label: "REM", pct: currentStages.rem ?? 12, color: "text-emerald-700 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-900/50", desc: "Dream / Memory" },
            ].map((stage) => (
              <div key={stage.key} className={`border rounded-xl p-4 ${stage.bg} transition-transform hover:scale-[1.02]`}>
                <p className={`font-semibold text-xs uppercase tracking-wider ${stage.color} mb-1`}>{stage.label}</p>
                <p className={`text-3xl font-extrabold ${stage.color}`}>{stage.pct}%</p>
                <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1">{stage.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Hypnogram */}
        <div className="mb-8">
          <SleepHypnogram data={hypnogramData} />
        </div>

        {/* Sensor Charts */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <SensorChart
            data={sensorData.hr}
            title="Heart Rate (HR Trace)"
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

        {/* Clinical Insights & Recommendations */}
        {recommendations.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="w-5 h-5 text-blue-500" />
              <h3 className="font-bold text-gray-900 dark:text-gray-100 text-lg">
                Clinical Screening Insights ({timeframeData?.timeframe_label || selectedTimeframe.toUpperCase()})
              </h3>
            </div>
            <div className="space-y-3">
              {recommendations.map((rec, idx) => (
                <div key={idx} className="flex items-start gap-3 p-3.5 bg-blue-50/50 dark:bg-gray-700/50 rounded-xl border border-blue-100/50 dark:border-gray-600/40">
                  <div className="mt-0.5">
                    <Check className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                  </div>
                  <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed font-medium">{rec}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50 rounded-xl text-xs text-amber-800 dark:text-amber-300">
              ⚠️ <b>Analytical Disclaimer:</b> This report is an analytical screening tool and does not constitute a medical diagnosis. Clinical interpretation should be performed by a qualified healthcare professional.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
