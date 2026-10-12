import React, { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router";
import { ArrowLeft, Upload, FileText, CheckCircle2, AlertCircle, Loader2, Download, Moon, Sparkles, Activity } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const REQUIRED_COLUMNS = [
  "timestamp_iso",
  "elapsed_sec",
  "hr_bpm",
  "movement_magnitude",
  "eda_us",
  "spo2_pct",
  "temp_c",
  "bvp_au",
  "resp_rpm",
  "ambient_lux",
  "snore_decibels",
  "user_id",
  "session_id",
];

export function RecordSleep() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [userId, setUserId] = useState(user?.email || user?.name || "U001");
  const [customSid, setCustomSid] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (user?.email) {
      setUserId(user.email);
    }
  }, [user]);
  
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [activeSid, setActiveSid] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [sleepScore, setSleepScore] = useState<number | null>(null);
  const [riskLevel, setRiskLevel] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const validateCsvHeader = async (file: File): Promise<boolean> => {
    setValidationError(null);
    try {
      const text = await file.slice(0, 4096).text();
      const lines = text.split(/\r?\n/);
      const firstLine = lines[0] || "";
      const headers = firstLine.split(",").map((h) => h.trim().replace(/^"|"$/g, ""));
      const missing = REQUIRED_COLUMNS.filter((col) => !headers.includes(col));
      
      if (missing.length > 0) {
        setValidationError("CSV missing required 1 Hz sensor contract columns: " + missing.join(", "));
        return false;
      }
      return true;
    } catch (err) {
      setValidationError("Could not read CSV file headers.");
      return false;
    }
  };

  const handleFileChange = async (file: File | null) => {
    if (!file) return;
    if (!file.name.endsWith(".csv")) {
      setValidationError("Please select a valid .csv night sensor file.");
      setSelectedFile(null);
      return;
    }
    const isValid = await validateCsvHeader(file);
    if (isValid) {
      setSelectedFile(file);
      if (!customSid) {
        setCustomSid(file.name.replace(".csv", ""));
      }
    } else {
      setSelectedFile(null);
    }
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setValidationError("Please select a valid CSV file to upload.");
      return;
    }

    setIsUploading(true);
    setErrorMsg(null);
    setStatus("queued");

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("user_id", userId);
    if (customSid) formData.append("session_id", customSid);
    if (notes) formData.append("notes", notes);

    try {
      const resp = await fetch("/api/v1/sessions/upload", {
        method: "POST",
        body: formData,
      });

      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(errJson.detail || "Upload failed");
      }

      const res = await resp.json();
      setActiveSid(res.session_id);
      setStatus(res.status || "queued");
    } catch (err: any) {
      setIsUploading(false);
      setErrorMsg(err.message || "Failed to upload night sensor file.");
      setStatus("failed");
    }
  };

  useEffect(() => {
    if (!activeSid || status === "completed" || status === "failed") return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch("/api/v1/sessions/" + activeSid + "/status");
        if (!res.ok) return;
        const data = await res.json();
        setStatus(data.status);
        if (data.sleep_score !== undefined) setSleepScore(data.sleep_score);
        if (data.risk_level) setRiskLevel(data.risk_level);
        if (data.error) setErrorMsg(data.error);

        if (data.status === "completed" || data.status === "failed") {
          setIsUploading(false);
          clearInterval(interval);

          if (data.status === "completed") {
            const patientKey = user?.email ? `sessions_${user.email}` : `sessions_${userId}`;
            try {
              const existing = JSON.parse(localStorage.getItem(patientKey) || "[]");
              const alreadyExists = existing.some((s: any) => s.id === activeSid || s.sid === activeSid);
              if (!alreadyExists) {
                const score = data.sleep_score ?? (sleepScore ?? 85);
                const newSessionRecord = {
                  id: activeSid,
                  sid: activeSid,
                  date: new Date().toISOString().split("T")[0],
                  duration: 480,
                  riskProbability: (data.risk_level === "HIGH" || riskLevel === "HIGH") ? 0.8 : (data.risk_level === "MODERATE" || riskLevel === "MODERATE") ? 0.5 : 0.15,
                  riskLevel: (data.risk_level || riskLevel || "low").toLowerCase(),
                  status: "completed",
                  features: {
                    HR_mean: 62.0,
                    HR_std: 4.5,
                    EDA_mean: 2.1,
                    TEMP_mean: 35.8,
                    event_rate: 0.02,
                    sleep_efficiency: Math.round(score),
                  },
                  sleepStages: {
                    wake: 8,
                    n1: 5,
                    n2: 45,
                    n3: 22,
                    rem: 20,
                  },
                };
                existing.unshift(newSessionRecord);
                localStorage.setItem(patientKey, JSON.stringify(existing));
              }
            } catch (err) {
              console.error("Failed to store local session history:", err);
            }
          }
        }
      } catch (e) {
        // Continue polling
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [activeSid, status]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-4">
          <Link to="/dashboard" className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
            <ArrowLeft className="w-5 h-5 text-gray-600 dark:text-gray-300" />
          </Link>
          <div className="p-2 bg-blue-100 dark:bg-blue-900/40 rounded-lg">
            <Moon className="w-6 h-6 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Upload Night Sensor Data</h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Submit 1 Hz sensor CSV streams for Spark night-level epoching, hypnogram, and EDA analytics
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-8">
        <div className="space-y-6">
          <form onSubmit={handleUploadSubmit} className="space-y-6">
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onClick={() => fileInputRef.current?.click()}
              className={"border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all " + (
                selectedFile
                  ? "border-blue-500 bg-blue-50/50 dark:bg-blue-950/20"
                  : "border-gray-300 dark:border-gray-700 hover:border-blue-400 dark:hover:border-blue-500 bg-white dark:bg-gray-800"
              )}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={(e) => handleFileChange(e.target.files?.[0] || null)}
                className="hidden"
              />
              <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/40 rounded-full flex items-center justify-center mx-auto mb-3 text-blue-600 dark:text-blue-400">
                <Upload className="w-6 h-6" />
              </div>
              {selectedFile ? (
                <div className="space-y-1">
                  <p className="font-bold text-blue-600 dark:text-blue-400 flex items-center justify-center gap-2">
                    <FileText className="w-5 h-5" /> {selectedFile.name}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB | Ready for ingestion
                  </p>
                </div>
              ) : (
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-gray-700 dark:text-gray-200">
                    Drag and drop your 1 Hz night sensor CSV file here
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Or click to browse your local filesystem (.csv files up to 100 MB)
                  </p>
                </div>
              )}
            </div>

            {validationError && (
              <div className="p-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-700 dark:text-red-300 flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">Validation Error: </span>
                  {validationError}
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5">
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Patient / User ID
                </label>
                <input
                  type="text"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Session ID (Optional)
                </label>
                <input
                  type="text"
                  value={customSid}
                  onChange={(e) => setCustomSid(e.target.value)}
                  placeholder="Auto-generated if empty"
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Clinical Notes
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Optional notes on patient condition, symptoms, or sleep environment..."
                  rows={2}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={!selectedFile || isUploading}
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold rounded-xl transition-colors flex items-center justify-center gap-2 shadow-sm"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" /> Processing Night Pipeline...
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" /> Ingest & Execute Night Analytics
                </>
              )}
            </button>
          </form>

          <div className="bg-blue-50/60 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900/40 rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-2 text-blue-900 dark:text-blue-300 font-bold text-sm">
              <Download className="w-4 h-4" /> Need Demo Data? Download Pre-Generated Sensor CSVs:
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <a
                href="/api/v1/sample-data/healthy_night.csv"
                download
                className="p-3 bg-white dark:bg-gray-800 border border-blue-200 dark:border-blue-800 rounded-lg text-xs font-semibold text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/40 transition-colors flex items-center gap-2 justify-center"
              >
                <FileText className="w-4 h-4 text-green-500" /> Healthy Night (U001)
              </a>
              <a
                href="/api/v1/sample-data/insomnia_night.csv"
                download
                className="p-3 bg-white dark:bg-gray-800 border border-blue-200 dark:border-blue-800 rounded-lg text-xs font-semibold text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/40 transition-colors flex items-center gap-2 justify-center"
              >
                <FileText className="w-4 h-4 text-amber-500" /> Insomnia Night (U002)
              </a>
              <a
                href="/api/v1/sample-data/apnea_night.csv"
                download
                className="p-3 bg-white dark:bg-gray-800 border border-blue-200 dark:border-blue-800 rounded-lg text-xs font-semibold text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/40 transition-colors flex items-center gap-2 justify-center"
              >
                <FileText className="w-4 h-4 text-red-500" /> Apnea Pattern (U034)
              </a>
            </div>
          </div>
        </div>

        <aside className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 h-fit space-y-4">
          <h2 className="text-base font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-500" /> Pipeline Execution Status
          </h2>

          {!activeSid && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Select a 1 Hz CSV stream and click submit to trigger PySpark processing.
            </p>
          )}

          {activeSid && (
            <div className="space-y-4 text-xs">
              <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg space-y-1 font-mono">
                <div className="text-gray-500 dark:text-gray-400">Session ID:</div>
                <div className="font-bold text-gray-900 dark:text-gray-100 truncate">{activeSid}</div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-medium">
                  <span>Status:</span>
                  <span className="uppercase font-bold text-blue-600 dark:text-blue-400 flex items-center gap-1.5">
                    {status !== "completed" && status !== "failed" && (
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-500" />
                    )}
                    {status}
                  </span>
                </div>

                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
                  <div
                    className={"h-2 transition-all duration-500 " + (
                      status === "completed" ? "w-full bg-green-500" : status === "failed" ? "w-full bg-red-500" : "w-2/3 bg-blue-500 animate-pulse"
                    )}
                  />
                </div>
              </div>

              {status === "completed" && (
                <div className="p-4 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg space-y-3">
                  <div className="flex items-center gap-2 font-bold text-green-800 dark:text-green-300">
                    <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" /> Processing Completed!
                  </div>
                  {sleepScore !== null && (
                    <div className="text-gray-700 dark:text-gray-200 space-y-1">
                      <p>Sleep Score: <span className="font-bold text-blue-600 dark:text-blue-400">{sleepScore.toFixed(1)}</span> / 100</p>
                      {riskLevel && <p>Risk Profile: <span className="font-semibold">{riskLevel}</span></p>}
                    </div>
                  )}
                  <button
                    onClick={() => navigate("/session/" + activeSid)}
                    className="w-full py-2 bg-green-600 hover:bg-green-700 text-white font-bold rounded-lg transition-colors text-center text-xs block"
                  >
                    Open Tabbed EDA & Hypnogram View →
                  </button>
                </div>
              )}

              {status === "failed" && (
                <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300 space-y-1">
                  <div className="font-bold">Pipeline Failed</div>
                  <p>{errorMsg || "An unexpected error occurred during execution."}</p>
                </div>
              )}
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}
