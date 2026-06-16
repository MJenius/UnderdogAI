"use client";

import React, { useState, useEffect } from "react";
import { Shuffle, RefreshCw, Layers, Grid } from "lucide-react";

interface Team {
  team: string;
  rank: number;
  conf: string;
}

interface Group {
  group_name: string;
  teams: Team[];
}

interface Pot {
  pot_number: number;
  teams: Team[];
}

export default function SeedingSimulator({ year }: { year: number }) {
  const [pots, setPots] = useState<Pot[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [drawing, setDrawing] = useState(false);

  const fetchSeeding = async () => {
    try {
      const res = await fetch(`/api/seeding?year=${year}`);
      if (!res.ok) throw new Error();
      const data = await res.json();
      setPots(data.pots || []);
      setGroups(data.groups || []);
    } catch {
      setPots([]);
      setGroups([]);
    } finally {
      setLoading(false);
      setDrawing(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchSeeding();
  }, [year]);

  const handleSimulateDraw = () => {
    setDrawing(true);
    fetchSeeding();
  };

  const getConfBadgeClass = (conf: string) => {
    const classes: Record<string, string> = {
      UEFA: "bg-blue-500/10 text-blue-400 border border-blue-500/20",
      CONMEBOL: "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20",
      CAF: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
      CONCACAF: "bg-orange-500/10 text-orange-400 border border-orange-500/20",
      AFC: "bg-fuchsia-500/10 text-fuchsia-400 border border-fuchsia-500/20",
      OFC: "bg-teal-500/10 text-teal-400 border border-teal-500/20",
    };
    return classes[conf] || "bg-zinc-800 text-zinc-400 border border-zinc-700";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 gap-3">
        <RefreshCw className="h-8 w-8 text-indigo-500 animate-spin" />
        <span className="text-sm text-zinc-400 font-medium">Assembling seeding pots...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 bg-zinc-900/10 border border-zinc-850 p-6 rounded-2xl backdrop-blur-sm shadow-xl">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-850 pb-4">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Shuffle className="h-5 w-5 text-indigo-400" />
            Confederation-Aware Seeding Simulator
          </h3>
          <p className="text-xs text-zinc-400 mt-1">
            Simulate group draws under official constraints (maximum 2 UEFA teams, maximum 1 from other confederations per group).
          </p>
        </div>

        <button
          onClick={handleSimulateDraw}
          disabled={drawing}
          className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold py-2.5 px-4 rounded-xl transition-all duration-200 shadow-md flex items-center gap-2 disabled:opacity-50 shrink-0 self-start md:self-auto"
        >
          {drawing ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Shuffle className="h-3.5 w-3.5" />}
          Run Simulated Draw
        </button>
      </div>

      <div className="flex flex-col gap-3">
        <h4 className="text-xs font-black uppercase tracking-widest text-zinc-550 flex items-center gap-1.5">
          <Layers className="h-3.5 w-3.5" /> Allocated Seeding Pots
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {pots.map((pot) => (
            <div key={pot.pot_number} className="bg-zinc-950/70 border border-zinc-850 p-4 rounded-xl shadow-inner">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-indigo-400">Pot {pot.pot_number}</span>
              <ul className="flex flex-col gap-2 mt-3 text-xs">
                {pot.teams.map((t) => (
                  <li key={t.team} className="flex items-center justify-between py-1 border-b border-zinc-900/40">
                    <span className="font-semibold text-white truncate max-w-[110px]">{t.team}</span>
                    <div className="flex items-center gap-2">
                      <span className={`text-[8px] px-1.5 py-0.5 rounded font-black ${getConfBadgeClass(t.conf)}`}>
                        {t.conf}
                      </span>
                      <span className="font-mono text-zinc-500 text-[10px]">#{t.rank}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-3 border-t border-zinc-850 pt-6">
        <h4 className="text-xs font-black uppercase tracking-widest text-zinc-550 flex items-center gap-1.5">
          <Grid className="h-3.5 w-3.5" /> Simulated Confederation-Compliant Groups
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {groups.map((group) => (
            <div key={group.group_name} className="bg-zinc-950 border border-zinc-850 p-4.5 rounded-xl shadow-md">
              <span className="text-xs font-black text-white">Group {group.group_name}</span>
              <ul className="flex flex-col gap-2 mt-3 text-xs">
                {group.teams.map((t) => (
                  <li key={t.team} className="flex items-center justify-between py-1">
                    <span className="font-bold text-zinc-300 truncate max-w-[110px]">{t.team}</span>
                    <div className="flex items-center gap-2">
                      <span className={`text-[8px] px-1.5 py-0.5 rounded font-black ${getConfBadgeClass(t.conf)}`}>
                        {t.conf}
                      </span>
                      <span className="font-mono text-zinc-500 text-[10px]">#{t.rank}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
