/**
 * Centred animated loading spinner component.
 * Used as the Suspense fallback for lazy-loaded routes.
 */

export function LoadingSpinner() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        minHeight: "400px",
      }}
    >
      <svg
        width="48"
        height="48"
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{
          animation: "spin 1s linear infinite",
        }}
      >
        <style>{`
          @keyframes spin {
            from {
              transform: rotate(0deg);
            }
            to {
              transform: rotate(360deg);
            }
          }
        `}</style>
        <circle
          cx="24"
          cy="24"
          r="20"
          stroke="rgba(91, 140, 255, 0.2)"
          strokeWidth="2"
          fill="none"
        />
        <circle
          cx="24"
          cy="24"
          r="20"
          stroke="var(--accent-primary, #5b8cff)"
          strokeWidth="2"
          fill="none"
          strokeDasharray="31.4 125.6"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}
