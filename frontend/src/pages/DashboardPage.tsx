import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import ReportCard from '../components/ReportCard';
import MedicalDisclaimer from '../components/MedicalDisclaimer';

interface ReportSummary {
  id: string;
  file_name: string;
  uploaded_at: string;
  status: string;
  summary: string | null;
}

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Upload states
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');

  // Fetch reports on mount
  const fetchReports = useCallback(async () => {
    try {
      const res = await api.get<ReportSummary[]>('/reports');
      setReports(res.data);
    } catch (err: any) {
      console.error(err);
      setError('Failed to load reports. Please refresh the page.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  // Handle Drag Events
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  // Process and Upload File
  const processFile = async (file: File) => {
    setUploadError('');
    
    // 1. Client-side MIME Type Validation (PDF, JPEG, PNG)
    const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg'];
    if (!allowedTypes.includes(file.type)) {
      setUploadError('Invalid file type. Only PDF, PNG, and JPEG files are supported.');
      return;
    }

    // 2. Client-side Size Validation (10MB limit)
    const maxSizeBytes = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSizeBytes) {
      setUploadError('File is too large. Maximum size allowed is 10 MB.');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post<{ report_id: string; message: string }>('/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      // Navigate to detailed page to monitor progress via polling
      navigate(`/report/${res.data.report_id}`);
    } catch (err: any) {
      console.error(err);
      setUploadError(
        err.response?.data?.detail || 'An error occurred during file upload.'
      );
      setUploading(false);
    }
  };

  // Handle Drop Event
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  // Handle File Input Change
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  // Delete a Report
  const handleDeleteReport = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this report? This will remove all associated analysis.')) {
      return;
    }

    try {
      await api.delete(`/report/${id}`);
      setReports((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      console.error(err);
      alert('Failed to delete the report. Please try again.');
    }
  };

  // Stats calculation
  const totalReports = reports.length;
  const processingReportsCount = reports.filter(
    (r) => !['complete', 'failed_ocr', 'failed_extraction', 'failed_classification'].includes(r.status)
  ).length;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Decorative background glows */}
      <div className="absolute top-10 right-10 h-[250px] w-[250px] rounded-full bg-indigo-600/5 dark:bg-indigo-600/5 blur-[80px] pointer-events-none"></div>

      <div className="space-y-8">
        {/* Welcome Banner */}
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
              Health Report Analytics
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Upload laboratory reports to analyze biomarker status and monitor health trends over time.
            </p>
          </div>
        </div>

        {/* Global Medical Disclaimer */}
        <MedicalDisclaimer />

        {/* Quick Stats Grid */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/30 p-5 backdrop-blur-sm shadow-sm transition-colors duration-300">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Analyzed Reports</p>
            <h3 className="mt-2 text-3xl font-bold text-slate-800 dark:text-slate-100">{totalReports}</h3>
          </div>
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/30 p-5 backdrop-blur-sm shadow-sm transition-colors duration-300">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Processing Reports</p>
            <h3 className="mt-2 text-3xl font-bold text-slate-800 dark:text-slate-100">{processingReportsCount}</h3>
          </div>
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/30 p-5 backdrop-blur-sm shadow-sm transition-colors duration-300">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Biomarkers Seeded</p>
            <h3 className="mt-2 text-3xl font-bold text-violet-600 dark:text-violet-400">10 Core</h3>
          </div>
        </div>

        {/* Upload and File Drop Area */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/20 p-6 shadow-sm transition-colors duration-300">
          <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100 mb-4">Analyze New Report</h2>
          
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            className={`relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-all duration-300 ${
              dragActive
                ? 'border-violet-500 bg-violet-500/5 dark:bg-violet-500/5'
                : 'border-slate-200 hover:border-slate-300 dark:border-slate-800 dark:hover:border-slate-700 bg-slate-50/50 dark:bg-slate-900/10'
            }`}
          >
            {uploading ? (
              <div className="flex flex-col items-center gap-4 py-4">
                <div className="h-10 w-10 animate-spin rounded-full border-4 border-violet-500 border-t-transparent"></div>
                <div>
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Uploading file...</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Starting the AI diagnostic processing pipeline</p>
                </div>
              </div>
            ) : (
              <>
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800/80 text-violet-600 dark:text-violet-400 mb-4 border border-slate-200 dark:border-slate-700 shadow-sm transition-colors duration-300">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    className="h-6 w-6"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5a4.5 4.5 0 0 1-1.41-8.775 5.25 5.25 0 0 1 10.233-2.33 3 3 0 0 1 3.758 3.848A3.752 3.752 0 0 1 18 19.5H6.75Z"
                    />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                  Drag and drop your medical report here, or{' '}
                  <label className="text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300 cursor-pointer transition-colors">
                    browse
                    <input
                      type="file"
                      className="hidden"
                      accept=".pdf,.png,.jpg,.jpeg"
                      onChange={handleFileChange}
                    />
                  </label>
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  Supports PDF, PNG, or JPEG (Max 10 MB)
                </p>
              </>
            )}
          </div>

          {uploadError && (
            <div className="mt-4 flex gap-2.5 rounded-lg border border-rose-500/20 bg-rose-500/5 p-3.5 text-xs text-rose-600 dark:text-rose-400">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
                className="h-4 w-4 flex-shrink-0"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
                />
              </svg>
              <span>{uploadError}</span>
            </div>
          )}
        </div>

        {/* Reports History */}
        <div className="space-y-4">
          <h2 className="text-xl font-bold text-slate-800 dark:text-slate-100">Reports History</h2>
          
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-3 border-violet-500 border-t-transparent"></div>
            </div>
          ) : error ? (
            <div className="rounded-lg border border-rose-500/20 bg-rose-500/5 p-4 text-center text-sm text-rose-600 dark:text-rose-400">
              {error}
            </div>
          ) : reports.length === 0 ? (
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/10 p-12 text-center shadow-sm transition-colors duration-300">
              <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700 mb-3 transition-colors duration-300">
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
                    d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
                  />
                </svg>
              </div>
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">No reports analyzed yet</h3>
              <p className="text-xs text-slate-550 dark:text-slate-400 mt-1 max-w-sm mx-auto leading-normal">
                Upload your first laboratory report above to get a comprehensive biomarker extraction and AI analysis.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {reports.map((report) => (
                <ReportCard
                  key={report.id}
                  report={report}
                  onDeleteClick={handleDeleteReport}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
