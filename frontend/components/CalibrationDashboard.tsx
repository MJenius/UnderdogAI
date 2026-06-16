"use client";

import React, { useState, useEffect } from "react";
import { Cpu, RefreshCw, CheckCircle } from "lucide-react";

interface CalibrationData {
  model_file: string;
  intercept: number;
  home_adv: number;
  beta_diff: number;
  beta_vel: number;
  beta_vol: number;
  status: string;
}

export default function CalibrationDashboard() {
  const [data, setData] = useState<CalibrationData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/calibration")
      .then((res) => {
        if (!res.ok) throw new Error();
        return res.json();
      })
      .then((calib) => {
        setData(calib);
        setLoading(false);
      })
      .catch(() => {
        setData(null);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 gap-2">
        <RefreshCw className="h-4 w-4 text-indigo-500 animate-spin" />
        <span className="text-xs text-zinc-550">Connecting to model registry...</span>
      </div>
    );
  }

  if (!data || data.status !== "loaded") {
    return (
      <div className="text-center py-8 text-xs text-zinc-500 italic">
        No active model calibrated in MLflow registry. Run bayesian_match_engine.py first.
      </div>
    );
  }

  const coefficients = [
    { name: "Intercept", val: data.intercept, desc: "Baseline tournament goal rate multiplier" },
    { name: "Home Advantage", val: data.home_adv, desc: "Log-odds multiplier for host/home advantage" },
    { name: "Tier Performance Weight (Velocity)", val: data.beta_vel, desc: "Multiplier matching point spikes against opponent tiers" },
    { name: "Tier Goal Margin Weight (Volatility)", val: data.beta_vol, desc: "Multiplier adjusting team rank swing volatility" },
  ];

  return (
    <div className="flex flex-col gap-6 bg-zinc-900/10 border border-zinc-850 p-6 rounded-2xl backdrop-blur-sm shadow-xl">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-850 pb-4">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Cpu className="h-5 w-5 text-indigo-400" />
            Model Calibration Dashboard
          </h3>
          <p className="text-xs text-zinc-400 mt-1">
            Real-time telemetry from the active Bayesian Inference Engine registry. Monitors NUTS calibrated parameters.
          </p>
        </div>

        <div className="flex items-center gap-2 bg-emerald-500/5 border border-emerald-500/15 text-emerald-400 px-3.5 py-1.5 rounded-xl self-start md:self-auto text-xs font-bold uppercase tracking-wider">
          <CheckCircle className="h-4 w-4 shrink-0" />
          Active Model: {data.status}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {coefficients.map((c) => (
          <div key={c.name} className="bg-zinc-950 border border-zinc-850 p-4.5 rounded-xl flex flex-col justify-between gap-3 shadow-inner">
            <div>
              <span className="text-[10px] font-black uppercase tracking-widest text-zinc-550 block">{c.name}</span>
              <p className="text-[10px] text-zinc-400 leading-normal mt-1">{c.desc}</p>
            </div>
            <span className="text-2xl font-black text-indigo-400 font-mono tracking-tight">
              {c.val >= 0 ? "+" : ""}
              {c.val.toFixed(4)}
            </span>
          </div>
        ))}
      </div>

      <div className="bg-zinc-950/60 border border-zinc-850/60 p-4.5 rounded-xl text-xs flex flex-col md:flex-row md:items-center md:justify-between gap-2.5 font-mono">
        <span className="text-zinc-500">Registry Path:</span>
        <span className="text-zinc-300 select-all truncate max-w-full text-right">{data.model_file}</span>
      </div>
    </div>
  );
}
