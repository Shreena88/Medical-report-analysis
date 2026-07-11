import React from 'react';

const MedicalDisclaimer: React.FC = () => {
  return (
    <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 dark:bg-amber-500/5 p-4 text-amber-800 dark:text-amber-400">
      <div className="flex gap-3">
        <div className="flex-shrink-0">
          <svg
            className="h-5 w-5 text-amber-600 dark:text-amber-500"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
            />
          </svg>
        </div>
        <div>
          <h3 className="text-sm font-bold tracking-wide uppercase text-amber-900 dark:text-amber-400">Medical Disclaimer</h3>
          <p className="mt-1 text-sm text-amber-800/90 dark:text-amber-400/80 leading-relaxed">
            This application is for educational purposes only. It is not a substitute for professional medical advice, 
            diagnosis, or treatment. Always consult with a qualified healthcare provider regarding a medical condition.
          </p>
        </div>
      </div>
    </div>
  );
};

export default MedicalDisclaimer;
