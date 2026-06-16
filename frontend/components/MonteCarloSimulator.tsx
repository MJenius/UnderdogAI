"use client";

import React, { useState, useEffect, useRef } from "react";
import { Play, RefreshCw, Trophy, Activity } from "lucide-react";
import SimulationBracket from "./SimulationBracket";

export default function MonteCarloSimulator({ year }: { year: number }) {
  const [runs, setRuns] = useState<number>(500);
  const [progressionMode, setProgressionMode] = useState<string>("winner");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, number> | null>(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    setTaskId(null);
    setStatus(null);
    setResults(null);
    setProgress(0);
    setErrorMsg(null);
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }
  }, [year]);

  const handleRunSimulation = async () => {
    setLoading(true);
    setStatus("PENDING");
    setResults(null);
    setProgress(0);
    setTaskId(null);
    setErrorMsg(null);

    try {
      const res = await fetch("/api/simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tournament_year: year,
          simulation_runs: runs,
          progression_mode: progressionMode,
        }),
      });

      if (!res.ok) {
        throw new Error("Failed to trigger simulation task");
      }

      const data = await res.json();
      setTaskId(data.task_id);
      startPolling(data.task_id);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
      setLoading(false);
      setStatus("ERROR");
    }
  };

  const startPolling = (tid: string) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/simulation/${tid}`);
        if (!res.ok) throw new Error();
        const data = await res.json();

        if (data.progress !== undefined) {
          setProgress(parseFloat(String(data.progress)));
        }

        if (data.status === "COMPLETED") {
          setStatus("COMPLETED");
          setResults(data.result);
          setProgress(100);
          setLoading(false);
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        } else if (data.status === "ERROR") {
          setStatus("ERROR");
          setLoading(false);
          setErrorMsg("Simulation task execution failed on background worker");
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        }
      } catch {
        setStatus("ERROR");
        setLoading(false);
        setErrorMsg("API Connection Error");
        if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      }
    }, 1500);
  };

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <Activity className="h-6 w-6 text-indigo-400" />
          Monte Carlo Bracket Simulator
        </h2>
        <p className="text-zinc-400 max-w-3xl text-sm leading-relaxed">
          Run simulated iterations of the tournament knockout structure. Requests are processed asynchronously via Kafka and cached to Redis for visualization.
        </p>
      </div>

      {errorMsg && (
        <div className="text-xs text-rose-400 bg-rose-500/5 p-3 rounded-lg border border-rose-500/10">
          {errorMsg}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 border border-zinc-850 bg-zinc-900/10 rounded-2xl p-6 flex flex-col justify-between shadow-xl">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="select-runs" className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                Simulation Runs
              </label>
              <select
                id="select-runs"
                className="bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none cursor-pointer"
                value={runs}
                onChange={(e) => setRuns(parseInt(e.target.value))}
              >
                <option value="100">100 Runs (Development)</option>
                <option value="500">500 Runs (Recommended)</option>
                <option value="1000">1000 Runs (Production)</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="select-milestone" className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                Target Milestone
              </label>
              <select
                id="select-milestone"
                className="bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none cursor-pointer"
                value={progressionMode}
                onChange={(e) => setProgressionMode(e.target.value)}
              >
                <option value="winner">Winner (Full Cup Win)</option>
                <option value="reach_knockouts">Group Stage Exit (Reach Round of 16)</option>
                <option value="reach_quarterfinals">Reach Quarter-Finals</option>
                <option value="reach_semifinals">Reach Semi-Finals</option>
                <option value="reach_finals">Reach Finals</option>
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-4 mt-6">
            <button
              id="btn-run-simulation"
              onClick={handleRunSimulation}
              disabled={loading}
              className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 px-4 rounded-xl transition-all duration-200 shadow-lg shadow-indigo-600/25 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Run Simulation
            </button>

            {status && (
              <div className="border-t border-zinc-850 pt-4 flex flex-col gap-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-zinc-500">Status</span>
                  <span className={`font-black uppercase tracking-wider text-[9px] px-2 py-0.5 rounded ${
                    status === "COMPLETED" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
                    status === "PENDING" ? "bg-yellow-500/10 text-yellow-400 animate-pulse border border-yellow-500/20" :
                    "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                  }`}>{status}</span>
                </div>
                {taskId && (
                  <div className="flex justify-between items-center text-[10px]">
                    <span className="text-zinc-500 font-medium">Task UUID</span>
                    <span className="text-zinc-400 font-mono truncate max-w-[140px]">{taskId}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-2 border border-zinc-850 bg-zinc-900/10 rounded-2xl p-6 shadow-xl">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 gap-4">
              <span className="text-xs text-zinc-450 font-bold uppercase tracking-widest">Sampling Trajectories</span>
              <div className="w-full max-w-sm bg-zinc-950 border border-zinc-850 rounded-full h-2.5 overflow-hidden">
                <div
                  className="bg-indigo-500 h-full rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
              <span className="text-sm font-black text-white font-mono">{progress.toFixed(0)}%</span>
            </div>
          ) : results ? (
            <div className="flex flex-col gap-5">
              <div className="flex items-center justify-between border-b border-zinc-850 pb-3">
                <h3 className="text-sm font-black text-zinc-500 uppercase tracking-widest">Milestone Graduation Matrix</h3>
                <span className="text-xs text-zinc-450 font-semibold">Ordered by probability</span>
              </div>
              <div className="flex flex-col gap-3 max-h-[300px] overflow-y-auto pr-2">
                {Object.entries(results)
                  .sort((a, b) => b[1] - a[1])
                  .map(([team, prob]) => (
                    <div key={team} className="flex flex-col gap-1">
                      <div className="flex justify-between items-center text-xs font-semibold">
                        <span className="text-zinc-300 font-bold">{team}</span>
                        <span className="text-indigo-400 font-bold font-mono">{(prob * 100).toFixed(1)}%</span>
                      </div>
                      <div className="w-full bg-zinc-950 h-2 rounded-full border border-zinc-850 overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-indigo-500 to-violet-500 h-full rounded-full transition-all duration-500"
                          style={{ width: `${prob * 100}%` }}
                        ></div>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-20 flex flex-col items-center gap-3">
              <Trophy className="h-10 w-10 text-zinc-750" />
              <div className="text-xs text-zinc-500">Trigger Monte Carlo simulations to view progressive outcomes.</div>
            </div>
          )}
        </div>
      </div>

      <SimulationBracket simResults={results} />
    </div>
  );
}
