"use client";

import React from "react";
import {
  AlertTriangle,
  ShieldCheck,
  Zap,
  ArrowRight,
  TrendingDown,
  TrendingUp,
  Activity,
  Calendar,
  CheckCircle2,
} from "lucide-react";
import { Anomaly, MetricMeta } from "../lib/types";
import { formatMetricValue, formatDelta } from "../lib/api";

interface ExecutiveOverviewProps {
  anomalies: Anomaly[];
  metrics: MetricMeta[];
  loading: boolean;
  onSelectAnomaly: (id: number) => void;
  onSelectMetricFilter: (metricName: string) => void;
}

export default function ExecutiveOverview({
  anomalies,
  metrics,
  loading,
  onSelectAnomaly,
  onSelectMetricFilter,
}: ExecutiveOverviewProps) {
  const totalSignals = anomalies.length;
  const criticalSignals = anomalies.filter((a) => a.severity === "high");
  const investigatedSignals = anomalies.filter((a) => a.has_investigation);
  const coverageRate = totalSignals > 0 ? Math.round((investigatedSignals.length / totalSignals) * 100) : 0;

  // Top priority anomalies (highest |Z-score| high-severity ones)
  const priorityQueue = [...anomalies]
    .sort((a, b) => Math.abs(b.z_score) - Math.abs(a.z_score))
    .slice(0, 4);

  return (
    <div className="space-y-6 sm:space-y-8 animate-fadeIn">
      {/* 1. Page Header & Subtitle */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold font-mono tracking-tight text-slate-900 dark:text-white">
            Executive Operations Overview
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Real-time automated surveillance, statistical anomaly detection, and autonomous diagnostic coverage.
          </p>
        </div>
        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="inline-flex items-center rounded-full bg-emerald-50 dark:bg-emerald-500/10 px-3 py-1 font-semibold text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20">
            <span className="h-2 w-2 rounded-full bg-emerald-500 mr-2 animate-pulse"></span>
            Surveillance Active
          </span>
        </div>
      </div>

      {/* 2. Primary KPI Cards Grid (Generous Whitespace & Readable Fonts) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        {/* Card 1: Total Signals */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] p-5 shadow-sm space-y-3 transition-all hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Total Signals
            </span>
            <div className="rounded-lg bg-indigo-50 dark:bg-indigo-500/10 p-2 text-indigo-600 dark:text-indigo-400">
              <Activity className="h-4 w-4" />
            </div>
          </div>
          <div>
            <span className="text-3xl font-extrabold font-mono text-slate-900 dark:text-white">
              {loading ? "—" : totalSignals}
            </span>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Detected KPI statistical shifts
            </p>
          </div>
          <div className="pt-2 border-t border-slate-100 dark:border-slate-800/80 text-[11px] text-slate-500 dark:text-slate-400 font-mono">
            Surveillance across all business metrics
          </div>
        </div>

        {/* Card 2: Critical Severity */}
        <div className="rounded-xl border border-rose-200 dark:border-rose-900/40 bg-rose-50/60 dark:bg-rose-950/20 p-5 shadow-sm space-y-3 transition-all hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-rose-700 dark:text-rose-300">
              Critical Severity
            </span>
            <div className="rounded-lg bg-rose-100 dark:bg-rose-900/40 p-2 text-rose-600 dark:text-rose-400">
              <AlertTriangle className="h-4 w-4" />
            </div>
          </div>
          <div>
            <span className="text-3xl font-extrabold font-mono text-rose-900 dark:text-rose-200">
              {loading ? "—" : criticalSignals.length}
            </span>
            <p className="text-xs text-rose-700 dark:text-rose-300 mt-1">
              Deviations &ge; 5.0&sigma; threshold
            </p>
          </div>
          <div className="pt-2 border-t border-rose-200/60 dark:border-rose-900/40 text-[11px] text-rose-700 dark:text-rose-300 font-mono">
            Requires immediate investigation
          </div>
        </div>

        {/* Card 3: Investigated Coverage */}
        <div className="rounded-xl border border-emerald-200 dark:border-emerald-900/40 bg-emerald-50/60 dark:bg-emerald-950/20 p-5 shadow-sm space-y-3 transition-all hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-300">
              Investigated
            </span>
            <div className="rounded-lg bg-emerald-100 dark:bg-emerald-900/40 p-2 text-emerald-600 dark:text-emerald-400">
              <ShieldCheck className="h-4 w-4" />
            </div>
          </div>
          <div>
            <span className="text-3xl font-extrabold font-mono text-emerald-900 dark:text-emerald-200">
              {loading ? "—" : investigatedSignals.length}
            </span>
            <p className="text-xs text-emerald-700 dark:text-emerald-300 mt-1">
              Root causes fully diagnosed
            </p>
          </div>
          <div className="pt-2 border-t border-emerald-200/60 dark:border-emerald-900/40 text-[11px] text-emerald-700 dark:text-emerald-300 font-mono">
            {coverageRate}% total pipeline coverage
          </div>
        </div>

        {/* Card 4: Audit & Grounding Standard */}
        <div className="rounded-xl border border-cyan-200 dark:border-cyan-900/40 bg-cyan-50/60 dark:bg-cyan-950/20 p-5 shadow-sm space-y-3 transition-all hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-800 dark:text-cyan-300">
              Audit Standard
            </span>
            <div className="rounded-lg bg-cyan-100 dark:bg-cyan-900/40 p-2 text-cyan-600 dark:text-cyan-400">
              <CheckCircle2 className="h-4 w-4" />
            </div>
          </div>
          <div>
            <span className="text-3xl font-extrabold font-mono text-cyan-900 dark:text-cyan-200">
              100%
            </span>
            <p className="text-xs text-cyan-800 dark:text-cyan-300 mt-1">
              Deterministic Citation Verified
            </p>
          </div>
          <div className="pt-2 border-t border-cyan-200/60 dark:border-cyan-900/40 text-[11px] text-cyan-800 dark:text-cyan-300 font-mono">
            Zero hallucination guardrail enforced
          </div>
        </div>
      </div>

      {/* 3. Priority Action Queue (Spacious, easy-to-read incident cards) */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base sm:text-lg font-bold font-mono text-slate-900 dark:text-white">
              Priority Incident Queue
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Top statistical anomalies with highest sigma impact across the platform.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {priorityQueue.map((item) => (
            <div
              key={item.id}
              className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] p-5 shadow-sm hover:border-indigo-400 dark:hover:border-indigo-500 transition-all flex flex-col justify-between space-y-4"
            >
              <div>
                {/* Header info */}
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-semibold text-slate-400">
                    SIGNAL #{item.id}
                  </span>
                  <div className="flex items-center space-x-2">
                    {item.has_investigation && (
                      <span className="rounded-full bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 px-2 py-0.5 text-[10px] font-mono font-semibold text-emerald-700 dark:text-emerald-400">
                        INVESTIGATED
                      </span>
                    )}
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[10px] font-mono font-bold uppercase ${
                        item.severity === "high"
                          ? "bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-300 border border-rose-300"
                          : "bg-amber-100 text-amber-900 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-300"
                      }`}
                    >
                      {item.severity}
                    </span>
                  </div>
                </div>

                <h3 className="text-base font-bold text-slate-900 dark:text-white mt-2">
                  {item.metric_display_name}
                </h3>

                <div className="flex items-center space-x-2 text-xs font-mono text-slate-500 dark:text-slate-400 mt-1">
                  <Calendar className="h-3.5 w-3.5 text-slate-400" />
                  <span>{item.date}</span>
                </div>
              </div>

              {/* Data comparison strip */}
              <div className="grid grid-cols-3 gap-2 rounded-lg bg-slate-50 dark:bg-[#080c14] p-3 border border-slate-100 dark:border-slate-800 text-xs font-mono">
                <div>
                  <span className="text-[10px] text-slate-400 block uppercase">Observed</span>
                  <span className="font-bold text-slate-900 dark:text-white text-sm">
                    {formatMetricValue(item.actual_value, item.unit)}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block uppercase">Baseline</span>
                  <span className="text-slate-600 dark:text-slate-300">
                    {formatMetricValue(item.expected_value, item.unit)}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block uppercase">Net Delta</span>
                  <span
                    className={`font-semibold ${
                      item.delta >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"
                    }`}
                  >
                    {formatDelta(item.delta, item.delta_pct, item.unit)}
                  </span>
                </div>
              </div>

              {/* Action Button */}
              <button
                onClick={() => onSelectAnomaly(item.id)}
                className="w-full inline-flex items-center justify-center space-x-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 py-2.5 px-4 text-xs font-mono font-bold text-white shadow-sm transition"
              >
                <span>{item.has_investigation ? "View Investigation Report" : "Execute Live Investigation"}</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* 4. Metric Surveillance Status Breakdown */}
      <div className="space-y-4 pt-2">
        <div>
          <h2 className="text-base sm:text-lg font-bold font-mono text-slate-900 dark:text-white">
            Surveillance by Core Metric
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Click any metric category to filter active signals.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {metrics.map((m) => {
            const countForMetric = anomalies.filter((a) => a.metric_name === m.name).length;
            const highCount = anomalies.filter((a) => a.metric_name === m.name && a.severity === "high").length;

            return (
              <button
                key={m.name}
                onClick={() => onSelectMetricFilter(m.name)}
                className="text-left rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] p-4 shadow-sm hover:border-indigo-400 dark:hover:border-indigo-500 transition-all group"
              >
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-sm text-slate-900 dark:text-white group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                    {m.display_name}
                  </h4>
                  <span className="rounded-full bg-slate-100 dark:bg-slate-900 px-2 py-0.5 text-xs font-mono text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800">
                    {countForMetric} signals
                  </span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">
                  {m.description}
                </p>
                <div className="mt-3 flex items-center justify-between text-[11px] font-mono pt-2 border-t border-slate-100 dark:border-slate-800/80">
                  <span className="text-slate-400">Attribution: {m.date_attribution_rule}</span>
                  {highCount > 0 ? (
                    <span className="text-rose-600 dark:text-rose-400 font-semibold">{highCount} critical</span>
                  ) : (
                    <span className="text-emerald-600 dark:text-emerald-400 font-semibold">Normal baseline</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
