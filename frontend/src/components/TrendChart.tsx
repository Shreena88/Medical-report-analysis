import React from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ChartOptions,
} from 'chart.js';
import { useTheme } from '../contexts/ThemeContext';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface TrendPoint {
  uploaded_at: string;
  value: number;
  status: string;
}

interface TrendChartProps {
  testName: string;
  data: TrendPoint[];
  unit: string;
}

const TrendChart: React.FC<TrendChartProps> = ({ testName, data, unit }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  // Sort data by uploaded_at date ascending for proper timeline plotting
  const sortedData = [...data].sort(
    (a, b) => new Date(a.uploaded_at).getTime() - new Date(b.uploaded_at).getTime()
  );

  const labels = sortedData.map((d) =>
    new Date(d.uploaded_at).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: '2-digit',
    })
  );

  const values = sortedData.map((d) => d.value);

  const chartData = {
    labels,
    datasets: [
      {
        label: `${testName} Level (${unit})`,
        data: values,
        borderColor: 'rgb(139, 92, 246)', // Violet 500
        backgroundColor: 'rgba(139, 92, 246, 0.1)',
        borderWidth: 2,
        tension: 0.3,
        fill: true,
        pointBackgroundColor: 'rgb(139, 92, 246)',
        pointBorderColor: isDark ? '#0f172a' : '#ffffff', // Slate 900 vs white
        pointBorderWidth: 2,
        pointRadius: 5,
        pointHoverRadius: 7,
      },
    ],
  };

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: isDark ? '#1e293b' : '#ffffff',
        titleColor: isDark ? '#f8fafc' : '#0f172a',
        bodyColor: isDark ? '#cbd5e1' : '#334155',
        borderColor: isDark ? '#334155' : '#e2e8f0',
        borderWidth: 1,
        padding: 12,
        displayColors: false,
        callbacks: {
          label: (context) => {
            const index = context.dataIndex;
            const item = sortedData[index];
            return `Value: ${context.parsed.y} ${unit} (${item.status.toUpperCase()})`;
          },
        },
      },
    },
    scales: {
      x: {
        grid: {
          color: isDark ? 'rgba(51, 65, 85, 0.2)' : 'rgba(15, 23, 42, 0.06)',
        },
        ticks: {
          color: isDark ? '#94a3b8' : '#475569',
          font: {
            size: 10,
          },
        },
      },
      y: {
        grid: {
          color: isDark ? 'rgba(51, 65, 85, 0.2)' : 'rgba(15, 23, 42, 0.06)',
        },
        ticks: {
          color: isDark ? '#94a3b8' : '#475569',
          font: {
            size: 10,
          },
        },
      },
    },
  };

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/20 p-5 shadow-sm transition-colors duration-300">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-sm font-bold tracking-wide text-slate-800 dark:text-slate-200">{testName} Trend</h4>
        <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700">
          Unit: {unit}
        </span>
      </div>
      <div className="h-64 w-full">
        <Line data={chartData} options={options} />
      </div>
    </div>
  );
};

export default TrendChart;
