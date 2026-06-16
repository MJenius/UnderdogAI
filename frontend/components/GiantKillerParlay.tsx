"use client";

import React, { useState } from "react";
import { Plus, Trash2, Award, Zap, AlertCircle } from "lucide-react";

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
}

export default function GiantKillerParlay({
  fixtures,
}: {
  fixtures: Fixture[];
}) {
  const [slip, setSlip] = useState<Fixture[]>([]);

  const eligibleFixtures = fixtures.filter(
    (fix) =>
      fix.upset_probability > 0.15 &&
      !slip.some((s) => s.home_team === fix.home_team && s.away_team === fix.away_team)
  );

  const addToSlip = (fix: Fixture) => {
    if (slip.length < 5) {
      setSlip([...slip, fix]);
    }
  };

  const removeFromSlip = (idx: number) => {
    setSlip(slip.filter((_, i) => i !== idx));
  };

  const getCumulativeProb = () => {
    if (slip.length === 0) return 0;
    return slip.reduce((acc, fix) => acc * fix.upset_probability, 1);
  };

  const cumulativeProbability = getCumulativeProb();
  const oddsMultiplier = cumulativeProbability > 0 ? 1 / cumulativeProbability : 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-8 bg-zinc-900/10 border border-zinc-800 rounded-2xl p-6 backdrop-blur-sm">
      <div className="flex flex-col gap-4">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Zap className="h-5 w-5 text-indigo-400" />
            Giant-Killer Parlay Builder
          </h3>
          <p className="text-xs text-zinc-400 mt-1">
            Chain high-value underdog outcomes together. Probability multiplication calculates the cumulative joint likelihood and implied odds multiplier.
          </p>
        </div>

        <div className="flex flex-col gap-2.5 max-h-[360px] overflow-y-auto pr-2">
          {eligibleFixtures.length > 0 ? (
            eligibleFixtures.map((fix, idx) => (
              <div
                key={`${fix.home_team}-${fix.away_team}-${idx}`}
                className="flex items-center justify-between p-3.5 bg-zinc-900/35 border border-zinc-850 hover:border-zinc-700 rounded-xl transition-all"
              >
                <div className="flex-grow min-w-0">
                  <div className="text-[10px] text-zinc-550 font-mono">{fix.match_date}</div>
                  <div className="text-xs font-bold text-white truncate">
                    {fix.home_team} vs {fix.away_team}
                  </div>
                  <div className="text-[10px] text-zinc-400 mt-0.5">
                    Underdog Win: <span className="text-indigo-400 font-semibold">{(fix.upset_probability * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <button
                  onClick={() => addToSlip(fix)}
                  disabled={slip.length >= 5}
                  className="p-1.5 bg-indigo-500/10 text-indigo-400 hover:bg-indigo-600 hover:text-white rounded-lg transition-colors disabled:opacity-40 disabled:hover:bg-indigo-500/10 disabled:hover:text-indigo-400"
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>
            ))
          ) : (
            <div className="text-center py-12 text-xs text-zinc-500 italic">
              No high-value underdog fixtures available.
            </div>
          )}
        </div>
      </div>

      <div className="bg-zinc-950 border border-zinc-850/80 rounded-2xl p-5 flex flex-col justify-between shadow-2xl relative">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 to-violet-500 rounded-t-2xl" />

        <div className="flex flex-col gap-4">
          <div className="flex justify-between items-center border-b border-zinc-850 pb-3">
            <span className="text-xs font-black uppercase tracking-widest text-zinc-400">Giant-Killer Ticket</span>
            <span className="text-[10px] text-zinc-550 font-mono">{slip.length} / 5 Selections</span>
          </div>

          {slip.length > 0 ? (
            <div className="flex flex-col gap-3 max-h-[200px] overflow-y-auto pr-1">
              {slip.map((fix, idx) => (
                <div
                  key={`${fix.home_team}-${fix.away_team}-${idx}`}
                  className="flex items-center justify-between bg-zinc-900/40 p-2.5 rounded-xl border border-zinc-850"
                >
                  <div className="min-w-0">
                    <div className="text-[9px] text-zinc-500 font-mono">{fix.match_date}</div>
                    <div className="text-xs font-bold text-white truncate">
                      {fix.home_team} vs {fix.away_team}
                    </div>
                    <div className="text-[10px] text-indigo-400 font-semibold mt-0.5">
                      Upset: {(fix.upset_probability * 100).toFixed(0)}%
                    </div>
                  </div>
                  <button
                    onClick={() => removeFromSlip(idx)}
                    className="p-1.5 text-zinc-550 hover:text-rose-400 transition-colors"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-center text-zinc-550 gap-2 border border-dashed border-zinc-850 rounded-xl">
              <Award className="h-8 w-8 text-zinc-800" />
              <span className="text-xs">Slip is empty. Add up to 5 underdog selections from the schedule.</span>
            </div>
          )}
        </div>

        {slip.length > 0 && (
          <div className="border-t border-dashed border-zinc-800 pt-5 mt-5 flex flex-col gap-4">
            <div className="flex justify-between items-center text-xs">
              <span className="text-zinc-550 font-medium">Parlay Likelihood</span>
              <span className="text-indigo-400 font-extrabold font-mono">
                {(cumulativeProbability * 100).toFixed(3)}%
              </span>
            </div>

            <div className="flex justify-between items-center bg-indigo-500/5 border border-indigo-500/10 p-3.5 rounded-xl">
              <div>
                <span className="text-[10px] text-indigo-300 uppercase tracking-widest font-black block">Implied Risk Multiplier</span>
                <span className="text-2xl font-black text-white font-mono mt-0.5">
                  {oddsMultiplier.toFixed(1)}x
                </span>
              </div>
              <Award className="h-8 w-8 text-indigo-500/30" />
            </div>

            {cumulativeProbability < 0.005 && (
              <div className="flex items-start gap-2 text-rose-400 bg-rose-500/5 p-2.5 rounded-lg border border-rose-500/10 text-[10px]">
                <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                <span>Extremely high volatility: Parlay likelihood is less than 0.5%. Risk of collapse is significant.</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
