"use client";

import React, { useState, useEffect } from "react";
import { History, RefreshCw, Award, Swords } from "lucide-react";

interface Upset {
  match_date: string;
  home_team: string;
  away_team: string;
  home_score: number;
  away_score: number;
  home_rank: number;
  away_rank: number;
  rank_gap: number;
  upset_winner: string;
}

export default function HistoricalUpsetArchive({ year }: { year: number }) {
  const [upsets, setUpsets] = useState<Upset[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/historical-upsets?year=${year}`)
      .then((res) => {
        if (!res.ok) throw new Error();
        return res.json();
      })
      .then((data) => {
        setUpsets(data || []);
        setLoading(false);
      })
      .catch(() => {
        setUpsets([]);
        setLoading(false);
      });
  }, [year]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 gap-3">
        <RefreshCw className="h-6 w-6 text-indigo-500 animate-spin" />
        <span className="text-xs text-zinc-400">Loading historical matches...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 bg-zinc-900/10 border border-zinc-850 p-6 rounded-2xl backdrop-blur-sm shadow-xl">
      <div>
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          <History className="h-5 w-5 text-indigo-400" />
          Historical Upset Archive
        </h3>
        <p className="text-xs text-zinc-400 mt-1">
          Historical World Cup fixtures where a lower-ranked team defeated a top seed.
        </p>
      </div>

      {upsets.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[400px] overflow-y-auto pr-2">
          {upsets.map((u, idx) => {
            const isHomeWinner = u.upset_winner === u.home_team;
            return (
              <div
                key={`${u.home_team}-vs-${u.away_team}-${idx}`}
                className="bg-zinc-950 border border-zinc-850 p-4 rounded-xl flex flex-col justify-between gap-3 shadow-md hover:border-zinc-700 transition-colors relative overflow-hidden"
              >
                <div className="absolute top-0 right-0 h-16 w-16 bg-rose-500/[0.02] rounded-full blur-xl pointer-events-none" />

                <div className="flex items-center justify-between text-[10px] text-zinc-500 font-mono">
                  <span>{u.match_date}</span>
                  <span className="flex items-center gap-1 bg-rose-500/10 text-rose-400 px-2 py-0.5 rounded font-black border border-rose-500/15 uppercase tracking-wider text-[8px]">
                    <Award className="h-3 w-3" /> Giant Killer
                  </span>
                </div>

                <div className="flex justify-between items-center py-1">
                  <div className="flex-grow min-w-0">
                    <div className="flex items-center justify-between text-xs font-bold text-white mb-2">
                      <span className={isHomeWinner ? "text-indigo-400 font-black" : "text-zinc-300"}>
                        {u.home_team} {isHomeWinner && "★"}
                      </span>
                      <span className="font-mono text-zinc-200">{u.home_score}</span>
                    </div>
                    <div className="flex items-center justify-between text-xs font-bold text-white">
                      <span className={!isHomeWinner ? "text-indigo-400 font-black" : "text-zinc-300"}>
                        {u.away_team} {!isHomeWinner && "★"}
                      </span>
                      <span className="font-mono text-zinc-200">{u.away_score}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between border-t border-zinc-900/60 pt-2 text-[10px] text-zinc-400 font-mono">
                  <span>FIFA Ranks: {u.home_rank} vs {u.away_rank}</span>
                  <span className="font-semibold text-rose-400 flex items-center gap-1">
                    <Swords className="h-3.5 w-3.5" /> Defeated (+{u.rank_gap} rank gap)
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-12 text-xs text-zinc-500 italic">
          No major upsets recorded in World Cup match fixtures for {year}.
        </div>
      )}
    </div>
  );
}
