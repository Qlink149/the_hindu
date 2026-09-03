import React, { useState, useEffect, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../lib/api";
import {
  mapDispositionBreakdown,
  parseProjectsPayload,
  buildStatsParams,
  buildAICallingDrillParams,
  formatDashboardNumber,
} from "../lib/adapters/dashboardAdapter";
import { DashboardSkeleton } from "../components/feedback/Skeletons";
import { LoadingOverlay, FetchError } from "../components/loading";
import {
  Users,
  Crown,
  Flame,
  CheckCircle,
  Calendar,
  ChevronDown,
  Info,
  Building,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { BRAND_COLORS } from "../components/charts/brandChartTheme";
import { Button } from "../components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../components/ui/dropdown-menu";
import { Calendar as CalendarUI } from "../components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "../components/ui/popover";
import {
  Tooltip as TooltipUI,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../components/ui/tooltip";
import { isFeatureLocked, SHOW_PROJECT_DISTRIBUTION, navigateToVirtualCustomer } from "../lib/featureAccess";
import AgentSelect from "../components/shared/AgentSelect";
import { useCallingAgents } from "../hooks/useCallingAgents";

const LEAD_CRITERIA = {
  attending: {
    title: "Attending Criteria",
    rules: [
      "Matches: Area only, Timeline only, or Area + Timeline",
    ],
  },
  not_attending: {
    title: "Not Attending Criteria",
    rules: [
      "Matches: No match (No Budget, Area, or Timeline match)",
    ],
  },
  hot: {
    title: "Hot Lead Criteria",
    rules: [
      "Matches: (Budget + Area) OR (Budget + Timeline)",
    ],
  },
  qualified: {
    title: "Qualified Lead Criteria",
    rules: [
      "Matches: Budget + Area + Timeline",
    ],
  },
  warm: {
    title: "Warm Lead Criteria",
    rules: [
      "Matches: ONLY Budget",
    ],
  },
};

const LeadCriteriaTooltip = ({ type }) => {
  const criteria = LEAD_CRITERIA[type];
  if (!criteria) return null;
  return (
    <TooltipProvider>
      <TooltipUI>
        <TooltipTrigger asChild>
          <button type="button" className="ml-2 text-[var(--executive-text-muted)] transition-colors hover:text-[var(--executive-accent)]">
            <Info size={16} />
          </button>
        </TooltipTrigger>
        <TooltipContent side="right" className="max-w-xs border-[rgb(var(--navy-rgb)/0.09)] bg-white p-4 text-[var(--executive-text-strong)]">
          <p className="mb-2 font-medium text-[var(--executive-accent)]">{criteria.title}</p>
          <ul className="space-y-1">
            {criteria.rules.map((rule, idx) => (
              <li key={idx} className="text-[#A1A1AA] text-xs flex items-start gap-2">
                <span className="text-[#C5A059] mt-0.5">•</span>
                {rule}
              </li>
            ))}
          </ul>
        </TooltipContent>
      </TooltipUI>
    </TooltipProvider>
  );
};

const DashboardPage = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [projectList, setProjectList] = useState([]);
  const [projectMeta, setProjectMeta] = useState(null);
  const [salesOwners, setSalesOwners] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [timeFilter, setTimeFilter] = useState("all");
  const [dateRange, setDateRange] = useState(null);
  const [statsAgentId, setStatsAgentId] = useState("all");
  const {
    agents,
    loading: agentsLoading,
  } = useCallingAgents();

  const timeFilters = [
    { value: "7", label: "7 Days" },
    { value: "15", label: "15 Days" },
    { value: "30", label: "30 Days" },
    { value: "all", label: "All Time" },
    { value: "custom", label: "Custom Range" },
  ];

  const fetchData = useCallback(async () => {
    if (agentsLoading) return;
    setLoading(true);
    setError(null);
    try {
      const params = buildStatsParams(timeFilter, "all", dateRange, statsAgentId);
      const [statsRes, projectsRes, ownersRes] = await Promise.all([
        api.get("/dashboard/stats", { params }),
        api.get("/dashboard/projects"),
        api.get("/dashboard/sales-owners", { params }).catch(() => ({ data: [] })),
      ]);
      setStats(statsRes.data);
      const { projects, meta } = parseProjectsPayload(projectsRes.data);
      setProjectList(projects);
      setProjectMeta(meta);
      setSalesOwners(ownersRes.data || []);
      setHasLoadedOnce(true);
    } catch (err) {
      console.error("Failed to fetch dashboard:", err);
      toast.error("Failed to load dashboard");
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [timeFilter, dateRange, statsAgentId, agentsLoading]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleProjectClick = (projectName) => {
    if (projectName === "__none__") {
      navigateToVirtualCustomer(
        navigate,
        "/virtual-customer?project=__none__&futwork_sync_status=all"
      );
      return;
    }
    navigateToVirtualCustomer(
      navigate,
      `/virtual-customer?project=${encodeURIComponent(projectName)}&futwork_sync_status=all`
    );
  };

  const dispositionData = useMemo(() => mapDispositionBreakdown(stats), [stats]);
  const displayProjects = useMemo(() => {
    const otherProjectCard =
      projectMeta && projectMeta.otherCount > 0
        ? { name: "__none__", label: "Other / No project", count: projectMeta.otherCount }
        : null;
    return otherProjectCard
      ? [
        ...projectList,
        {
          name: otherProjectCard.name,
          count: otherProjectCard.count,
          label: otherProjectCard.label,
        },
      ]
      : projectList;
  }, [projectList, projectMeta]);

  const handleDispositionClick = (entry) => {
    const disposition = entry?.filterKey || entry?.name;
    if (!disposition || disposition === "No Disposition") return;
    const params = buildAICallingDrillParams(
      disposition,
      timeFilter,
      "all",
      dateRange,
      statsAgentId
    );
    navigate(`/ai-calling?${params.toString()}`);
  };

  const handleDispositionDrill = (disposition) => {
    if (!disposition) return;
    const params = buildAICallingDrillParams(
      disposition,
      timeFilter,
      "all",
      dateRange,
      statsAgentId
    );
    navigate(`/ai-calling?${params.toString()}`);
  };

  const dispositionTileProps = (disposition) => ({
    role: "button",
    tabIndex: 0,
    onClick: () => handleDispositionDrill(disposition),
    onKeyDown: (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleDispositionDrill(disposition);
      }
    },
  });

  const statTileInteractive =
    "card-hover cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#C5A059]/50";

  const isInitialLoading = loading && !hasLoadedOnce;
  const isRefetching = loading && hasLoadedOnce;
  const displayStat = (key) => {
    if (!stats) return "—";
    const v = stats[key];
    return v != null ? v : 0;
  };

  return (
    <motion.div className="space-y-8">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="flex flex-wrap items-center gap-3"
      >
        <AgentSelect
          value={statsAgentId}
          onValueChange={(agentId) => setStatsAgentId(agentId || "all")}
          agents={agents}
          loading={agentsLoading}
          allowAll
          placeholder="All agents"
        />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              className="bg-[#1A1A1A] border-white/10 text-white hover:bg-white/5 hover:text-[#C5A059]"
              data-testid="time-filter-dropdown"
            >
              <Calendar size={16} className="mr-2" />
              {timeFilters.find((f) => f.value === timeFilter)?.label || "All Time"}
              <ChevronDown size={16} className="ml-2" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="bg-[#1A1A1A] border-white/10">
            {timeFilters.map((filter) => (
              <DropdownMenuItem
                key={filter.value}
                onClick={() => setTimeFilter(filter.value)}
                className="text-white hover:bg-[#C5A059]/10 hover:text-[#C5A059] cursor-pointer"
              >
                {filter.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        {timeFilter === "custom" && (
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" className="bg-[#1A1A1A] border-white/10 text-white hover:bg-white/5">
                Select Date Range
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0 bg-[#1A1A1A] border-white/10">
              <CalendarUI
                mode="range"
                selected={dateRange}
                onSelect={setDateRange}
                className="bg-[#1A1A1A] text-white"
              />
            </PopoverContent>
          </Popover>
        )}
      </motion.div>

      {error && !stats ? (
        <FetchError
          title="Dashboard unavailable"
          message="We couldn't load your dashboard data. Check your connection and try again."
          onRetry={fetchData}
        />
      ) : (
        <div className="relative space-y-8">
          {isInitialLoading ? (
            <DashboardSkeleton />
          ) : (
            <div className="space-y-8">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="grid grid-cols-1 md:grid-cols-2 gap-4"
              >
                <div
                  className={`glass-card rounded-lg p-6 border-l-4 border-blue-500 ${statTileInteractive}`}
                  data-testid="attending-tile"
                  {...dispositionTileProps("Attending")}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center">
                        <p className="text-[#A1A1AA] text-sm uppercase tracking-wider">Attending</p>
                      </div>
                      <p className="font-serif text-4xl text-white mt-2 tabular-nums truncate" title={String(displayStat("attending_calls"))}>{displayStat("attending_calls")}</p>
                      <p className="text-blue-400 text-sm mt-1">Confirmed attendance</p>
                    </div>
                    <div className="w-14 h-14 rounded-full bg-blue-500/20 flex items-center justify-center">
                      <CheckCircle className="text-blue-500" size={28} />
                    </div>
                  </div>
                </div>

                <div
                  className={`glass-card rounded-lg p-6 border-l-4 border-orange-500 ${statTileInteractive}`}
                  data-testid="not-attending-tile"
                  {...dispositionTileProps("Not Attending")}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center">
                        <p className="text-[#A1A1AA] text-sm uppercase tracking-wider">Not Attending</p>
                      </div>
                      <p className="font-serif text-4xl text-white mt-2 tabular-nums truncate" title={String(displayStat("not_attending_calls"))}>{displayStat("not_attending_calls")}</p>
                      <p className="text-orange-400 text-sm mt-1">Declined or unavailable</p>
                    </div>
                    <div className="w-14 h-14 rounded-full bg-orange-500/20 flex items-center justify-center">
                      <Flame className="text-orange-500" size={28} />
                    </div>
                  </div>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
              >
                <div
                  className="glass-card rounded-lg p-6"
                  data-testid="total-leads-tile"
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-12 h-12 rounded-lg bg-[#C5A059]/20 flex items-center justify-center">
                      <Users className="text-[#C5A059]" size={24} />
                    </div>
                  </div>
                  <p className="text-[#A1A1AA] text-sm">Total Leads</p>
                  <p className="font-serif text-3xl text-white mt-1 tabular-nums truncate" title={String(displayStat("total_leads"))}>{displayStat("total_leads")}</p>
                </div>

                <div
                  className="glass-card rounded-lg p-6"
                  data-testid="total-min-tile"
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-12 h-12 rounded-lg bg-orange-500/20 flex items-center justify-center">
                      <Crown className="text-orange-500" size={24} />
                    </div>
                  </div>
                  <p className="text-[#A1A1AA] text-sm">Total Min</p>
                  <p className="font-serif text-3xl text-white mt-1 tabular-nums truncate" title={String(displayStat("total_billed_minutes"))}>{displayStat("total_billed_minutes")}</p>
                </div>

                <div
                  className="glass-card rounded-lg p-6"
                  data-testid="total-calls-tile"
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-12 h-12 rounded-lg bg-red-500/20 flex items-center justify-center">
                      <Users className="text-red-500" size={24} />
                    </div>
                  </div>
                  <p className="text-[#A1A1AA] text-sm">Total Calls</p>
                  <p className="font-serif text-3xl text-white mt-1 tabular-nums truncate" title={String(displayStat("total_calls"))}>{displayStat("total_calls")}</p>
                </div>
              </motion.div>

              <div className="grid grid-cols-1 gap-6">
                {dispositionData.length > 0 ? (
                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.3 }}
                    className="glass-card rounded-lg p-6"
                    data-testid="disposition-chart"
                  >
                    <h3 className="font-serif text-xl text-white mb-2">Disposition Distribution</h3>
                    <p className="text-[#737373] text-xs mb-4">
                      Calling Engine call outcomes · Click a slice to view matching calls in AI Calling
                    </p>
                    <div className="flex items-center justify-center">
                      <ResponsiveContainer width="100%" height={280}>
                        <PieChart>
                          <Pie
                            data={dispositionData}
                            cx="50%"
                            cy="50%"
                            innerRadius={55}
                            outerRadius={95}
                            paddingAngle={4}
                            dataKey="value"
                            nameKey="name"
                            style={{ cursor: "pointer" }}
                            onClick={(_, index) => handleDispositionClick(dispositionData[index])}
                          >
                            {dispositionData.map((entry, index) => (
                              <Cell key={`disp-cell-${index}`} fill={entry.color} />
                            ))}
                          </Pie>
                          <Tooltip
                            content={({ active, payload }) => {
                              if (active && payload?.length) {
                                return (
                                  <div className="rounded-xl border border-[rgb(var(--navy-rgb)/0.09)] bg-white p-3 shadow-xl">
                                    <p className="font-medium text-[var(--executive-accent)]">{payload[0].name}</p>
                                    <p className="text-[var(--executive-text-strong)]">{payload[0].value} calls</p>
                                  </div>
                                );
                              }
                              return null;
                            }}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="flex flex-wrap justify-center gap-x-4 gap-y-2 mt-4">
                      {dispositionData.map((item) => (
                        <div key={item.name} className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
                          <span className="text-[#A1A1AA] text-xs whitespace-nowrap">
                            {item.name} ({item.value})
                          </span>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                ) : (
                  <div className="glass-card rounded-lg p-6 flex items-center justify-center text-[#52525B]">
                    No disposition data available
                  </div>
                )}
              </div>


              {SHOW_PROJECT_DISTRIBUTION && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
                className="glass-card rounded-lg p-6"
                data-testid="project-distribution"
              >
                <h3 className="font-serif text-xl text-white mb-2">Project Interest Distribution</h3>
                <p className="text-[#52525B] text-sm mb-4">
                  Click on a project to view its leads
                  {projectMeta ? (
                    <>
                      {" "}
                      · Top 10 shown · {formatDashboardNumber(projectMeta.withProject)} with project ·{" "}
                      {formatDashboardNumber(projectMeta.withoutProject)} without ·{" "}
                      {formatDashboardNumber(projectMeta.totalLeads)} total
                    </>
                  ) : null}
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {displayProjects.map((project) => (
                    <div
                      key={project.name}
                      role="button"
                      tabIndex={0}
                      onClick={() => handleProjectClick(project.name)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleProjectClick(project.name);
                      }}
                      className="p-4 rounded-lg bg-[#1A1A1A] border border-white/10 hover:border-[#C5A059]/50 transition-all cursor-pointer group overflow-hidden relative"
                      data-testid={`project-card-${project.name}`}
                    >
                      <div className="relative z-10">
                        <div className="flex items-center gap-2 mb-3 min-w-0">
                          <Building className="text-[#C5A059] flex-shrink-0" size={18} />
                          <span className="text-white font-medium group-hover:text-[#C5A059] transition-colors truncate" title={project.label || project.name}>
                            {project.label || project.name}
                          </span>
                        </div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[#52525B] text-sm">Leads</span>
                          <span className="text-[#C5A059] font-serif text-xl">{project.count}</span>
                        </div>
                        <div className="h-2 bg-black/50 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{
                              background: `linear-gradient(135deg, ${BRAND_COLORS.soft}, ${BRAND_COLORS.primary})`,
                              width: `${(project.count / Math.max(...displayProjects.map((p) => p.count), 1)) * 100}%`,
                            }}
                          />
                        </div>
                        <p className="text-[#52525B] text-xs mt-2 group-hover:text-[#A1A1AA] transition-colors">
                          Click to view leads →
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
              )}
            </div>
          )}
          <LoadingOverlay show={isRefetching} />
        </div>
      )}
    </motion.div>
  );
};

export default DashboardPage;
