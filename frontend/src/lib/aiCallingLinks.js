/** Build an AI Calling deep link, optionally scoped to an upload batch. */
export function buildAICallingPath({
  uploadBatchId,
  batchName,
  status,
} = {}) {
  const params = new URLSearchParams();
  if (uploadBatchId && uploadBatchId !== "all") {
    params.set("upload_batch_id", uploadBatchId);
  }
  if (batchName) params.set("batch_name", batchName);
  if (status && status !== "all") params.set("status", status);
  const query = params.toString();
  return query ? `/ai-calling?${query}` : "/ai-calling";
}

export const LIVE_STATUS_TO_CALL_STATUS = {
  completed: "completed",
  busy: "busy",
  no_answer: "no-answer",
  call_disconnected: "call-disconnected",
  failed: "failed",
};
