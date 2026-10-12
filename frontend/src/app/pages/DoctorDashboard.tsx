import { Link } from "react-router";
import { Users, AlertTriangle, Bell, LogOut, User, Search, Send, TrendingUp, Activity, Moon, FileText, X, ChevronRight, ListOrdered } from "lucide-react";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../context/AuthContext";
import { RiskBadge } from "../components/RiskBadge";
import { DoctorReportView } from "../components/DoctorReportView";
import { useState, useEffect } from "react";
import { readStoredSessions } from "../data/sessionUtils";

interface Patient {
  email: string;
  name: string;
  riskLevel: "low" | "moderate" | "high";
  lastSession: string;
  sessionsCount: number;
  avgQuality: number;
  latestSessionId?: string;
}

interface PatientSession {
  session_id: string;
  sid: string;
  user_id: string;
  date: string | null;
  duration_seconds: number | null;
  sleep_score: number | null;
  risk_level: string;
  status: string;
  source: string;
}

export function DoctorDashboard() {
  const { user, logout } = useAuth();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [selectedReportPatient, setSelectedReportPatient] = useState<Patient | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessionListPatient, setSessionListPatient] = useState<Patient | null>(null);
  const [patientSessions, setPatientSessions] = useState<PatientSession[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [alertMessage, setAlertMessage] = useState("");
  const [alertType, setAlertType] = useState<"warning" | "info" | "success">("info");
  const [showAlertModal, setShowAlertModal] = useState(false);

  useEffect(() => {
    loadPatients();
  }, []);

  const loadPatients = () => {
    const allUsers = JSON.parse(localStorage.getItem("sleepsense_users") || "[]");
    
    // Also discover any patients from localStorage session keys (e.g. sessions_riddhi@... or sessions_riddhi)
    const discoveredPatientEmails = new Set<string>();
    
    allUsers.forEach((u: any) => {
      if (u.role === "patient" || u.role === "user" || !u.role) {
        discoveredPatientEmails.add(u.email);
      }
    });

    // Check all localStorage keys for sessions_
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith("sessions_")) {
        const emailOrUid = key.replace("sessions_", "");
        if (emailOrUid && emailOrUid !== "undefined") {
          discoveredPatientEmails.add(emailOrUid);
        }
      }
    }

    const patientData: Patient[] = Array.from(discoveredPatientEmails).map((email) => {
      const matchedUser = allUsers.find((u: any) => u.email === email);
      const name = matchedUser?.name || (email.includes("@") ? email.split("@")[0] : email);
      const sessions = readStoredSessions(`sessions_${email}`);
      const avgQuality = sessions.length > 0
        ? Math.round(
            sessions.reduce((acc: number, s) => acc + (s.features?.sleep_efficiency ?? 80), 0) / sessions.length
          )
        : 82;

      // Determine risk level based on sleep quality and sessions
      let riskLevel: "low" | "moderate" | "high" = "low";
      if (sessions.length > 0 && avgQuality < 50) {
        riskLevel = "high";
      } else if (sessions.length > 0 && avgQuality < 70) {
        riskLevel = "moderate";
      }

      const latestSession = sessions.length > 0 ? sessions[0] : null;

      return {
        email: email,
        name: name,
        riskLevel,
        lastSession: latestSession ? (latestSession.date || "Recent") : "No sessions",
        sessionsCount: sessions.length,
        avgQuality,
        latestSessionId: latestSession?.sid || latestSession?.id || "S_U001_N01",
      };
    });

    setPatients(patientData);
  };

  const openPatientSessions = async (patient: Patient) => {
    setSessionListPatient(patient);
    setLoadingSessions(true);
    try {
      const token = localStorage.getItem("token");
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      let backendData: PatientSession[] = [];
      try {
        const res = await fetch(`/api/v1/doctor/patients/${encodeURIComponent(patient.email)}/sessions`, { headers });
        if (res.ok) {
          backendData = await res.json();
        }
      } catch {
        // Backend doctor sessions endpoint unavailable or unassigned
      }

      // Merge with stored local sessions for this patient
      const stored = readStoredSessions(`sessions_${patient.email}`);
      const mappedStored: PatientSession[] = stored.map((s, idx) => ({
        session_id: s.sid || s.id || `S_LOCAL_${idx + 1}`,
        sid: s.sid || s.id || `S_LOCAL_${idx + 1}`,
        user_id: patient.email,
        date: s.date || "Recent",
        duration_seconds: s.duration ? s.duration * 60 : 28800,
        sleep_score: (s.features as any)?.sleep_score ?? s.features?.sleep_efficiency ?? 82,
        risk_level: (s.riskLevel || "low").toUpperCase(),
        status: s.status || "COMPLETED",
        source: "session_storage",
      }));

      const seen = new Set<string>();
      const combined: PatientSession[] = [];

      for (const item of [...backendData, ...mappedStored]) {
        const key = item.sid || item.session_id;
        if (!seen.has(key)) {
          seen.add(key);
          combined.push(item);
        }
      }

      if (combined.length > 0) {
        setPatientSessions(combined);
      } else {
        // Fallback demo session if completely empty
        setPatientSessions([
          {
            session_id: patient.latestSessionId || "S_U001_N01",
            sid: patient.latestSessionId || "S_U001_N01",
            user_id: patient.email,
            date: patient.lastSession || "2026-03-28",
            duration_seconds: 27000,
            sleep_score: patient.avgQuality || 85,
            risk_level: patient.riskLevel.toUpperCase(),
            status: "COMPLETED",
            source: "sensor_stream",
          }
        ]);
      }
    } catch {
      const stored = readStoredSessions(`sessions_${patient.email}`);
      if (stored.length > 0) {
        setPatientSessions(
          stored.map((s, idx) => ({
            session_id: s.sid || s.id || `S_LOCAL_${idx + 1}`,
            sid: s.sid || s.id || `S_LOCAL_${idx + 1}`,
            user_id: patient.email,
            date: s.date || "Recent",
            duration_seconds: s.duration ? s.duration * 60 : 28800,
            sleep_score: (s.features as any)?.sleep_score ?? s.features?.sleep_efficiency ?? 82,
            risk_level: (s.riskLevel || "low").toUpperCase(),
            status: s.status || "COMPLETED",
            source: "session_storage",
          }))
        );
      } else {
        setPatientSessions([
          {
            session_id: patient.latestSessionId || "S_U001_N01",
            sid: patient.latestSessionId || "S_U001_N01",
            user_id: patient.email,
            date: patient.lastSession || "2026-03-28",
            duration_seconds: 27000,
            sleep_score: patient.avgQuality || 85,
            risk_level: patient.riskLevel.toUpperCase(),
            status: "COMPLETED",
            source: "sensor_stream",
          }
        ]);
      }
    } finally {
      setLoadingSessions(false);
    }
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
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => openPatientSessions(patient)}
                            className="flex items-center gap-1 px-2.5 py-1.5 text-xs bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 rounded-lg hover:bg-indigo-100 transition-colors shadow-sm"
                            title="View patient sleep sessions"
                          >
                            <ListOrdered className="w-3.5 h-3.5" />
                            Sessions
                          </button>
                          <button
                            onClick={() => {
                              setSelectedPatient(patient);
                              setShowAlertModal(true);
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors shadow-sm"
                          >
                            <Bell className="w-3.5 h-3.5" />
                            Alert
                          </button>
                          <button
                            onClick={() => {
                              setSelectedReportPatient(patient);
                              setActiveSessionId(patient.latestSessionId || "S_U001_N01");
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 rounded-lg transition-colors border border-gray-200 dark:border-gray-600 shadow-sm"
                          >
                            <FileText className="w-3.5 h-3.5" />
                            Full Report
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

      {/* Patient Sessions Modal */}
      {sessionListPatient && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-6 overflow-y-auto">
          <div className="bg-white dark:bg-gray-800 rounded-2xl max-w-3xl w-full p-6 border border-gray-200 dark:border-gray-700 relative my-8 max-h-[85vh] overflow-y-auto shadow-2xl space-y-4">
            <button
              onClick={() => setSessionListPatient(null)}
              className="absolute top-6 right-6 p-2 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-indigo-50 dark:bg-indigo-900/40 text-indigo-600 flex items-center justify-center">
                <ListOrdered className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Sessions: {sessionListPatient.name}
                </h3>
                <p className="text-xs text-gray-500">{sessionListPatient.email}</p>
              </div>
            </div>

            {loadingSessions ? (
              <div className="py-12 flex flex-col items-center justify-center text-sm text-gray-500">
                <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mb-2"></div>
                Loading patient session history...
              </div>
            ) : patientSessions.length === 0 ? (
              <p className="text-center py-8 text-sm text-gray-500">No sleep sessions recorded for this patient yet.</p>
            ) : (
              <div className="divide-y divide-gray-200 dark:divide-gray-700 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
                {patientSessions.map((sess) => (
                  <div key={sess.session_id} className="p-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-gray-800 dark:text-gray-200">
                          {sess.session_id}
                        </span>
                        <RiskBadge risk={(sess.risk_level || "low").toLowerCase() as any} />
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Date: {sess.date || "Recent"} • Duration: {sess.duration_seconds ? `${Math.round(sess.duration_seconds / 3600 * 10) / 10} hrs` : "N/A"}
                      </p>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <span className="text-xs font-bold text-gray-800 dark:text-gray-200">
                          Score: {sess.sleep_score ?? "N/A"}
                        </span>
                        <p className="text-[10px] text-gray-500 uppercase">{sess.status}</p>
                      </div>
                      <button
                        onClick={() => {
                          setSelectedReportPatient(sessionListPatient);
                          setActiveSessionId(sess.session_id);
                          setSessionListPatient(null);
                        }}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors shadow-sm font-medium"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        Full Report
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Send Alert Modal */}
      {showAlertModal && selectedPatient && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-6">
          <div className="bg-white dark:bg-gray-800 rounded-xl max-w-lg w-full p-6 border border-gray-200 dark:border-gray-700">
            <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">
              Send Alert to {selectedPatient.name}
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Alert Severity
                </label>
                <div className="grid grid-cols-3 gap-3">
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

      {/* View Doctor Full Report Modal (Blueprint Section 8) */}
      {selectedReportPatient && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-6 overflow-y-auto">
          <div className="bg-white dark:bg-gray-800 rounded-2xl max-w-5xl w-full p-6 border border-gray-200 dark:border-gray-700 relative my-8 max-h-[92vh] overflow-y-auto shadow-2xl">
            <button
              onClick={() => {
                setSelectedReportPatient(null);
                setActiveSessionId(null);
              }}
              className="absolute top-6 right-6 p-2 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
            <DoctorReportView
              patientUid={selectedReportPatient.email}
              sessionId={activeSessionId || selectedReportPatient.latestSessionId || "S_U001_N01"}
              onBack={() => {
                setSelectedReportPatient(null);
                setActiveSessionId(null);
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
