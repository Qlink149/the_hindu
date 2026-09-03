import { useMemo } from "react";
import { Bot } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";

/**
 * Placeholder + dropdown to pick a Bolna voice agent, or All agents on viewing surfaces.
 */
export default function AgentSelect({
  value,
  onValueChange,
  agents = [],
  loading = false,
  saving = false,
  allowAll = false,
  placeholder = "Select agent",
  className = "",
  triggerClassName = "w-[240px] brand-select",
  showIcon = true,
  testId = "agent-select",
}) {
  const options = useMemo(() => (Array.isArray(agents) ? agents : []), [agents]);

  const selectValue = value || (allowAll ? "all" : undefined);
  const disabled = loading || saving || (!allowAll && options.length === 0);

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {showIcon ? <Bot className="h-4 w-4 shrink-0 text-[#C5A059]" /> : null}
      <Select
        value={selectValue}
        onValueChange={onValueChange}
        disabled={disabled}
      >
        <SelectTrigger
          className={triggerClassName}
          data-testid={testId}
        >
          <SelectValue placeholder={loading ? "Loading agents…" : placeholder} />
        </SelectTrigger>
        <SelectContent className="bg-white border-[rgb(var(--navy-rgb)/0.09)] text-[var(--executive-text-strong)]">
          {allowAll ? <SelectItem value="all">All agents</SelectItem> : null}
          {options.map((agent) => (
            <SelectItem key={agent.id} value={agent.id}>
              {agent.name}
              {agent.status && agent.status !== "processed" ? ` (${agent.status})` : ""}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
