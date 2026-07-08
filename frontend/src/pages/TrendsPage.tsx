import React, { useState, useEffect } from 'react';
import api from '../api/axios';
import TrendChart from '../components/TrendChart';
import MedicalDisclaimer from '../components/MedicalDisclaimer';

interface TrendPoint {
  report_id: string;
  uploaded_at: string;
  value: number;
  unit: string;
  status: string;
}

const TRACKED_TESTS = [
  'Blood Sugar',
  'Hemoglobin',
  'Vitamin D',
  'Platelets',
  'WBC',
  'RBC',
  'Hematocrit',
  'Creatinine',
  'ALT',
  'AST',
  'HbA1c',
  'TSH',
  'Free T4',
  'Free T3',
  'Total Cholesterol',
  'LDL Cholesterol',
  'HDL Cholesterol',
  'Triglycerides',
  'Sodium',
  'Potassium',
  'Chloride',
  'Calcium',
  'BUN',
  'Total Bilirubin',
  'Alkaline Phosphatase',
  'Albumin',
  'Vitamin B12',
  'CRP',
  'MCV',
  'MCH',
  'MCHC',
  'RDW',
];

const TrendsPage: React.FC = () => {
  const [trendsData, setTrendsData] = useState<Record<string, TrendPoint[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchAllTrends = async () => {
      setLoading(true);
      try {
        const fetchPromises = TRACKED_TESTS.map(async (testName) => {
          const res = await api.get<TrendPoint[]>(`/trends/${testName}`);
          return { testName, data: res.data };
        });

        const results = await Promise.all(fetchPromises);
        const aggregated: Record<string, TrendPoint[]> = {};
        
        results.forEach((item) => {
          aggregated[item.testName] = item.data;
        });

        setTrendsData(aggregated);
        setError('');
      } catch (err) {
        console.error('Failed to fetch historical trends data:', err);
        setError('Failed to retrieve historical biomarker data. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    fetchAllTrends();
  }, []);

  // Filter out biomarkers that actually have enough data to display (at least 2 points)
  const activeTrends = Object.keys(trendsData).filter(
    (key) => trendsData[key] && trendsData[key].length >= 2
  );

  const inactiveTrends = Object.keys(trendsData).filter(
    (key) => !trendsData[key] || trendsData[key].length < 2
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Decorative background glows */}
      <div className="absolute top-10 left-10 h-[250px] w-[250px] rounded-full bg-violet-600/5 blur-[80px] pointer-events-none"></div>

      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">Biomarker Trends</h1>
          <p className="mt-1 text-sm text-slate-400">
            Visualize your physiological developments over time across multiple uploaded lab reports.
          </p>
        </div>

        {/* Disclaimer banner */}
        <MedicalDisclaimer />

        {loading ? (
          <div className="flex justify-center py-16">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-violet-500 border-t-transparent"></div>
          </div>
        ) : error ? (
          <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-6 text-center text-rose-450">
            {error}
          </div>
        ) : (
          <div className="space-y-10">
            {/* 1. Active Charts Grid */}
            {activeTrends.length > 0 ? (
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                {activeTrends.map((testName) => {
                  const data = trendsData[testName];
                  const unit = data[0]?.unit || '';
                  return (
                    <TrendChart
                      key={testName}
                      testName={testName}
                      data={data}
                      unit={unit}
                    />
                  );
                })}
              </div>
            ) : (
              <div className="rounded-2xl border border-slate-800 bg-slate-900/10 p-12 text-center">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg bg-slate-850 text-slate-400 border border-slate-700 mb-4">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    className="h-5 w-5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941"
                    />
                  </svg>
                </div>
                <h3 className="text-base font-semibold text-slate-200">Insufficient Trend Data</h3>
                <p className="text-xs text-slate-400 mt-2 max-w-md mx-auto leading-relaxed">
                  To view trend lines, you must upload at least **two separate laboratory reports** containing 
                  matching biomarkers (e.g., Blood Sugar or Hemoglobin).
                </p>
              </div>
            )}

            {/* 2. Parameters with insufficient data details */}
            {inactiveTrends.length > 0 && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/10 p-6">
                <h4 className="text-sm font-bold text-slate-355 uppercase tracking-wider mb-4">
                  Other Tracked Biomarkers
                </h4>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
                  {inactiveTrends.map((testName) => {
                    const dataPoints = trendsData[testName]?.length || 0;
                    return (
                      <div
                        key={testName}
                        className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 hover:border-slate-700 transition-colors"
                      >
                        <div className="text-xs font-semibold text-slate-300 truncate">{testName}</div>
                        <div className="text-[10px] text-slate-500 mt-1">
                          {dataPoints === 0 ? 'No data' : `${dataPoints} data point`}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default TrendsPage;
