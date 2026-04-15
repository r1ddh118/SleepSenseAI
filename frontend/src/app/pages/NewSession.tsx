import { Link } from "react-router";
import { ArrowLeft, Wifi, Activity, CheckCircle2, Loader2 } from "lucide-react";
import { ThemeToggle } from "../components/ThemeToggle";
import { useState } from "react";

export function NewSession() {
  const [step, setStep] = useState<"device" | "recording" | "processing">("device");
  const [sessionId, setSessionId] = useState("");
  const [recordingProgress, setRecordingProgress] = useState(0);

  const startRecording = () => {
    const id = `S${String(Math.floor(Math.random() * 1000)).padStart(3, "0")}`;
    setSessionId(id);
    setStep("recording");

    // Simulate recording progress
    const interval = setInterval(() => {
      setRecordingProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setStep("processing");
          return 100;
        }
        return prev + 1;
      });
    }, 100);
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
                <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">New Recording Session</h1>
                <p className="text-sm text-gray-600 dark:text-gray-400">Connect your Empatica E4 device and start monitoring</p>
              </div>
            </div>
            <ThemeToggle />
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
              <div className="flex items-start gap-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-green-900 dark:text-green-300">Raspberry Pi 5 Connected</p>
                  <p className="text-sm text-green-700 dark:text-green-400">Device ID: E4-RPi5-001</p>
                </div>
              </div>

              <div className="flex items-start gap-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                <Activity className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5 animate-pulse" />
                <div>
                  <p className="font-medium text-blue-900 dark:text-blue-300">Empatica E4 Detected</p>
                  <p className="text-sm text-blue-700 dark:text-blue-400">Signal strength: Excellent</p>
                </div>
              </div>
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Session ID</label>
              <input
                type="text"
                placeholder="Auto-generated (optional override)"
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              />
            </div>

            <div className="mb-8">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Duration (hours)</label>
              <select className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100">
                <option>8 hours (recommended)</option>
                <option>6 hours</option>
                <option>7 hours</option>
                <option>9 hours</option>
                <option>Custom</option>
              </select>
            </div>

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
                <span>{recordingProgress}% (Demo: 10s = 8hr)</span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
                <div
                  className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                  style={{ width: `${recordingProgress}%` }}
                />
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

            <button className="w-full px-6 py-3 border border-red-300 dark:border-red-700 text-red-700 dark:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors font-medium">
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