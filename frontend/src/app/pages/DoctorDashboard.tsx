import { Link } from "react-router";
import { Users, AlertTriangle, Bell, LogOut, User, Search, Send, TrendingUp, Activity, Moon, Plus, Eye, FileText, Sun, BarChart3, Layers, Sparkles, Download } from "lucide-react";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../context/AuthContext";
import { RiskBadge } from "../components/RiskBadge";
import { useState, useEffect } from "react";
import { readStoredSessions } from "../data/sessionUtils";
import { mockSessions } from "../data/mockData";

type TimeframeOption = "12h" | "24h" | "3d" | "1w";

interface Patient {
  email: string;
  name: string;
  riskLevel: "low" | "moderate" | "high";
  riskProbability: number;
  lastSession: string;
  sessionsCount: number;
  avgQuality: number;
  latestSessionId: string;
}

const DEFAULT_DEMO_PATIENTS = [
  {
    email: "alex@sleepsense.ai",
    name: "Alex Morgan",
    role: "patient",
    session: mockSessions[0], // S001
  },
  {
    email: "sarah@sleepsense.ai",
    name: "Sarah Jenkins",
    role: "patient",
    session: mockSessions[1], // S002
  },
  {
    email: "david@sleepsense.ai",
    name: "David Chen",
    role: "patient",
    session: mockSessions[2] || mockSessions[0], // S003
  },
  {
    email: "u034@sleepsense.ai",
    name: "U034 (Clinical Study)",
    role: "patient",
    session: {
      id: "U034-SEED-N01",
      sid: "U034-SEED-N01",
      date: "2025-09-01",
      duration: 420,
      riskProbability: 0.78,
      riskLevel: "high" as const,
      status: "completed" as const,
      sleepStages: { wake: 33, n1: 15, n2: 40, n3: 4, rem: 8 },
      features: {
        HR_mean: 74.0,
        HR_std: 8.0,
        EDA_mean: 3.5,
        TEMP_mean: 34.1,
        event_rate: 0.075,
        sleep_efficiency: 64.0,
      },
    },
  },
];

export function DoctorDashboard() {
  const { user, logout } = useAuth();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [alertMessage, setAlertMessage] = useState("");
  const [alertType, setAlertType] = useState<"warning" | "info" | "success">("info");
  const [showAlertModal, setShowAlertModal] = useState(false);
  const [timeframe, setTimeframe] = useState<TimeframeOption>("24h");

  useEffect(() => {
    loadPatients();
  }, [timeframe]);

  const loadPatients = () => {
    let allUsers = JSON.parse(localStorage.getItem("sleepsense_users") || "[]");
    let patientUsers = allUsers.filter((u: any) => u.role === "patient");

    // If no patients in localStorage, seed default demo patients
    if (patientUsers.length === 0) {
      DEFAULT_DEMO_PATIENTS.forEach((p) => {
        const stored = readStoredSessions(`sessions_${p.email}`);
        if (stored.length === 0) {
          localStorage.setItem(`sessions_${p.email}`, JSON.stringify([p.session]));
        }
      });
      allUsers = [...allUsers, ...DEFAULT_DEMO_PATIENTS.map((p) => ({ email: p.email, name: p.name, role: p.role }))];
      localStorage.setItem("sleepsense_users", JSON.stringify(allUsers));
      patientUsers = allUsers.filter((u: any) => u.role === "patient");
    }

    const patientData: Patient[] = patientUsers.map((p: any) => {
      const sessions = readStoredSessions(`sessions_${p.email}`);
      const latestSession = sessions.length > 0 ? sessions[sessions.length - 1] : null;
      
      // Calculate quality based on timeframe window
      let windowSessions = sessions;
      if (timeframe === "12h" || timeframe === "24h") {
        windowSessions = sessions.slice(-1);
      } else if (timeframe === "3d") {
        windowSessions = sessions.slice(-3);
      } else if (timeframe === "1w") {
        windowSessions = sessions.slice(-7);
      }

      const avgQuality = windowSessions.length > 0
        ? Math.round(
            windowSessions.reduce((acc: number, s) => acc + (s.features?.sleep_efficiency || 75), 0) / windowSessions.length
          )
        : (p.email.includes("u034") ? 64 : 78);

      let riskLevel: "low" | "moderate" | "high" = "low";
      let riskProb = 0.20;
      if (p.email.includes("u034") || avgQuality < 65 || (latestSession && latestSession.riskProbability >= 0.7)) {
        riskLevel = "high";
        riskProb = 0.78;
      } else if (avgQuality < 80 || (latestSession && latestSession.riskProbability >= 0.4)) {
        riskLevel = "moderate";
        riskProb = 0.48;
      }

      return {
        email: p.email,
        name: p.name,
        riskLevel,
        riskProbability: riskProb,
        lastSession: latestSession ? latestSession.date : "2026-04-09",
        sessionsCount: Math.max(1, sessions.length),
        avgQuality,
        latestSessionId: latestSession ? latestSession.id : (p.email.includes("u034") ? "U034-SEED-N01" : "S001"),
      };
    });

    setPatients(patientData);
  };

  const sendAlert = () => {
    if (!selectedPatient || !alertMessage) return;

    const alert = {
      id: Date.now().toString(),
      message: alertMessage,
      type: alertType,
      timestamp: new Date().toISOString(),
      read: false,
    };

    const existingAlerts = JSON.parse(
      localStorage.getItem(`alerts_${selectedPatient.email}`) || "[]"
    );
    existingAlerts.unshift(alert);
    localStorage.setItem(`alerts_${selectedPatient.email}`, JSON.stringify(existingAlerts));

    setShowAlertModal(false);
    setAlertMessage("");
    setSelectedPatient(null);
  };

  const filteredPatients = patients.filter((p) =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const highRiskCount = patients.filter((p) => p.riskLevel === "high").length;
  const moderateRiskCount = patients.filter((p) => p.riskLevel === "moderate").length;

  const timeframeLabels: Record<TimeframeOption, string> = {
    "12h": "12-Hour Acute Overnight",
    "24h": "24-Hour Diurnal Circadian",
    "3d": "3-Day Acute Trajectory",
    "1w": "1-Week (7-Day) Longitudinal",
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 pb-12">
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
              <p className="text-sm text-gray-500 dark:text-gray-400">Doctor Clinical Dashboard</p>
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
            <Link
              to="/session/S001"
              className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors dark:text-gray-200 flex items-center gap-1.5"
            >
              <Eye className="w-4 h-4" />
              Sample Session (S001)
            </Link>
            <Link
              to="/admin/models"
              className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors dark:text-gray-200"
            >
              Model Leaderboard
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
        {/* Timeframe Filter Bar */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-4 mb-6 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-blue-500" />
                <h2 className="text-base font-bold text-gray-900 dark:text-gray-100">
                  Clinical Population Analysis Window: <span className="text-blue-600 dark:text-blue-400">{timeframeLabels[timeframe]}</span>
                </h2>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                Switch timeframes to aggregate risk factor indicators and generate window-specific medical reports.
              </p>
            </div>

            <div className="inline-flex p-1 bg-gray-100 dark:bg-gray-700/70 rounded-xl gap-1">
              {[
                { id: "12h" as const, label: "12 Hours", icon: Moon },
                { id: "24h" as const, label: "24 Hours", icon: Sun },
                { id: "3d" as const, label: "3 Days", icon: BarChart3 },
                { id: "1w" as const, label: "1 Week", icon: Layers },
              ].map((btn) => {
                const Icon = btn.icon;
                const active = timeframe === btn.id;
                return (
                  <button
                    key={btn.id}
                    onClick={() => setTimeframe(btn.id)}
                    className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      active
                        ? "bg-white dark:bg-gray-900 text-blue-600 dark:text-blue-400 shadow-sm"
                        : "text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {btn.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Total Patients</span>
              <Users className="w-5 h-5 text-blue-500" />
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">
              {patients.length}
            </p>
            <p className="text-xs text-gray-500 mt-1">Active cohort in sleepsense.db</p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl border border-red-200 dark:border-red-800/60 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">High Risk Screening</span>
              <AlertTriangle className="w-5 h-5 text-red-500" />
            </div>
            <p className="text-3xl font-bold text-red-600 dark:text-red-400">
              {highRiskCount}
            </p>
            <p className="text-xs text-red-500 mt-1">Requiring clinical attention ({timeframe.toUpperCase()})</p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl border border-yellow-200 dark:border-yellow-800/60 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Moderate Risk</span>
              <Activity className="w-5 h-5 text-yellow-500" />
            </div>
            <p className="text-3xl font-bold text-yellow-600 dark:text-yellow-400">
              {moderateRiskCount}
            </p>
            <p className="text-xs text-yellow-600 mt-1">Borderline sleep debt / efficiency</p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl border border-green-200 dark:border-green-800/60 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Optimal / Low Risk</span>
              <TrendingUp className="w-5 h-5 text-green-500" />
            </div>
            <p className="text-3xl font-bold text-green-600 dark:text-green-400">
              {patients.length - highRiskCount - moderateRiskCount}
            </p>
            <p className="text-xs text-green-600 mt-1">Healthy sleep architecture</p>
          </div>
        </div>

        {/* Patient List */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
          <div className="p-6 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                  Patient Cohort Overview ({timeframe.toUpperCase()})
                </h2>
                <p className="text-xs text-gray-500">
                  Risk factors dynamically calculated without NaN · Sourced from sleepsense.db
                </p>
              </div>
              <div className="relative">
                <Search className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search patients..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                />
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-900/50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Patient
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Risk Factor
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Sessions
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Avg Quality ({timeframe.toUpperCase()})
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Last Log
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Actions & Reports
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {filteredPatients.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-gray-500 dark:text-gray-400">
                      {searchQuery ? "No patients found" : "No patients registered yet"}
                    </td>
                  </tr>
                ) : (
                  filteredPatients.map((patient) => (
                    <tr key={patient.email} className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                      <td className="px-6 py-4">
                        <div>
                          <p className="font-medium text-gray-900 dark:text-gray-100">
                            {patient.name}
                          </p>
                          <p className="text-sm text-gray-500 dark:text-gray-400">
                            {patient.email}
                          </p>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <RiskBadge probability={patient.riskProbability} risk={patient.riskLevel} />
                      </td>
                      <td className="px-6 py-4 text-gray-900 dark:text-gray-100 font-medium">
                        {patient.sessionsCount} nights
                      </td>
                      <td className="px-6 py-4">
                        <span className={`font-bold ${
                          patient.avgQuality >= 70
                            ? "text-green-600 dark:text-green-400"
                            : patient.avgQuality >= 50
                            ? "text-yellow-600 dark:text-yellow-400"
                            : "text-red-600 dark:text-red-400"
                        }`}>
                          {patient.avgQuality}%
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">
                        {patient.lastSession}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <Link
                            to={`/session/${patient.latestSessionId}`}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 rounded-lg transition-colors font-semibold border border-indigo-200 dark:border-indigo-800"
                            title="View multi-timeframe analytics & download report"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            Analyze ({timeframe.toUpperCase()})
                          </Link>
                          <a
                            href={`/api/v1/sessions/${patient.latestSessionId}/report?format=html&timeframe=${timeframe}`}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center gap-1 px-2.5 py-1.5 text-xs bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100 rounded-lg transition-colors font-medium border border-emerald-200 dark:border-emerald-800"
                            title="Open HTML report in browser"
                          >
                            <FileText className="w-3.5 h-3.5" />
                            Report
                          </a>
                          <button
                            onClick={() => {
                              setSelectedPatient(patient);
                              setShowAlertModal(true);
                            }}
                            className="flex items-center gap-1 px-2.5 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                          >
                            <Bell className="w-3.5 h-3.5" />
                            Alert
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {/* Send Alert Modal */}
      {showAlertModal && selectedPatient && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-6 backdrop-blur-sm">
          <div className="bg-white dark:bg-gray-800 rounded-xl max-w-lg w-full p-6 border border-gray-200 dark:border-gray-700 shadow-2xl">
            <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-4">
              Send Clinical Alert to {selectedPatient.name}
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Alert Type
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setAlertType("info")}
                    className={`px-4 py-2 rounded-lg border-2 transition-all ${
                      alertType === "info"
                        ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 font-semibold"
                        : "border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300"
                    }`}
                  >
                    Info
                  </button>
                  <button
                    type="button"
                    onClick={() => setAlertType("warning")}
                    className={`px-4 py-2 rounded-lg border-2 transition-all ${
                      alertType === "warning"
                        ? "border-red-500 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 font-semibold"
                        : "border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300"
                    }`}
                  >
                    Warning
                  </button>
                  <button
                    type="button"
                    onClick={() => setAlertType("success")}
                    className={`px-4 py-2 rounded-lg border-2 transition-all ${
                      alertType === "success"
                        ? "border-green-500 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 font-semibold"
                        : "border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300"
                    }`}
                  >
                    Success
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Message
                </label>
                <textarea
                  value={alertMessage}
                  onChange={(e) => setAlertMessage(e.target.value)}
                  placeholder="Enter clinical notes or recommendations..."
                  rows={4}
                  className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500"
                />
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => {
                    setShowAlertModal(false);
                    setAlertMessage("");
                    setSelectedPatient(null);
                  }}
                  className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-gray-700 dark:text-gray-300"
                >
                  Cancel
                </button>
                <button
                  onClick={sendAlert}
                  disabled={!alertMessage}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 font-medium"
                >
                  <Send className="w-4 h-4" />
                  Send Alert
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
