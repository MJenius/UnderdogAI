"use client";

import React, { useState, useEffect } from "react";
import { LineChart, Line, ResponsiveContainer } from "recharts";
import { RefreshCw } from "lucide-react";

interface SparklinePoint {
  date: string;
  rank: number;
  points: number;
  rank_change: number;
}

export default function MomentumSparkline({ team }: { team: string }) {
  const [data, setData] = useState<SparklinePoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetch(`/api/sparkline?team=${encodeURIComponent(team)}`)
      .then((res) => {
        if (!res.ok) throw new Error();
        return res.json();
      })
      .then((points) => {
        if (active) {
          setData(points);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [team]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full w-full">
        <RefreshCw className="h-3.5 w-3.5 text-indigo-500/50 animate-spin" />
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full w-full text-[10px] text-zinc-650 italic">
        No history
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}>
        <Line
          type="monotone"
          dataKey="points"
          stroke="#6366f1"
          strokeWidth={1.5}
          dot={false}
          animationDuration={300}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
