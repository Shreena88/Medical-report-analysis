import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import api from '../api/axios';
import StatusBadge, { LabTestStatus } from '../components/StatusBadge';
import MedicalDisclaimer from '../components/MedicalDisclaimer';

interface LabTest {
  test_name: string;
  value: number;
  unit: string;
  reference_range: string;
  status: LabTestStatus;
  explanation: string | null;
}

interface Report {
  id: string;
  file_name: string;
  file_path: string;
  uploaded_at: string;
  status: string;
  ocr_text: string | null;
  lab_tests: LabTest[];
  summary: string | null;
  error_message: string | null;
}

const ReportDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showOcr, setShowOcr] = useState(false);
  const [expandedExplanations, setExpandedExplanations] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let intervalId: any;

    const fetchReport = async (isInitial = false) => {
      if (isInitial) setLoading(true);
      try {
        const res = await api.get<Report>(`/report/${id}`);
        setReport(res.data);
        setError('');

        // If the report status is in-progress, continue polling
        const inProgressStatuses = ['pending', 'ocr_complete', 'extracted', 'validated'];
        if (inProgressStatuses.includes(res.data.status)) {
          if (!intervalId) {
            intervalId = setInterval(() => fetchReport(false), 3000);
          }
        } else {
          // Finished status (complete or failed), clear polling
          if (intervalId) clearInterval(intervalId);
        }
      } catch (err: any) {
        console.error(err);
        setError(err.response?.data?.detail || 'Failed to load report analysis.');
        if (intervalId) clearInterval(intervalId);
      } finally {
        if (isInitial) setLoading(false);
      }
    };

    fetchReport(true);

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [id]);

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this report? This action cannot be undone.')) {
      return;
    }
    try {
      await api.delete(`/report/${id}`);
      navigate('/dashboard');
    } catch (err) {
      console.error(err);
      alert('Failed to delete report. Please try again.');
    }
  };

  const toggleExplanation = (testName: string) => {
    setExpandedExplanations((prev) => ({
      ...prev,
      [testName]: !prev[testName],
    }));
  };

  const getStepProgress = (status: string) => {
    switch (status) {
      case 'pending':
        return { percent: 15, text: 'File Uploaded. Queuing analysis...' };
      case 'ocr_complete':
        return { percent: 40, text: 'OCR complete. Extracting test metrics...' };
      case 'extracted':
        return { percent: 70, text: 'Metrics extracted. Cross-referencing ranges...' };
      case 'validated':
        return { percent: 90, text: 'Reference ranges validated. Writing AI explanations...' };
      default:
        return { percent: 0, text: 'Initializing...' };
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-violet-500 border-t-transparent"></div>
          <p className="text-sm text-slate-400 font-medium">Fetching report analysis...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center">
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-8">
          <h2 className="text-xl font-bold text-rose-450">Error Loading Analysis</h2>
          <p className="mt-2 text-sm text-slate-400">{error}</p>
          <Link
            to="/dashboard"
            className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-violet-400 hover:text-violet-300"
          >
            &larr; Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  if (!report) return null;

  const isProcessing = ['pending', 'ocr_complete', 'extracted', 'validated'].includes(report.status);
  const isFailed = ['failed_ocr', 'failed_extraction'].includes(report.status);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="space-y-8">
        {/* Navigation & Header Actions */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-5">
          <div className="flex flex-col gap-1">
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-1 text-xs font-semibold text-slate-400 hover:text-violet-400 transition-colors"
            >
              &larr; Back to Dashboard
            </Link>
            <h1 className="mt-1 text-2xl font-bold text-slate-100 break-all">{report.file_name}</h1>
            <p className="text-xs text-slate-500">
              Uploaded on {new Date(report.uploaded_at).toLocaleString()}
            </p>
          </div>

          {!isProcessing && (
            <button
              onClick={handleDelete}
              className="rounded-lg border border-rose-500/20 bg-rose-500/5 px-4 py-2 text-sm font-semibold text-rose-400 hover:bg-rose-500/10 transition-colors"
            >
              Delete Analysis
            </button>
          )}
        </div>

        {/* 1. Loading/Polling View */}
        {isProcessing && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-8 backdrop-blur-sm">
            <div className="flex flex-col items-center justify-center text-center space-y-4">
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-violet-500 border-t-transparent"></div>
              
              <div className="w-full max-w-md">
                <p className="text-sm font-semibold text-slate-200">{getStepProgress(report.status).text}</p>
                <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-slate-800">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-violet-600 to-indigo-500 transition-all duration-500"
                    style={{ width: `${getStepProgress(report.status).percent}%` }}
                  ></div>
                </div>
              </div>
              <p className="text-xs text-slate-500">Analyzing medical files can take up to 30 seconds. Feel free to wait or come back later.</p>
            </div>
          </div>
        )}

        {/* 2. Failure View */}
        {isFailed && (
          <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-8 text-center">
            <svg
              className="mx-auto h-12 w-12 text-rose-500"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
              />
            </svg>
            <h2 className="mt-4 text-lg font-bold text-slate-200">Analysis Pipeline Failed</h2>
            <p className="mt-2 text-sm text-slate-400">
              {report.error_message || 'An unexpected failure occurred while processing your report. Please ensure the file is a readable medical report.'}
            </p>
            <Link
              to="/dashboard"
              className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-violet-400 hover:text-violet-300"
            >
              Try uploading another file
            </Link>
          </div>
        )}

        {/* 3. Successful Loaded View */}
        {report.status === 'complete' && (
          <div className="space-y-8 animate-fade-in">
            {/* Medical Disclaimer Banner */}
            <MedicalDisclaimer />

            {/* AI Summary Box */}
            {report.summary && (
              <div className="rounded-2xl border border-violet-500/20 bg-gradient-to-r from-slate-900/60 to-slate-900/40 p-6 backdrop-blur-sm">
                <h3 className="text-sm font-bold tracking-wider uppercase text-violet-400">Clinical Overview</h3>
                <p className="mt-3 text-slate-250 leading-relaxed text-sm md:text-base font-light whitespace-pre-line">
                  {report.summary}
                </p>
              </div>
            )}

            {/* Extracted Lab Tests Results */}
            <div className="space-y-4">
              <h3 className="text-lg font-bold text-slate-200">Extracted Biomarkers</h3>
              
              {report.lab_tests.length === 0 ? (
                <div className="rounded-xl border border-slate-800 bg-slate-900/10 p-6 text-center text-sm text-slate-450">
                  No medical parameters were extracted. The document may not contain clear medical data.
                </div>
              ) : (
                <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/20 backdrop-blur-sm">
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-left text-sm text-slate-300">
                      <thead className="border-b border-slate-800 bg-slate-900/40 text-slate-400">
                        <tr>
                          <th className="px-6 py-4 font-semibold">Test Name</th>
                          <th className="px-6 py-4 font-semibold">Value</th>
                          <th className="px-6 py-4 font-semibold">Reference Range</th>
                          <th className="px-6 py-4 font-semibold">Status</th>
                          <th className="px-6 py-4 font-semibold text-right">Details</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {report.lab_tests.map((test) => {
                          const isExpanded = !!expandedExplanations[test.test_name];
                          return (
                            <React.Fragment key={test.test_name}>
                              <tr className="hover:bg-slate-900/30 transition-colors">
                                <td className="px-6 py-4 font-medium text-slate-100">{test.test_name}</td>
                                <td className="px-6 py-4 font-semibold text-slate-200">
                                  {test.value} <span className="text-xs font-normal text-slate-400">{test.unit}</span>
                                </td>
                                <td className="px-6 py-4 text-slate-400">{test.reference_range}</td>
                                <td className="px-6 py-4">
                                  <StatusBadge status={test.status} />
                                </td>
                                <td className="px-6 py-4 text-right">
                                  {test.explanation && (
                                    <button
                                      onClick={() => toggleExplanation(test.test_name)}
                                      className="inline-flex items-center gap-1 text-xs font-semibold text-violet-400 hover:text-violet-300 transition-colors"
                                    >
                                      {isExpanded ? 'Hide' : 'Explain'}
                                      <svg
                                        xmlns="http://www.w3.org/2000/svg"
                                        fill="none"
                                        viewBox="0 0 24 24"
                                        strokeWidth={2.5}
                                        stroke="currentColor"
                                        className={`h-3 w-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                                      >
                                        <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                                      </svg>
                                    </button>
                                  )}
                                </td>
                              </tr>
                              {/* Collapsible Explanation Row */}
                              {isExpanded && test.explanation && (
                                <tr>
                                  <td colSpan={5} className="bg-slate-900/10 px-8 py-4 text-xs text-slate-350 leading-relaxed border-t border-slate-850">
                                    <div className="flex gap-2">
                                      <div className="mt-0.5 text-violet-400 font-bold">Explanation:</div>
                                      <div className="flex-1 font-light text-slate-300">{test.explanation}</div>
                                    </div>
                                  </td>
                                </tr>
                              )}
                            </React.Fragment>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Collapsible raw OCR Text drawer */}
            {report.ocr_text && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/15">
                <button
                  onClick={() => setShowOcr(!showOcr)}
                  className="flex w-full items-center justify-between px-6 py-4 text-sm font-semibold text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <span>View Raw Extracted Text (OCR)</span>
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2}
                    stroke="currentColor"
                    className={`h-4 w-4 transition-transform ${showOcr ? 'rotate-180' : ''}`}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                  </svg>
                </button>
                {showOcr && (
                  <div className="border-t border-slate-800 bg-slate-950/40 p-6">
                    <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-[11px] text-slate-450 leading-relaxed select-all">
                      {report.ocr_text}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportDetailPage;
