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
        SELECT DISTINCT team
        FROM (
            SELECT home_team AS team
            FROM fct_underdog_feature_mart
            WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = $1
            UNION ALL
            SELECT away_team AS team
            FROM fct_underdog_feature_mart
            WHERE tournament = 'FIFA World Cup' AND EXTRACT(YEAR FROM match_date) = $1
        ) q
        ORDER BY team ASC;
      `;
      const result = await client.query(query, [parseInt(year)]);
      const teams = result.rows.map((row) => row.team);
      return NextResponse.json(teams);
    } finally {
      client.release();
    }
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : String(err) }, { status: 500 });
  }
}
