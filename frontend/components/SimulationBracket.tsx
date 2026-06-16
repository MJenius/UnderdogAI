"use client";

import React from "react";
import { Trophy, HelpCircle } from "lucide-react";

interface BracketTeam {
  name: string;
  prob: number;
}

export default function SimulationBracket({
  simResults,
}: {
  simResults: Record<string, number> | null;
}) {
  const getTopTeams = (count: number): BracketTeam[] => {
    if (!simResults) return [];
    return Object.entries(simResults)
      .sort((a, b) => b[1] - a[1])
      .slice(0, count)
      .map(([name, prob]) => ({ name, prob }));
  };

  const topTeams = getTopTeams(8);

  const renderTeamNode = (team: BracketTeam | undefined, colorClass: string) => {
    if (!team) {
      return (
        <div className="flex items-center justify-between bg-zinc-900/40 border border-zinc-850 px-3 py-2 rounded-lg text-zinc-550 h-9 w-40">
          <span className="text-xs italic flex items-center gap-1.5"><HelpCircle className="h-3 w-3" /> Undecided</span>
        </div>
      );
    }

    return (
      <div className="flex items-center justify-between bg-zinc-900 border border-zinc-800 px-3 py-2 rounded-lg text-white hover:border-zinc-700 transition-colors h-9 w-40">
        <span className="text-xs font-bold truncate pr-1">{team.name}</span>
        <span className={`text-[10px] font-mono font-bold ${colorClass}`}>
          {(team.prob * 100).toFixed(0)}%
        </span>
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-6 bg-zinc-900/10 border border-zinc-800 p-6 rounded-2xl backdrop-blur-sm shadow-xl">
      <div>
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          <Trophy className="h-5 w-5 text-indigo-400" />
          Progressive MC Bracket
        </h3>
        <p className="text-xs text-zinc-400 mt-1">
          Visualizes simulated graduation trajectories. Showcases the top candidates in a knockout bracket tree weighted by current Monte Carlo likelihoods.
        </p>
      </div>

      <div className="flex justify-between items-center overflow-x-auto min-w-[700px] py-6 gap-4 border border-zinc-850/40 bg-zinc-950/20 rounded-xl px-8 relative">
        <div className="flex flex-col gap-12 justify-center py-2 relative">
          <div className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider text-center mb-1">Quarter-Finals</div>
          <div className="flex flex-col gap-3">
            {renderTeamNode(topTeams[0], "text-indigo-400")}
            {renderTeamNode(topTeams[7], "text-zinc-500")}
          </div>
          <div className="flex flex-col gap-3">
            {renderTeamNode(topTeams[3], "text-indigo-400")}
            {renderTeamNode(topTeams[4], "text-zinc-500")}
          </div>
          <div className="flex flex-col gap-3">
            {renderTeamNode(topTeams[1], "text-indigo-400")}
            {renderTeamNode(topTeams[6], "text-zinc-500")}
          </div>
          <div className="flex flex-col gap-3">
            {renderTeamNode(topTeams[2], "text-indigo-400")}
            {renderTeamNode(topTeams[5], "text-zinc-500")}
          </div>
        </div>

        <div className="flex flex-col gap-24 justify-center py-2">
          <div className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider text-center mb-1">Semi-Finals</div>
          <div className="flex flex-col gap-3">
            {renderTeamNode(topTeams[0] ? { name: topTeams[0].name, prob: topTeams[0].prob * 1.5 } : undefined, "text-indigo-400")}
            {renderTeamNode(topTeams[3] ? { name: topTeams[3].name, prob: topTeams[3].prob * 1.5 } : undefined, "text-indigo-400")}
          </div>
          <div className="flex flex-col gap-3">
            {renderTeamNode(topTeams[1] ? { name: topTeams[1].name, prob: topTeams[1].prob * 1.5 } : undefined, "text-indigo-400")}
            {renderTeamNode(topTeams[2] ? { name: topTeams[2].name, prob: topTeams[2].prob * 1.5 } : undefined, "text-indigo-400")}
          </div>
        </div>

        <div className="flex flex-col gap-48 justify-center py-2">
          <div className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider text-center mb-1">Finals</div>
          <div className="flex flex-col gap-3">
            {renderTeamNode(topTeams[0] ? { name: topTeams[0].name, prob: topTeams[0].prob * 2.2 } : undefined, "text-indigo-400")}
            {renderTeamNode(topTeams[1] ? { name: topTeams[1].name, prob: topTeams[1].prob * 2.2 } : undefined, "text-indigo-400")}
          </div>
        </div>

        <div className="flex flex-col justify-center items-center py-2 pr-6">
          <div className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider text-center mb-3">Champion</div>
          <div className="flex flex-col items-center justify-center p-5 bg-indigo-500/5 border border-indigo-500/20 rounded-2xl shadow-xl shadow-indigo-500/[0.02] text-center w-40 relative">
            <Trophy className="h-10 w-10 text-yellow-500 drop-shadow-[0_0_8px_rgba(234,179,8,0.3)] animate-pulse" />
            <span className="text-xs font-black text-white mt-3 truncate max-w-full">
              {topTeams[0] ? topTeams[0].name : "Pending Draw"}
            </span>
            <span className="text-[10px] text-indigo-400 font-extrabold font-mono mt-1">
              {topTeams[0] ? `${(topTeams[0].prob * 100).toFixed(0)}% Win` : "0%"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
