"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  AlertTriangle,
  Calendar,
  RefreshCw,
  Search,
  Filter,
  BarChart3,
  CheckCircle,
  RotateCcw,
  SlidersHorizontal,
  ArrowRight,
  ChevronRight,
  Radio,
} from "lucide-react";
import {
  Anomaly,
  InvestigationResponse,
  MetricMeta,
} from "../lib/types";
import {
  fetchAnomalies,
  fetchMetrics,
  fetchAnomalyInvestigation,
  triggerInvestigation,
  formatMetricValue,
  formatDelta,
} from "../lib/api";
import Header, { ActiveView } from "../components/Header";
import ExecutiveOverview from "../components/ExecutiveOverview";
import InvestigationWorkspace from "../components/InvestigationWorkspace";
import SystemArchitectureGuide from "../components/SystemArchitectureGuide";

export default function DashboardPage() {
  // Navigation View Mode ("feed" | "overview" | "guide")
  const [activeView, setActiveView] = useState<ActiveView>("feed");

  // State
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [metrics, setMetrics] = useState<MetricMeta[]>([]);
  const [selectedAnomalyId, setSelectedAnomalyId] = useState<number | null>(null);
  const [investigationData, setInvestigationData] = useState<InvestigationResponse | null>(null);
  const [isWorkspaceExpanded, setIsWorkspaceExpanded] = useState<boolean>(false);

  // Filters & sorting
  const [selectedMetric, setSelectedMetric] = useState<string>("all");
  const [selectedSeverity, setSelectedSeverity] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [sortBy, setSortBy] = useState<"z_score_desc" | "date_desc" | "date_asc">("z_score_desc");

  // Loading & error states
  const [loadingFeed, setLoadingFeed] = useState<boolean>(true);
  const [loadingInvestigation, setLoadingInvestigation] = useState<boolean>(false);
  const [investigating, setInvestigating] = useState<boolean>(false);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [investigationError, setInvestigationError] = useState<string | null>(null);

  // Load initial data
  const loadInitialFeed = async () => {
    try {
      setLoadingFeed(true);
      setFeedError(null);
      const [metricData, anomalyData] = await Promise.all([
        fetchMetrics().catch(() => []),
        fetchAnomalies({ limit: 100 }),
      ]);
      setMetrics(metricData);
      setAnomalies(anomalyData.items);

      // Auto-select the top anomaly if available and none currently selected
      if (anomalyData.items.length > 0 && !selectedAnomalyId) {
        setSelectedAnomalyId(anomalyData.items[0].id);
      }
    } catch (err: any) {
      setFeedError(err.message || "Failed to connect to backend API");
    } finally {
      setLoadingFeed(false);
    }
  };

  useEffect(() => {
    loadInitialFeed();
  }, []);

  // When selected anomaly changes, load its investigation if one exists
  useEffect(() => {
    if (!selectedAnomalyId) {
      setInvestigationData(null);
      return;
    }

    async function loadInvestigation() {
      try {
        setLoadingInvestigation(true);
        setInvestigationError(null);
        const inv = await fetchAnomalyInvestigation(selectedAnomalyId!);
        setInvestigationData(inv);
      } catch (err: any) {
        setInvestigationError(err.message || "Failed to load investigation details");
      } finally {
        setLoadingInvestigation(false);
      }
    }

    loadInvestigation();
  }, [selectedAnomalyId]);

  // Handle triggering live investigation
  const handleRunInvestigation = async () => {
    if (!selectedAnomalyId) return;

    try {
      setInvestigating(true);
      setInvestigationError(null);
      const res = await triggerInvestigation(selectedAnomalyId);
      setInvestigationData(res);

      // Update the has_investigation status in the local state
      setAnomalies((prev) =>
        prev.map((a) =>
          a.id === selectedAnomalyId
            ? { ...a, has_investigation: true, latest_investigation_id: res.investigation.id }
            : a
        )
      );
    } catch (err: any) {
      setInvestigationError(err.message || "Investigation execution failed");
    } finally {
      setInvestigating(false);
    }
  };

  // Switch to anomaly from Overview
  const handleSelectFromOverview = (anomalyId: number) => {
    setSelectedAnomalyId(anomalyId);
    setActiveView("feed");
  };

  // Filter by metric from Overview
  const handleSelectMetricFilter = (metricName: string) => {
    setSelectedMetric(metricName);
    setActiveView("feed");
  };

  // Filtered & sorted anomalies
  const filteredAnomalies = useMemo(() => {
    return anomalies
      .filter((item) => {
        if (selectedMetric !== "all" && item.metric_name !== selectedMetric) {
          return false;
        }
        if (selectedSeverity !== "all" && item.severity !== selectedSeverity) {
          return false;
        }
        if (selectedStatus === "investigated" && !item.has_investigation) {
          return false;
        }
        if (selectedStatus === "open" && item.has_investigation) {
          return false;
        }
        if (searchQuery.trim() !== "") {
          const query = searchQuery.toLowerCase().trim();
          const matchMetric = item.metric_name.toLowerCase().includes(query);
          const matchDisplay = item.metric_display_name.toLowerCase().includes(query);
          const matchDate = item.date.includes(query);
          const matchId = item.id.toString() === query.replace("#", "");
          if (!matchMetric && !matchDisplay && !matchDate && !matchId) {
            return false;
          }
        }
        return true;
      })
      .sort((a, b) => {
        if (sortBy === "z_score_desc") {
          return Math.abs(b.z_score) - Math.abs(a.z_score);
        }
        if (sortBy === "date_desc") {
          return new Date(b.date).getTime() - new Date(a.date).getTime();
        }
        if (sortBy === "date_asc") {
          return new Date(a.date).getTime() - new Date(b.date).getTime();
        }
        return 0;
      });
  }, [anomalies, selectedMetric, selectedSeverity, selectedStatus, searchQuery, sortBy]);

  // Currently selected anomaly object
  const activeAnomaly = useMemo(() => {
    return anomalies.find((a) => a.id === selectedAnomalyId) || null;
  }, [anomalies, selectedAnomalyId]);

  const criticalCount = anomalies.filter((a) => a.severity === "high").length;

  return (
    <div className="space-y-6">
      {/* Top Header with Navigation */}
      <Header
        activeView={activeView}
        setActiveView={setActiveView}
        anomalyCount={anomalies.length}
        criticalCount={criticalCount}
      />

      {/* Main Container Area */}
      <div className="mx-auto max-w-[1600px] px-4 sm:px-6 lg:px-8 pb-12">
        {/* ========================================================================= */}
        {/* VIEW 1: EXECUTIVE OVERVIEW                                                */}
        {/* ========================================================================= */}
        {activeView === "overview" && (
          <ExecutiveOverview
            anomalies={anomalies}
            metrics={metrics}
            loading={loadingFeed}
            onSelectAnomaly={handleSelectFromOverview}
            onSelectMetricFilter={handleSelectMetricFilter}
          />
        )}

        {/* ========================================================================= */}
        {/* VIEW 2: SYSTEM ARCHITECTURE & INTERVIEW GUIDE                             */}
        {/* ========================================================================= */}
        {activeView === "guide" && <SystemArchitectureGuide />}

        {/* ========================================================================= */}
        {/* VIEW 3: SIGNALS WORKSPACE & INVESTIGATION (CORE WORKFLOW)                 */}
        {/* ========================================================================= */}
        {activeView === "feed" && (
          <div className="space-y-6 animate-fadeIn">
            {/* Top Workspace Bar */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-4">
              <div>
                <h1 className="text-xl sm:text-2xl font-bold font-mono tracking-tight text-slate-900 dark:text-white">
                  Signal Investigation Workspace
                </h1>
                <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                  Select any detected business deviation to inspect deterministic findings and root causes.
                </p>
              </div>

              <div className="flex items-center space-x-2 text-xs font-mono">
                <span className="rounded-lg bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-3 py-1.5 text-slate-700 dark:text-slate-300 font-semibold">
                  Showing {filteredAnomalies.length} of {anomalies.length} signals
                </span>
              </div>
            </div>

            {/* Layout: Master-Detail Grid or Full-Width Focus View */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* ===================================================================== */}
              {/* LEFT PANEL: SIGNAL FEED (Hidden if Workspace is in Focus/Expanded mode) */}
              {/* ===================================================================== */}
              {!isWorkspaceExpanded && (
                <div className="lg:col-span-5 flex flex-col space-y-4">
                  {/* Filter & Search Card */}
                  <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] p-4 sm:p-5 shadow-sm space-y-4 transition-colors">
                    {/* Search */}
                    <div className="relative">
                      <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                      <input
                        type="text"
                        placeholder="Search by date, metric name, or #ID..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-[#080c14] py-2 pl-9 pr-8 text-xs text-slate-900 dark:text-slate-200 placeholder-slate-400 focus:border-indigo-500 focus:bg-white dark:focus:bg-[#080c14] focus:outline-none transition"
                      />
                      {searchQuery && (
                        <button
                          onClick={() => setSearchQuery("")}
                          className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xs"
                        >
                          &times;
                        </button>
                      )}
                    </div>

                    {/* Metric Select & Sort */}
                    <div className="grid grid-cols-2 gap-2.5 text-xs">
                      <div>
                        <label className="block text-[10px] font-mono font-medium text-slate-500 dark:text-slate-400 mb-1">
                          Filter KPI
                        </label>
                        <select
                          value={selectedMetric}
                          onChange={(e) => setSelectedMetric(e.target.value)}
                          className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-[#080c14] py-1.5 px-2.5 text-xs text-slate-800 dark:text-slate-300 focus:border-indigo-500 focus:outline-none"
                        >
                          <option value="all">All Metrics</option>
                          {metrics.map((m) => (
                            <option key={m.name} value={m.name}>
                              {m.display_name}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-[10px] font-mono font-medium text-slate-500 dark:text-slate-400 mb-1">
                          Sort Order
                        </label>
                        <select
                          value={sortBy}
                          onChange={(e: any) => setSortBy(e.target.value)}
                          className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-[#080c14] py-1.5 px-2.5 text-xs text-slate-800 dark:text-slate-300 focus:border-indigo-500 focus:outline-none"
                        >
                          <option value="z_score_desc">Highest |Z| Score</option>
                          <option value="date_desc">Newest Date</option>
                          <option value="date_asc">Oldest Date</option>
                        </select>
                      </div>
                    </div>

                    {/* Severity & Status filter pills */}
                    <div className="pt-3 border-t border-slate-100 dark:border-slate-800/80 space-y-2.5">
                      <div className="flex items-center space-x-1.5 flex-wrap gap-y-1">
                        <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400 mr-1">Severity:</span>
                        {(["all", "high", "medium", "low"] as const).map((sev) => {
                          const isActive = selectedSeverity === sev;
                          return (
                            <button
                              key={sev}
                              onClick={() => setSelectedSeverity(sev)}
                              className={`rounded-lg px-2.5 py-1 text-[10px] font-mono uppercase tracking-wide transition ${
                                isActive
                                  ? sev === "high"
                                    ? "bg-rose-100 text-rose-800 dark:bg-rose-500/20 dark:text-rose-300 border border-rose-300 font-bold"
                                    : sev === "medium"
                                    ? "bg-amber-100 text-amber-900 dark:bg-amber-500/20 dark:text-amber-300 border border-amber-300 font-bold"
                                    : sev === "low"
                                    ? "bg-blue-100 text-blue-800 dark:bg-blue-500/20 dark:text-blue-300 border border-blue-300 font-bold"
                                    : "bg-indigo-100 text-indigo-800 dark:bg-indigo-500/20 dark:text-indigo-300 border border-indigo-300 font-bold"
                                  : "bg-slate-100 dark:bg-[#080c14] text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 border border-slate-200 dark:border-slate-800"
                              }`}
                            >
                              {sev}
                            </button>
                          );
                        })}
                      </div>

                      <div className="flex items-center space-x-1.5 flex-wrap gap-y-1">
                        <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400 mr-1">Status:</span>
                        {[
                          { key: "all", label: "ALL" },
                          { key: "investigated", label: "INVESTIGATED" },
                          { key: "open", label: "OPEN" },
                        ].map((st) => {
                          const isActive = selectedStatus === st.key;
                          return (
                            <button
                              key={st.key}
                              onClick={() => setSelectedStatus(st.key)}
                              className={`rounded-lg px-2.5 py-1 text-[10px] font-mono uppercase tracking-wide transition ${
                                isActive
                                  ? "bg-indigo-100 text-indigo-800 dark:bg-indigo-500/20 dark:text-indigo-300 border border-indigo-300 font-bold"
                                  : "bg-slate-100 dark:bg-[#080c14] text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 border border-slate-200 dark:border-slate-800"
                              }`}
                            >
                              {st.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  {/* Incident Feed List */}
                  <div className="space-y-2.5 max-h-[calc(100vh-280px)] overflow-y-auto pr-1">
                    {loadingFeed ? (
                      <div className="flex flex-col items-center justify-center p-12 space-y-2 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-[#0c121e]/60 text-slate-500">
                        <RefreshCw className="h-5 w-5 animate-spin text-indigo-600" />
                        <p className="text-xs font-mono">Loading signal stream...</p>
                      </div>
                    ) : feedError ? (
                      <div className="rounded-2xl border border-rose-300 dark:border-rose-900/40 bg-rose-50 dark:bg-rose-950/20 p-5 text-center text-xs text-rose-800 dark:text-rose-300 space-y-2">
                        <AlertTriangle className="mx-auto h-5 w-5 text-rose-600" />
                        <p className="font-bold">Failed to load signals</p>
                        <p className="text-rose-600 text-xs">{feedError}</p>
                        <button
                          onClick={loadInitialFeed}
                          className="mt-2 inline-flex items-center space-x-1.5 rounded-lg bg-rose-100 dark:bg-rose-900/40 px-3 py-1.5 text-xs text-rose-900 border border-rose-300"
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                          <span>Retry</span>
                        </button>
                      </div>
                    ) : filteredAnomalies.length === 0 ? (
                      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] p-8 text-center text-xs text-slate-500 space-y-2">
                        <Filter className="mx-auto h-6 w-6 text-slate-400" />
                        <p className="font-semibold text-slate-800 dark:text-slate-200">No signals match filters</p>
                        <button
                          onClick={() => {
                            setSelectedMetric("all");
                            setSelectedSeverity("all");
                            setSelectedStatus("all");
                            setSearchQuery("");
                          }}
                          className="mt-1 rounded-lg bg-slate-200 dark:bg-slate-800 px-3 py-1.5 text-xs font-mono text-slate-800 dark:text-slate-200"
                        >
                          Reset Filters
                        </button>
                      </div>
                    ) : (
                      filteredAnomalies.map((item) => {
                        const isSelected = item.id === selectedAnomalyId;
                        return (
                          <button
                            key={item.id}
                            onClick={() => setSelectedAnomalyId(item.id)}
                            className={`w-full text-left rounded-2xl p-4 transition-all border ${
                              isSelected
                                ? "border-indigo-500 bg-indigo-50/80 dark:bg-[#121a2d] shadow-sm ring-2 ring-indigo-500/30"
                                : "border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] hover:border-slate-300 dark:hover:border-slate-700 hover:shadow-sm"
                            }`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-mono text-xs font-semibold text-slate-400">
                                #{item.id}
                              </span>
                              <div className="flex items-center space-x-1.5">
                                {item.has_investigation && (
                                  <span className="rounded-full bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 px-2 py-0.2 text-[9px] font-mono font-semibold text-emerald-700 dark:text-emerald-400">
                                    INVESTIGATED
                                  </span>
                                )}
                                <span
                                  className={`rounded-full px-2 py-0.2 text-[9px] font-mono font-bold uppercase ${
                                    item.severity === "high"
                                      ? "bg-rose-100 text-rose-800 dark:bg-rose-500/20 dark:text-rose-300 border border-rose-200"
                                      : "bg-amber-100 text-amber-900 dark:bg-amber-500/20 dark:text-amber-300 border border-amber-200"
                                  }`}
                                >
                                  {item.severity}
                                </span>
                              </div>
                            </div>

                            <h4 className="font-bold text-sm text-slate-900 dark:text-white mt-1.5">
                              {item.metric_display_name}
                            </h4>

                            <div className="mt-2 flex items-center justify-between text-xs font-mono text-slate-500 dark:text-slate-400">
                              <div className="flex items-center space-x-1">
                                <Calendar className="h-3.5 w-3.5 text-slate-400" />
                                <span>{item.date}</span>
                              </div>
                              <span className="font-bold text-slate-800 dark:text-slate-200">
                                {formatMetricValue(item.actual_value, item.unit)}
                              </span>
                            </div>

                            <div className="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-[11px] font-mono">
                              <span
                                className={`font-semibold ${
                                  item.delta >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"
                                }`}
                              >
                                {formatDelta(item.delta, item.delta_pct, item.unit)}
                              </span>
                              <span className="rounded bg-slate-100 dark:bg-[#080c14] px-1.5 py-0.5 text-indigo-700 dark:text-indigo-300 font-bold border border-slate-200 dark:border-slate-800">
                                Z: {item.z_score >= 0 ? `+${item.z_score.toFixed(2)}` : item.z_score.toFixed(2)}
                              </span>
                            </div>
                          </button>
                        );
                      })
                    )}
                  </div>
                </div>
              )}

              {/* ===================================================================== */}
              {/* RIGHT PANEL: INVESTIGATION WORKSPACE (Focus Mode = 12 cols, Split = 7 cols) */}
              {/* ===================================================================== */}
              <div className={`${isWorkspaceExpanded ? "lg:col-span-12" : "lg:col-span-7"} space-y-4`}>
                <InvestigationWorkspace
                  activeAnomaly={activeAnomaly}
                  investigationData={investigationData}
                  loadingInvestigation={loadingInvestigation}
                  investigating={investigating}
                  investigationError={investigationError}
                  onRunInvestigation={handleRunInvestigation}
                  isExpanded={isWorkspaceExpanded}
                  onToggleExpand={() => setIsWorkspaceExpanded(!isWorkspaceExpanded)}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
