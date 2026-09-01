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
 * Placeholder + dropdown to pick which Bolna voice agent places outbound calls.
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
  triggerClassName = "w-[240px] bg-[#1A1A1A] border-white/10 text-white",
  showIcon = true,
  testId = "agent-select",
}) {
  const options = useMemo(() => {
    const list = Array.isArray(agents) ? [...agents] : [];
    if (value && value !== "all" && !list.some((agent) => agent.id === value)) {
      list.unshift({ id: value, name: "Current agent", status: "" });
    }
    return list;
  }, [agents, value]);

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
        <SelectContent className="bg-[#1A1A1A] border-white/10 text-white">
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
