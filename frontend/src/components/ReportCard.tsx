import React from 'react';
import { Link } from 'react-router-dom';

interface ReportSummary {
  id: string;
  file_name: string;
  uploaded_at: string;
  status: string;
  summary: string | null;
}

interface ReportCardProps {
  report: ReportSummary;
  onDeleteClick: (id: string, e: React.MouseEvent) => void;
}

const ReportCard: React.FC<ReportCardProps> = ({ report, onDeleteClick }) => {
  const formattedDate = new Date(report.uploaded_at).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  const getStatusDisplay = (status: string) => {
    switch (status) {
      case 'complete':
        return {
          label: 'Ready',
          class: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
        };
      case 'failed_ocr':
      case 'failed_extraction':
      case 'failed_classification':
        return {
          label: 'Failed',
          class: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
        };
      case 'pending':
        return {
          label: 'Uploading',
          class: 'bg-blue-500/10 text-blue-400 border-blue-500/20 animate-pulse',
        };
      case 'ocr_complete':
        return {
          label: 'Extracting Text',
          class: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20 animate-pulse',
        };
      case 'extracted':
      case 'validated':
        return {
          label: 'Analyzing Ranges',
          class: 'bg-violet-500/10 text-violet-400 border-violet-500/20 animate-pulse',
        };
      default:
        return {
          label: status,
          class: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
        };
    }
  };

  const statusInfo = getStatusDisplay(report.status);

  return (
    <div className="group relative rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/40 p-5 backdrop-blur-sm transition-all duration-300 hover:border-slate-300 dark:hover:border-slate-700 hover:shadow-md dark:hover:shadow-lg dark:hover:shadow-violet-950/10">
      <div className="flex flex-col gap-4">
        {/* Header (File Name and Status Badge) */}
        <div className="flex items-start justify-between gap-3">
          <Link
            to={`/report/${report.id}`}
            className="flex-1 font-semibold text-slate-800 dark:text-slate-100 hover:text-violet-600 dark:hover:text-violet-400 transition-colors line-clamp-1 break-all"
          >
            {report.file_name}
          </Link>
          <span
            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${statusInfo.class}`}
          >
            {statusInfo.label}
          </span>
        </div>

        {/* Date and details */}
        <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
          <span>Uploaded {formattedDate}</span>
        </div>

        {/* Short Summary (if available) */}
        {report.status === 'complete' && report.summary && (
          <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed line-clamp-2 mt-1">
            {report.summary}
          </p>
        )}

        {/* Action Tray */}
        <div className="flex items-center justify-between mt-2 pt-3 border-t border-slate-100 dark:border-slate-800/80">
          <Link
            to={`/report/${report.id}`}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300 transition-colors"
          >
            View Analysis
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
            </svg>
          </Link>

          <button
            onClick={(e) => onDeleteClick(report.id, e)}
            className="rounded p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-rose-600 dark:hover:text-rose-400 transition-all duration-200"
            title="Delete Report"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="h-4 w-4"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ReportCard;
