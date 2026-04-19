import { Link } from "react-router";
import { Users, AlertTriangle, Bell, LogOut, User, Search, Send, TrendingUp, Activity, Moon } from "lucide-react";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../context/AuthContext";
import { RiskBadge } from "../components/RiskBadge";
import { useState, useEffect } from "react";

interface Patient {
  email: string;
  name: string;
  riskLevel: "low" | "moderate" | "high";
  lastSession: string;
  sessionsCount: number;
  avgQuality: number;
}

export function DoctorDashboard() {
  const { user, logout } = useAuth();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [alertMessage, setAlertMessage] = useState("");
  const [alertType, setAlertType] = useState<"warning" | "info" | "success">("info");
  const [showAlertModal, setShowAlertModal] = useState(false);

  useEffect(() => {
    loadPatients();
  }, []);

  const loadPatients = () => {
    const allUsers = JSON.parse(localStorage.getItem("sleepsense_users") || "[]");
    const patientUsers = allUsers.filter((u: any) => u.role === "patient");

    const patientData: Patient[] = patientUsers.map((p: any) => {
      const sessions = JSON.parse(localStorage.getItem(`sessions_${p.email}`) || "[]");
      const avgQuality = sessions.length > 0
        ? Math.round(sessions.reduce((acc: number, s: any) => acc + (s.sleepQuality || 75), 0) / sessions.length)
        : 0;

      // Determine risk level based on sleep quality and sessions
      let riskLevel: "low" | "moderate" | "high" = "low";
      if (avgQuality < 50 || sessions.length === 0) {
        riskLevel = "high";
      } else if (avgQuality < 70) {
        riskLevel = "moderate";
      }

      return {
        email: p.email,
        name: p.name,
        riskLevel,
        lastSession: sessions.length > 0 ? sessions[sessions.length - 1].date : "No sessions",
        sessionsCount: sessions.length,
        avgQuality,
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
              <p className="text-sm text-gray-500 dark:text-gray-400">Doctor Dashboard</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/admin/models"
              className="px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors dark:text-gray-200"
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

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Total Patients</span>
              <Users className="w-5 h-5 text-blue-500" />
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">
              {patients.length}
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl border border-red-200 dark:border-red-800 p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">High Risk</span>
              <AlertTriangle className="w-5 h-5 text-red-500" />
            </div>
            <p className="text-3xl font-bold text-red-600 dark:text-red-400">
              {highRiskCount}
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl border border-yellow-200 dark:border-yellow-800 p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Moderate Risk</span>
              <Activity className="w-5 h-5 text-yellow-500" />
            </div>
            <p className="text-3xl font-bold text-yellow-600 dark:text-yellow-400">
              {moderateRiskCount}
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl border border-green-200 dark:border-green-800 p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Low Risk</span>
              <TrendingUp className="w-5 h-5 text-green-500" />
            </div>
            <p className="text-3xl font-bold text-green-600 dark:text-green-400">
              {patients.length - highRiskCount - moderateRiskCount}
            </p>
          </div>
        </div>

        {/* Patient List */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="p-6 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                Patient Overview
              </h2>
              <div className="relative">
                <Search className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search patients..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
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
                    Risk Level
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Sessions
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Avg Quality
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Last Session
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Actions
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
                    <tr key={patient.email} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
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
                        <RiskBadge risk={patient.riskLevel} />
                      </td>
                      <td className="px-6 py-4 text-gray-900 dark:text-gray-100">
                        {patient.sessionsCount}
                      </td>
                      <td className="px-6 py-4">
                        <span className={`font-medium ${
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
                        <button
                          onClick={() => {
                            setSelectedPatient(patient);
                            setShowAlertModal(true);
                          }}
                          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                        >
                          <Bell className="w-4 h-4" />
                          Send Alert
                        </button>
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
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-6">
          <div className="bg-white dark:bg-gray-800 rounded-xl max-w-lg w-full p-6 border border-gray-200 dark:border-gray-700">
            <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-4">
              Send Alert to {selectedPatient.name}
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
                        ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300"
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
                        ? "border-red-500 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300"
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
                        ? "border-green-500 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300"
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
                  placeholder="Enter your message to the patient..."
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
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
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
