import React from 'react';

export type LabTestStatus =
  | 'LOW'
  | 'NORMAL'
  | 'HIGH'
  | 'UNKNOWN'
  | 'SLIGHTLY_LOW'
  | 'SIGNIFICANTLY_LOW'
  | 'SLIGHTLY_HIGH'
  | 'SIGNIFICANTLY_HIGH';

interface StatusBadgeProps {
  status: LabTestStatus;
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const normalizedStatus = (status || 'UNKNOWN').toUpperCase() as LabTestStatus;

  const styles = {
    LOW: 'border-rose-200 dark:border-rose-500/30 bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-400',
    NORMAL: 'border-emerald-200 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
    HIGH: 'border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400',
    UNKNOWN: 'border-slate-200 dark:border-slate-500/30 bg-slate-100 dark:bg-slate-500/10 text-slate-600 dark:text-slate-400',
    SLIGHTLY_LOW: 'border-orange-200 dark:border-orange-500/30 bg-orange-50 dark:bg-orange-500/10 text-orange-700 dark:text-orange-400',
    SIGNIFICANTLY_LOW: 'border-rose-300 dark:border-rose-600/30 bg-rose-100 dark:bg-rose-600/10 text-rose-800 dark:text-rose-400 font-bold',
    SLIGHTLY_HIGH: 'border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400',
    SIGNIFICANTLY_HIGH: 'border-rose-300 dark:border-rose-600/30 bg-rose-100 dark:bg-rose-600/10 text-rose-800 dark:text-rose-400 font-bold',
  };

  const labels = {
    LOW: 'Low',
    NORMAL: 'Normal',
    HIGH: 'High',
    UNKNOWN: 'Unchecked',
    SLIGHTLY_LOW: 'Slightly Low',
    SIGNIFICANTLY_LOW: 'Significantly Low',
    SLIGHTLY_HIGH: 'Slightly High',
    SIGNIFICANTLY_HIGH: 'Significantly High',
  };

  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold uppercase tracking-wider ${
        styles[normalizedStatus] || styles.UNKNOWN
      }`}
    >
      {labels[normalizedStatus] || labels.UNKNOWN}
    </span>
  );
};

export default StatusBadge;
