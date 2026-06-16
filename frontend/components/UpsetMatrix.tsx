"use client";

import React, { useState, useEffect } from "react";
import { RefreshCw, Shield, Users, Info, ChevronUp, ChevronDown } from "lucide-react";
import Combobox from "./Combobox";
import RadarComparison from "./RadarComparison";
import UpsetAlertCard from "./UpsetAlertCard";
import SensitivityAnalyzer from "./SensitivityAnalyzer";

interface Prediction {
  home_win_prob: number;
  away_win_prob: number;
  draw_prob: number;
  underdog_signal_score: number;
  risk_label: string;
  explainability_narrative: string;
  home_tier_form: number;
  away_tier_form: number;
  h2h_bias: number;
  shootout_resilience_home?: number;
  shootout_resilience_away?: number;
}

export default function UpsetMatrix({
  teams,
  year,
}: {
  teams: string[];
  year: number;
}) {
  const [homeTeam, setHomeTeam] = useState<string>("");
  const [awayTeam, setAwayTeam] = useState<string>("");
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [homeFeats, setHomeFeats] = useState<any>(null);
  const [awayFeats, setAwayFeats] = useState<any>(null);

  useEffect(() => {
    if (teams.length > 1) {
      setHomeTeam(teams[0]);
      setAwayTeam(teams[1]);
    } else {
      setHomeTeam("");
      setAwayTeam("");
    }
    setPrediction(null);
  }, [teams]);

  useEffect(() => {
    if (homeTeam) {
      fetch(`/api/features?team=${encodeURIComponent(homeTeam)}&year=${year}`)
        .then((res) => {
          if (!res.ok) throw new Error();
          return res.json();
        })
        .then((data) => {
          setHomeFeats({
            team: homeTeam,
            rank: parseInt(String(data.rank), 10) || 100,
            velocity: parseFloat(String(data.vel)) || 0.0,
            volatility: parseFloat(String(data.vol)) || 0.0,
            underdog_score: parseFloat(String(data.underdog_score)) || 0.0,
          });
        })
        .catch(() => setHomeFeats(null));
    } else {
      setHomeFeats(null);
    }
  }, [homeTeam, year]);

  useEffect(() => {
    if (awayTeam) {
      fetch(`/api/features?team=${encodeURIComponent(awayTeam)}&year=${year}`)
        .then((res) => {
          if (!res.ok) throw new Error();
          return res.json();
        })
        .then((data) => {
          setAwayFeats({
            team: awayTeam,
            rank: parseInt(String(data.rank), 10) || 100,
            velocity: parseFloat(String(data.vel)) || 0.0,
            volatility: parseFloat(String(data.vol)) || 0.0,
            underdog_score: parseFloat(String(data.underdog_score)) || 0.0,
          });
        })
        .catch(() => setAwayFeats(null));
    } else {
      setAwayFeats(null);
    }
  }, [awayTeam, year]);

  const handlePredict = async () => {
    if (!homeTeam || !awayTeam) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch(
        `/api/predict?home=${encodeURIComponent(homeTeam)}&away=${encodeURIComponent(awayTeam)}&year=${year}`
      );
      if (!res.ok) {
        throw new Error("Failed to calculate prediction");
      }
      const data = await res.json();
      setPrediction(data);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const homeRank = homeFeats ? homeFeats.rank : 100;
  const awayRank = awayFeats ? awayFeats.rank : 100;

  const getUpsetRisk = () => {
    if (!prediction) return 0.0;
    const homeWinProb = prediction.home_win_prob || 0.0;
    const awayWinProb = prediction.away_win_prob || 0.0;
    const drawProb = prediction.draw_prob || 0.0;
    if (homeRank > awayRank) {
      return homeWinProb + drawProb;
    } else if (awayRank > homeRank) {
      return awayWinProb + drawProb;
    }
    return drawProb;
  };

  const upsetRisk = getUpsetRisk();

  const getBadgeClass = (label: string) => {
    if (label === "Safe") {
      return "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
    }
    if (label.includes("Moderate")) {
      return "bg-amber-500/10 text-amber-400 border border-amber-500/20";
    }
    return "bg-rose-500/10 text-rose-400 border border-rose-500/20 animate-pulse";
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <div className="border border-zinc-850 bg-zinc-900/10 rounded-2xl p-6 flex flex-col gap-6 shadow-xl">
        {errorMsg && (
          <div className="text-xs text-rose-400 bg-rose-500/5 p-3 rounded-lg border border-rose-500/10">
            {errorMsg}
          </div>
        )}

        <div>
          <h3 className="text-lg font-bold text-white mb-4">Single Match Calculator</h3>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="select-home" className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                Home Team
              </label>
              <Combobox
                id="select-home"
                options={teams}
                value={homeTeam}
                onChange={setHomeTeam}
                placeholder="Search Home Team..."
                disabled={loading}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="select-away" className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                Away Team
              </label>
              <Combobox
                id="select-away"
                options={teams.filter((t) => t !== homeTeam)}
                value={awayTeam}
                onChange={setAwayTeam}
                placeholder="Search Away Team..."
                disabled={loading}
              />
            </div>
          </div>

          <button
            id="btn-predict"
            onClick={handlePredict}
            disabled={loading || !homeTeam || !awayTeam}
            className="w-full mt-4 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 px-4 rounded-xl transition-all duration-200 shadow-lg shadow-indigo-600/20 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
            Generate Upset Matrix
          </button>
        </div>

        {prediction ? (
          <div className="flex flex-col gap-5 border-t border-zinc-850 pt-5">
            <div>
              <h4 className="text-xs font-black uppercase tracking-widest text-zinc-500 mb-3">
                Outcome Likelihoods
              </h4>
              <div className="flex flex-col gap-3">
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-zinc-300 font-semibold">{homeTeam} Win</span>
                    <span className="text-white font-bold">{(prediction.home_win_prob * 100).toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-zinc-950 h-2 rounded-full border border-zinc-850 overflow-hidden">
                    <div
                      className="bg-indigo-600 h-full transition-all duration-500"
                      style={{ width: `${prediction.home_win_prob * 100}%` }}
                    ></div>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-zinc-300 font-semibold">Draw</span>
                    <span className="text-white font-bold">{(prediction.draw_prob * 100).toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-zinc-950 h-2 rounded-full border border-zinc-850 overflow-hidden">
                    <div
                      className="bg-zinc-650 h-full transition-all duration-500"
                      style={{ width: `${prediction.draw_prob * 100}%` }}
                    ></div>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-zinc-300 font-semibold">{awayTeam} Win</span>
                    <span className="text-white font-bold">{(prediction.away_win_prob * 100).toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-zinc-950 h-2 rounded-full border border-zinc-850 overflow-hidden">
                    <div
                      className="bg-fuchsia-600 h-full transition-all duration-500"
                      style={{ width: `${prediction.away_win_prob * 100}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-4 bg-zinc-900/30 border border-zinc-850/50 p-4 rounded-xl">
              <div className="h-16 w-16 rounded-xl bg-indigo-500/5 border border-indigo-500/15 flex flex-col justify-center items-center shrink-0">
                <div className="text-2xl font-black text-indigo-400">{(upsetRisk * 100).toFixed(0)}%</div>
                <div className="text-[8px] font-bold text-indigo-300 uppercase tracking-widest mt-0.5">Upset Risk</div>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-zinc-550 uppercase tracking-wider">Classification</span>
                  <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${getBadgeClass(prediction.risk_label)}`}>
                    {prediction.risk_label}
                  </span>
                </div>
                <p className="text-zinc-400 text-xs mt-1 leading-relaxed">
                  Inversion risk is derived using relative confederation strengths, bogey parameters, and tournament tiers.
                </p>
              </div>
            </div>

            <div className="bg-indigo-950/10 border border-indigo-900/20 p-4 rounded-xl flex flex-col gap-2">
              <div className="flex items-center gap-2 text-indigo-400">
                <Info className="h-4 w-4 shrink-0" />
                <span className="text-[10px] font-black uppercase tracking-widest">Explainability narrative</span>
              </div>
              <div className="text-xs text-zinc-300 font-mono leading-relaxed">
                {prediction.explainability_narrative}
              </div>
            </div>
            
            <SensitivityAnalyzer home={homeTeam} away={awayTeam} year={year} />
          </div>
        ) : (
          <div className="border-t border-zinc-850 pt-12 flex flex-col justify-center items-center py-12 text-center text-zinc-500 gap-2">
            <Users className="h-8 w-8 text-zinc-800" />
            <span className="text-xs">Select custom home and away matches above to run predictions.</span>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-6">
        <div className="border border-zinc-850 bg-zinc-900/10 rounded-2xl p-6 flex flex-col gap-4 shadow-xl">
          <h3 className="text-base font-bold text-white">Head-to-Head Comparison</h3>
          <RadarComparison
            homeTeam={homeTeam}
            awayTeam={awayTeam}
            homeFeats={homeFeats}
            awayFeats={awayFeats}
            homeShootout={prediction?.shootout_resilience_home}
            awayShootout={prediction?.shootout_resilience_away}
          />
        </div>

        {prediction && (
          <UpsetAlertCard
            homeTeam={homeTeam}
            awayTeam={awayTeam}
            homeRank={homeRank}
            awayRank={awayRank}
            upsetProbability={upsetRisk}
            riskLabel={prediction.risk_label}
            narrative={prediction.explainability_narrative}
          />
        )}
      </div>
    </div>
  );
}
