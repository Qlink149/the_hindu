import React from "react";

export const BRAND_COLORS = {
  primary: "#2563A8",
  deep: "#1B4F8C",
  soft: "#4A7AB5",
  lavender: "#8AA9D1",
  mist: "#E8EEF5",
  midnight: "#0D2A4A",
  navy: "#0A1628",
  success: "#22b07d",
  danger: "#d25f86",
  warning: "#f59e0b",
};

export const BRAND_SERIES_COLORS = [
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

export const BRAND_CHART_TONES = {
  primary: ["#4A7AB5", "#1B4F8C"],
  secondary: ["#8AA9D1", "#2563A8"],
  deep: ["#2563A8", "#0D2A4A"],
  soft: ["#E8EEF5", "#4A7AB5"],
  success: ["#22b07d", "#0f7a55"],
  danger: ["#d25f86", "#a83060"],
  warning: ["#f59e0b", "#b45309"],
};

export const BRAND_CHART_AXIS = "#5C6570";
export const BRAND_CHART_GRID = "rgba(10, 22, 40, 0.12)";
export const BRAND_CHART_CURSOR = "rgba(27, 79, 140, 0.14)";

export const BrandChartGradient = ({ id, variant = "primary", direction = "vertical" }) => {
  const [from, to] = BRAND_CHART_TONES[variant] ?? BRAND_CHART_TONES.primary;
  const axis =
    direction === "horizontal"
      ? { x1: "0", y1: "0", x2: "1", y2: "0" }
      : { x1: "0", y1: "0", x2: "0", y2: "1" };

  return (
    <linearGradient id={id} {...axis}>
      <stop offset="0%" stopColor={from} stopOpacity={1} />
      <stop offset="100%" stopColor={to} stopOpacity={1} />
    </linearGradient>
  );
};

export const BrandAreaGradient = ({ id, variant = "primary" }) => {
  const [from] = BRAND_CHART_TONES[variant] ?? BRAND_CHART_TONES.primary;
  return (
    <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%" stopColor={from} stopOpacity={0.28} />
      <stop offset="95%" stopColor={from} stopOpacity={0.03} />
    </linearGradient>
  );
};

export const brandDonutSegments = (pct, total = 100) => {
  const rest = total - pct;
  return `conic-gradient(${BRAND_COLORS.primary} 0 ${pct}%, ${BRAND_COLORS.lavender} ${pct}% ${
    pct + rest * 0.48
  }%, ${BRAND_COLORS.mist} ${pct + rest * 0.48}% 100%)`;
};
