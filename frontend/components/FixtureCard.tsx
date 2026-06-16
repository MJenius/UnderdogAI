"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronUp, AlertCircle, Info } from "lucide-react";

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

export default function FixtureCard({
  fixture,
}: {
  fixture: Fixture;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getBadgeClass = (label: string) => {
    if (label === "Safe") {
      return "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
    }
    if (label === "Moderate" || label === "Moderate Risk") {
      return "bg-amber-500/10 text-amber-400 border border-amber-500/20";
    }
    return "bg-rose-500/10 text-rose-400 border border-rose-500/20 shadow-lg shadow-rose-500/5 animate-pulse";
  };

  return (
    <div
      className={`flex flex-col border border-zinc-805 bg-zinc-900/10 rounded-xl overflow-hidden transition-all duration-200 shrink-0 ${
        isExpanded ? "border-indigo-500 ring-1 ring-indigo-500/20" : "hover:border-zinc-700"
      }`}
    >
      <div className="flex items-center justify-between p-4 gap-4">
        <div className="flex-grow min-w-0">
          <div className="text-[10px] text-zinc-500 font-mono mb-1">{fixture.match_date}</div>
          <div className="text-sm font-bold text-white flex items-center gap-1.5 flex-wrap">
            <span>{fixture.home_team}</span>
            <span className="text-zinc-500 text-xs font-normal">vs</span>
            <span>{fixture.away_team}</span>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex flex-col items-end">
            <span className="text-xs font-extrabold text-indigo-400">{(fixture.upset_probability * 100).toFixed(0)}%</span>
            <span className="text-[8px] font-bold text-zinc-500 uppercase tracking-wider">Upset</span>
          </div>
          <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${getBadgeClass(fixture.risk_label)}`}>
            {fixture.risk_label}
          </span>
          <button
            type="button"
            className="text-zinc-550 hover:text-zinc-350"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>
      {isExpanded && (
        <div className="px-4 pb-4 pt-1 bg-zinc-950/45 border-t border-zinc-850 text-xs flex flex-col gap-2.5">
          <div className="text-zinc-300 font-mono leading-relaxed bg-zinc-900/20 p-2.5 rounded-lg border border-zinc-850/30">
            {fixture.explainability_narrative}
          </div>
          <div className="grid grid-cols-4 gap-2 pt-2 border-t border-zinc-850/40 text-[9px]">
            <div>
              <span className="text-zinc-550 block uppercase tracking-wider">Home Win</span>
              <span className="text-zinc-300 font-semibold font-mono">{(fixture.home_win_prob * 100).toFixed(1)}%</span>
            </div>
            <div>
              <span className="text-zinc-550 block uppercase tracking-wider">Draw</span>
              <span className="text-zinc-300 font-semibold font-mono">{(fixture.draw_prob * 100).toFixed(1)}%</span>
            </div>
            <div>
              <span className="text-zinc-550 block uppercase tracking-wider">Away Win</span>
              <span className="text-zinc-300 font-semibold font-mono">{(fixture.away_win_prob * 100).toFixed(1)}%</span>
            </div>
            <div>
              <span className="text-zinc-550 block uppercase tracking-wider">H2H Bias</span>
              <span className="text-zinc-300 font-semibold font-mono">
                {fixture.h2h_bias >= 0 ? "+" : ""}
                {fixture.h2h_bias?.toFixed(3)}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
