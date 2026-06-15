import { NextResponse } from "next/server";
import { Pool } from "pg";

const pool = new Pool({
  host: process.env.POSTGRES_HOST || "localhost",
  port: parseInt(process.env.POSTGRES_PORT || "5433"),
  database: process.env.POSTGRES_DB || "analytical_sandbox",
  user: process.env.POSTGRES_USER || "postgres",
  password: process.env.POSTGRES_PASSWORD || "postgres",
});

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const year = searchParams.get("year");
  if (!year) {
    return NextResponse.json({ error: "Missing year parameter" }, { status: 400 });
  }
  try {
    const client = await pool.connect();
    try {
      const query = `
        WITH team_stats AS (
            SELECT 
                home_team AS team,
                home_rank AS rank,
                home_rolling_point_velocity_5 AS velocity,
                home_rank_volatility_12m AS volatility,
                home_underdog_signal_score AS underdog_score,
                match_date
            FROM fct_underdog_feature_mart
            WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = $1
            UNION ALL
            SELECT 
                away_team AS team,
                away_rank AS rank,
                away_rolling_point_velocity_5 AS velocity,
                away_rank_volatility_12m AS volatility,
                away_underdog_signal_score AS underdog_score,
                match_date
            FROM fct_underdog_feature_mart
            WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = $1
        ),
        ranked_stats AS (
            SELECT 
                team,
                rank,
                velocity,
                volatility,
                underdog_score,
                ROW_NUMBER() OVER (PARTITION BY team ORDER BY match_date ASC) as rn
            FROM team_stats
        )
        SELECT 
            team,
            rank,
            velocity,
            volatility,
            underdog_score
        FROM ranked_stats
        WHERE rn = 1
        ORDER BY underdog_score DESC;
      `;
      const result = await client.query(query, [parseInt(year)]);
      const darkHorses = result.rows.map((row) => ({
        team: row.team,
        rank: row.rank !== null && row.rank !== undefined ? Number(row.rank) : 100,
        velocity: row.velocity !== null && row.velocity !== undefined ? Number(row.velocity) : 1.0,
        volatility: row.volatility !== null && row.volatility !== undefined ? Number(row.volatility) : 0.0,
        underdog_score: row.underdog_score !== null && row.underdog_score !== undefined ? Number(row.underdog_score) : 0.0,
      }));
      return NextResponse.json(darkHorses);
    } finally {
      client.release();
    }
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : String(err) }, { status: 500 });
  }
}
