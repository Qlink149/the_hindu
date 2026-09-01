import React from "react";

const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-[rgb(var(--navy-rgb)/0.09)] bg-white p-3 shadow-xl">
      <p className="font-medium text-[var(--executive-accent)]">{label || payload[0].payload?.name}</p>
      <p className="text-[var(--executive-text-strong)]">{payload[0].value} leads</p>
    </div>
  );
};

export default ChartTooltip;
