/** Whole billed minutes, always rounded up. 1–60s → 1, 61–120s → 2. */
export function billedMinutes(seconds) {
  const n = Number(seconds);
  if (!Number.isFinite(n) || n <= 0) return 0;
  return Math.ceil(n / 60);
}

/** Call talk-time for the product UI: never show seconds. */
export function formatDuration(seconds) {
  return `${billedMinutes(seconds)}m`;
}

/** Recording scrubber only — clock time, not billed minutes. */
export function formatPlaybackClock(seconds) {
  const n = Math.max(0, Math.floor(Number(seconds) || 0));
  const mins = Math.floor(n / 60);
  const secs = n % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}
