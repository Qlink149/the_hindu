import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { agentsAPI, campaignsAPI } from "../lib/api";

/**
 * Loads Bolna agents and the campaign's currently selected calling agent.
 * Selecting an agent persists it on the campaign so Dashboard, Campaigns,
 * and AI Calling all dial with the same voice agent.
 */
export function useCallingAgents() {
  const [agents, setAgents] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [agentName, setAgentName] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [agentsRes, campaignRes] = await Promise.allSettled([
        agentsAPI.list(),
        campaignsAPI.getCurrent(),
      ]);
      const list = agentsRes.status === "fulfilled" ? agentsRes.value.data : [];
      setAgents(Array.isArray(list) ? list : []);
      if (campaignRes.status === "fulfilled") {
        const campaign = campaignRes.value.data || {};
        setSelectedId(campaign.agent_id || "");
        setAgentName(campaign.agent_name || "");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [agentsRes, campaignRes] = await Promise.allSettled([
          agentsAPI.list(),
          campaignsAPI.getCurrent(),
        ]);
        if (cancelled) return;
        const list = agentsRes.status === "fulfilled" ? agentsRes.value.data : [];
        setAgents(Array.isArray(list) ? list : []);
        if (campaignRes.status === "fulfilled") {
          const campaign = campaignRes.value.data || {};
          setSelectedId(campaign.agent_id || "");
          setAgentName(campaign.agent_name || "");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const options = useMemo(() => {
    const list = Array.isArray(agents) ? [...agents] : [];
    if (selectedId && !list.some((agent) => agent.id === selectedId)) {
      list.unshift({
        id: selectedId,
        name: agentName || "Current agent",
        status: "",
      });
    }
    return list;
  }, [agents, selectedId, agentName]);

  const selectAgent = useCallback(async (agentId) => {
    if (!agentId || agentId === "all") {
      setSelectedId(agentId || "");
      return null;
    }
    setSaving(true);
    try {
      const res = await campaignsAPI.setAgent(agentId);
      const updated = res.data || {};
      setSelectedId(updated.agent_id || agentId);
      setAgentName(updated.agent_name || "");
      toast.success(`Calling agent set to ${updated.agent_name || agentId}`);
      return updated;
    } catch (error) {
      toast.error(error.response?.data?.detail || "Could not update calling agent");
      return null;
    } finally {
      setSaving(false);
    }
  }, []);

  return {
    agents: options,
    selectedId,
    agentName,
    loading,
    saving,
    selectAgent,
    refresh,
  };
}
