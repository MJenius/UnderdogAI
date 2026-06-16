"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Shield, Calendar, List, BarChart2, Play, Sparkles, Layout, Cpu, History, Shuffle, RefreshCw } from "lucide-react";

import DarkHorseTable from "@/components/DarkHorseTable";
import UpsetMatrix from "@/components/UpsetMatrix";
import MonteCarloSimulator from "@/components/MonteCarloSimulator";
import FixtureCard from "@/components/FixtureCard";
import GiantKillerParlay from "@/components/GiantKillerParlay";
import WhatIfMatrix from "@/components/WhatIfMatrix";
import SeedingSimulator from "@/components/SeedingSimulator";
import CalibrationDashboard from "@/components/CalibrationDashboard";
import HistoricalUpsetArchive from "@/components/HistoricalUpsetArchive";

interface DarkHorse {
  team: string;
  rank: number;
  velocity: number;
  volatility: number;
  underdog_score: number;
}

interface Fixture {
  home_team: string;
  away_team: string;
  match_date: string;
  home_win_prob: number;
  away_win_prob: number;
  draw_prob: number;
  upset_probability: number;
  risk_label: string;
  explainability_narrative: string;
  home_tier_form: number;
  away_tier_form: number;
  h2h_bias: number;
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<string>("dark-horses");
  const [selectedYear, setSelectedYear] = useState<number>(2022);
  const [darkHorses, setDarkHorses] = useState<DarkHorse[]>([]);
  const [darkHorsesLoading, setDarkHorsesLoading] = useState<boolean>(false);
  const [teams, setTeams] = useState<string[]>([]);
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [fixturesLoading, setFixturesLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchDarkHorses = useCallback(async (year: number) => {
    setDarkHorsesLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/dark-horses?year=${year}`);
      if (!res.ok) {
        throw new Error("Failed to load dark horse index");
      }
      const data = await res.json();
      setDarkHorses(data);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setDarkHorsesLoading(false);
    }
  }, []);

  const fetchTeams = useCallback(async (year: number) => {
    try {
      const res = await fetch(`/api/teams?year=${year}`);
      if (!res.ok) {
        throw new Error("Failed to load tournament teams");
      }
      const data = await res.json();
      setTeams(data);
    } catch {
      setTeams([]);
    }
  }, []);

  const fetchFixtures = useCallback(async (year: number) => {
    setFixturesLoading(true);
    try {
      const res = await fetch(`/api/fixtures?year=${year}`);
      if (!res.ok) {
        throw new Error("Failed to load fixtures");
      }
      const data = await res.json();
      setFixtures(data);
    } catch {
      setFixtures([]);
    } finally {
      setFixturesLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDarkHorses(selectedYear);
    fetchTeams(selectedYear);
    fetchFixtures(selectedYear);
  }, [selectedYear, fetchDarkHorses, fetchTeams, fetchFixtures]);

  const tabs = [
    { id: "dark-horses", label: "Dark Horse Index", icon: List },
    { id: "upset-matrix", label: "Match Upset Matrix", icon: BarChart2 },
    { id: "simulator", label: "Monte Carlo Simulator", icon: Play },
    { id: "parlay", label: "Giant-Killer Parlay", icon: Sparkles },
    { id: "what-if", label: "What-If Scenario Matrix", icon: Layout },
    { id: "seeding", label: "Seeding Simulator", icon: Shuffle },
    { id: "historical", label: "Upset Archive", icon: History },
    { id: "calibration", label: "Calibration Telemetry", icon: Cpu },
  ];

  return (
    <div className="flex flex-col min-h-screen bg-zinc-950 text-zinc-100 font-sans antialiased">
      <header className="border-b border-zinc-900 bg-zinc-900/40 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Shield className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white animate-fade-in">UnderdogAI</h1>
              <p className="text-xs text-zinc-400">Decision Intelligence Platform</p>
            </div>
          </div>
          <div className="flex items-center gap-3 bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2 self-start sm:self-auto shadow-inner">
            <Calendar className="h-4 w-4 text-indigo-400 animate-pulse" />
            <span className="text-sm font-medium text-zinc-300 font-sans">Tournament Cycle</span>
            <select
              id="select-year"
              className="bg-transparent text-sm font-semibold text-white border-0 focus:ring-0 cursor-pointer outline-none font-sans"
              value={selectedYear}
              onChange={(e) => setSelectedYear(parseInt(e.target.value))}
            >
              <option value="2018" className="bg-zinc-900">2018 World Cup</option>
              <option value="2022" className="bg-zinc-900">2022 World Cup</option>
              <option value="2026" className="bg-zinc-900">2026 World Cup</option>
            </select>
          </div>
        </div>
      </header>

      <main className="flex-grow max-w-7xl w-full mx-auto px-6 py-8 flex flex-col gap-8">
        {errorMsg && (
          <div className="flex items-start gap-3 bg-red-950/40 border border-red-900/50 rounded-2xl p-4 text-red-200" id="error-banner">
            <Shield className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
            <div className="text-sm">{errorMsg}</div>
          </div>
        )}

        <nav className="flex overflow-x-auto border-b border-zinc-900 pb-px gap-2" aria-label="Tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                id={`tab-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 py-4 px-5 border-b-2 font-semibold text-xs uppercase tracking-wider transition-all duration-200 whitespace-nowrap shrink-0 ${
                  isActive
                    ? "border-indigo-500 text-indigo-400"
                    : "border-transparent text-zinc-455 hover:text-zinc-200 hover:border-zinc-800"
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>

        <section className="flex-grow">
          {activeTab === "dark-horses" && (
            <DarkHorseTable darkHorses={darkHorses} loading={darkHorsesLoading} />
          )}

          {activeTab === "upset-matrix" && (
            <div className="flex flex-col gap-8">
              <UpsetMatrix teams={teams} year={selectedYear} />
              
              <div className="border border-zinc-850 bg-zinc-900/10 rounded-2xl p-6 flex flex-col gap-4 shadow-xl">
                <div className="flex items-center justify-between border-b border-zinc-85 pb-3">
                  <h3 className="text-base font-bold text-white">Fixture Lineup Analysis</h3>
                  <span className="text-xs text-zinc-550 font-semibold">Ordered by Upset Risk Index</span>
                </div>
                
                {fixturesLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <RefreshCw className="h-6 w-6 text-indigo-500 animate-spin" />
                  </div>
                ) : fixtures.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[500px] overflow-y-auto pr-2">
                    {fixtures.map((fix, idx) => (
                      <FixtureCard key={`${fix.home_team}-${fix.away_team}-${idx}`} fixture={fix} />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 text-xs text-zinc-500 italic">
                    No fixtures available for the selected cycle.
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "simulator" && (
            <MonteCarloSimulator year={selectedYear} />
          )}

          {activeTab === "parlay" && (
            <GiantKillerParlay fixtures={fixtures} />
          )}

          {activeTab === "what-if" && (
            <WhatIfMatrix year={selectedYear} />
          )}

          {activeTab === "seeding" && (
            <SeedingSimulator year={selectedYear} />
          )}

          {activeTab === "historical" && (
            <HistoricalUpsetArchive year={selectedYear} />
          )}

          {activeTab === "calibration" && (
            <CalibrationDashboard />
          )}
        </section>
      </main>

      <footer className="border-t border-zinc-900 bg-zinc-950/20 py-6 text-center text-xs text-zinc-650">
        <div className="max-w-7xl mx-auto px-6">
          &copy; {new Date().getFullYear()} UnderdogAI Decision Intelligence. All rights reserved.
        </div>
      </footer>
    </div>
  );
}
