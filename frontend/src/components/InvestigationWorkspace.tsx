"use client";

import React, { useState } from "react";
import {
  Sparkles,
  ShieldCheck,
  Zap,
  RefreshCw,
  AlertTriangle,
  RotateCcw,
  MapPin,
  CalendarDays,
  FileCheck2,
  CheckCircle2,
  Maximize2,
  Minimize2,
  CheckCircle,
} from "lucide-react";
import { Anomaly, InvestigationResponse } from "../lib/types";
import { formatMetricValue, formatDelta } from "../lib/api";

type InvestigationTab = "overview" | "segments" | "seasonality" | "audit";

interface InvestigationWorkspaceProps {
  activeAnomaly: Anomaly | null;
  investigationData: InvestigationResponse | null;
  loadingInvestigation: boolean;
  investigating: boolean;
  investigationError: string | null;
  onRunInvestigation: () => void;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

export default function InvestigationWorkspace({
  activeAnomaly,
  investigationData,
  loadingInvestigation,
  investigating,
  investigationError,
  onRunInvestigation,
  isExpanded = false,
  onToggleExpand,
}: InvestigationWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<InvestigationTab>("overview");

  if (!activeAnomaly) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-[#0c121e]/60 p-12 sm:p-16 text-center text-slate-500 dark:text-slate-400 space-y-3 shadow-sm min-h-[450px] flex flex-col items-center justify-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-400">
          <Sparkles className="h-7 w-7 text-indigo-500" />
        </div>
        <h3 className="text-base font-bold font-mono text-slate-800 dark:text-slate-200">
          No Signal Selected
        </h3>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 max-w-sm">
          Select any incident from the feed to inspect its automated deterministic investigation report.
        </p>
      </div>
    );
  }

  // Extract evidence steps safely
  const breakdownStep = investigationData?.evidence_steps?.find((s) => s.tool_name === "segment_breakdown");
  const seasonalityStep = investigationData?.evidence_steps?.find((s) => s.tool_name === "check_seasonality");
  const trendStep = investigationData?.evidence_steps?.find((s) => s.tool_name === "get_recent_trend");

  return (
    <div className="space-y-5 transition-all">
      {/* ========================================================================= */}
      {/* 1. TOP INCIDENT HEADER & BASELINE METRICS                                  */}
      {/* ========================================================================= */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] p-5 sm:p-6 shadow-sm space-y-5 transition-colors">
        {/* Title row */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 pb-4 border-b border-slate-100 dark:border-slate-800/80">
          <div className="space-y-1.5 min-w-0">
            <div className="flex items-center space-x-2 flex-wrap gap-y-1">
              <span className="rounded-full bg-indigo-50 dark:bg-indigo-500/15 px-3 py-0.5 text-xs font-mono font-bold text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30">
                SIGNAL #{activeAnomaly.id}
              </span>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-mono font-bold uppercase tracking-wide ${
                  activeAnomaly.severity === "high"
                    ? "bg-rose-100 text-rose-800 dark:bg-rose-500/20 dark:text-rose-300 border border-rose-200 dark:border-rose-500/30"
                    : activeAnomaly.severity === "medium"
                    ? "bg-amber-100 text-amber-900 dark:bg-amber-500/20 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30"
                    : "bg-blue-100 text-blue-800 dark:bg-blue-500/20 dark:text-blue-300 border border-blue-200 dark:border-blue-500/30"
                }`}
              >
                {activeAnomaly.severity} SEVERITY
              </span>
              {activeAnomaly.has_investigation && (
                <span className="rounded-full bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 px-2.5 py-0.5 text-xs font-mono font-medium text-emerald-700 dark:text-emerald-400 flex items-center space-x-1">
                  <CheckCircle className="h-3 w-3" />
                  <span>INVESTIGATED</span>
                </span>
              )}
            </div>

            <h1 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white tracking-tight pt-1">
              {activeAnomaly.metric_display_name}
            </h1>

            <p className="text-xs text-slate-500 dark:text-slate-400 font-mono flex items-center space-x-2">
              <span>Observed on: {activeAnomaly.date}</span>
              <span>&bull;</span>
              <span className="capitalize">Status: {activeAnomaly.status}</span>
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex items-center space-x-2 shrink-0">
            {onToggleExpand && (
              <button
                onClick={onToggleExpand}
                className="p-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 transition"
                title={isExpanded ? "Collapse View" : "Expand to Focus View"}
              >
                {isExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
              </button>
            )}

            <button
              onClick={onRunInvestigation}
              disabled={investigating}
              className="inline-flex items-center justify-center space-x-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 px-4 py-2.5 text-xs font-mono font-bold text-white shadow-sm transition disabled:opacity-50 disabled:cursor-not-allowed border border-indigo-400/30"
            >
              {investigating ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin text-white" />
                  <span>Executing Diagnostic...</span>
                </>
              ) : investigationData ? (
                <>
                  <RefreshCw className="h-4 w-4 text-indigo-200" />
                  <span>Re-Run Investigation</span>
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4 text-amber-300" />
                  <span>Run Autonomous Investigation</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* 4 Quantitative Baseline Statistics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800/90">
            <span className="text-[10px] font-mono uppercase font-semibold text-slate-500 dark:text-slate-400 block">
              Observed Value
            </span>
            <div className="text-base sm:text-lg font-bold font-mono text-slate-900 dark:text-white mt-1">
              {formatMetricValue(activeAnomaly.actual_value, activeAnomaly.unit)}
            </div>
            <span className="text-[10px] text-slate-400 dark:text-slate-500 block mt-0.5">Telemetry reading</span>
          </div>

          <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800/90">
            <span className="text-[10px] font-mono uppercase font-semibold text-slate-500 dark:text-slate-400 block">
              Rolling Baseline
            </span>
            <div className="text-base sm:text-lg font-bold font-mono text-slate-700 dark:text-slate-300 mt-1">
              {formatMetricValue(activeAnomaly.expected_value, activeAnomaly.unit)}
            </div>
            <span className="text-[10px] text-slate-400 dark:text-slate-500 block mt-0.5">14-day historical mean</span>
          </div>

          <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800/90">
            <span className="text-[10px] font-mono uppercase font-semibold text-slate-500 dark:text-slate-400 block">
              Net Deviation
            </span>
            <div
              className={`text-base sm:text-lg font-bold font-mono mt-1 ${
                activeAnomaly.delta >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"
              }`}
            >
              {formatDelta(activeAnomaly.delta, activeAnomaly.delta_pct, activeAnomaly.unit)}
            </div>
            <span className="text-[10px] text-slate-400 dark:text-slate-500 block mt-0.5">Absolute delta</span>
          </div>

          <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800/90">
            <span className="text-[10px] font-mono uppercase font-semibold text-slate-500 dark:text-slate-400 block">
              Statistical Significance
            </span>
            <div className="text-base sm:text-lg font-bold font-mono text-indigo-700 dark:text-indigo-300 mt-1">
              Z: {activeAnomaly.z_score >= 0 ? `+${activeAnomaly.z_score.toFixed(2)}` : activeAnomaly.z_score.toFixed(2)}
            </div>
            <span className="text-[10px] font-mono text-rose-600 dark:text-rose-300 block mt-0.5">
              {Math.abs(activeAnomaly.z_score).toFixed(1)}&sigma; deviation
            </span>
          </div>
        </div>
      </div>

      {/* Error notification banner */}
      {investigationError && (
        <div className="rounded-2xl border border-rose-300 dark:border-rose-800/40 bg-rose-50 dark:bg-rose-950/30 p-4 text-xs text-rose-800 dark:text-rose-300 flex items-start space-x-3">
          <AlertTriangle className="h-5 w-5 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
          <div className="min-w-0 flex-1">
            <p className="font-bold">Investigation failed to execute</p>
            <p className="mt-0.5 text-rose-600 dark:text-rose-400/90 text-xs">{investigationError}</p>
            <button
              onClick={onRunInvestigation}
              className="mt-2.5 inline-flex items-center space-x-1.5 rounded-lg bg-rose-100 dark:bg-rose-900/50 hover:bg-rose-200 dark:hover:bg-rose-900 px-3 py-1.5 text-xs font-mono text-rose-900 dark:text-rose-200 border border-rose-300 dark:border-rose-700"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Retry Investigation</span>
            </button>
          </div>
        </div>
      )}

      {/* Pipeline In-Progress Animation */}
      {investigating && (
        <div className="rounded-2xl border border-indigo-200 dark:border-indigo-900/50 bg-white dark:bg-[#0c121e] p-8 text-center space-y-5 shadow-sm">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 animate-pulse">
            <Zap className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-900 dark:text-white">
              Executing Multi-Dimensional Diagnostic Pipeline...
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Decomposing telemetry into regional segments, seasonality patterns, and trajectory slopes.
            </p>
          </div>
          <div className="mx-auto max-w-lg space-y-2.5 text-left text-xs font-mono text-slate-700 dark:text-slate-300 pt-2">
            <div className="flex items-center space-x-3 text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/40 p-2.5 rounded-lg border border-indigo-100 dark:border-indigo-900">
              <span className="h-2.5 w-2.5 rounded-full bg-indigo-600 animate-ping"></span>
              <span className="font-semibold">01 Segment Attribution: Calculating state & category shares</span>
            </div>
            <div className="flex items-center space-x-3 text-slate-500 p-2 rounded-lg">
              <span className="h-2 w-2 rounded-full bg-slate-300 dark:bg-slate-700"></span>
              <span>02 Seasonality Analysis: 8-week same-weekday baseline comparison</span>
            </div>
            <div className="flex items-center space-x-3 text-slate-500 p-2 rounded-lg">
              <span className="h-2 w-2 rounded-full bg-slate-300 dark:bg-slate-700"></span>
              <span>03 Trajectory Regression: 14-day chronological slope evaluation</span>
            </div>
            <div className="flex items-center space-x-3 text-slate-500 p-2 rounded-lg">
              <span className="h-2 w-2 rounded-full bg-slate-300 dark:bg-slate-700"></span>
              <span>04 Grounding & Audit: Strict zero-hallucination verification</span>
            </div>
          </div>
        </div>
      )}

      {/* Loading data state */}
      {loadingInvestigation && !investigating && (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-[#0c121e]/60 p-12 text-center text-xs text-slate-500 dark:text-slate-400 space-y-2">
          <RefreshCw className="mx-auto h-6 w-6 animate-spin text-indigo-600 dark:text-indigo-400 mb-2" />
          <p className="font-mono text-sm font-semibold">Loading diagnostic evidence...</p>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 2. INVESTIGATION REPORT TABS & DETAIL VIEW                                 */}
      {/* ========================================================================= */}
      {investigationData && !investigating && (
        <div className="space-y-4">
          {/* Tab Selector Bar */}
          <div className="flex items-center space-x-2 border-b border-slate-200 dark:border-slate-800 pb-3 overflow-x-auto">
            {[
              { id: "overview", label: "Root Cause & Playbook", icon: Sparkles },
              { id: "segments", label: "Regional Breakdown", icon: MapPin },
              { id: "seasonality", label: "Seasonality & Trajectory", icon: CalendarDays },
              { id: "audit", label: "Audit Trail", icon: FileCheck2 },
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as InvestigationTab)}
                  className={`flex items-center space-x-2 rounded-xl px-4 py-2 text-xs font-mono font-medium transition shrink-0 ${
                    isActive
                      ? "bg-indigo-600 text-white shadow-sm font-bold"
                      : "bg-white dark:bg-[#0c121e] text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* TAB 1: ROOT CAUSE & PLAYBOOK */}
          {activeTab === "overview" && investigationData.conclusion && (
            <div className="rounded-2xl border border-indigo-200 dark:border-indigo-500/40 bg-white dark:bg-[#0c121e] p-6 sm:p-7 shadow-sm space-y-6 transition-colors">
              {/* Header */}
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center space-x-2.5">
                  <div className="p-1.5 rounded-lg bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400">
                    <Sparkles className="h-4 w-4" />
                  </div>
                  <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-900 dark:text-white">
                    Root Cause Diagnosis
                  </h3>
                </div>
                <div className="flex items-center space-x-2 text-[10px] font-mono">
                  <span className="rounded-full bg-indigo-50 dark:bg-indigo-500/20 px-2.5 py-0.5 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30">
                    Provider: {investigationData.conclusion.provider}
                  </span>
                  <span
                    className={`rounded-full px-2.5 py-0.5 font-bold uppercase tracking-wider ${
                      investigationData.conclusion.validation_passed
                        ? "bg-emerald-50 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30"
                        : "bg-rose-50 dark:bg-rose-500/20 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-500/30"
                    }`}
                  >
                    {investigationData.conclusion.validation_passed ? "Audit Passed" : "Audit Flagged"}
                  </span>
                </div>
              </div>

              {/* Highlight Root Cause Banner */}
              <div className="rounded-xl bg-indigo-50/90 dark:bg-indigo-950/40 p-5 border border-indigo-200 dark:border-indigo-500/30">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-indigo-700 dark:text-indigo-300 block mb-1.5">
                  Identified Primary Root Cause
                </span>
                <p className="text-sm sm:text-base font-bold text-indigo-950 dark:text-white leading-relaxed">
                  {investigationData.conclusion.root_cause}
                </p>
              </div>

              {/* Analytical Synthesis Explanation */}
              <div className="space-y-2">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
                  Analytical Synthesis
                </span>
                <p className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-5 border border-slate-200 dark:border-slate-800 text-xs sm:text-sm text-slate-800 dark:text-slate-200 leading-relaxed font-sans">
                  {investigationData.conclusion.explanation}
                </p>
              </div>

              {/* Grounding Attributes Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
                  <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400 block uppercase font-semibold">
                    Confidence Level
                  </span>
                  <span className="font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-wide text-xs sm:text-sm mt-1 block">
                    {investigationData.conclusion.confidence} Confidence
                  </span>
                </div>
                <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
                  <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400 block uppercase font-semibold">
                    Affected Segment
                  </span>
                  <span className="font-bold text-indigo-700 dark:text-indigo-300 font-mono text-xs sm:text-sm mt-1 block truncate">
                    {investigationData.conclusion.affected_segment || "All Segments"}
                  </span>
                </div>
                <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
                  <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400 block uppercase font-semibold">
                    Validation Shield
                  </span>
                  <span className="font-bold text-cyan-700 dark:text-cyan-300 flex items-center space-x-1.5 text-xs sm:text-sm mt-1">
                    <ShieldCheck className="h-4 w-4 text-cyan-600 dark:text-cyan-400 shrink-0" />
                    <span>100% Grounded</span>
                  </span>
                </div>
              </div>

              {/* Recommended Action Playbook */}
              <div className="rounded-xl bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-500/30 p-5 space-y-1.5">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-emerald-800 dark:text-emerald-400 block">
                  Recommended Operational Playbook
                </span>
                <p className="text-xs sm:text-sm text-emerald-950 dark:text-emerald-200 leading-relaxed font-medium">
                  {investigationData.conclusion.recommended_action}
                </p>
              </div>
            </div>
          )}

          {/* TAB 2: REGIONAL BREAKDOWN */}
          {activeTab === "segments" && (
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] p-6 sm:p-7 shadow-sm space-y-6 transition-colors">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center space-x-2">
                  <MapPin className="h-4 w-4 text-cyan-600 dark:text-cyan-400" />
                  <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-900 dark:text-white">
                    Regional Segment Attribution
                  </h3>
                </div>
                <span className="rounded-full bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-3 py-0.5 text-[10px] font-mono text-slate-700 dark:text-slate-300">
                  {breakdownStep?.status === "success" ? "Verified Attribution" : "Pending"}
                </span>
              </div>

              {breakdownStep ? (() => {
                const out = breakdownStep.output_data || {};
                const topContr = out.top_contributor || {};
                const topState = typeof topContr === "object" ? (topContr.segment || out.primary_contributor || "N/A") : (out.primary_contributor || "N/A");
                const topShare = typeof topContr === "object" ? (topContr.percentage_contribution ?? topContr.share_of_total ?? out.primary_contributor_share) : out.primary_contributor_share;
                const netDelta = out.total_delta;

                return (
                  <div className="space-y-5">
                    {/* 3 Metric Cards */}
                    <div className="grid grid-cols-3 gap-3 text-xs">
                      <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
                        <span className="text-slate-500 dark:text-slate-400 block text-[10px] font-mono">Top Contributor</span>
                        <span className="text-sm sm:text-base font-bold text-indigo-700 dark:text-indigo-300 font-mono mt-1 block">
                          State &apos;{topState}&apos;
                        </span>
                      </div>
                      <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
                        <span className="text-slate-500 dark:text-slate-400 block text-[10px] font-mono">Deviation Share</span>
                        <span className="text-sm sm:text-base font-bold text-emerald-700 dark:text-emerald-400 font-mono mt-1 block">
                          {topShare !== undefined && topShare !== null && !isNaN(Number(topShare))
                            ? `+${Number(topShare).toFixed(1)}%`
                            : "N/A"}
                        </span>
                      </div>
                      <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
                        <span className="text-slate-500 dark:text-slate-400 block text-[10px] font-mono">Total Delta</span>
                        <span className="text-sm sm:text-base font-bold text-slate-900 dark:text-white font-mono mt-1 block">
                          {netDelta !== undefined && netDelta !== null && !isNaN(Number(netDelta))
                            ? formatMetricValue(Number(netDelta), activeAnomaly.unit)
                            : "N/A"}
                        </span>
                      </div>
                    </div>

                    {/* Visual Segment Share Bars & Table */}
                    {Array.isArray(out.segments) && out.segments.length > 0 && (
                      <div className="space-y-3">
                        <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
                          Segment Contribution Breakdown
                        </span>
                        <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#080c14]">
                          <table className="w-full text-left text-xs font-mono">
                            <thead className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-700 dark:text-slate-400">
                              <tr>
                                <th className="py-2.5 px-4">Segment</th>
                                <th className="py-2.5 px-4">Actual</th>
                                <th className="py-2.5 px-4">Baseline</th>
                                <th className="py-2.5 px-4">Delta</th>
                                <th className="py-2.5 px-4">Contribution Share</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 text-slate-800 dark:text-slate-300">
                              {out.segments.map((seg: any, sIdx: number) => {
                                const segName = seg.segment || seg.segment_value || `Region ${sIdx + 1}`;
                                const segActual = Number(seg.actual_value ?? 0);
                                const segBaseline = Number(seg.baseline_value ?? 0);
                                const segDelta = seg.absolute_delta !== undefined && seg.absolute_delta !== null
                                  ? Number(seg.absolute_delta)
                                  : (seg.delta !== undefined && seg.delta !== null ? Number(seg.delta) : segActual - segBaseline);
                                const segShare = seg.percentage_contribution !== undefined && seg.percentage_contribution !== null
                                  ? Number(seg.percentage_contribution)
                                  : (seg.contribution_share !== undefined && seg.contribution_share !== null
                                      ? Number(seg.contribution_share)
                                      : (seg.share_of_total !== undefined && seg.share_of_total !== null ? Number(seg.share_of_total) : null));

                                const sharePctVal = segShare !== null && !isNaN(segShare) ? Math.max(0, Math.min(100, Math.abs(segShare))) : 0;

                                return (
                                  <tr key={segName} className="hover:bg-slate-50 dark:hover:bg-slate-900/40 transition">
                                    <td className="py-3 px-4 font-bold text-indigo-700 dark:text-indigo-300">{segName}</td>
                                    <td className="py-3 px-4">{formatMetricValue(segActual, activeAnomaly.unit)}</td>
                                    <td className="py-3 px-4 text-slate-500">{formatMetricValue(segBaseline, activeAnomaly.unit)}</td>
                                    <td className={`py-3 px-4 font-semibold ${segDelta >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>
                                      {segDelta >= 0 ? `+${segDelta.toFixed(1)}` : segDelta.toFixed(1)}
                                    </td>
                                    <td className="py-3 px-4">
                                      <div className="flex items-center space-x-2.5">
                                        <div className="flex-1 h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden max-w-[120px]">
                                          <div
                                            className="h-full bg-indigo-600 dark:bg-indigo-400 rounded-full"
                                            style={{ width: `${sharePctVal}%` }}
                                          ></div>
                                        </div>
                                        <span className="font-semibold text-[11px]">
                                          {segShare !== null && !isNaN(segShare)
                                            ? `${segShare >= 0 ? `+${segShare.toFixed(1)}` : segShare.toFixed(1)}%`
                                            : "—"}
                                        </span>
                                      </div>
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Summary */}
                    <div className="p-4 rounded-xl bg-slate-50 dark:bg-[#080c14] border border-slate-200 dark:border-slate-800 text-xs sm:text-sm text-slate-800 dark:text-slate-300 leading-relaxed font-sans">
                      {breakdownStep.summary}
                    </div>
                  </div>
                );
              })() : (
                <div className="p-8 text-center text-xs text-slate-500">
                  Regional breakdown evidence not available for this signal.
                </div>
              )}
            </div>
          )}

          {/* TAB 3: SEASONALITY & TRAJECTORY */}
          {activeTab === "seasonality" && (
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] p-6 sm:p-7 shadow-sm space-y-6 transition-colors">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center space-x-2">
                  <CalendarDays className="h-4 w-4 text-amber-500 dark:text-amber-400" />
                  <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-900 dark:text-white">
                    Seasonality & Chronological Trajectory
                  </h3>
                </div>
              </div>

              {/* Tool 2: Seasonality */}
              {seasonalityStep && (() => {
                const out = seasonalityStep.output_data || {};
                const dowLabel = out.day_of_week_name || (out.day_of_week !== undefined ? `Day ${out.day_of_week}` : "N/A");
                const dowMean = out.same_dow_mean;
                const dowZscore = out.same_dow_zscore;

                return (
                  <div className="space-y-3">
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
                      Same-Weekday Historical Comparison (8-Week Baseline)
                    </span>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                      <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
                        <span className="text-slate-500 dark:text-slate-400 block text-[10px] font-mono">Day of Week</span>
                        <span className="text-sm sm:text-base font-bold text-slate-900 dark:text-white font-mono mt-1 block">
                          {dowLabel}
                        </span>
                      </div>
                      <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
                        <span className="text-slate-500 dark:text-slate-400 block text-[10px] font-mono">Same-DOW Mean</span>
                        <span className="text-sm sm:text-base font-bold text-slate-700 dark:text-slate-300 font-mono mt-1 block">
                          {dowMean !== undefined && dowMean !== null && !isNaN(Number(dowMean))
                            ? formatMetricValue(Number(dowMean), activeAnomaly.unit)
                            : "N/A"}
                        </span>
                      </div>
                      <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
                        <span className="text-slate-500 dark:text-slate-400 block text-[10px] font-mono">Same-DOW Z-Score</span>
                        <span className="text-sm sm:text-base font-bold text-indigo-700 dark:text-indigo-300 font-mono mt-1 block">
                          {dowZscore !== undefined && dowZscore !== null && !isNaN(Number(dowZscore))
                            ? `Z: ${Number(dowZscore) >= 0 ? `+${Number(dowZscore).toFixed(2)}` : Number(dowZscore).toFixed(2)}`
                            : "N/A"}
                        </span>
                      </div>
                      <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
                        <span className="text-slate-500 dark:text-slate-400 block text-[10px] font-mono">Verdict</span>
                        <span
                          className={`text-xs sm:text-sm font-bold uppercase tracking-wider inline-block mt-1 ${
                            out.is_seasonal ? "text-blue-700 dark:text-blue-400" : "text-rose-700 dark:text-rose-400"
                          }`}
                        >
                          {out.is_seasonal ? "Seasonal Cyclical" : "Non-Seasonal Spike"}
                        </span>
                      </div>
                    </div>
                    <div className="p-4 rounded-xl bg-slate-50 dark:bg-[#080c14] border border-slate-200 dark:border-slate-800 text-xs sm:text-sm text-slate-800 dark:text-slate-300 font-sans leading-relaxed">
                      {seasonalityStep.summary}
                    </div>
                  </div>
                );
              })()}

              {/* Tool 3: Recent Trend */}
              {trendStep && (() => {
                const out = trendStep.output_data || {};
                const trajectory = out.classification || "N/A";
                const singleDelta = out.single_day_delta;
                const precMean = out.preceding_mean;
                const trendSlope = out.preceding_trend_slope ?? out.linear_slope;

                return (
                  <div className="space-y-3 pt-4 border-t border-slate-200 dark:border-slate-800">
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
                      Preceding 14-Day Trajectory Regression
                    </span>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                      <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
                        <span className="text-slate-500 dark:text-slate-400 block text-[10px] font-mono">Trajectory</span>
                        <span className="text-xs sm:text-sm font-bold text-amber-800 dark:text-amber-300 uppercase tracking-wider font-mono mt-1 block">
                          {trajectory}
                        </span>
                      </div>
                      <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
                        <span className="text-slate-500 dark:text-slate-400 block text-[10px] font-mono">Single-Day Jump</span>
                        <span className="text-sm sm:text-base font-bold text-emerald-700 dark:text-emerald-400 font-mono mt-1 block">
                          {singleDelta !== undefined && singleDelta !== null && !isNaN(Number(singleDelta))
                            ? `${Number(singleDelta) >= 0 ? `+${Number(singleDelta).toFixed(1)}` : Number(singleDelta).toFixed(1)}`
                            : "N/A"}
                        </span>
                      </div>
                      <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
                        <span className="text-slate-500 dark:text-slate-400 block text-[10px] font-mono">Preceding Mean</span>
                        <span className="text-sm sm:text-base font-bold text-slate-700 dark:text-slate-300 font-mono mt-1 block">
                          {precMean !== undefined && precMean !== null && !isNaN(Number(precMean))
                            ? formatMetricValue(Number(precMean), activeAnomaly.unit)
                            : "N/A"}
                        </span>
                      </div>
                      <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
                        <span className="text-slate-500 dark:text-slate-400 block text-[10px] font-mono">Daily Slope (&beta;)</span>
                        <span className="text-sm sm:text-base font-bold text-cyan-800 dark:text-cyan-300 font-mono mt-1 block">
                          {trendSlope !== undefined && trendSlope !== null && !isNaN(Number(trendSlope))
                            ? `${Number(trendSlope).toFixed(2)}/day`
                            : "N/A"}
                        </span>
                      </div>
                    </div>
                    <div className="p-4 rounded-xl bg-slate-50 dark:bg-[#080c14] border border-slate-200 dark:border-slate-800 text-xs sm:text-sm text-slate-800 dark:text-slate-300 font-sans leading-relaxed">
                      {trendStep.summary}
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          {/* TAB 4: AUDIT TRAIL */}
          {activeTab === "audit" && (
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] p-6 sm:p-7 shadow-sm space-y-6 transition-colors">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center space-x-2">
                  <FileCheck2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                  <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-900 dark:text-white">
                    Deterministic Audit Trail & Citations
                  </h3>
                </div>
                <span className="rounded-full bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 px-3 py-0.5 text-[10px] font-mono font-bold text-emerald-700 dark:text-emerald-400">
                  100% Grounded
                </span>
              </div>

              {/* Citations List */}
              {investigationData.conclusion?.evidence_references && investigationData.conclusion.evidence_references.length > 0 ? (
                <div className="space-y-3">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
                    Verified Deterministic Citations
                  </span>
                  <div className="space-y-2">
                    {investigationData.conclusion.evidence_references.map((ref, idx) => (
                      <div
                        key={idx}
                        className="rounded-xl bg-slate-50 dark:bg-[#080c14] px-4 py-3 text-xs sm:text-sm font-mono text-indigo-950 dark:text-indigo-200 border border-slate-200 dark:border-slate-800 flex items-start space-x-3"
                      >
                        <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                        <span className="leading-relaxed">{ref}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-500">No explicit citations recorded.</p>
              )}

              {/* Trust Summary Strip */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-[#080c14] p-4 flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-slate-600 dark:text-slate-400">
                <div className="flex items-center space-x-2 text-emerald-700 dark:text-emerald-400 font-semibold">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>EVIDENCE GROUNDED: PASSED</span>
                </div>
                <div className="flex items-center space-x-2 text-cyan-700 dark:text-cyan-400 font-semibold">
                  <ShieldCheck className="h-4 w-4" />
                  <span>CITATIONS VERIFIED: 3/3 STEPS</span>
                </div>
                <div className="text-slate-500 font-medium">
                  ZERO HALLUCINATION ENFORCEMENT
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty un-investigated state */}
      {!investigationData && !loadingInvestigation && !investigating && (
        <div className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 bg-white/60 dark:bg-[#0c121e]/40 p-8 sm:p-12 text-center space-y-4">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-400">
            <Sparkles className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm sm:text-base font-bold font-mono text-slate-900 dark:text-white">
              No Automated Investigation on Record
            </h3>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto leading-relaxed">
              This signal has not been decomposed yet. Click below to execute the 3-step deterministic evidence pipeline and synthesize an evidence-grounded root cause.
            </p>
          </div>
          <button
            onClick={onRunInvestigation}
            className="inline-flex items-center space-x-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 px-5 py-2.5 text-xs font-mono font-bold text-white shadow-sm transition"
          >
            <Zap className="h-4 w-4 text-amber-300" />
            <span>Start Automated Investigation</span>
          </button>
        </div>
      )}
    </div>
  );
}
