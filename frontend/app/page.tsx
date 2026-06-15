"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { AlertCircle, Play, RefreshCw, BarChart2, Shield, Calendar, Users, List, Info, ChevronDown, ChevronUp, AlertTriangle } from "lucide-react";

interface DarkHorse {
  team: string;
  rank: number;
  velocity: number;
  volatility: number;
  underdog_score: number;
}

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
}

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

function Combobox({
  id,
  options,
  value,
  onChange,
  placeholder,
  disabled,
}: {
  id: string;
  options: string[];
  value: string;
  onChange: (val: string) => void;
  placeholder: string;
  disabled?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [justFocused, setJustFocused] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSearch(value);
  }, [value]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearch(value);
        setJustFocused(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [value]);

  const filteredOptions = options.filter((opt) =>
    opt.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="flex items-center bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500">
        <input
          id={id}
          type="text"
          className="bg-transparent text-sm text-white w-full outline-none"
          placeholder={placeholder}
          value={search}
          disabled={disabled}
          onChange={(e) => {
            const val = e.target.value;
            if (justFocused && value !== "") {
              setJustFocused(false);
              if (val === "") {
                setSearch("");
              } else if (val.length < value.length && (value.startsWith(val) || value.endsWith(val))) {
                setSearch("");
              } else {
                const typed = val.replace(value, "");
                setSearch(typed || val);
              }
              return;
            }
            setSearch(val);
            setIsOpen(true);
          }}
          onFocus={(e) => {
            setIsOpen(true);
            setJustFocused(true);
            const target = e.target;
            setTimeout(() => {
              target.select();
            }, 50);
          }}
        />
        <button
          type="button"
          tabIndex={-1}
          className="text-zinc-500 hover:text-zinc-350 outline-none"
          onClick={() => setIsOpen(!isOpen)}
          disabled={disabled}
        >
          <ChevronDown className={`h-4 w-4 transform transition-transform ${isOpen ? "rotate-185" : ""}`} />
        </button>
      </div>
      {isOpen && (
        <ul className="absolute z-50 w-full mt-2 max-h-60 overflow-y-auto bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl divide-y divide-zinc-800/40">
          {filteredOptions.length > 0 ? (
            filteredOptions.map((opt) => (
              <li
                key={opt}
                className={`px-4 py-2.5 text-sm cursor-pointer transition-colors hover:bg-indigo-600 hover:text-white ${
                  opt === value ? "bg-indigo-600/30 text-indigo-400 font-semibold" : "text-zinc-300"
                }`}
                onClick={() => {
                  onChange(opt);
                  setSearch(opt);
                  setIsOpen(false);
                  setJustFocused(false);
                }}
              >
                {opt}
              </li>
            ))
          ) : (
            <li className="px-4 py-3 text-sm text-zinc-500 italic">No matches found</li>
          )}
        </ul>
      )}
    </div>
  );
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<string>("dark-horses");
  const [selectedYear, setSelectedYear] = useState<number>(2022);
  const [darkHorses, setDarkHorses] = useState<DarkHorse[]>([]);
  const [darkHorsesLoading, setDarkHorsesLoading] = useState<boolean>(false);
  const [teams, setTeams] = useState<string[]>([]);
  const [homeTeam, setHomeTeam] = useState<string>("");
  const [awayTeam, setAwayTeam] = useState<string>("");
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [predictionLoading, setPredictionLoading] = useState<boolean>(false);
  const [simulationRuns, setSimulationRuns] = useState<number>(500);
  const [progressionMode, setProgressionMode] = useState<string>("winner");
  const [simTaskId, setSimTaskId] = useState<string | null>(null);
  const [simStatus, setSimStatus] = useState<string | null>(null);
  const [simResults, setSimResults] = useState<Record<string, number> | null>(null);
  const [simLoading, setSimLoading] = useState<boolean>(false);
  const [simProgress, setSimProgress] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [fixturesLoading, setFixturesLoading] = useState<boolean>(false);
  const [expandedFixtureIndex, setExpandedFixtureIndex] = useState<number | null>(null);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchDarkHorses = useCallback(async (year: number) => {
    setDarkHorsesLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/dark-horses?year=${year}`);
      if (!res.ok) {
        throw new Error("Failed to load dark horse index");
      }
      const data = await res.json();
      setDarkHorses(data);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setDarkHorsesLoading(false);
    }
  }, []);

  const fetchTeams = useCallback(async (year: number) => {
    try {
      const res = await fetch(`/api/teams?year=${year}`);
      if (!res.ok) {
        throw new Error("Failed to load tournament teams");
      }
      const data = await res.json();
      setTeams(data);
      if (data.length > 1) {
        setHomeTeam(data[0]);
        setAwayTeam(data[1]);
      } else {
        setHomeTeam("");
        setAwayTeam("");
      }
    } catch {
      setTeams([]);
    }
  }, []);

  const fetchFixtures = useCallback(async (year: number) => {
    setFixturesLoading(true);
    try {
      const res = await fetch(`/api/fixtures?year=${year}`);
      if (!res.ok) {
        throw new Error("Failed to load fixtures");
      }
      const data = await res.json();
      setFixtures(data);
    } catch {
      setFixtures([]);
    } finally {
      setFixturesLoading(false);
    }
  }, []);

  useEffect(() => {
    Promise.resolve().then(() => {
      fetchDarkHorses(selectedYear);
      fetchTeams(selectedYear);
      fetchFixtures(selectedYear);
      setPrediction(null);
      setSimTaskId(null);
      setSimStatus(null);
      setSimResults(null);
      setExpandedFixtureIndex(null);
    });
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }
  }, [selectedYear, fetchDarkHorses, fetchTeams, fetchFixtures]);

  const handlePredict = async () => {
    if (!homeTeam || !awayTeam) return;
    setPredictionLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/predict?home=${encodeURIComponent(homeTeam)}&away=${encodeURIComponent(awayTeam)}&year=${selectedYear}`);
      if (!res.ok) {
        throw new Error("Failed to calculate prediction");
      }
      const data = await res.json();
      setPrediction(data);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setPredictionLoading(false);
    }
  };

  const handleRunSimulation = async () => {
    setSimLoading(true);
    setSimStatus("PENDING");
    setSimResults(null);
    setSimProgress(0);
    setSimTaskId(null);
    setErrorMsg(null);
    try {
      const res = await fetch("/api/simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tournament_year: selectedYear,
          simulation_runs: simulationRuns,
          progression_mode: progressionMode,
        }),
      });
      if (!res.ok) {
        throw new Error("Failed to trigger simulation task");
      }
      const data = await res.json();
      setSimTaskId(data.task_id);
      startPolling(data.task_id);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
      setSimLoading(false);
      setSimStatus("ERROR");
    }
  };

  const startPolling = (taskId: string) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }
    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/simulation/${taskId}`);
        if (!res.ok) {
          throw new Error("Connection dropped");
        }
        const data = await res.json();
        if (data.progress !== undefined) {
          setSimProgress(parseFloat(String(data.progress)));
        }
        if (data.status === "COMPLETED") {
          setSimStatus("COMPLETED");
          setSimResults(data.result);
          setSimProgress(100);
          setSimLoading(false);
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
          }
        } else if (data.status === "ERROR") {
          setSimStatus("ERROR");
          setSimLoading(false);
          setErrorMsg("Simulation task execution failed on worker");
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
          }
        }
      } catch {
        setSimStatus("ERROR");
        setSimLoading(false);
        setErrorMsg("API gateway connection offline");
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
        }
      }
    }, 2000);
  };

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const [homeFeats, setHomeFeats] = useState<any>(null);
  const [awayFeats, setAwayFeats] = useState<any>(null);

  useEffect(() => {
    if (homeTeam) {
      fetch(`/api/features?team=${encodeURIComponent(homeTeam)}&year=${selectedYear}`)
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
        .catch(() => {
          setHomeFeats(null);
        });
    } else {
      setHomeFeats(null);
    }
  }, [homeTeam, selectedYear]);

  useEffect(() => {
    if (awayTeam) {
      fetch(`/api/features?team=${encodeURIComponent(awayTeam)}&year=${selectedYear}`)
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
        .catch(() => {
          setAwayFeats(null);
        });
    } else {
      setAwayFeats(null);
    }
  }, [awayTeam, selectedYear]);

  const homeRank = homeFeats ? homeFeats.rank : 100;
  const awayRank = awayFeats ? awayFeats.rank : 100;

  const getUpsetRisk = () => {
    if (!prediction || !homeFeats || !awayFeats) return 0.0;
    const homeWinProb = parseFloat(String(prediction.home_win_prob)) || 0.0;
    const awayWinProb = parseFloat(String(prediction.away_win_prob)) || 0.0;
    const drawProb = parseFloat(String(prediction.draw_prob)) || 0.0;
    if (homeRank > awayRank) {
      return homeWinProb + drawProb;
    } else if (awayRank > homeRank) {
      return awayWinProb + drawProb;
    }
    return drawProb;
  };

  const upsetRisk = getUpsetRisk();

  const getUpsetRiskLabel = (riskVal: number) => {
    if (riskVal < 0.15) return "Safe";
    if (riskVal < 0.35) return "Moderate Risk";
    return "High Upset Potential";
  };

  const getBadgeClass = (label: string) => {
    if (label === "Safe") {
      return "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
    }
    if (label === "Moderate Risk" || label === "Moderate") {
      return "bg-amber-500/10 text-amber-400 border border-amber-500/20";
    }
    return "bg-rose-500/10 text-rose-400 border border-rose-500/20 shadow-lg shadow-rose-500/5 animate-pulse";
  };

  return (
    <div className="flex flex-col min-h-screen bg-zinc-950 text-zinc-100 font-sans antialiased">
      <header className="border-b border-zinc-900 bg-zinc-900/40 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Shield className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white">UnderdogAI</h1>
              <p className="text-xs text-zinc-400">Decision Intelligence Platform</p>
            </div>
          </div>
          <div className="flex items-center gap-3 bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2 self-start sm:self-auto">
            <Calendar className="h-4 w-4 text-indigo-400" />
            <span className="text-sm font-medium text-zinc-300">Tournament Cycle</span>
            <select
              id="select-year"
              className="bg-transparent text-sm font-semibold text-white border-0 focus:ring-0 cursor-pointer outline-none"
              value={selectedYear}
              onChange={(e) => setSelectedYear(parseInt(e.target.value))}
            >
              <option value="2018" className="bg-zinc-900">2018 World Cup</option>
              <option value="2022" className="bg-zinc-900">2022 World Cup</option>
              <option value="2026" className="bg-zinc-900">2026 World Cup</option>
            </select>
          </div>
        </div>
      </header>

      <main className="flex-grow max-w-7xl w-full mx-auto px-6 py-8 flex flex-col gap-8">
        {errorMsg && (
          <div className="flex items-start gap-3 bg-red-950/40 border border-red-900/50 rounded-2xl p-4 text-red-200" id="error-banner">
            <AlertCircle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
            <div className="text-sm">{errorMsg}</div>
          </div>
        )}

        <nav className="flex border-b border-zinc-800" aria-label="Tabs">
          <button
            id="tab-dark-horse"
            onClick={() => setActiveTab("dark-horses")}
            className={`flex items-center gap-2 py-4 px-6 border-b-2 font-medium text-sm transition-all duration-200 ${
              activeTab === "dark-horses"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-zinc-400 hover:text-zinc-200 hover:border-zinc-700"
            }`}
          >
            <List className="h-4 w-4" />
            Dark Horse Index
          </button>
          <button
            id="tab-upset-matrix"
            onClick={() => setActiveTab("upset-matrix")}
            className={`flex items-center gap-2 py-4 px-6 border-b-2 font-medium text-sm transition-all duration-200 ${
              activeTab === "upset-matrix"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-zinc-400 hover:text-zinc-200 hover:border-zinc-700"
            }`}
          >
            <BarChart2 className="h-4 w-4" />
            Match Upset Matrix
          </button>
          <button
            id="tab-simulator"
            onClick={() => setActiveTab("simulator")}
            className={`flex items-center gap-2 py-4 px-6 border-b-2 font-medium text-sm transition-all duration-200 ${
              activeTab === "simulator"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-zinc-400 hover:text-zinc-200 hover:border-zinc-700"
            }`}
          >
            <Play className="h-4 w-4" />
            Monte Carlo Simulator
          </button>
        </nav>

        <section className="flex-grow">
          {activeTab === "dark-horses" && (
            <div className="flex flex-col gap-6">
              <div className="flex flex-col gap-2">
                <h2 className="text-2xl font-bold tracking-tight text-white">World Cup Dark Horse Rankings</h2>
                <p className="text-zinc-400 max-w-3xl text-sm">
                  Evaluates tournament selections by filtering countries where point velocity was spiking while baseline static rankings remained low, mapping computed underdog signal score indexes.
                </p>
              </div>

              {darkHorsesLoading ? (
                <div className="flex items-center justify-center py-20">
                  <RefreshCw className="h-8 w-8 text-indigo-500 animate-spin" />
                </div>
              ) : (
                <div className="border border-zinc-800 bg-zinc-900/20 rounded-2xl overflow-hidden backdrop-blur-sm">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-sm">
                      <thead>
                        <tr className="border-b border-zinc-800 bg-zinc-900/60 text-zinc-400 font-semibold">
                          <th className="px-6 py-4">Rank</th>
                          <th className="px-6 py-4">Country</th>
                          <th className="px-6 py-4">FIFA Rank</th>
                          <th className="px-6 py-4">Point Velocity</th>
                          <th className="px-6 py-4">Volatility</th>
                          <th className="px-6 py-4 text-right">Underdog Signal Score</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-800/60">
                        {darkHorses.map((horse, idx) => (
                          <tr key={horse.team} className="hover:bg-zinc-900/40 transition-colors">
                            <td className="px-6 py-4 font-medium text-zinc-300">#{idx + 1}</td>
                            <td className="px-6 py-4 font-bold text-white flex items-center gap-2">
                              {horse.team}
                              {idx === 0 && (
                                <span className="bg-indigo-500/20 text-indigo-400 text-xs px-2 py-0.5 rounded font-medium">
                                  Top Candidate
                                </span>
                              )}
                            </td>
                            <td className="px-6 py-4 text-zinc-300">{horse.rank}</td>
                            <td className="px-6 py-4">
                              <span className="text-emerald-400 font-semibold">{Number(horse.velocity).toFixed(2)}</span>
                            </td>
                            <td className="px-6 py-4 text-zinc-400">{Number(horse.volatility).toFixed(2)}</td>
                            <td className="px-6 py-4 text-right font-bold text-indigo-400">
                              {Number(horse.underdog_score).toFixed(1)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === "upset-matrix" && (
            <div className="flex flex-col gap-6">
              <div className="flex flex-col gap-2">
                <h2 className="text-2xl font-bold tracking-tight text-white">Match-Level Upset Calculator & Fixture Lineup</h2>
                <p className="text-zinc-400 max-w-3xl text-sm">
                  Simulate point-in-time custom pairings snapping team strength priors to the selected tournament cycle kickoff. Identifies Poisson goal distribution ratios and upset risks.
                </p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="border border-zinc-800 bg-zinc-900/30 rounded-2xl p-6 flex flex-col gap-6">
                  <div>
                    <h3 className="text-lg font-bold text-white mb-4">Single Match Selector</h3>
                    <div className="flex flex-col gap-4">
                      <div className="flex flex-col gap-1.5">
                        <label htmlFor="select-home" className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Home Team</label>
                        <Combobox
                          id="select-home"
                          options={teams}
                          value={homeTeam}
                          onChange={setHomeTeam}
                          placeholder="Search Home Team..."
                          disabled={predictionLoading}
                        />
                      </div>

                      <div className="flex flex-col gap-1.5">
                        <label htmlFor="select-away" className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Away Team</label>
                        <Combobox
                          id="select-away"
                          options={teams.filter(t => t !== homeTeam)}
                          value={awayTeam}
                          onChange={setAwayTeam}
                          placeholder="Search Away Team..."
                          disabled={predictionLoading}
                        />
                      </div>
                    </div>

                    <button
                      id="btn-predict"
                      onClick={handlePredict}
                      disabled={predictionLoading || !homeTeam || !awayTeam}
                      className="w-full mt-4 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 px-4 rounded-xl transition-all duration-200 shadow-lg shadow-indigo-600/25 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {predictionLoading ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Shield className="h-4 w-4" />
                      )}
                      Generate Upset Matrix
                    </button>
                  </div>

                  {prediction ? (
                    <div className="flex flex-col gap-6 border-t border-zinc-800/80 pt-6">
                      <div>
                        <h4 className="text-sm font-bold text-zinc-400 uppercase tracking-wider mb-3">Outcome Probabilities</h4>
                        <div className="flex flex-col gap-3">
                          <div>
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-zinc-300 font-semibold">{homeTeam} Win</span>
                              <span className="text-white font-bold">{(parseFloat(String(prediction.home_win_prob)) * 100).toFixed(1)}%</span>
                            </div>
                            <div className="w-full bg-zinc-950 h-2 rounded-full overflow-hidden border border-zinc-800">
                              <div className="bg-indigo-600 h-full rounded-full transition-all duration-500" style={{ width: `${parseFloat(String(prediction.home_win_prob)) * 100}%` }}></div>
                            </div>
                          </div>

                          <div>
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-zinc-300 font-semibold">Draw</span>
                              <span className="text-white font-bold">{(parseFloat(String(prediction.draw_prob)) * 100).toFixed(1)}%</span>
                            </div>
                            <div className="w-full bg-zinc-950 h-2 rounded-full overflow-hidden border border-zinc-800">
                              <div className="bg-zinc-600 h-full rounded-full transition-all duration-500" style={{ width: `${parseFloat(String(prediction.draw_prob)) * 100}%` }}></div>
                            </div>
                          </div>

                          <div>
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-zinc-300 font-semibold">{awayTeam} Win</span>
                              <span className="text-white font-bold">{(parseFloat(String(prediction.away_win_prob)) * 100).toFixed(1)}%</span>
                            </div>
                            <div className="w-full bg-zinc-950 h-2 rounded-full overflow-hidden border border-zinc-800">
                              <div className="bg-violet-600 h-full rounded-full transition-all duration-500" style={{ width: `${parseFloat(String(prediction.away_win_prob)) * 100}%` }}></div>
                            </div>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 bg-zinc-900/60 border border-zinc-800 rounded-xl p-4">
                        <div className="h-16 w-16 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex flex-col justify-center items-center shrink-0">
                          <div className="text-2xl font-extrabold text-indigo-400">{(upsetRisk * 100).toFixed(0)}%</div>
                          <div className="text-[9px] font-bold text-indigo-300 uppercase tracking-widest mt-0.5">Upset Risk</div>
                        </div>
                        <div className="flex-grow">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Risk Level</span>
                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${getBadgeClass(getUpsetRiskLabel(upsetRisk))}`}>
                              {getUpsetRiskLabel(upsetRisk)}
                            </span>
                          </div>
                          <p className="text-zinc-400 text-xs mt-1">
                            Probability inversion calculated using opponent tier forms and chronological Head-to-Head multipliers.
                          </p>
                        </div>
                      </div>

                      <div className="bg-indigo-950/20 border border-indigo-900/30 rounded-xl p-4 flex flex-col gap-2">
                        <div className="flex items-center gap-2 text-indigo-400">
                          <Info className="h-4 w-4 shrink-0" />
                          <span className="text-xs font-bold uppercase tracking-wider">Explainability Card</span>
                        </div>
                        <div className="text-xs text-zinc-300 leading-relaxed font-mono">
                          {prediction.explainability_narrative}
                        </div>
                        <div className="grid grid-cols-3 gap-2 mt-2 pt-2 border-t border-indigo-900/30 text-[10px]">
                          <div>
                            <span className="text-zinc-500 block">Home Tier Form</span>
                            <span className="text-zinc-200 font-semibold">{prediction.home_tier_form?.toFixed(2)} pts</span>
                          </div>
                          <div>
                            <span className="text-zinc-500 block">Away Tier Form</span>
                            <span className="text-zinc-200 font-semibold">{prediction.away_tier_form?.toFixed(2)} pts</span>
                          </div>
                          <div>
                            <span className="text-zinc-500 block">H2H Bias Offset</span>
                            <span className="text-zinc-200 font-semibold">{prediction.h2h_bias >= 0 ? "+" : ""}{prediction.h2h_bias?.toFixed(3)}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="border-t border-zinc-800/80 pt-6 flex flex-col justify-center items-center py-12 text-center text-zinc-500 gap-2">
                      <Users className="h-10 w-10 text-zinc-700" />
                      <span className="text-xs">Select custom home and away matches above to run predictions.</span>
                    </div>
                  )}
                </div>

                <div className="border border-zinc-800 bg-zinc-900/10 rounded-2xl p-6 flex flex-col gap-4">
                  <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                    <h3 className="text-lg font-bold text-white">World Cup Fixture Lineups</h3>
                    <span className="text-xs text-zinc-400 font-semibold">Sorted by Upset Probability</span>
                  </div>

                  {fixturesLoading ? (
                    <div className="flex flex-col items-center justify-center py-20 gap-3">
                      <RefreshCw className="h-6 w-6 text-indigo-500 animate-spin" />
                      <span className="text-xs text-zinc-400 font-medium">Loading match fixtures schedule...</span>
                    </div>
                  ) : fixtures.length > 0 ? (
                    <div className="flex flex-col gap-3 overflow-y-auto max-h-[500px] pr-2">
                      {fixtures.map((fix, idx) => {
                        const isExpanded = expandedFixtureIndex === idx;
                        return (
                          <div
                            key={`${fix.home_team}-${fix.away_team}-${idx}`}
                            className={`flex flex-col border border-zinc-800 bg-zinc-900/20 rounded-xl overflow-hidden transition-all duration-200 shrink-0 ${
                              isExpanded ? "border-indigo-500 ring-1 ring-indigo-500/20" : "hover:border-zinc-700"
                            }`}
                          >
                            <div className="flex items-center justify-between p-4 gap-4">
                              <div className="flex-grow min-w-0">
                                <div className="text-[10px] text-zinc-500 font-mono mb-1">{fix.match_date}</div>
                                <div className="text-sm font-bold text-white flex items-center gap-1.5 flex-wrap">
                                  <span>{fix.home_team}</span>
                                  <span className="text-zinc-500 text-xs font-normal">vs</span>
                                  <span>{fix.away_team}</span>
                                </div>
                              </div>
                              <div className="flex items-center gap-3 shrink-0">
                                <div className="flex flex-col items-end">
                                  <span className="text-xs font-extrabold text-indigo-400">{(fix.upset_probability * 100).toFixed(0)}%</span>
                                  <span className="text-[8px] font-bold text-zinc-500 uppercase tracking-wider">Upset</span>
                                </div>
                                <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${getBadgeClass(fix.risk_label)}`}>
                                  {fix.risk_label}
                                </span>
                                <button
                                  type="button"
                                  className="text-zinc-500 hover:text-zinc-350"
                                  onClick={() => setExpandedFixtureIndex(isExpanded ? null : idx)}
                                >
                                  {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                                </button>
                              </div>
                            </div>
                            {isExpanded && (
                              <div className="px-4 pb-4 pt-1 bg-zinc-950/40 border-t border-zinc-800 text-xs flex flex-col gap-2">
                                <div className="text-zinc-400 font-mono leading-relaxed">
                                  {fix.explainability_narrative}
                                </div>
                                <div className="grid grid-cols-4 gap-2 pt-2 border-t border-zinc-800/40 text-[9px]">
                                  <div>
                                    <span className="text-zinc-600 block">Home Win</span>
                                    <span className="text-zinc-350 font-semibold">{(fix.home_win_prob * 100).toFixed(1)}%</span>
                                  </div>
                                  <div>
                                    <span className="text-zinc-600 block">Draw</span>
                                    <span className="text-zinc-350 font-semibold">{(fix.draw_prob * 100).toFixed(1)}%</span>
                                  </div>
                                  <div>
                                    <span className="text-zinc-600 block">Away Win</span>
                                    <span className="text-zinc-350 font-semibold">{(fix.away_win_prob * 100).toFixed(1)}%</span>
                                  </div>
                                  <div>
                                    <span className="text-zinc-600 block">H2H Bias</span>
                                    <span className="text-zinc-350 font-semibold">{fix.h2h_bias >= 0 ? "+" : ""}{fix.h2h_bias?.toFixed(3)}</span>
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="flex flex-col justify-center items-center py-20 text-center text-zinc-500 gap-2">
                      <AlertTriangle className="h-10 w-10 text-zinc-700" />
                      <span className="text-xs">No fixtures schedule loaded for this cycle year.</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === "simulator" && (
            <div className="flex flex-col gap-6">
              <div className="flex flex-col gap-2">
                <h2 className="text-2xl font-bold tracking-tight text-white">Monte Carlo Bracket Simulator</h2>
                <p className="text-zinc-400 max-w-3xl text-sm">
                  Run simulated iterations of the tournament knockout structure. Requests are processed asynchronously via Kafka and cached to Redis for visualization.
                </p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-1 border border-zinc-800 bg-zinc-900/30 rounded-2xl p-6 flex flex-col gap-6">
                  <div className="flex flex-col gap-4">
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="select-runs" className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Simulation Runs</label>
                      <select
                        id="select-runs"
                        className="bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                        value={simulationRuns}
                        onChange={(e) => setSimulationRuns(parseInt(e.target.value))}
                      >
                        <option value="100">100 Runs (Development)</option>
                        <option value="500">500 Runs (Recommended)</option>
                        <option value="1000">1000 Runs (Production)</option>
                      </select>
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="select-milestone" className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Tournament Milestone</label>
                      <select
                        id="select-milestone"
                        className="bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
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

                  <button
                    id="btn-run-simulation"
                    onClick={handleRunSimulation}
                    disabled={simLoading}
                    className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 px-4 rounded-xl transition-all duration-200 shadow-lg shadow-indigo-600/25 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {simLoading ? (
                      <RefreshCw className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                    Run Simulation
                  </button>

                  {simStatus && (
                    <div className="border-t border-zinc-800 pt-6 flex flex-col gap-4">
                      <div className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Task Info</div>
                      <div className="flex flex-col gap-2">
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-zinc-500">Status</span>
                          <span className={`font-bold uppercase tracking-wider text-[10px] px-2 py-0.5 rounded ${
                            simStatus === "COMPLETED" ? "bg-emerald-500/20 text-emerald-400" :
                            simStatus === "PENDING" ? "bg-yellow-500/20 text-yellow-400 animate-pulse" :
                            "bg-red-500/20 text-red-400"
                          }`}>{simStatus}</span>
                        </div>
                        {simTaskId && (
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-zinc-500">Task ID</span>
                            <span className="text-zinc-400 font-mono text-[10px] truncate max-w-[120px]">{simTaskId}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                <div className="lg:col-span-2 border border-zinc-800 bg-zinc-900/10 rounded-2xl p-6">
                  {simLoading ? (
                    <div className="flex flex-col items-center justify-center py-20 gap-6">
                      <div className="flex flex-col items-center gap-4 w-full max-w-md">
                        <div className="text-sm font-semibold text-zinc-305">Processing simulation runs on background workers...</div>
                        <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden relative">
                          <div
                            className="bg-indigo-500 h-full rounded-full transition-all duration-300 ease-out"
                            style={{ width: `${simProgress}%` }}
                          ></div>
                        </div>
                        <div className="text-xs text-zinc-400 font-medium">{simProgress.toFixed(0)}% Complete</div>
                      </div>
                    </div>
                  ) : simResults ? (
                    <div className="flex flex-col gap-6">
                      <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
                        <h3 className="text-lg font-bold text-white">Target Milestone Graduation Probabilities</h3>
                        <span className="text-xs text-zinc-400 font-semibold">Aggregated Outcomes Matrix</span>
                      </div>
                      <div className="flex flex-col gap-4 max-h-[420px] overflow-y-auto pr-2">
                        {Object.entries(simResults)
                          .sort((a, b) => b[1] - a[1])
                          .map(([team, prob]) => (
                            <div key={team} className="flex flex-col gap-1.5">
                              <div className="flex justify-between items-center text-xs font-semibold">
                                <span className="text-zinc-300">{team}</span>
                                <span className="text-indigo-400 font-bold">{(prob * 100).toFixed(1)}%</span>
                              </div>
                              <div className="w-full bg-zinc-900 h-2.5 rounded-full overflow-hidden border border-zinc-800/80">
                                <div className="bg-gradient-to-r from-indigo-500 to-violet-500 h-full rounded-full transition-all duration-500" style={{ width: `${prob * 100}%` }}></div>
                              </div>
                            </div>
                          ))}
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-20 flex flex-col items-center gap-3">
                      <Play className="h-12 w-12 text-zinc-600" />
                      <div className="text-sm font-semibold text-zinc-400">Trigger Monte Carlo simulations to view progressive outcomes.</div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </section>
      </main>

      <footer className="border-t border-zinc-800 bg-zinc-900/20 py-6 text-center text-xs text-zinc-500">
        <div className="max-w-7xl mx-auto px-6">
          &copy; {new Date().getFullYear()} UnderdogAI Decision Intelligence. All rights reserved.
        </div>
      </footer>
    </div>
  );
}
