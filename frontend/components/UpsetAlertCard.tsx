"use client";

import React, { useRef } from "react";
import { Download, AlertTriangle, Share2 } from "lucide-react";

export default function UpsetAlertCard({
  homeTeam,
  awayTeam,
  homeRank,
  awayRank,
  upsetProbability,
  riskLabel,
  narrative,
}: {
  homeTeam: string;
  awayTeam: string;
  homeRank: number;
  awayRank: number;
  upsetProbability: number;
  riskLabel: string;
  narrative: string;
}) {
  const cardRef = useRef<HTMLDivElement>(null);

  const handleExport = async () => {
    if (!cardRef.current) return;
    const html2canvas = (await import("html2canvas")).default;
    try {
      const canvas = await html2canvas(cardRef.current, {
        backgroundColor: "#09090b",
        scale: 2,
        logging: false,
        useCORS: true,
      });
      const link = document.createElement("a");
      link.download = `${homeTeam}-vs-${awayTeam}-upset-alert.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
    } catch (err) {
      console.error("Failed to generate image", err);
    }
  };

  const isUpsetHigh = upsetProbability > 0.35;

  return (
    <div className="flex flex-col gap-4">
      <div
        ref={cardRef}
        className="w-full bg-zinc-950 border border-zinc-800 rounded-2xl p-6 relative overflow-hidden shadow-2xl flex flex-col gap-4 select-none"
      >
        <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-32 h-32 bg-fuchsia-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-center justify-between border-b border-zinc-850 pb-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className={`h-5 w-5 ${isUpsetHigh ? "text-rose-400 animate-bounce" : "text-amber-400"}`} />
            <span className="text-xs font-black uppercase tracking-widest text-zinc-400">UnderdogAI Intelligence</span>
          </div>
          <span className={`text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded ${
            riskLabel.includes("High") ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" :
            riskLabel.includes("Moderate") ? "bg-amber-500/10 text-amber-400 border border-amber-500/20" :
            "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
          }`}>
            {riskLabel}
          </span>
        </div>

        <div className="flex flex-col items-center py-4 text-center">
          <div className="text-4xl font-extrabold text-white tracking-tight flex items-center justify-center gap-3 flex-wrap">
            <span>{homeTeam}</span>
            <span className="text-zinc-650 text-xl font-medium font-sans">vs</span>
            <span>{awayTeam}</span>
          </div>
          <div className="text-xs text-zinc-500 mt-1 font-mono">
            FIFA Rankings: {homeTeam} (#{homeRank}) • {awayTeam} (#{awayRank})
          </div>
        </div>

        <div className="flex flex-col items-center justify-center py-4 bg-zinc-900/30 border border-zinc-850/50 rounded-xl relative">
          <div className="text-6xl font-black text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-violet-500 tracking-tight">
            {(upsetProbability * 100).toFixed(0)}%
          </div>
          <div className="text-[10px] font-extrabold text-indigo-300 uppercase tracking-widest mt-1">Upset Probability</div>
        </div>

        <div className="text-xs text-zinc-400 leading-relaxed italic bg-zinc-900/10 p-3 rounded-lg border border-zinc-850/30 font-mono text-center">
          "{narrative}"
        </div>

        <div className="text-[9px] text-zinc-600 font-mono text-center pt-2">
          Generated on underdog.ai decision engine • calibrated Poisson likelihoods
        </div>
      </div>

      <button
        onClick={handleExport}
        className="w-full bg-zinc-900 hover:bg-zinc-850 text-white font-semibold py-3 px-4 rounded-xl transition-all duration-200 border border-zinc-850 flex items-center justify-center gap-2"
      >
        <Download className="h-4 w-4" />
        Download Shareable Graphics Card
      </button>
    </div>
  );
}
