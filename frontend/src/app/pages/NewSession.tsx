import { Link, useNavigate } from "react-router";
import { ArrowLeft, Wifi, Activity, CheckCircle2, Loader2, LogOut, User } from "lucide-react";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../context/AuthContext";
import { useEffect, useMemo, useRef, useState } from "react";
import { readStoredSessions } from "../data/sessionUtils";

const DEMO_MS_PER_HOUR = 1250;

export function NewSession() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState<"device" | "recording" | "processing">("device");
  const [sessionId, setSessionId] = useState("");
  const [sessionIdInput, setSessionIdInput] = useState("");
  const [durationChoice, setDurationChoice] = useState("8");
  const [customDurationHours, setCustomDurationHours] = useState("8");
  const [recordingProgress, setRecordingProgress] = useState(0);
  const [isSensorConnected, setIsSensorConnected] = useState(true);
  const [isReceivingData, setIsReceivingData] = useState(false);
  const [lastDataAt, setLastDataAt] = useState<Date | null>(null);
  const [recordingStartedAt, setRecordingStartedAt] = useState<Date | null>(null);
  const [validationError, setValidationError] = useState("");
  const recordingIntervalRef = useRef<number | null>(null);
  const redirectTimeoutRef = useRef<number | null>(null);

  const selectedDurationHours = useMemo(() => {
    if (durationChoice === "custom") {
      const parsed = Number(customDurationHours);
      return Number.isFinite(parsed) ? parsed : 0;
    }
    return Number(durationChoice);
  }, [customDurationHours, durationChoice]);

  const clearRecordingInterval = () => {
    if (recordingIntervalRef.current !== null) {
      window.clearInterval(recordingIntervalRef.current);
      recordingIntervalRef.current = null;
    }
  };

  const moveToProcessing = (id: string) => {
    clearRecordingInterval();
    setIsReceivingData(false);
    setStep("processing");

    if (user?.role === "patient") {
      savePatientSession(id);
    }

    redirectTimeoutRef.current = window.setTimeout(() => {
      navigate("/dashboard");
    }, 2000);
  };

  const startRecording = () => {
    if (!isSensorConnected) {
      setValidationError("Connect sensors before starting a recording.");
      return;
    }

    if (!selectedDurationHours || selectedDurationHours <= 0 || selectedDurationHours > 24) {
      setValidationError("Duration must be between 1 and 24 hours.");
      return;
    }

    setValidationError("");
    const id = (sessionIdInput.trim() || `S${String(Math.floor(Math.random() * 1000)).padStart(3, "0")}`).toUpperCase();
    setSessionId(id);
    setStep("recording");
    setRecordingProgress(0);
    setIsReceivingData(true);
    setLastDataAt(new Date());
    setRecordingStartedAt(new Date());

    const totalDemoDurationMs = Math.max(selectedDurationHours * DEMO_MS_PER_HOUR, DEMO_MS_PER_HOUR);
    const startedAt = Date.now();

    clearRecordingInterval();
    recordingIntervalRef.current = window.setInterval(() => {
      const elapsed = Date.now() - startedAt;
      const nextProgress = Math.min(100, Math.round((elapsed / totalDemoDurationMs) * 100));
      setRecordingProgress(nextProgress);
      setLastDataAt(new Date());
      setIsReceivingData(isSensorConnected);

      if (nextProgress >= 100) {
        moveToProcessing(id);
      }
    }, 150);
  };

  const stopRecording = () => {
    if (step !== "recording") {
      return;
    }
    moveToProcessing(sessionId);
  };

  const savePatientSession = (id: string) => {
    const durationMinutes = 432;
    const sleepEfficiency = Math.floor(Math.random() * 30) + 65;
    const riskProbability = Math.random();
    const session = {
      id,
      sid: id,
      patientName: user?.name || "Unknown",
      date: new Date().toISOString().split("T")[0],
      duration: durationMinutes,
      sleepQuality: sleepEfficiency,
      riskProbability,
      risk:
        riskProbability >= 0.7 ? "high" : riskProbability >= 0.4 ? "moderate" : "low",
      riskScore: riskProbability * 100,
      riskLevel:
        riskProbability >= 0.7 ? "high" : riskProbability >= 0.4 ? "moderate" : "low",
      status: "completed",
      sleepStages: {
        wake: Math.floor(Math.random() * 15) + 5,
        n1: Math.floor(Math.random() * 10) + 8,
        n2: Math.floor(Math.random() * 20) + 35,
        n3: Math.floor(Math.random() * 15) + 8,
        rem: Math.floor(Math.random() * 12) + 10,
      },
      features: {
        HR_mean: 60 + Math.random() * 20,
        HR_std: 6 + Math.random() * 8,
        EDA_mean: 2 + Math.random() * 3,
        TEMP_mean: 33 + Math.random() * 1.5,
        event_rate: Math.random() * 0.12,
        sleep_efficiency: sleepEfficiency,
      },
      createdAt: new Date().toISOString(),
    };

    const existingSessions = readStoredSessions(`sessions_${user?.email}`);
    existingSessions.push(session);
    localStorage.setItem(`sessions_${user?.email}`, JSON.stringify(existingSessions));
  };

  useEffect(() => {
    return () => {
      clearRecordingInterval();
      if (redirectTimeoutRef.current !== null) {
        window.clearTimeout(redirectTimeoutRef.current);
      }
    };
  }, []);

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
                <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">New Recording Session</h1>
                <p className="text-sm text-gray-600 dark:text-gray-400">Connect your Empatica E4 device and start monitoring</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
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

      <div className="max-w-3xl mx-auto px-6 py-12">
        {step === "device" && (
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8">
            <div className="text-center mb-8">
              <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
                <Wifi className="w-8 h-8 text-blue-600 dark:text-blue-400" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Connect Empatica E4 Device</h2>
              <p className="text-gray-600 dark:text-gray-400">Make sure your device is powered on and within range</p>
            </div>

            <div className="space-y-4 mb-8">
              <div className={`flex items-start gap-4 p-4 border rounded-lg ${isSensorConnected ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800" : "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800"}`}>
                <CheckCircle2 className={`w-5 h-5 flex-shrink-0 mt-0.5 ${isSensorConnected ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`} />
                <div>
                  <p className={`font-medium ${isSensorConnected ? "text-green-900 dark:text-green-300" : "text-red-900 dark:text-red-300"}`}>
                    Raspberry Pi 5 {isSensorConnected ? "Connected" : "Disconnected"}
                  </p>
                  <p className={`text-sm ${isSensorConnected ? "text-green-700 dark:text-green-400" : "text-red-700 dark:text-red-400"}`}>Device ID: E4-RPi5-001</p>
                </div>
              </div>

              <div className={`flex items-start gap-4 p-4 border rounded-lg ${isSensorConnected ? "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800" : "bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700"}`}>
                <Activity className={`w-5 h-5 flex-shrink-0 mt-0.5 ${isSensorConnected ? "text-blue-600 dark:text-blue-400 animate-pulse" : "text-gray-500 dark:text-gray-400"}`} />
                <div>
                  <p className={`font-medium ${isSensorConnected ? "text-blue-900 dark:text-blue-300" : "text-gray-800 dark:text-gray-200"}`}>
                    Empatica E4 {isSensorConnected ? "Detected" : "Not detected"}
                  </p>
                  <p className={`text-sm ${isSensorConnected ? "text-blue-700 dark:text-blue-400" : "text-gray-600 dark:text-gray-400"}`}>
                    {isSensorConnected ? "Signal strength: Excellent" : "No signal from paired sensor"}
                  </p>
                </div>
              </div>
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Session ID</label>
              <input
                type="text"
                placeholder="Auto-generated (optional override)"
                value={sessionIdInput}
                onChange={(e) => setSessionIdInput(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              />
            </div>

            <div className="mb-8">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Duration (hours)</label>
              <select
                value={durationChoice}
                onChange={(e) => setDurationChoice(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              >
                <option value="8">8 hours (recommended)</option>
                <option value="6">6 hours</option>
                <option value="7">7 hours</option>
                <option value="9">9 hours</option>
                <option value="custom">Custom</option>
              </select>
              {durationChoice === "custom" && (
                <input
                  type="number"
                  min={1}
                  max={24}
                  step={1}
                  value={customDurationHours}
                  onChange={(e) => setCustomDurationHours(e.target.value)}
                  placeholder="Enter custom hours (1-24)"
                  className="mt-3 w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                />
              )}
            </div>

            <div className="mb-8 flex items-center justify-between rounded-lg border border-gray-200 dark:border-gray-700 p-4">
              <p className="text-sm text-gray-700 dark:text-gray-300">Sensor connection</p>
              <button
                type="button"
                onClick={() => setIsSensorConnected((prev) => !prev)}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${isSensorConnected ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300" : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"}`}
              >
                {isSensorConnected ? "Connected" : "Disconnected"}
              </button>
            </div>

            {validationError && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{validationError}</p>}

            <button
              onClick={startRecording}
              className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              Start Recording
            </button>
          </div>
        )}

        {step === "recording" && (
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8">
            <div className="text-center mb-8">
              <div className="w-16 h-16 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
                <div className="w-4 h-4 bg-red-500 dark:bg-red-400 rounded-full animate-pulse" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Recording in Progress</h2>
              <p className="text-gray-600 dark:text-gray-400">Session {sessionId}</p>
            </div>

            <div className="mb-8">
              <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400 mb-2">
                <span>Progress</span>
                <span>{recordingProgress}% (Demo: {selectedDurationHours || 0}h ≈ {Math.max(Math.round((selectedDurationHours || 0) * (DEMO_MS_PER_HOUR / 1000)), 1)}s)</span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
                <div
                  className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                  style={{ width: `${recordingProgress}%` }}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
              <div className={`rounded-lg border p-4 ${isSensorConnected ? "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-900/20" : "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20"}`}>
                <p className={`text-sm ${isSensorConnected ? "text-green-800 dark:text-green-300" : "text-red-800 dark:text-red-300"}`}>Sensor connection</p>
                <p className={`font-semibold ${isSensorConnected ? "text-green-900 dark:text-green-200" : "text-red-900 dark:text-red-200"}`}>
                  {isSensorConnected ? "Connected" : "Disconnected"}
                </p>
              </div>
              <div className={`rounded-lg border p-4 ${isReceivingData ? "border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/20" : "border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800"}`}>
                <p className={`text-sm ${isReceivingData ? "text-blue-800 dark:text-blue-300" : "text-gray-700 dark:text-gray-300"}`}>Data stream</p>
                <p className={`font-semibold ${isReceivingData ? "text-blue-900 dark:text-blue-200" : "text-gray-900 dark:text-gray-100"}`}>
                  {isReceivingData ? "Receiving sensor packets" : "No incoming sensor data"}
                </p>
                {lastDataAt && <p className="mt-1 text-xs text-gray-600 dark:text-gray-400">Last packet: {lastDataAt.toLocaleTimeString()}</p>}
              </div>
            </div>

            <div className="grid grid-cols-4 gap-4 mb-8">
              <div className="text-center p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Heart Rate</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {Math.floor(60 + Math.random() * 20)}
                  <span className="text-sm font-normal text-gray-500 dark:text-gray-400"> bpm</span>
                </p>
              </div>
              <div className="text-center p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">EDA</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {(2 + Math.random() * 2).toFixed(1)}
                  <span className="text-sm font-normal text-gray-500 dark:text-gray-400"> µS</span>
                </p>
              </div>
              <div className="text-center p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Temp</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {(33 + Math.random()).toFixed(1)}
                  <span className="text-sm font-normal text-gray-500 dark:text-gray-400"> °C</span>
                </p>
              </div>
              <div className="text-center p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">BVP</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {Math.floor(40 + Math.random() * 40)}
                  <span className="text-sm font-normal text-gray-500 dark:text-gray-400"> a.u.</span>
                </p>
              </div>
            </div>

            {recordingStartedAt && (
              <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
                Started at {recordingStartedAt.toLocaleTimeString()} • Target duration: {selectedDurationHours} hour(s)
              </p>
            )}

            <button
              onClick={stopRecording}
              className="w-full px-6 py-3 border border-red-300 dark:border-red-700 text-red-700 dark:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors font-medium"
            >
              Stop Recording
            </button>
          </div>
        )}

        {step === "processing" && (
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8">
            <div className="text-center mb-8">
              <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
                <Loader2 className="w-8 h-8 text-blue-600 dark:text-blue-400 animate-spin" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Processing Session Data</h2>
              <p className="text-gray-600 dark:text-gray-400">Running ML pipeline on {sessionId}</p>
            </div>

            <div className="space-y-3 mb-8">
              <div className="flex items-center gap-3 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
                <span className="text-sm text-green-900 dark:text-green-300">Data ingestion complete</span>
              </div>
              <div className="flex items-center gap-3 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
                <span className="text-sm text-green-900 dark:text-green-300">40+ features engineered</span>
              </div>
              <div className="flex items-center gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                <Loader2 className="w-5 h-5 text-blue-600 dark:text-blue-400 animate-spin" />
                <span className="text-sm text-blue-900 dark:text-blue-300">Running XGBoost prediction...</span>
              </div>
            </div>

            <p className="text-center text-sm text-gray-600 dark:text-gray-400">
              This usually takes 30-60 seconds. You'll be redirected automatically.
            </p>
          </div>
        )}

        {/* Instructions */}
        <div className="mt-8 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6">
          <h3 className="font-semibold text-blue-900 dark:text-blue-300 mb-3">Recording Tips</h3>
          <ul className="space-y-2 text-sm text-blue-800 dark:text-blue-300">
            <li className="flex items-start gap-2">
              <span className="text-blue-600 mt-0.5">•</span>
              <span>Ensure the E4 wristband is worn snugly but comfortably on your non-dominant wrist</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 mt-0.5">•</span>
              <span>Keep the Raspberry Pi within 10 meters of the E4 during recording</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 mt-0.5">•</span>
              <span>Aim for 7-9 hours of recording for best sleep staging accuracy</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 mt-0.5">•</span>
              <span>
                Data is streamed via MQTT and stored locally — internet connection not required during recording
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
