import React, { useState, useRef, useEffect } from "react";
import { Download, ChevronDown, Loader2, Check, AlertCircle } from "lucide-react";

export type ReportFormat = "pdf" | "html" | "csv" | "json";

interface DownloadReportButtonProps {
  sessionId: string;
  variant?: "primary" | "secondary" | "compact";
  className?: string;
}

export const DownloadReportButton: React.FC<DownloadReportButtonProps> = ({
  sessionId,
  variant = "primary",
  className = "",
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [downloadingFormat, setDownloadingFormat] = useState<ReportFormat | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Clear feedback toast after 4s
  useEffect(() => {
    if (feedback) {
      const timer = setTimeout(() => setFeedback(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [feedback]);

  const handleDownload = async (format: ReportFormat) => {
    setIsOpen(false);
    setDownloadingFormat(format);
    setFeedback(null);

    try {
      const response = await fetch(`/api/v1/sessions/${encodeURIComponent(sessionId)}/report?format=${format}`);
      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `sleepsense_report_${sessionId}.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      setFeedback({
        type: "success",
        message: `Saved ${format.toUpperCase()} report successfully`,
      });
    } catch (err: any) {
      console.error("Report download failed:", err);
      setFeedback({
        type: "error",
        message: `Failed to download ${format.toUpperCase()} report: ${err.message || "Unknown error"}`,
      });
    } finally {
      setDownloadingFormat(null);
    }
  };

  const formats: { id: ReportFormat; label: string; desc: string }[] = [
    { id: "pdf", label: "PDF Document (.pdf)", desc: "Clinical printable report with full biometric & EDA charts" },
    { id: "html", label: "Interactive HTML (.html)", desc: "Web-viewable document formatted for clinical review" },
    { id: "csv", label: "Structured CSV (.csv)", desc: "Tabular metrics dataset for statistics & spreadsheets" },
    { id: "json", label: "Raw JSON (.json)", desc: "Complete serialized schema with EDA & model metadata" },
  ];

  const buttonStyle =
    variant === "primary"
      ? "bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
      : variant === "compact"
      ? "bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 text-xs px-2.5 py-1"
      : "bg-white hover:bg-gray-50 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-600 shadow-sm";

  return (
    <div className={`relative inline-block text-left ${className}`} ref={menuRef}>
      <div className="inline-flex rounded-lg shadow-sm">
        <button
          type="button"
          onClick={() => handleDownload("pdf")}
          disabled={downloadingFormat !== null}
          className={`flex items-center gap-1.5 px-3.5 py-2 font-medium text-xs rounded-l-lg transition-colors disabled:opacity-60 ${buttonStyle}`}
          title="Download PDF clinical report"
        >
          {downloadingFormat ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Download className="w-3.5 h-3.5" />
          )}
          <span>{downloadingFormat ? `Generating ${downloadingFormat.toUpperCase()}...` : "Download Report"}</span>
        </button>

        <button
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          disabled={downloadingFormat !== null}
          className={`px-2 py-2 border-l border-white/20 dark:border-gray-600 rounded-r-lg transition-colors hover:brightness-95 disabled:opacity-60 ${buttonStyle}`}
          aria-expanded={isOpen}
          aria-label="Select report format"
        >
          <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
        </button>
      </div>

      {/* Format Selection Dropdown */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-72 origin-top-right rounded-xl bg-white dark:bg-gray-800 shadow-xl ring-1 ring-black/10 dark:ring-white/10 z-50 divide-y divide-gray-100 dark:divide-gray-700 overflow-hidden animate-in fade-in zoom-in-95 duration-100">
          <div className="px-3.5 py-2.5 bg-gray-50/70 dark:bg-gray-900/40">
            <p className="text-xs font-semibold text-gray-700 dark:text-gray-300">Choose Report Format</p>
            <p className="text-[11px] text-gray-500 dark:text-gray-400">Includes complete EDA autonomic and sleep metrics</p>
          </div>

          <div className="py-1">
            {formats.map((fmt) => (
              <button
                key={fmt.id}
                type="button"
                onClick={() => handleDownload(fmt.id)}
                className="w-full text-left px-3.5 py-2.5 text-xs hover:bg-blue-50 dark:hover:bg-gray-700/60 transition-colors flex flex-col gap-0.5 group"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-gray-900 dark:text-gray-100 group-hover:text-blue-600 dark:group-hover:text-blue-400">
                    {fmt.label}
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 uppercase">
                    .{fmt.id}
                  </span>
                </div>
                <span className="text-[11px] text-gray-500 dark:text-gray-400 line-clamp-1">
                  {fmt.desc}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Feedback Toast Notification */}
      {feedback && (
        <div
          className={`absolute right-0 mt-2 w-72 rounded-lg p-2.5 shadow-lg border text-xs flex items-start gap-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150 ${
            feedback.type === "success"
              ? "bg-green-50 dark:bg-green-950/80 border-green-200 dark:border-green-800 text-green-900 dark:text-green-200"
              : "bg-red-50 dark:bg-red-950/80 border-red-200 dark:border-red-800 text-red-900 dark:text-red-200"
          }`}
        >
          {feedback.type === "success" ? (
            <Check className="w-4 h-4 text-green-600 dark:text-green-400 shrink-0 mt-0.5" />
          ) : (
            <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
          )}
          <span className="leading-tight">{feedback.message}</span>
        </div>
      )}
    </div>
  );
};
