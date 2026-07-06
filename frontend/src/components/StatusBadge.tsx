import React from 'react';

export type LabTestStatus = 'LOW' | 'NORMAL' | 'HIGH' | 'UNKNOWN';

interface StatusBadgeProps {
  status: LabTestStatus;
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const normalizedStatus = (status || 'UNKNOWN').toUpperCase() as LabTestStatus;

  const styles = {
    LOW: 'border-rose-500/30 bg-rose-500/10 text-rose-400',
    NORMAL: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
    HIGH: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
    UNKNOWN: 'border-slate-500/30 bg-slate-500/10 text-slate-400',
  };

  const labels = {
    LOW: 'Low',
    NORMAL: 'Normal',
    HIGH: 'High',
    UNKNOWN: 'Unchecked',
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
