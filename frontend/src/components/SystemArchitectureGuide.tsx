"use client";

import React from "react";
import {
  ShieldCheck,
  Zap,
  Database,
  Layers,
  Sparkles,
  BarChart3,
  Cpu,
  CheckCircle2,
  Lock,
} from "lucide-react";

export default function SystemArchitectureGuide() {
  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 pb-5">
        <div className="inline-flex items-center space-x-2 rounded-full bg-indigo-50 dark:bg-indigo-500/10 px-3 py-1 text-xs font-mono font-semibold text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/20 mb-2">
          <Cpu className="h-3.5 w-3.5" />
          <span>System Architecture & Engineering Specification</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold font-mono text-slate-900 dark:text-white tracking-tight">
          How PicketIQ Operates
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-2xl">
          Deterministic business telemetry decomposition and zero-hallucination root cause synthesis for high-volume enterprise operations.
        </p>
      </div>

      {/* 4 Architectural Pillars Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Pillar 1 */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] p-6 shadow-sm space-y-3">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
              <BarChart3 className="h-5 w-5" />
            </div>
            <div>
              <span className="text-[10px] font-mono text-slate-400 uppercase font-bold">Pillar 01</span>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                Rolling Baseline Anomaly Detection
              </h3>
            </div>
          </div>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            Continuously computes 14-day rolling means and standard deviations across core KPIs (Revenue, Freight, Order Volume, Delivery Duration). Signals are flagged when deviations exceed statistically rigorous thresholds (|Z| &ge; 3.0&sigma; or 5.0&sigma;).
          </p>
        </div>

        {/* Pillar 2 */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] p-6 shadow-sm space-y-3">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <Layers className="h-5 w-5" />
            </div>
            <div>
              <span className="text-[10px] font-mono text-slate-400 uppercase font-bold">Pillar 02</span>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                Deterministic Diagnostic Tooling
              </h3>
            </div>
          </div>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            Instead of asking LLMs to guess causes, Python backend tools query PostgreSQL directly to compute: (1) Segment & State contributions, (2) 8-week same-weekday seasonality, and (3) 14-day chronological slope regression.
          </p>
        </div>

        {/* Pillar 3 */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] p-6 shadow-sm space-y-3">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <span className="text-[10px] font-mono text-slate-400 uppercase font-bold">Pillar 03</span>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                Evidence-Grounded AI Synthesis
              </h3>
            </div>
          </div>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            Google Gemini 2.5 Flash ingests ONLY the verified mathematical output from the 3 deterministic tools, generating an executive explanation and actionable playbook without ever hallucinating metrics or numbers.
          </p>
        </div>

        {/* Pillar 4 */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] p-6 shadow-sm space-y-3">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-cyan-50 dark:bg-cyan-500/10 text-cyan-600 dark:text-cyan-400">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <span className="text-[10px] font-mono text-slate-400 uppercase font-bold">Pillar 04</span>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                Zero-Hallucination Audit Guardrail
              </h3>
            </div>
          </div>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            Every conclusion is subjected to an automated programmatic validation step before persistence. If the synthesis references unsupported claims, the audit flag is raised, ensuring 100% trustworthiness for business leadership.
          </p>
        </div>
      </div>

      {/* Enterprise Tech Stack Summary */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] p-6 sm:p-7 shadow-sm space-y-4">
        <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-900 dark:text-white">
          Production Technology Stack
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
          <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
            <span className="text-[10px] text-slate-400 block uppercase">Backend API</span>
            <span className="font-bold text-slate-900 dark:text-white text-sm mt-1 block">FastAPI + Python 3.12</span>
          </div>
          <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
            <span className="text-[10px] text-slate-400 block uppercase">Warehouse DB</span>
            <span className="font-bold text-slate-900 dark:text-white text-sm mt-1 block">PostgreSQL 16 Engine</span>
          </div>
          <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
            <span className="text-[10px] text-slate-400 block uppercase">Synthesis Model</span>
            <span className="font-bold text-indigo-700 dark:text-indigo-400 text-sm mt-1 block">Gemini 2.5 Flash</span>
          </div>
          <div className="rounded-xl bg-slate-50 dark:bg-[#080c14] p-3.5 border border-slate-200 dark:border-slate-800">
            <span className="text-[10px] text-slate-400 block uppercase">UI Framework</span>
            <span className="font-bold text-cyan-700 dark:text-cyan-400 text-sm mt-1 block">Next.js 16 + Tailwind v4</span>
          </div>
        </div>
      </div>
    </div>
  );
}
