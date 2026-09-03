import { useEffect, useState } from "react";
import { PhoneCall, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { campaignsAPI } from "../../lib/api";
import AgentSelect from "./AgentSelect";
import { useCallingAgents } from "../../hooks/useCallingAgents";

/**
 * Places one outbound Bolna call from the agent chosen in this control.
 * Does not change the campaign's default calling agent.
 */
export default function TestCallControls({ disabled = false, compact = false }) {
  const [phone, setPhone] = useState("");
  const [calling, setCalling] = useState(false);
  const [testAgentId, setTestAgentId] = useState("");
  const { agents, selectedId, loading: agentsLoading } = useCallingAgents();

  useEffect(() => {
    if (testAgentId || agentsLoading) return;
    setTestAgentId(
      (selectedId && selectedId !== "all" ? selectedId : "") || agents[0]?.id || ""
    );
  }, [agentsLoading, selectedId, agents, testAgentId]);

  const handleCall = async () => {
    const digits = String(phone || "").replace(/\D/g, "").slice(-10);
    if (digits.length !== 10) {
      toast.error("Enter a valid 10-digit mobile number");
      return;
    }
    if (!testAgentId) {
      toast.error("Choose which agent should place the test call");
      return;
    }
    setCalling(true);
    try {
      const res = await campaignsAPI.placeTestCall(phone, testAgentId);
      const executionId = res.data?.execution_id;
      const agentName = agents.find((a) => a.id === testAgentId)?.name || "agent";
      toast.success(
        executionId
          ? `${agentName} queued (${executionId})`
          : `Call queued with ${agentName}`
      );
    } catch (error) {
      toast.error(error.response?.data?.detail || "Could not place the call");
    } finally {
      setCalling(false);
    }
  };

  return (
    <div
      className={
        compact
          ? "flex flex-wrap items-center gap-2"
          : "flex flex-col gap-2 sm:flex-row sm:items-center"
      }
    >
      <span className="text-xs text-[#A3A3A3] whitespace-nowrap">Test with</span>
      <AgentSelect
        value={testAgentId}
        onValueChange={setTestAgentId}
        agents={agents}
        loading={agentsLoading}
        placeholder="Choose agent"
        triggerClassName="w-full sm:w-[240px] h-9 bg-[#1A1A1A] border-white/10 text-white"
        showIcon={false}
        testId="test-call-agent-select"
      />
      <Input
        type="tel"
        inputMode="numeric"
        autoComplete="tel"
        placeholder="10-digit mobile number"
        value={phone}
        onChange={(event) => setPhone(event.target.value)}
        disabled={disabled || calling}
        className="h-9 w-full sm:w-52 bg-[#1A1A1A] border-white/10 text-white placeholder:text-[#737373]"
        data-testid="test-call-phone"
      />
      <Button
        type="button"
        onClick={handleCall}
        disabled={disabled || calling || agentsLoading || !testAgentId}
        className="bg-[#C5A059] text-black hover:bg-[#E5C585]"
        data-testid="test-call-submit"
      >
        {calling ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <PhoneCall className="mr-2 h-4 w-4" />
        )}
        {calling ? "Calling…" : "Place test call"}
      </Button>
    </div>
  );
}
