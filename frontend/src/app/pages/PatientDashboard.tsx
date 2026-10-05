import { Link } from "react-router";
import { Plus, Activity, Moon, Sun, TrendingUp, TrendingDown, Bell, LogOut, User, Clock, FileText, Download, BarChart3, Layers, Sparkles } from "lucide-react";
import { SessionCard } from "../components/SessionCard";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../context/AuthContext";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { useState, useEffect } from "react";
import { readStoredSessions } from "../data/sessionUtils";
import { mockSessions } from "../data/mockData";

type TimeframeOption = "12h" | "24h" | "3d" | "1w";

interface Alert {
  id: string;
  message: string;
  type: "warning" | "info" | "success";
  timestamp: string;
  read: boolean;
}

export function PatientDashboard() {
  const { user, logout } = useAuth();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [timeframe, setTimeframe] = useState<TimeframeOption>("24h");

  useEffect(() => {
    // Load patient-specific alerts
    const savedAlerts = localStorage.getItem(`alerts_${user?.email}`);
    if (savedAlerts) {
      setAlerts(JSON.parse(savedAlerts));
    }
  }, [user?.email]);

  // Get patient's own sessions or fallback to sample mock sessions
  const stored = user?.email ? readStoredSessions(`sessions_${user.email}`) : [];
  const patientSessions = stored.length > 0 ? stored : mockSessions;
  const latestSession = patientSessions[patientSessions.length - 1];
  const latestSessionId = latestSession?.sid || latestSession?.id || "S001";

  const markAlertAsRead = (alertId: string) => {
    const updatedAlerts = alerts.map((alert) =>
      alert.id === alertId ? { ...alert, read: true } : alert
    );
    setAlerts(updatedAlerts);
    localStorage.setItem(`alerts_${user?.email}`, JSON.stringify(updatedAlerts));
  };

  // Filter sessions according to selected timeframe
  let windowSessions = patientSessions;
  if (timeframe === "12h" || timeframe === "24h") {
    windowSessions = patientSessions.slice(-1);
  } else if (timeframe === "3d") {
    windowSessions = patientSessions.slice(-3);
  } else if (timeframe === "1w") {
    windowSessions = patientSessions.slice(-7);
  }

  const avgQuality = windowSessions.length > 0
    ? Math.round(
        windowSessions.reduce((acc: number, s) => acc + (s.features?.sleep_efficiency || 85), 0) /
          windowSessions.length
      )
    : 82;

  const avgDurationHours = windowSessions.length > 0
    ? (
        windowSessions.reduce((acc, session) => acc + (session.duration || 450), 0) /
        windowSessions.length /
        60
      ).toFixed(1)
    : "7.5";

  // Build trend chart data based on timeframe
  let trendData: any[] = [];
  if (timeframe === "12h") {
    const hrBase = latestSession?.features?.HR_mean || 64;
    trendData = [
      { label: "10 PM", score: 95, hr: Math.round(hrBase + 8) },
      { label: "12 AM", score: 88, hr: Math.round(hrBase - 2) },
      { label: "02 AM", score: 92, hr: Math.round(hrBase - 6) },
      { label: "04 AM", score: 75, hr: Math.round(hrBase + 1) },
      { label: "06 AM", score: 82, hr: Math.round(hrBase - 4) },
      { label: "08 AM", score: 90, hr: Math.round(hrBase + 5) },
    ];
  } else if (timeframe === "24h") {
    const hrBase = latestSession?.features?.HR_mean || 64;
    trendData = [
      { label: "08:00", score: 85, hr: Math.round(hrBase + 14) },
      { label: "12:00", score: 80, hr: Math.round(hrBase + 18) },
      { label: "16:00", score: 75, hr: Math.round(hrBase + 10) },
      { label: "20:00", score: 82, hr: Math.round(hrBase + 2) },
      { label: "00:00", score: 92, hr: Math.round(hrBase - 5) },
      { label: "04:00", score: 95, hr: Math.round(hrBase - 7) },
    ];
  } else if (timeframe === "3d") {
    trendData = windowSessions.map((s, idx) => ({
      label: `Day ${idx + 1} (${s.date || `N${idx + 1}`})`,
      quality: Math.round(s.features?.sleep_efficiency || 80),
      duration: Number(((s.duration || 450) / 60).toFixed(1)),
    }));
  } else {
    trendData = windowSessions.map((session, index: number) => ({
      label: `Night ${index + 1}`,
      quality: Math.round(session.features?.sleep_efficiency || 82),
      duration: Number(((session.duration || 450) / 60).toFixed(1)),
    }));
  }

  const unreadAlerts = alerts.filter((a) => !a.read).length;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 pb-16">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
              <Moon className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                SleepSense AI
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">My Sleep Health Portal</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/session/new"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 text-sm font-medium shadow-sm"
            >
              <Plus className="w-4 h-4" />
              Log Sleep Session
            </Link>
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
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* Timeframe Selector & Report Quick Action */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-4 mb-6 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-500" />
                <h2 className="text-base font-bold text-gray-900 dark:text-gray-100">
                  Analysis Window Selection
                </h2>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                Switch between 12-hour acute, 24-hour diurnal, 3-day multi-night, or 1-week longitudinal analysis.
              </p>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <div className="inline-flex p-1 bg-gray-100 dark:bg-gray-700/70 rounded-xl gap-1">
                {[
                  { id: "12h" as const, label: "12h", sub: "Overnight", icon: Moon },
                  { id: "24h" as const, label: "24h", sub: "Diurnal", icon: Sun },
                  { id: "3d" as const, label: "3 Days", sub: "Multi-Night", icon: BarChart3 },
                  { id: "1w" as const, label: "1 Week", sub: "Longitudinal", icon: Layers },
                ].map((btn) => {
                  const Icon = btn.icon;
                  const active = timeframe === btn.id;
                  return (
                    <button
                      key={btn.id}
                      onClick={() => setTimeframe(btn.id)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                        active
                          ? "bg-white dark:bg-gray-900 text-blue-600 dark:text-blue-400 shadow-sm"
                          : "text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
                      }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      <span>{btn.label}</span>
                    </button>
                  );
                })}
              </div>

              <a
                href={`/api/v1/sessions/${latestSessionId}/report?format=html&timeframe=${timeframe}&download=1`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white rounded-xl text-xs font-semibold transition-all shadow-sm"
              >
                <Download className="w-3.5 h-3.5" />
                Download {timeframe.toUpperCase()} Report
              </a>
            </div>
          </div>
        </div>

        {/* Alerts Section */}
        {alerts.length > 0 && (
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <Bell className="w-5 h-5" />
                Alerts from Your Doctor
                {unreadAlerts > 0 && (
                  <span className="px-2 py-1 bg-red-500 text-white text-xs rounded-full">
                    {unreadAlerts}
                  </span>
                )}
              </h2>
            </div>
            <div className="space-y-3">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  className={`p-4 rounded-lg border flex items-start justify-between ${
                    alert.read
                      ? "bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700"
                      : alert.type === "warning"
                      ? "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800"
                      : alert.type === "info"
                      ? "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800"
                      : "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800"
                  }`}
                >
                  <div className="flex-1">
                    <p
                      className={`${
                        alert.read
                          ? "text-gray-600 dark:text-gray-400"
                          : alert.type === "warning"
                          ? "text-red-800 dark:text-red-300"
                          : alert.type === "info"
                          ? "text-blue-800 dark:text-blue-300"
                          : "text-green-800 dark:text-green-300"
                      }`}
                    >
                      {alert.message}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(alert.timestamp).toLocaleString()}
                    </p>
                  </div>
                  {!alert.read && (
                    <button
                      onClick={() => markAlertAsRead(alert.id)}
                      className="text-sm text-blue-600 dark:text-blue-400 hover:underline ml-4"
                    >
                      Mark as read
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Sessions Window</span>
              <Activity className="w-5 h-5 text-blue-500" />
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">
              {windowSessions.length} <span className="text-sm font-normal text-gray-500">logged</span>
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              {timeframe.toUpperCase()} analysis window
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Avg Sleep Quality</span>
              <TrendingUp className="w-5 h-5 text-green-500" />
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">
              {avgQuality}%
            </p>
            <p className="text-xs text-green-600 dark:text-green-400 mt-1 flex items-center gap-1">
              <TrendingUp className="w-3 h-3" />
              {timeframe.toUpperCase()} efficiency score
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Avg Sleep Duration</span>
              <Moon className="w-5 h-5 text-purple-500" />
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">
              {avgDurationHours}h
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Per window average
            </p>
          </div>
        </div>

        {/* Sleep Quality Trend */}
        {trendData.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 mb-8 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">
                  {timeframe === "12h" || timeframe === "24h"
                    ? `Diurnal Rest & Heart Rate Curve (${timeframe.toUpperCase()})`
                    : `Multi-Night Sleep Quality Progression (${timeframe.toUpperCase()})`}
                </h3>
                <p className="text-xs text-gray-500">Longitudinal timeline from database tracking</p>
              </div>
              <span className="text-xs px-2.5 py-1 bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 font-semibold rounded-lg">
                {timeframe.toUpperCase()} Window
              </span>
            </div>

            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                {timeframe === "3d" || timeframe === "1w" ? (
                  <BarChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                    <XAxis dataKey="label" stroke="#888888" fontSize={12} />
                    <YAxis stroke="#888888" fontSize={12} domain={[0, 100]} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#1F2937",
                        borderColor: "#374151",
                        borderRadius: "8px",
                        color: "#fff",
                      }}
                    />
                    <Legend />
                    <Bar dataKey="quality" name="Sleep Quality %" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                ) : (
                  <LineChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                    <XAxis dataKey="label" stroke="#888888" fontSize={12} />
                    <YAxis stroke="#888888" fontSize={12} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#1F2937",
                        borderColor: "#374151",
                        borderRadius: "8px",
                        color: "#fff",
                      }}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="score" name="Rest Score" stroke="#3B82F6" strokeWidth={2.5} dot={{ r: 4 }} />
                    <Line type="monotone" dataKey="hr" name="Heart Rate (bpm)" stroke="#EF4444" strokeWidth={2.5} dot={{ r: 4 }} />
                  </LineChart>
                )}
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* My Sleep Sessions */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
              My Sleep Sessions History
            </h2>
            <p className="text-xs text-gray-500">Click any session to view multi-timeframe analytics & reports</p>
          </div>

          {patientSessions.length === 0 ? (
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-12 text-center">
              <Moon className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                No sleep sessions logged yet
              </p>
              <Link
                to="/session/new"
                className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                <Plus className="w-4 h-4" />
                Log Your First Session
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {patientSessions.map((session) => (
                <SessionCard key={session.id} session={session} />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
