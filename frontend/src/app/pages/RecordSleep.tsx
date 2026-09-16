import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router";
import { ArrowLeft, Loader2, Moon, Send } from "lucide-react";

type AnalyticsResult = {
  status: string;
  sleep_score?: number;
  sleep_category?: string;
  risk_level?: string;
  recommendations?: Array<{ area: string; message: string }>;
  error?: string | null;
};

const initialForm = {
  user_id: "U034",
  date: new Date().toISOString().slice(0, 10),
  bed_time: "23:00",
  sleep_onset: "23:20",
  wake_time: "07:00",
  sleep_duration_hours: "7.4",
  sleep_efficiency: "0.88",
  n3_fraction: "0.16",
  rem_fraction: "0.20",
  wake_fraction: "0.10",
  heart_rate: "64",
  hr_std: "4",
  movement_std: "0.10",
  event_rate: "0.004",
  spo2: "96",
  caffeine: "80",
  screen_time: "60",
  exercise_minutes: "30",
  stress_level: "4",
  nap_minutes: "0",
  awakenings: "2",
};

export function RecordSleep() {
  const [form, setForm] = useState(initialForm);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [analytics, setAnalytics] = useState<AnalyticsResult | null>(null);
  const [error, setError] = useState("");

  const update = (key: string, value: string) => setForm((current) => ({ ...current, [key]: value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setAnalytics(null);
    setStatus("PROCESSING");
    try {
      const response = await fetch("/api/v1/sessions/manual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const data = await response.json();
      setSessionId(data.session_id);
      setStatus(data.status);
    } catch (err) {
      setStatus("");
      setError(err instanceof Error ? err.message : "Failed to submit sleep session");
    }
  };

  useEffect(() => {
    if (!sessionId || status !== "PROCESSING") {
      return;
    }
    const timer = window.setInterval(async () => {
      const response = await fetch(`/api/v1/sessions/${sessionId}/analytics`);
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      setAnalytics(data);
      setStatus(data.status);
      if (data.status !== "PROCESSING") {
        window.clearInterval(timer);
      }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [sessionId, status]);

  const fields = [
    ["user_id", "Patient ID"],
    ["date", "Date"],
    ["bed_time", "Bed time"],
    ["sleep_onset", "Sleep onset"],
    ["wake_time", "Wake time"],
    ["sleep_duration_hours", "Duration hours"],
    ["sleep_efficiency", "Sleep efficiency"],
    ["n3_fraction", "N3 fraction"],
    ["rem_fraction", "REM fraction"],
    ["wake_fraction", "Wake fraction"],
    ["heart_rate", "Average HR"],
    ["hr_std", "HR std"],
    ["movement_std", "Movement std"],
    ["event_rate", "Event rate"],
    ["spo2", "SpO2"],
    ["caffeine", "Caffeine mg"],
    ["screen_time", "Screen time min"],
    ["exercise_minutes", "Exercise min"],
    ["stress_level", "Stress 1-10"],
    ["nap_minutes", "Nap min"],
    ["awakenings", "Awakenings"],
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-4">
          <Link to="/dashboard" className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
            <ArrowLeft className="w-5 h-5 text-gray-600 dark:text-gray-300" />
          </Link>
          <Moon className="w-6 h-6 text-blue-600" />
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Record Sleep</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Manual entry is processed asynchronously by Celery and Spark</p>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        <form onSubmit={submit} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {fields.map(([key, label]) => (
              <label key={key} className="block">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{label}</span>
                <input
                  type={key === "date" ? "date" : "text"}
                  value={form[key as keyof typeof form]}
                  onChange={(event) => update(key, event.target.value)}
                  placeholder="unknown"
                  className="mt-1 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                />
              </label>
            ))}
          </div>
          <button className="mt-6 inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
            <Send className="w-4 h-4" />
            Submit
          </button>
          {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
        </form>

        <aside className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 h-fit">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Processing Status</h2>
          {!sessionId && <p className="text-sm text-gray-500 dark:text-gray-400">Submit a session to start analytics.</p>}
          {sessionId && (
            <div className="space-y-3">
              <p className="text-sm text-gray-600 dark:text-gray-300">Session: {sessionId}</p>
              <p className="inline-flex items-center gap-2 text-sm font-medium text-blue-700 dark:text-blue-300">
                {status === "PROCESSING" && <Loader2 className="w-4 h-4 animate-spin" />}
                {status}
              </p>
              {analytics?.status === "COMPLETED" && (
                <div className="space-y-2 text-sm text-gray-700 dark:text-gray-200">
                  <p>Score: {analytics.sleep_score} ({analytics.sleep_category})</p>
                  <p>Risk: {analytics.risk_level}</p>
                  <p>Recommendations: {analytics.recommendations?.length ?? 0}</p>
                </div>
              )}
              {analytics?.status === "FAILED" && <p className="text-sm text-red-600">{analytics.error}</p>}
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}
