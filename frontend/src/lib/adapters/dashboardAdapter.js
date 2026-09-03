export const REGIONAL_COLORS = [
  { bg: "rgba(37, 99, 168, 0.13)", border: "rgba(37, 99, 168, 0.30)", text: "#2563A8" },
  { bg: "rgba(74, 122, 181, 0.14)", border: "rgba(74, 122, 181, 0.34)", text: "#4A7AB5" },
  { bg: "rgba(27, 79, 140, 0.12)", border: "rgba(27, 79, 140, 0.28)", text: "#1B4F8C" },
  { bg: "rgba(138, 169, 209, 0.20)", border: "rgba(138, 169, 209, 0.40)", text: "#2563A8" },
  { bg: "rgba(34, 176, 125, 0.14)", border: "rgba(34, 176, 125, 0.32)", text: "#22b07d" },
  { bg: "rgba(210, 95, 134, 0.13)", border: "rgba(210, 95, 134, 0.30)", text: "#d25f86" },
  { bg: "rgba(245, 158, 11, 0.14)", border: "rgba(245, 158, 11, 0.34)", text: "#f59e0b" },
  { bg: "rgba(232, 238, 245, 0.68)", border: "rgba(37, 99, 168, 0.20)", text: "#0D2A4A" },
];

const CHART_COLORS = [
  "#2563A8",
  "#4A7AB5",
  "#1B4F8C",
  "#8AA9D1",
  "#0D2A4A",
  "#E8EEF5",
  "#22b07d",
  "#d25f86",
  "#f59e0b",
];

import { mapLeadSourceLabel } from "../brandLabels";
import {
  IDAC_DISPOSITIONS,
  normalizeDispositionChartLabel,
} from "../idacDispositions";

export { mapLeadSourceLabel };

export function mapLeadSources(stats) {
  if (!stats?.lead_source_stats) return [];
  return Object.entries(stats.lead_source_stats)
    .map(([name, count]) => ({
      name: mapLeadSourceLabel(name),
      count: Number(count) || 0,
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 12);
}

export function mapStatusBreakdown(stats) {
  if (!stats?.lead_status_stats) return [];
  const colorByName = {
    Attending: "#2563A8",
    "Not Attending": "#d25f86",
    Warm: "#F59E0B",
    Hot: "#4A7AB5",
    Qualified: "#22b07d",
  };
  const order = ["Qualified", "Hot", "Warm", "Attending", "Not Attending"];
  const entries = Object.entries(stats.lead_status_stats)
    .filter(([, v]) => Number(v) > 0)
    .map(([name, value]) => ({
      name,
      value: Number(value) || 0,
      color: colorByName[name] || CHART_COLORS[0],
    }));
  entries.sort((a, b) => {
    const ai = order.indexOf(a.name);
    const bi = order.indexOf(b.name);
    if (ai === -1 && bi === -1) return b.value - a.value;
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });
  return entries;
}

export function mapDispositionBreakdown(stats) {
  if (!stats?.disposition_stats) return [];
  const counts = stats.disposition_stats;
  const colorByKey = Object.fromEntries(IDAC_DISPOSITIONS.map((d) => [d.key, d.color]));

  const primary = IDAC_DISPOSITIONS.map((d) => ({
    name: normalizeDispositionChartLabel(d.key),
    value: Number(counts[d.key] ?? 0) || 0,
    color: d.color,
    filterKey: d.filterKey,
  })).filter((row) => row.value > 0);

  const known = new Set(IDAC_DISPOSITIONS.map((d) => d.key));
  const extras = Object.entries(counts)
    .filter(([name, v]) => !known.has(name) && Number(v) > 0)
    .map(([name, value], idx) => ({
      name: normalizeDispositionChartLabel(name),
      value: Number(value) || 0,
      color: CHART_COLORS[idx % CHART_COLORS.length],
      filterKey: name,
    }))
    .sort((a, b) => b.value - a.value);

  return [...primary, ...extras];
}

export function mapAvgDurationBreakdown(stats) {
  if (!stats?.disposition_avg_duration) return [];

  return IDAC_DISPOSITIONS.map((d, idx) => ({
    name: d.label === "NA" ? "NA" : `Avg ${d.label}`,
    value: Math.round(Number(stats.disposition_avg_duration[d.key] || 0)),
    color: d.color || CHART_COLORS[idx % CHART_COLORS.length],
  }));
}

const SKIP_PROJECT_NAMES = new Set(["", "Unknown", "Profiling in Progress"]);

function coerceProjectName(raw) {
  if (raw == null) return "";
  if (typeof raw === "string" || typeof raw === "number") return String(raw).trim();
  if (typeof raw === "object" && raw.name != null) {
    return coerceProjectName(raw.name);
  }
  return "";
}

export function mapProjects(projectList) {
  if (!Array.isArray(projectList)) return [];
  return projectList
    .map((p) => {
      if (typeof p === "string") {
        const name = p.trim();
        return { name, count: 0 };
      }
      const name = coerceProjectName(p?.name ?? p?._id);
      const count = Number(p?.count) || 0;
      return { name, count };
    })
    .filter((p) => p.name && !SKIP_PROJECT_NAMES.has(p.name));
}

/** Normalize /dashboard/projects payload (array legacy or structured object). */
export function parseProjectsPayload(data) {
  if (Array.isArray(data)) {
    return {
      projects: mapProjects(data),
      meta: null,
    };
  }
  if (data && Array.isArray(data.projects)) {
    return {
      projects: mapProjects(data.projects),
      meta: {
        totalLeads: Number(data.total_leads) || 0,
        withProject: Number(data.with_project) || 0,
        otherCount: Number(data.other_count) || 0,
        withoutProject: Number(data.without_project) || 0,
      },
    };
  }
  return { projects: [], meta: null };
}

/** Build AI Calling URL params for disposition chart drill-down. */
export function buildAICallingDrillParams(
  disposition,
  timeFilter,
  projectFilter,
  dateRange,
  agentId
) {
  const params = new URLSearchParams();
  if (disposition) params.set("disposition", disposition);
  if (agentId && agentId !== "all") params.set("agent_id", agentId);
  const statsParams = buildStatsParams(timeFilter, projectFilter, dateRange);
  if (statsParams.start_date) params.set("start_date", statsParams.start_date);
  if (statsParams.end_date) params.set("end_date", statsParams.end_date);
  return params;
}

/** Build Virtual Customer URL params for dashboard KPI drill-down. */
export function buildVirtualDrillParams(bucket, timeFilter, projectFilter, dateRange) {
  const params = new URLSearchParams();
  params.set("futwork_sync_status", "all");
  const statsParams = buildStatsParams(timeFilter, projectFilter, dateRange);
  if (statsParams.project) params.set("project", statsParams.project);
  if (statsParams.days != null) params.set("days", String(statsParams.days));
  if (statsParams.start_date) params.set("start_date", statsParams.start_date);
  if (statsParams.end_date) params.set("end_date", statsParams.end_date);
  if (bucket) params.set("dashboard_bucket", bucket);
  return params;
}

export const DASHBOARD_BUCKET_LABELS = {
  attending: "Attending",
  not_attending: "Not Attending",
  cold: "Attending",
  dormant: "Not Attending",
  hot: "Hot Leads",
  qualified: "Qualified Leads",
  warm: "Warm Leads",
};

export function buildStatsParams(timeFilter, projectFilter, dateRange, agentId) {
  const params = {};
  if (projectFilter && projectFilter !== "all") {
    params.project =
      typeof projectFilter === "string" ? projectFilter : coerceProjectName(projectFilter);
  }
  if (timeFilter === "7") params.days = 7;
  else if (timeFilter === "15") params.days = 15;
  else if (timeFilter === "30") params.days = 30;
  else if (timeFilter === "custom" && dateRange?.from) {
    const from = dateRange.from;
    const to = dateRange.to || dateRange.from;
    params.start_date = from.toISOString().slice(0, 10);
    params.end_date = to.toISOString().slice(0, 10);
  }
  if (agentId && agentId !== "all") {
    params.agent_id = agentId;
  }
  return params;
}

export function formatDashboardNumber(num) {
  const n = Number(num);
  if (!Number.isFinite(n)) return "0";
  return n.toLocaleString("en-IN");
}
