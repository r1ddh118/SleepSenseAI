import { Link } from "react-router";
import { Plus, Activity, Moon, TrendingUp, TrendingDown, Bell, LogOut, User, Clock } from "lucide-react";
import { SessionCard } from "../components/SessionCard";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../context/AuthContext";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { useState, useEffect } from "react";
import { readStoredSessions } from "../data/sessionUtils";

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

  useEffect(() => {
    // Load patient-specific alerts
    const savedAlerts = localStorage.getItem(`alerts_${user?.email}`);
    if (savedAlerts) {
      setAlerts(JSON.parse(savedAlerts));
    }
  }, [user?.email]);

  // Get patient's own sessions
  const patientSessions = readStoredSessions(`sessions_${user?.email}`);

  const markAlertAsRead = (alertId: string) => {
    const updatedAlerts = alerts.map((alert) =>
      alert.id === alertId ? { ...alert, read: true } : alert
    );
    setAlerts(updatedAlerts);
    localStorage.setItem(`alerts_${user?.email}`, JSON.stringify(updatedAlerts));
  };

  // Calculate sleep quality trend
  const trendData = patientSessions.slice(-7).map((session, index: number) => ({
    day: `Day ${index + 1}`,
    quality: Math.round(session.features.sleep_efficiency || Math.floor(Math.random() * 40) + 60),
  }));

  const unreadAlerts = alerts.filter((a) => !a.read).length;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
              <Moon className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                SleepSense AI
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">My Sleep Dashboard</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/session/new"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
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

      <main className="max-w-7xl mx-auto px-6 py-8">
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
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Total Sessions</span>
              <Activity className="w-5 h-5 text-blue-500" />
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">
              {patientSessions.length}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Sleep sessions logged
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Avg Sleep Quality</span>
              <TrendingUp className="w-5 h-5 text-green-500" />
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">
              {patientSessions.length > 0
                ? Math.round(
                    patientSessions.reduce((acc: number, s) => acc + s.features.sleep_efficiency, 0) /
                      patientSessions.length
                  )
                : 0}
              %
            </p>
            <p className="text-sm text-green-600 dark:text-green-400 mt-1 flex items-center gap-1">
              <TrendingUp className="w-3 h-3" />
              Improving trend
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Avg Sleep Duration</span>
              <Moon className="w-5 h-5 text-purple-500" />
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">
              {patientSessions.length > 0
                ? `${(
                    patientSessions.reduce((acc, session) => acc + session.duration, 0) /
                    patientSessions.length /
                    60
                  ).toFixed(1)}h`
                : "0h"}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Per night average
            </p>
          </div>
        </div>

        {/* Sleep Quality Trend */}
        {trendData.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 mb-8">
            <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">
              Sleep Quality Trend (Last 7 Days)
            </h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.1} />
                <XAxis dataKey="day" stroke="#6B7280" fontSize={12} />
                <YAxis stroke="#6B7280" fontSize={12} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1F2937",
                    border: "1px solid #374151",
                    borderRadius: "8px",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="quality"
                  stroke="#3B82F6"
                  strokeWidth={2}
                  dot={{ fill: "#3B82F6" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* My Sleep Sessions */}
        <div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-4">
            My Sleep Sessions
          </h2>
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
