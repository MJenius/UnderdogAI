"use client";

import React, { useState, useEffect } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from "recharts";
import { Sliders, RefreshCw, AlertCircle } from "lucide-react";

interface Factor {
  name: string;
  value: number;
  impact: string;
}

interface SensitivityData {
  contributing_factors?: Factor[];
}

export default function SensitivityAnalyzer({
  home,
  away,
  year,
}: {
  home: string;
  away: string;
  year: number;
}) {
  const [data, setData] = useState<SensitivityData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!home || !away) return;
    setLoading(true);
    fetch(`/api/sensitivity?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&year=${year}`)
      .then((res) => {
        if (!res.ok) throw new Error();
        return res.json();
      })
      .then((resData) => {
        setData(resData);
        setLoading(false);
      })
      .catch(() => {
        setData(null);
        setLoading(false);
      });
  }, [home, away, year]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 gap-2">
        <RefreshCw className="h-4 w-4 text-indigo-500 animate-spin" />
        <span className="text-xs text-zinc-550">Analyzing factor sensitivities...</span>
      </div>
    );
  }

  if (!data || !data.contributing_factors) return null;

  // Render a mini bar chart of factor values
  const chartData = data.contributing_factors.map((f) => ({
    name: f.name,
    weight: Math.abs(f.value),
    originalValue: f.value,
  }));

  const getImpactColor = (impact: string) => {
    if (impact === "high") return "text-rose-400 bg-rose-500/5 border border-rose-500/10";
    if (impact === "moderate") return "text-amber-400 bg-amber-500/5 border border-amber-500/10";
    return "text-zinc-400 bg-zinc-900 border border-zinc-800";
  };

  return (
    <div className="flex flex-col gap-4 border-t border-zinc-850 pt-5 mt-3">
      <h4 className="text-xs font-black uppercase tracking-widest text-zinc-500 flex items-center gap-1.5">
        <Sliders className="h-3.5 w-3.5" /> Coefficient Sensitivity Breakdown
      </h4>

      <div className="h-44 w-full bg-zinc-950/40 border border-zinc-850/40 rounded-xl p-3">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" margin={{ left: -10, right: 10, top: 5, bottom: 5 }}>
            <XAxis type="number" stroke="#52525b" fontSize={9} tickLine={false} axisLine={false} />
            <YAxis dataKey="name" type="category" stroke="#a1a1aa" fontSize={9} width={90} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ backgroundColor: "#09090b", borderColor: "#27272a", fontSize: 10, color: "#fff" }}
              formatter={(value: any, name: any, props: any) => {
                const origVal = props?.payload?.originalValue;
                let displayVal = "N/A";
                if (typeof origVal === "number") {
                  displayVal = origVal.toFixed(2);
                } else if (typeof origVal === "boolean") {
                  displayVal = origVal ? "Yes" : "No";
                } else if (origVal !== undefined && origVal !== null) {
                  displayVal = String(origVal);
                }
                return [displayVal, "Magnitude"];
              }}
            />
            <Bar dataKey="weight" radius={[0, 4, 4, 0]}>
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={Math.abs(entry.originalValue) > 10 ? "#6366f1" : "#a78bfa"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-2 gap-2 text-[10px]">
        {data.contributing_factors.map((f) => (
          <div
            key={f.name}
            className={`flex items-center justify-between p-2 rounded-lg ${getImpactColor(f.impact)}`}
          >
            <span className="font-semibold truncate pr-1">{f.name}</span>
            <span className="font-mono font-bold shrink-0">{f.value !== undefined ? (typeof f.value === "boolean" ? (f.value ? "Yes" : "No") : f.value.toFixed(2)) : "N/A"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
