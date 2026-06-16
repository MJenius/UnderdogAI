"use client";

import React from "react";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Legend } from "recharts";

interface TeamFeatures {
  team: string;
  rank: number;
  velocity: number;
  volatility: number;
  underdog_score: number;
}

export default function RadarComparison({
  homeTeam,
  awayTeam,
  homeFeats,
  awayFeats,
  homeShootout,
  awayShootout,
}: {
  homeTeam: string;
  awayTeam: string;
  homeFeats: TeamFeatures | null;
  awayFeats: TeamFeatures | null;
  homeShootout?: number;
  awayShootout?: number;
}) {
  if (!homeFeats || !awayFeats) {
    return (
      <div className="flex items-center justify-center h-full text-zinc-550 text-xs italic">
        Select teams to view radar comparison
      </div>
    );
  }

  const hRankVal = Math.max(5, 100 - homeFeats.rank);
  const aRankVal = Math.max(5, 100 - awayFeats.rank);

  const hVelVal = Math.min(100, Math.max(5, homeFeats.velocity * 30));
  const aVelVal = Math.min(100, Math.max(5, awayFeats.velocity * 30));

  const hVolVal = Math.min(100, Math.max(5, homeFeats.volatility * 25));
  const aVolVal = Math.min(100, Math.max(5, awayFeats.volatility * 25));

  const hUnderdog = Math.min(100, Math.max(5, homeFeats.underdog_score));
  const aUnderdog = Math.min(100, Math.max(5, awayFeats.underdog_score));

  const hShootoutVal = Math.max(5, (homeShootout ?? 0.5) * 100);
  const aShootoutVal = Math.max(5, (awayShootout ?? 0.5) * 100);

  const data = [
    { subject: "FIFA Rank (Inv)", A: hRankVal, B: aRankVal },
    { subject: "Point Velocity", A: hVelVal, B: aVelVal },
    { subject: "Rank Volatility", A: hVolVal, B: aVolVal },
    { subject: "Underdog Signal", A: hUnderdog, B: aUnderdog },
    { subject: "Shootout Resilience", A: hShootoutVal, B: aShootoutVal },
  ];

  return (
    <div className="w-full h-80">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
          <PolarGrid stroke="#27272a" />
          <PolarAngleAxis dataKey="subject" stroke="#a1a1aa" fontSize={11} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
          <Radar
            name={homeTeam}
            dataKey="A"
            stroke="#6366f1"
            fill="#6366f1"
            fillOpacity={0.25}
          />
          <Radar
            name={awayTeam}
            dataKey="B"
            stroke="#d946ef"
            fill="#d946ef"
            fillOpacity={0.25}
          />
          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 10 }} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
