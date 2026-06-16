"use client";

import React from "react";
import { motion } from "framer-motion";
import { RefreshCw, TrendingUp } from "lucide-react";
import MomentumSparkline from "./MomentumSparkline";

interface DarkHorse {
  team: string;
  rank: number;
  velocity: number;
  volatility: number;
  underdog_score: number;
}

export default function DarkHorseTable({
  darkHorses,
  loading,
}: {
  darkHorses: DarkHorse[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <RefreshCw className="h-8 w-8 text-indigo-500 animate-spin" />
        <span className="text-sm text-zinc-400 font-medium">Analyzing point-in-time anomalies...</span>
      </div>
    );
  }

  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.05,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 100 } },
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <TrendingUp className="h-6 w-6 text-indigo-400" />
          World Cup Dark Horse Rankings
        </h2>
        <p className="text-zinc-400 max-w-3xl text-sm leading-relaxed">
          Evaluates tournament selections by filtering countries where point velocity was spiking while baseline static rankings remained low, mapping computed underdog signal score indexes.
        </p>
      </div>

      <div className="border border-zinc-800 bg-zinc-900/10 rounded-2xl overflow-hidden backdrop-blur-sm shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-zinc-850 bg-zinc-900/40 text-zinc-400 font-semibold">
                <th className="px-6 py-4">Rank</th>
                <th className="px-6 py-4">Country</th>
                <th className="px-6 py-4">FIFA Rank</th>
                <th className="px-6 py-4">Point Velocity</th>
                <th className="px-6 py-4">Volatility</th>
                <th className="px-6 py-4">Rank Momentum (24m)</th>
                <th className="px-6 py-4 text-right">Underdog Signal Score</th>
              </tr>
            </thead>
            <motion.tbody
              variants={containerVariants}
              initial="hidden"
              animate="show"
              className="divide-y divide-zinc-805/40"
            >
              {darkHorses.map((horse, idx) => (
                <motion.tr
                  variants={itemVariants}
                  key={horse.team}
                  className="hover:bg-zinc-900/30 transition-colors"
                >
                  <td className="px-6 py-4 font-medium text-zinc-400">#{idx + 1}</td>
                  <td className="px-6 py-4 font-bold text-white flex items-center gap-2">
                    {horse.team}
                    {idx === 0 && (
                      <span className="bg-indigo-500/15 text-indigo-400 text-[10px] px-2 py-0.5 rounded border border-indigo-500/20 font-semibold shadow-inner">
                        Top Candidate
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-zinc-300">{horse.rank}</td>
                  <td className="px-6 py-4">
                    <span className="text-emerald-400 font-semibold">+{Number(horse.velocity).toFixed(2)}</span>
                  </td>
                  <td className="px-6 py-4 text-zinc-450">{Number(horse.volatility).toFixed(2)}</td>
                  <td className="px-6 py-2 min-w-[140px]">
                    <div className="h-10 w-28">
                      <MomentumSparkline team={horse.team} />
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right font-bold text-indigo-400">
                    {Number(horse.underdog_score).toFixed(1)}
                  </td>
                </motion.tr>
              ))}
            </motion.tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
