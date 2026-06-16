"use client";

import React, { useState, useEffect } from "react";
import { Plus, Minus, Info, RefreshCw, BarChart } from "lucide-react";

interface Team {
  team: string;
  rank: number;
  conf: string;
}

interface Group {
  group_name: string;
  teams: Team[];
}

export default function WhatIfMatrix({ year }: { year: number }) {
  const [groups, setGroups] = useState<Group[]>([]);
  const [selectedGroupIndex, setSelectedGroupIndex] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  
  // Custom standings override
  const [standings, setStandings] = useState<Record<string, { pts: number; gd: number }>>({});

  useEffect(() => {
    setLoading(true);
    fetch(`/api/seeding?year=${year}`)
      .then((res) => {
        if (!res.ok) throw new Error();
        return res.json();
      })
      .then((data) => {
        setGroups(data.groups || []);
        setLoading(false);
        // Reset custom standings
        const initial: Record<string, { pts: number; gd: number }> = {};
        (data.groups || []).forEach((g: Group) => {
          g.teams.forEach((t) => {
            initial[t.team] = { pts: 0, gd: 0 };
          });
        });
        setStandings(initial);
      })
      .catch(() => {
        setLoading(false);
      });
  }, [year]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 gap-3">
        <RefreshCw className="h-6 w-6 text-indigo-500 animate-spin" />
        <span className="text-xs text-zinc-400">Drawing pots and groups...</span>
      </div>
    );
  }

  if (groups.length === 0) {
    return (
      <div className="text-center py-12 text-xs text-zinc-500 italic">
        Failed to load groups. Ensure database feature mart contains World Cup matchups for {year}.
      </div>
    );
  }

  const activeGroup = groups[selectedGroupIndex];
  
  const adjustStat = (teamName: string, field: "pts" | "gd", delta: number) => {
    setStandings((prev) => {
      const current = prev[teamName] || { pts: 0, gd: 0 };
      let newVal = current[field] + delta;
      if (field === "pts" && newVal < 0) newVal = 0;
      return {
        ...prev,
        [teamName]: {
          ...current,
          [field]: newVal,
        },
      };
    });
  };

  const getStandingsData = () => {
    return activeGroup.teams
      .map((t) => {
        const stats = standings[t.team] || { pts: 0, gd: 0 };
        return {
          ...t,
          pts: stats.pts,
          gd: stats.gd,
        };
      })
      .sort((a, b) => {
        if (b.pts !== a.pts) return b.pts - a.pts;
        if (b.gd !== a.gd) return b.gd - a.gd;
        return a.rank - b.rank; // Lower rank breaks tie
      });
  };

  const sortedTeams = getStandingsData();

  return (
    <div className="flex flex-col gap-6 bg-zinc-900/10 border border-zinc-850 p-6 rounded-2xl backdrop-blur-sm shadow-xl">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-850 pb-4">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <BarChart className="h-5 w-5 text-indigo-400" />
            What-If Group Scenario Matrix
          </h3>
          <p className="text-xs text-zinc-400 mt-1">
            Simulate group outcomes. Adjust points and goal margins to compute real-time standing permutations and see who advances as group winners or runners-up.
          </p>
        </div>

        <div className="flex gap-2 overflow-x-auto max-w-full pb-2 md:pb-0">
          {groups.map((g, idx) => (
            <button
              key={g.group_name}
              onClick={() => setSelectedGroupIndex(idx)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${
                selectedGroupIndex === idx
                  ? "bg-indigo-600 border-indigo-500 text-white"
                  : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700"
              }`}
            >
              Group {g.group_name}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 border border-zinc-850/60 bg-zinc-900/30 rounded-xl overflow-hidden shadow-md">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-zinc-900/50 text-zinc-400 font-semibold border-b border-zinc-850">
                <th className="px-5 py-3">Pos</th>
                <th className="px-5 py-3">Team</th>
                <th className="px-5 py-3">FIFA Rank</th>
                <th className="px-5 py-3">Conf</th>
                <th className="px-5 py-3 text-center">Pts</th>
                <th className="px-5 py-3 text-center">GD</th>
                <th className="px-5 py-3 text-center">Permute Standings</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-850/40">
              {sortedTeams.map((team, idx) => (
                <tr
                  key={team.team}
                  className={`transition-colors ${
                    idx < 2 ? "bg-indigo-500/[0.02] hover:bg-indigo-500/[0.05]" : "hover:bg-zinc-900/20"
                  }`}
                >
                  <td className="px-5 py-4 font-extrabold text-zinc-400">
                    {idx + 1}
                    {idx < 2 && (
                      <span className="ml-1 text-[8px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/25 px-1 py-0.5 rounded uppercase font-semibold">
                        Q
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-4 font-bold text-white">{team.team}</td>
                  <td className="px-5 py-4 text-zinc-300">{team.rank}</td>
                  <td className="px-5 py-4 text-zinc-450">{team.conf}</td>
                  <td className="px-5 py-4 text-center font-bold text-white">{team.pts}</td>
                  <td className="px-5 py-4 text-center font-semibold text-zinc-300">
                    {team.gd >= 0 ? "+" : ""}
                    {team.gd}
                  </td>
                  <td className="px-5 py-4 text-center">
                    <div className="flex items-center justify-center gap-4">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[9px] font-bold text-zinc-550 mr-1 uppercase">Pts</span>
                        <button
                          onClick={() => adjustStat(team.team, "pts", -1)}
                          className="p-1 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-zinc-400 hover:text-zinc-200 rounded"
                        >
                          <Minus className="h-3 w-3" />
                        </button>
                        <button
                          onClick={() => adjustStat(team.team, "pts", 1)}
                          className="p-1 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-zinc-400 hover:text-zinc-200 rounded"
                        >
                          <Plus className="h-3 w-3" />
                        </button>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <span className="text-[9px] font-bold text-zinc-550 mr-1 uppercase">GD</span>
                        <button
                          onClick={() => adjustStat(team.team, "gd", -1)}
                          className="p-1 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-zinc-400 hover:text-zinc-200 rounded"
                        >
                          <Minus className="h-3 w-3" />
                        </button>
                        <button
                          onClick={() => adjustStat(team.team, "gd", 1)}
                          className="p-1 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-zinc-400 hover:text-zinc-200 rounded"
                        >
                          <Plus className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="bg-zinc-950 border border-zinc-850 p-5 rounded-xl flex flex-col gap-4">
          <div className="flex items-center gap-2 text-indigo-400 border-b border-zinc-850 pb-2">
            <Info className="h-4 w-4 shrink-0" />
            <span className="text-xs font-black uppercase tracking-wider">Qualifying Simulation</span>
          </div>
          <div className="text-xs text-zinc-400 leading-relaxed flex flex-col gap-3">
            <div>
              The top two graduating spots in Group <span className="text-white font-bold">{activeGroup.group_name}</span> are currently:
              <ul className="list-disc list-inside mt-2 text-zinc-300 font-semibold flex flex-col gap-1.5">
                <li>1st: {sortedTeams[0]?.team}</li>
                <li>2nd: {sortedTeams[1]?.team}</li>
              </ul>
            </div>
            <div>
              Rules: Standing places are sorted by points first, then goal margins. In case of identical ties, the higher-seeded team (by FIFA rank) takes precedence in this simulator.
            </div>
            <div className="flex items-start gap-2 bg-indigo-500/5 p-2 rounded border border-indigo-500/10 text-[10px] text-indigo-300 mt-2">
              <span>Adjust group wins/draws dynamically to model alternative knockout brackets!</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
