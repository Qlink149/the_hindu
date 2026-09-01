/** Shared call status pill styles (AI Calling + call detail). */

export const CALL_STATUS_BADGE_CLASS = {
  completed: "bg-emerald-900/30 text-emerald-300 border border-emerald-500/30",
  "no-answer": "bg-yellow-900/30 text-yellow-300 border border-yellow-500/30",
  busy: "bg-orange-900/30 text-orange-300 border border-orange-500/30",
  failed: "bg-red-900/30 text-red-300 border border-red-500/30",
};

export function getCallStatusBadgeClass(status) {
  const key = String(status || "").trim().toLowerCase();
  return (
    CALL_STATUS_BADGE_CLASS[key] ||
    "bg-gray-900/30 text-gray-300 border border-gray-500/30"
  );
}
