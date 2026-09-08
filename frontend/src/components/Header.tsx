"use client";

import React from "react";
import { Sun, Moon, Cpu, LayoutDashboard, Radio, BookOpen } from "lucide-react";
import { useTheme } from "../context/ThemeContext";

export type ActiveView = "feed" | "overview" | "guide";

interface HeaderProps {
  activeView: ActiveView;
  setActiveView: (view: ActiveView) => void;
  anomalyCount: number;
  criticalCount: number;
}

export default function Header({
  activeView,
  setActiveView,
  anomalyCount,
  criticalCount,
}: HeaderProps) {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 dark:border-slate-800 bg-white/95 dark:bg-[#090d16]/95 backdrop-blur-md transition-colors duration-200 shadow-sm">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        {/* Brand Section */}
        <div className="flex items-center space-x-3.5 min-w-0">
          <div className="flex h-8 w-8 sm:h-9 sm:w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 via-indigo-700 to-indigo-900 text-white shadow-sm border border-indigo-400/30">
            <span className="font-mono text-xs sm:text-sm font-bold tracking-wider">IQ</span>
          </div>
          <div className="min-w-0">
            <div className="flex items-center space-x-2">
              <span className="text-base sm:text-lg font-bold tracking-tight font-mono text-slate-900 dark:text-slate-100">
                PicketIQ
              </span>
              <span className="hidden sm:inline-block rounded-full bg-indigo-50 dark:bg-indigo-500/10 px-2 py-0.5 text-[10px] font-mono uppercase font-semibold text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/20">
                Decision Intelligence
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium truncate">
              Autonomous Business Signal Investigation Platform
            </p>
          </div>
        </div>

        {/* Center Navigation Tabs (De-cluttering the platform) */}
        <nav className="hidden md:flex items-center space-x-1 rounded-xl bg-slate-100 dark:bg-slate-900/80 p-1 border border-slate-200 dark:border-slate-800 text-xs font-mono font-medium">
          <button
            onClick={() => setActiveView("feed")}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg transition-all ${
              activeView === "feed"
                ? "bg-white dark:bg-indigo-600 text-slate-900 dark:text-white shadow-sm font-semibold"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
            }`}
          >
            <Radio className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-200" />
            <span>Signal Workspace</span>
            {anomalyCount > 0 && (
              <span className="ml-1 rounded-full bg-slate-200 dark:bg-indigo-800 px-1.5 py-0.2 text-[10px]">
                {anomalyCount}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveView("overview")}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg transition-all ${
              activeView === "overview"
                ? "bg-white dark:bg-indigo-600 text-slate-900 dark:text-white shadow-sm font-semibold"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
            }`}
          >
            <LayoutDashboard className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-200" />
            <span>Executive Overview</span>
            {criticalCount > 0 && (
              <span className="ml-1 rounded-full bg-rose-100 dark:bg-rose-900/60 text-rose-700 dark:text-rose-300 px-1.5 py-0.2 text-[10px]">
                {criticalCount} critical
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveView("guide")}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg transition-all ${
              activeView === "guide"
                ? "bg-white dark:bg-indigo-600 text-slate-900 dark:text-white shadow-sm font-semibold"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
            }`}
          >
            <BookOpen className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-200" />
            <span>System Guide</span>
          </button>
        </nav>

        {/* Right Section: Status Indicators & Theme Toggle */}
        <div className="flex items-center space-x-2.5 sm:space-x-3 text-xs shrink-0">
          {/* Live System Status */}
          <div className="flex items-center space-x-1.5 rounded-full bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 px-2.5 py-1 text-emerald-700 dark:text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 dark:bg-emerald-400 animate-pulse"></span>
            <span className="font-mono text-[10px] sm:text-[11px] font-medium tracking-wide">
              OPERATIONAL
            </span>
          </div>

          {/* Theme Toggle Button */}
          <button
            onClick={toggleTheme}
            aria-label="Toggle Theme"
            className="flex items-center space-x-1.5 rounded-lg border border-slate-300 dark:border-slate-800 bg-slate-100 dark:bg-slate-900 hover:bg-slate-200 dark:hover:bg-slate-800 px-2.5 py-1.5 text-xs font-mono transition-colors text-slate-800 dark:text-slate-200 shadow-sm"
            title={`Switch to ${theme === "dark" ? "Light" : "Dark"} Mode`}
          >
            {theme === "dark" ? (
              <>
                <Sun className="h-3.5 w-3.5 text-amber-400" />
                <span className="hidden sm:inline text-[11px] font-medium">Light</span>
              </>
            ) : (
              <>
                <Moon className="h-3.5 w-3.5 text-indigo-600" />
                <span className="hidden sm:inline text-[11px] font-medium">Dark</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Mobile Subnav */}
      <div className="md:hidden flex items-center justify-around border-t border-slate-200 dark:border-slate-800 px-3 py-1.5 bg-slate-50 dark:bg-slate-900/60 text-xs font-mono">
        <button
          onClick={() => setActiveView("feed")}
          className={`flex items-center space-x-1 py-1 px-2 rounded ${
            activeView === "feed" ? "font-bold text-indigo-600 dark:text-indigo-400" : "text-slate-600 dark:text-slate-400"
          }`}
        >
          <Radio className="h-3 w-3" />
          <span>Signals ({anomalyCount})</span>
        </button>
        <button
          onClick={() => setActiveView("overview")}
          className={`flex items-center space-x-1 py-1 px-2 rounded ${
            activeView === "overview" ? "font-bold text-indigo-600 dark:text-indigo-400" : "text-slate-600 dark:text-slate-400"
          }`}
        >
          <LayoutDashboard className="h-3 w-3" />
          <span>Overview</span>
        </button>
        <button
          onClick={() => setActiveView("guide")}
          className={`flex items-center space-x-1 py-1 px-2 rounded ${
            activeView === "guide" ? "font-bold text-indigo-600 dark:text-indigo-400" : "text-slate-600 dark:text-slate-400"
          }`}
        >
          <BookOpen className="h-3 w-3" />
          <span>Guide</span>
        </button>
      </div>
    </header>
  );
}
