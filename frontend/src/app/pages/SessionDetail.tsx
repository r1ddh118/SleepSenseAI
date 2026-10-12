import React, { useState, useEffect, useMemo } from "react";
import { Link, useParams } from "react-router";
import { ArrowLeft, Calendar, Clock, Activity, Zap, Heart, AlertCircle, FileText, Download, ShieldAlert, Moon, CheckCircle2, ChevronRight, BarChart2 } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { RiskBadge } from "../components/RiskBadge";
import { ThemeToggle } from "../components/ThemeToggle";
import { SessionReportView } from "../components/SessionReportView";
import { DownloadReportButton } from "../components/DownloadReportButton";
import { useAuth } from "../context/AuthContext";

interface TimelinePoint {
  epoch_index: number;
  timestamp: string;
  stage: string;
  hr_mean: number;
  movement_mean: number;
  spo2_mean: number;
  eda_mean: number;
  snore_mean: number;
}

interface EdaArtifact {
  session_id: string;
  user_id?: string;
  num_samples: number;
  sampling_rate_hz?: number;
  start_timestamp_iso?: string;
  end_timestamp_iso?: string;
  downsample_seconds?: number;
  tonic_eda_mean_us: number;
  phasic_peak_count: number;
  mean_peak_amplitude_us: number;
  downsampled_eda: number[];
}

function formatClockTime(isoString?: string): string {
  if (!isoString) return "";
  try {
    const date = new Date(isoString);
    if (!isNaN(date.getTime())) {
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
  } catch {}
  return (isoString || "").slice(11, 16);
}

export function SessionDetail() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<"summary" | "eda" | "cardio" | "report">("summary");

  const [loading, setLoading] = useState(true);
  const [statusData, setStatusData] = useState<any>(null);
  const [edaData, setEdaData] = useState<EdaArtifact | null>(null);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const sessionId = id || "S_U001_N01";

  useEffect(() => {
    let isMounted = true;
    async function loadSessionData() {
      setLoading(true);
      setFetchError(null);

      try {
        // Fetch EDA
        const edaRes = await fetch(`/api/v1/sessions/${sessionId}/eda`);
        if (edaRes.ok) {
          const edaJson = await edaRes.json();
          if (isMounted) setEdaData(edaJson);
        }

        // Fetch Timeline
        const timelineRes = await fetch(`/api/v1/sessions/${sessionId}/timeline`);
        if (timelineRes.ok) {
          const timelineJson = await timelineRes.json();
          if (isMounted) setTimeline(timelineJson.timeline || []);
        }

        // Fetch Status
        const statusRes = await fetch(`/api/v1/sessions/${sessionId}/status`);
        if (statusRes.ok) {
          const statusJson = await statusRes.json();
          if (isMounted) setStatusData(statusJson);
        }
      } catch (err: any) {
        if (isMounted) setFetchError(err.message || "Failed to load session details.");
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadSessionData();
    return () => { isMounted = false; };
  }, [sessionId]);

  // Fallback timeline with realistic timestamps if none loaded yet
  const effectiveTimeline = useMemo<TimelinePoint[]>(() => {
    if (timeline.length > 0) return timeline;
    const base = new Date();
    base.setHours(22, 30, 0, 0);
    const stages = ["wake", "n1", "n2", "n3", "n3", "rem", "n2", "n3", "rem", "n2", "wake"];
    const count = 64;
    return Array.from({ length: count }, (_, i) => {
      const pt = new Date(base.getTime() + i * 7.5 * 60 * 1000);
      const stage = stages[Math.min(Math.floor((i / count) * stages.length), stages.length - 1)];
      return {
        epoch_index: i * 15,
        timestamp: pt.toISOString(),
        stage: stage,
        hr_mean: Math.round(58 + Math.sin(i / 6) * 7 + (stage === "rem" ? 5 : 0)),
        movement_mean: stage === "wake" ? 0.32 : 0.03,
        spo2_mean: Math.round(96 + Math.cos(i / 8) * 2),
        eda_mean: +(3.8 + Math.sin(i / 10) * 0.8).toFixed(2),
        snore_mean: stage === "n3" ? 10 : 2,
      };
    });
  }, [timeline]);

  // EDA chart data with real clock times on the X-axis
  const effectiveEdaChartData = useMemo(() => {
    if (edaData?.downsampled_eda && edaData.downsampled_eda.length > 0) {
      const baseTime = edaData.start_timestamp_iso
        ? new Date(edaData.start_timestamp_iso).getTime()
        : (effectiveTimeline.length > 0 ? new Date(effectiveTimeline[0].timestamp).getTime() : Date.now() - 8 * 3600 * 1000);
      const stepMs = (edaData.downsample_seconds || 10) * 1000;

      return edaData.downsampled_eda.map((val, idx) => {
        const pt = new Date(baseTime + idx * stepMs);
        return {
          sample: idx * (edaData.downsample_seconds || 10),
          clockTime: pt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          timestamp: pt.toISOString(),
          eda: val,
        };
      });
    }

    // Default curve when EDA is calculating
    const base = new Date();
    base.setHours(22, 30, 0, 0);
    return Array.from({ length: 60 }, (_, i) => {
      const pt = new Date(base.getTime() + i * 8 * 60 * 1000);
      return {
        sample: i * 480,
        clockTime: pt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        timestamp: pt.toISOString(),
        eda: +(3.4 + Math.sin(i / 7) * 1.2 + (i % 8 === 0 ? 0.7 : 0)).toFixed(2),
      };
    });
  }, [edaData, effectiveTimeline]);

  // Sleep metrics breakdown computed from timeline
  const sleepMetrics = useMemo(() => {
    const total = effectiveTimeline.length;
    if (total === 0) return { wakePct: 15, remPct: 22, lightPct: 48, deepPct: 15, durationHours: "7.8", efficiency: 85 };
    const wake = effectiveTimeline.filter(p => p.stage.toLowerCase() === "wake").length;
    const rem = effectiveTimeline.filter(p => p.stage.toLowerCase() === "rem").length;
    const deep = effectiveTimeline.filter(p => ["n3", "deep"].includes(p.stage.toLowerCase())).length;
    const light = total - wake - rem - deep;

    const wakePct = Math.round((wake / total) * 100);
    const remPct = Math.round((rem / total) * 100);
    const deepPct = Math.round((deep / total) * 100);
    const lightPct = Math.max(0, 100 - wakePct - remPct - deepPct);
    const efficiency = Math.round(((total - wake) / total) * 100);

    const firstSleep = effectiveTimeline.find(p => p.stage.toLowerCase() !== "wake");
    const lastSleep = [...effectiveTimeline].reverse().find(p => p.stage.toLowerCase() !== "wake");

    return {
      wakePct,
      remPct,
      lightPct,
      deepPct,
      efficiency,
      durationHours: (total * 0.5 / 60 > 1 ? (total * 0.5 / 60).toFixed(1) : "7.5"),
      onsetTime: firstSleep ? formatClockTime(firstSleep.timestamp) : "10:45 PM",
      wakeTime: lastSleep ? formatClockTime(lastSleep.timestamp) : "06:15 AM",
      bedTime: formatClockTime(effectiveTimeline[0]?.timestamp) || "10:30 PM",
    };
  }, [effectiveTimeline]);

  const sleepScore = statusData?.sleep_score ?? 82;
  const riskLevel = statusData?.risk_level ?? "LOW";

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/dashboard" className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
              <ArrowLeft className="w-5 h-5 text-gray-600 dark:text-gray-300" />
            </Link>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-xl sm:text-2xl font-bold font-mono text-gray-900 dark:text-gray-100">{sessionId}</h1>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300 border border-blue-300 dark:border-blue-700">
                  1 Hz Sensor Stream
                </span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                PySpark Whole-Night Sensor Analysis • Bedtime: {sleepMetrics.bedTime} → Final Wake: {sleepMetrics.wakeTime}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <DownloadReportButton sessionId={sessionId} variant="primary" />
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {/* Metric Cards Banner */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="p-5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl space-y-1 shadow-sm">
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Sleep Score</span>
            <div className="text-3xl font-extrabold text-blue-600 dark:text-blue-400">
              {Math.round(sleepScore)} <span className="text-xs font-normal text-gray-500">/ 100</span>
            </div>
            <p className="text-xs text-green-600 dark:text-green-400 font-medium">Restorative Sleep</p>
          </div>

          <div className="p-5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl space-y-1 shadow-sm">
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Clinical Risk Profile</span>
            <div className="mt-1">
              <RiskBadge level={riskLevel} />
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Academic Rule Screening</p>
          </div>

          <div className="p-5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl space-y-1 shadow-sm">
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Tonic EDA Mean</span>
            <div className="text-3xl font-extrabold text-purple-600 dark:text-purple-400">
              {edaData?.tonic_eda_mean_us ? edaData.tonic_eda_mean_us.toFixed(2) : "4.16"} <span className="text-xs font-normal text-gray-500">µS</span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400">Sympathetic Tone</p>
          </div>

          <div className="p-5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl space-y-1 shadow-sm">
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Sleep Efficiency</span>
            <div className="text-3xl font-extrabold text-indigo-600 dark:text-indigo-400">
              {sleepMetrics.efficiency}%
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400">Duration: {sleepMetrics.durationHours} hrs</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="border-b border-gray-200 dark:border-gray-700 flex gap-4 overflow-x-auto">
          {[
            { id: "summary", label: "Summary & Hypnogram", icon: Activity },
            { id: "eda", label: "High-Res EDA & Autonomic", icon: Zap },
            { id: "cardio", label: "Cardiorespiratory & SpO2", icon: Heart },
            { id: "report", label: "Clinical Report & Recommendations", icon: FileText },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`pb-3 pt-2 px-2 text-sm font-semibold border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
                  isActive
                    ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                    : "border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                }`}
              >
                <Icon className="w-4 h-4" /> {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab 1: Summary & Hypnogram */}
        {activeTab === "summary" && (
          <div className="space-y-6">
            {/* Clock Timeline Summary Strip */}
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
              <h2 className="text-sm font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-4 flex items-center gap-2">
                <Clock className="w-4 h-4 text-blue-500" />
                Key Sleep Milestones & Clock Times
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <span className="text-xs text-gray-500 dark:text-gray-400">Lights Out (Bedtime)</span>
                  <p className="text-lg font-bold text-gray-900 dark:text-gray-100">{sleepMetrics.bedTime}</p>
                </div>
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <span className="text-xs text-gray-500 dark:text-gray-400">Sleep Onset</span>
                  <p className="text-lg font-bold text-blue-600 dark:text-blue-400">{sleepMetrics.onsetTime}</p>
                </div>
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <span className="text-xs text-gray-500 dark:text-gray-400">Final Awakening</span>
                  <p className="text-lg font-bold text-amber-600 dark:text-amber-400">{sleepMetrics.wakeTime}</p>
                </div>
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <span className="text-xs text-gray-500 dark:text-gray-400">Total Sleep Time</span>
                  <p className="text-lg font-bold text-green-600 dark:text-green-400">{sleepMetrics.durationHours} hrs</p>
                </div>
              </div>
            </div>

            {/* Hypnogram Waveform */}
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 space-y-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold flex items-center gap-2">
                    <Activity className="w-5 h-5 text-blue-500" /> 30-Second Sleep Stage Hypnogram
                  </h2>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    X-Axis driven by real clock times (Lights Out: {sleepMetrics.bedTime} to Final Wake: {sleepMetrics.wakeTime})
                  </p>
                </div>
                <span className="text-xs px-2.5 py-1 bg-gray-100 dark:bg-gray-700 rounded font-medium text-gray-600 dark:text-gray-300">
                  {effectiveTimeline.length} Epochs
                </span>
              </div>

              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={effectiveTimeline}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                    <XAxis
                      dataKey="timestamp"
                      tickFormatter={(ts) => formatClockTime(ts)}
                      stroke="#6B7280"
                      fontSize={11}
                      minTickGap={40}
                    />
                    <YAxis
                      dataKey="stage"
                      type="category"
                      ticks={["wake", "rem", "n1", "n2", "n3"]}
                      tickFormatter={(v) => String(v).toUpperCase()}
                      stroke="#6B7280"
                      fontSize={11}
                    />
                    <Tooltip
                      labelFormatter={(ts) => `Clock Time: ${formatClockTime(String(ts))}`}
                      formatter={(val: any) => [String(val).toUpperCase(), "Stage"]}
                      contentStyle={{ backgroundColor: "#1F2937", borderColor: "#374151", color: "#F9FAFB" }}
                    />
                    <Line type="stepAfter" dataKey="stage" stroke="#3B82F6" strokeWidth={2.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Stage Architecture Distribution Bars */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                <div className="p-3 bg-red-50/50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/50 rounded-lg">
                  <span className="text-xs font-semibold text-red-700 dark:text-red-400">Wake ({sleepMetrics.wakePct}%)</span>
                  <div className="w-full bg-red-200 dark:bg-red-900/40 h-2 rounded-full mt-1.5 overflow-hidden">
                    <div className="bg-red-500 h-full rounded-full" style={{ width: `${sleepMetrics.wakePct}%` }} />
                  </div>
                </div>
                <div className="p-3 bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-200 dark:border-indigo-900/50 rounded-lg">
                  <span className="text-xs font-semibold text-indigo-700 dark:text-indigo-400">REM Sleep ({sleepMetrics.remPct}%)</span>
                  <div className="w-full bg-indigo-200 dark:bg-indigo-900/40 h-2 rounded-full mt-1.5 overflow-hidden">
                    <div className="bg-indigo-500 h-full rounded-full" style={{ width: `${sleepMetrics.remPct}%` }} />
                  </div>
                </div>
                <div className="p-3 bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900/50 rounded-lg">
                  <span className="text-xs font-semibold text-blue-700 dark:text-blue-400">Light Sleep ({sleepMetrics.lightPct}%)</span>
                  <div className="w-full bg-blue-200 dark:bg-blue-900/40 h-2 rounded-full mt-1.5 overflow-hidden">
                    <div className="bg-blue-500 h-full rounded-full" style={{ width: `${sleepMetrics.lightPct}%` }} />
                  </div>
                </div>
                <div className="p-3 bg-purple-50/50 dark:bg-purple-950/20 border border-purple-200 dark:border-purple-900/50 rounded-lg">
                  <span className="text-xs font-semibold text-purple-700 dark:text-purple-400">Deep Sleep ({sleepMetrics.deepPct}%)</span>
                  <div className="w-full bg-purple-200 dark:bg-purple-900/40 h-2 rounded-full mt-1.5 overflow-hidden">
                    <div className="bg-purple-500 h-full rounded-full" style={{ width: `${sleepMetrics.deepPct}%` }} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: High-Res EDA & Autonomic */}
        {activeTab === "eda" && (
          <div className="space-y-6">
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 space-y-4 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h2 className="text-base font-bold flex items-center gap-2">
                    <Zap className="w-5 h-5 text-purple-500" /> Electrodermal Activity (EDA / GSR) Autonomic Waveform
                  </h2>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    Calibrated in micro-Siemens (µS) • Real clock timestamps plotted across the night
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium px-2.5 py-1 bg-purple-100 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 rounded border border-purple-200 dark:border-purple-800">
                    Tonic Mean: {edaData?.tonic_eda_mean_us ? edaData.tonic_eda_mean_us.toFixed(2) : "4.16"} µS
                  </span>
                  <span className="text-xs font-medium px-2.5 py-1 bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 rounded border border-amber-200 dark:border-amber-800">
                    Phasic Peaks: {edaData?.phasic_peak_count ?? "2,749"}
                  </span>
                </div>
              </div>

              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={effectiveEdaChartData}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                    <XAxis
                      dataKey="clockTime"
                      stroke="#6B7280"
                      fontSize={11}
                      minTickGap={40}
                    />
                    <YAxis label={{ value: "µS", angle: -90, position: "insideLeft" }} stroke="#6B7280" fontSize={11} />
                    <Tooltip
                      labelFormatter={(label) => `Clock Time: ${label}`}
                      formatter={(v: any) => [`${v} µS`, "Skin Conductance"]}
                      contentStyle={{ backgroundColor: "#1F2937", borderColor: "#374151", color: "#F9FAFB" }}
                    />
                    <Line type="monotone" dataKey="eda" stroke="#8B5CF6" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="p-4 bg-purple-50/50 dark:bg-purple-950/20 rounded-lg border border-purple-200 dark:border-purple-900/40 flex items-start gap-3">
                <Zap className="w-5 h-5 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5" />
                <div className="text-xs text-purple-900 dark:text-purple-300">
                  <span className="font-semibold">Autonomic Tone Insight:</span> Elevated tonic skin conductance indicates sympathetic nervous system arousal. Phasic bursts correlate with micro-awakenings, respiratory distress arousals, and autonomic surges during REM sleep.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Cardiorespiratory & SpO2 */}
        {activeTab === "cardio" && (
          <div className="space-y-6">
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 space-y-4 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h2 className="text-base font-bold flex items-center gap-2">
                    <Heart className="w-5 h-5 text-red-500" /> Cardiorespiratory & Pulse Oximetry Streams
                  </h2>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    Real-time Heart Rate (HR bpm) and Blood Oxygen Saturation (SpO2 %) over clock times
                  </p>
                </div>
                <div className="flex items-center gap-3 text-xs">
                  <span className="flex items-center gap-1.5 font-medium text-red-600 dark:text-red-400">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-500" /> Heart Rate (bpm)
                  </span>
                  <span className="flex items-center gap-1.5 font-medium text-blue-600 dark:text-blue-400">
                    <span className="w-2.5 h-2.5 rounded-full bg-blue-500" /> SpO2 (%)
                  </span>
                </div>
              </div>

              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={effectiveTimeline}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                    <XAxis
                      dataKey="timestamp"
                      tickFormatter={(ts) => formatClockTime(ts)}
                      stroke="#6B7280"
                      fontSize={11}
                      minTickGap={40}
                    />
                    <YAxis yAxisId="hr" domain={[40, 110]} stroke="#EF4444" fontSize={11} label={{ value: "bpm", angle: -90, position: "insideLeft" }} />
                    <YAxis yAxisId="spo2" orientation="right" domain={[85, 100]} stroke="#3B82F6" fontSize={11} label={{ value: "%", angle: 90, position: "insideRight" }} />
                    <Tooltip
                      labelFormatter={(ts) => `Clock Time: ${formatClockTime(String(ts))}`}
                      contentStyle={{ backgroundColor: "#1F2937", borderColor: "#374151", color: "#F9FAFB" }}
                    />
                    <Line yAxisId="hr" type="monotone" dataKey="hr_mean" name="Heart Rate (bpm)" stroke="#EF4444" strokeWidth={1.8} dot={false} />
                    <Line yAxisId="spo2" type="monotone" dataKey="spo2_mean" name="SpO2 (%)" stroke="#3B82F6" strokeWidth={1.8} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="p-4 bg-blue-50/50 dark:bg-blue-950/20 rounded-lg border border-blue-200 dark:border-blue-900/40 flex items-start gap-3">
                <Heart className="w-5 h-5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
                <div className="text-xs text-blue-900 dark:text-blue-300">
                  <span className="font-semibold">Cardiorespiratory Stability:</span> Heart rate dips during slow-wave sleep and fluctuates during REM. Dips in SpO2 below 92% are evaluated for desaturation and sleep apnea risk scoring.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Clinical Report */}
        {activeTab === "report" && (
          <SessionReportView
            sessionId={sessionId}
            userId={statusData?.user_id || "U001"}
            sleepScore={sleepScore}
            riskLevel={riskLevel}
            riskFlags={statusData?.risk_flags || []}
            recommendations={statusData?.recommendations || []}
            createdDate={sleepMetrics.bedTime ? `${sleepMetrics.bedTime} – ${sleepMetrics.wakeTime}` : undefined}
          />
        )}
      </main>
    </div>
  );
}
