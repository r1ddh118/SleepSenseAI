import React from "react";
import { AlertTriangle, CheckCircle, FileText, ShieldAlert } from "lucide-react";
import { DownloadReportButton } from "./DownloadReportButton";

interface RiskFlag {
  condition: string;
  risk: string;
  confidence: number;
  reasons: string[];
  disclaimer?: string;
}

interface Recommendation {
  category?: string;
  area?: string;
  recommendation?: string;
  message?: string;
  priority?: string;
}

interface SessionReportViewProps {
  sessionId: string;
  userId?: string;
  sleepScore?: number;
  riskLevel?: string;
  riskFlags?: RiskFlag[];
  recommendations?: Recommendation[];
  disclaimer?: string;
  createdDate?: string;
}

export const SessionReportView: React.FC<SessionReportViewProps> = ({
  sessionId,
  userId = "U001",
  sleepScore = 75,
  riskLevel = "LOW",
  riskFlags = [],
  recommendations = [],
  disclaimer = "Academic risk screening only; not clinically validated and not a medical diagnosis.",
  createdDate = new Date().toLocaleDateString(),
}) => {
  const getRiskColor = (level?: string) => {
    switch (level?.toUpperCase()) {
      case "HIGH":
        return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300 border-red-300";
      case "MODERATE":
        return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 border-amber-300";
      default:
        return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 border-green-300";
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm space-y-6">
      {/* Header & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-200 dark:border-gray-700 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <FileText className="w-6 h-6 text-blue-600 dark:text-blue-400" />
            <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
              Clinical Session Summary
            </h2>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Session ID: <span className="font-mono font-medium text-gray-700 dark:text-gray-300">{sessionId}</span> | Patient: <span className="font-medium">{userId}</span> | Date: {createdDate}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <DownloadReportButton sessionId={sessionId} variant="primary" />
        </div>
      </div>

      {/* Disclaimer Banner */}
      <div className="bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 rounded-lg p-4 flex items-start gap-3">
        <ShieldAlert className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
        <div className="text-xs text-amber-800 dark:text-amber-300">
          <span className="font-semibold">Important Notice:</span> {disclaimer}
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="p-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
          <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider font-semibold">Sleep Score</span>
          <div className="text-3xl font-extrabold text-blue-600 dark:text-blue-400 mt-1">
            {Math.round(sleepScore)} <span className="text-sm font-normal text-gray-500 dark:text-gray-400">/ 100</span>
          </div>
        </div>
        <div className="p-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
          <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider font-semibold">Academic Risk Assessment</span>
          <div className="mt-1">
            <span className={`inline-block px-3 py-1 rounded-full text-xs font-bold border ${getRiskColor(riskLevel)}`}>
              {riskLevel.toUpperCase()} RISK
            </span>
          </div>
        </div>
      </div>

      {/* Risk Flags Section */}
      <div className="space-y-3">
        <h3 className="text-sm font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-500" />
          Identified Condition Patterns ({riskFlags.length})
        </h3>
        {riskFlags.length === 0 ? (
          <div className="p-3 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg text-xs text-green-700 dark:text-green-300 flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400" />
            No elevated risk patterns detected during this session.
          </div>
        ) : (
          <div className="space-y-2">
            {riskFlags.map((flag, idx) => (
              <div key={idx} className="p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900/40 text-xs space-y-1.5">
                <div className="flex items-center justify-between font-semibold text-gray-900 dark:text-gray-100">
                  <span>{flag.condition}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] uppercase border ${getRiskColor(flag.risk)}`}>
                    {flag.risk} ({Math.round(flag.confidence * 100)}% conf)
                  </span>
                </div>
                {flag.reasons && flag.reasons.length > 0 && (
                  <ul className="list-disc list-inside text-gray-600 dark:text-gray-400 space-y-0.5 pl-1">
                    {flag.reasons.map((r, rIdx) => (
                      <li key={rIdx}>{r}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recommendations Section */}
      <div className="space-y-3 border-t border-gray-200 dark:border-gray-700 pt-4">
        <h3 className="text-sm font-bold text-gray-900 dark:text-gray-100">
          Targeted Recommendations ({recommendations.length})
        </h3>
        {recommendations.length === 0 ? (
          <p className="text-xs text-gray-500 dark:text-gray-400">No specific action items generated for this session.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {recommendations.map((rec, idx) => (
              <div key={idx} className="p-3 rounded-lg border border-blue-100 dark:border-blue-900/40 bg-blue-50/50 dark:bg-blue-950/20 text-xs space-y-1">
                <div className="font-bold text-blue-900 dark:text-blue-300 uppercase text-[10px]">
                  {rec.category || rec.area || "Lifestyle"}
                </div>
                <p className="text-gray-700 dark:text-gray-300">
                  {rec.recommendation || rec.message}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
