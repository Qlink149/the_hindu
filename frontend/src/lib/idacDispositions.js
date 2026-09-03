/** IDAC Futwork disposition definitions (mirrors backend IDAC_DISPOSITION_ORDER). */

export const IDAC_DISPOSITIONS = [
  {
    key: "Dropped",
    label: "Dropped",
    statKey: "dropped_calls",
    filterKey: "Dropped",
    color: "#d25f86",
    borderClass: "border-red-500",
    badgeClass: "border bg-orange-900/30 text-orange-300 border-orange-500/30",
  },
  {
    key: "Attending",
    label: "Attending",
    statKey: "attending_calls",
    filterKey: "Attending",
    color: "#2563A8",
    borderClass: "border-teal-500",
    badgeClass: "border bg-emerald-900/30 text-emerald-300 border-emerald-500/30",
  },
  {
    key: "Busy",
    label: "Busy",
    statKey: "busy_calls",
    filterKey: "Busy",
    color: "#f59e0b",
    borderClass: "border-amber-500",
    badgeClass: "border bg-yellow-900/30 text-yellow-300 border-yellow-500/30",
  },
  {
    key: "No Answer",
    label: "NA",
    statKey: "na_calls",
    filterKey: "No Answer",
    color: "#b5a6f6",
    borderClass: "border-gray-500",
    badgeClass: "border bg-sky-900/30 text-sky-300 border-sky-500/30",
  },
  {
    key: "Not Attending",
    label: "Not Attending",
    statKey: "not_attending_calls",
    filterKey: "Not Attending",
    color: "#4A7AB5",
    borderClass: "border-orange-500",
    badgeClass: "border bg-blue-900/30 text-blue-300 border-blue-500/30",
  },
  {
    key: "Wrong Number",
    label: "Wrong Number",
    statKey: "wrong_number_calls",
    filterKey: "Wrong Number",
    color: "#1B4F8C",
    borderClass: "border-purple-500",
    badgeClass: "border bg-purple-900/30 text-purple-300 border-purple-500/30",
  },
];

export const IDAC_DISPOSITION_KEYS = IDAC_DISPOSITIONS.map((d) => d.key);

export const IDAC_DISPOSITION_FILTER_OPTIONS = IDAC_DISPOSITIONS.map((d) => d.filterKey);

const BADGE_BY_KEY = Object.fromEntries(
  IDAC_DISPOSITIONS.flatMap((d) => [
    [d.key, d.badgeClass],
    [d.label, d.badgeClass],
    [d.filterKey, d.badgeClass],
  ])
);

/** Badge classes for raw disposition strings (incl. Futwork aliases like Na). */
export function getIdacDispositionBadgeClass(disposition) {
  const raw = String(disposition || "").trim();
  if (!raw) return "border bg-gray-900/30 text-gray-300 border-gray-500/30";
  if (BADGE_BY_KEY[raw]) return BADGE_BY_KEY[raw];
  const lower = raw.toLowerCase();
  if (lower === "na" || lower === "no answer") return BADGE_BY_KEY["No Answer"];
  const match = IDAC_DISPOSITIONS.find(
    (d) =>
      d.key.toLowerCase() === lower ||
      d.label.toLowerCase() === lower ||
      d.filterKey.toLowerCase() === lower
  );
  return match?.badgeClass || "border bg-gray-900/30 text-gray-300 border-gray-500/30";
}

export function normalizeDispositionChartLabel(key) {
  const raw = String(key || "").trim();
  if (!raw) return raw;
  if (raw === "No Answer") return "NA";
  return raw;
}

const BOLNA_CATEGORY_KEYS = ["Attending", "Not Attending", "General"];

function nestedLeaf(extracted, ...path) {
  let node = extracted;
  for (const key of path) {
    if (!node || typeof node !== "object") return null;
    node = node[key];
  }
  return node && typeof node === "object" ? node : null;
}

function namedLeaf(extracted, leafName) {
  for (const category of BOLNA_CATEGORY_KEYS) {
    const node = nestedLeaf(extracted, category, leafName);
    if (node) return node;
  }
  for (const group of Object.values(extracted || {})) {
    if (group && typeof group === "object" && group[leafName] && typeof group[leafName] === "object") {
      return group[leafName];
    }
  }
  return null;
}

function leafConfidence(node) {
  const n = Number(node?.confidence);
  return Number.isFinite(n) ? n : 0;
}

/** Resolve Attending / Not Attending from call.disposition or Bolna extracted_data. */
export function resolveCallDisposition(call) {
  const direct = String(call?.disposition || "").trim();
  if (direct) return direct;
  const extracted = call?.extracted_data || call?.extractedData;
  if (!extracted || typeof extracted !== "object") return "";

  const att = namedLeaf(extracted, "Attending");
  const natt = namedLeaf(extracted, "Not Attending");
  const attConf = leafConfidence(att);
  const nattConf = leafConfidence(natt);
  if (attConf >= 0.5 || nattConf >= 0.5) {
    return attConf >= nattConf ? "Attending" : "Not Attending";
  }

  const summary = String(
    nestedLeaf(extracted, "General", "Call Summary")?.subjective || ""
  ).toLowerCase();
  if (!summary) return "";
  if (
    ["will not attend", "not attending", "not interested", "declined", "said no"].some((h) =>
      summary.includes(h)
    )
  ) {
    return "Not Attending";
  }
  if (
    [
      "expressed interest in attending",
      "confirmed attendance",
      "will attend",
      "agreed to attend",
      "user expressed interest",
      "user confirmed",
    ].some((h) => summary.includes(h))
  ) {
    return "Attending";
  }
  return "";
}
